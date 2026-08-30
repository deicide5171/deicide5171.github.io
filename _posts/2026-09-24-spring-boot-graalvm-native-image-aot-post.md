---
layout: single
title: "GraalVM Native Image로 스프링 부트 컴파일하기 — AOT 처리와 리플렉션 함정"
date: 2026-09-24 12:25:00 +0530
categories: backend
tags: ["GraalVM", "NativeImage", "SpringBoot", "AOT", "JVM"]
toc: true
toc_sticky: true
excerpt: "콜드 스타트가 곧 비용인 서버리스·컨테이너 환경에서 Spring Boot를 GraalVM Native Image로 컴파일할 때 반드시 이해해야 할 AOT 처리 방식과, 런타임 리플렉션이 조용히 깨지는 이유를 정리했다."
---

## 왜 지금 Native Image를 다시 봐야 하는가

전통적인 JVM 애플리케이션은 클래스를 런타임에 동적으로 로드하고 JIT 컴파일러가 실행하면서 점진적으로 최적화하는 방식으로 동작한다. 이 유연함은 강력하지만, 인스턴스가 요청마다 뜨고 사라지는 서버리스 환경이나 오토스케일링으로 파드가 자주 재생성되는 쿠버네티스 환경에서는 JVM의 시작 시간과 초기 메모리 사용량 자체가 비용이 된다. GraalVM Native Image는 애플리케이션 전체를 빌드 시점에 미리 분석해 OS 네이티브 실행 파일로 컴파일함으로써 이 콜드 스타트 문제를 근본적으로 해결하려는 접근이다. Spring Boot 3부터는 스프링 프레임워크 차원에서 AOT(Ahead-Of-Time) 처리 인프라를 정식 지원하면서 이 조합이 실무에서도 현실적인 선택지가 됐다.

## 핵심 개념 1 — 닫힌 세계 가정(Closed-World Assumption)

Native Image 컴파일의 핵심 전제는 "닫힌 세계 가정"이다. 빌드 시점에 애플리케이션이 실행 중 도달 가능한 모든 코드 경로를 정적으로 분석해서, 실제로 호출되지 않는 코드는 아예 바이너리에서 제거해버린다. 이 정적 분석 덕분에 결과물이 훨씬 작고 시작이 빠르지만, 문제는 리플렉션·동적 프록시·클래스패스 스캐닝처럼 런타임에야 비로소 어떤 클래스가 필요한지 결정되는 코드를 정적 분석기가 미리 알아낼 수 없다는 점이다. 이런 코드는 정적 분석 시점에는 "도달 불가능"으로 판단돼 바이너리에서 빠지고, 실행 중에야 `ClassNotFoundException`이나 `NoSuchMethodException`으로 터진다.

## 핵심 개념 2 — Spring AOT가 이 간극을 메우는 방식

Spring Framework 6와 Spring Boot 3는 빌드 시점에 애플리케이션 컨텍스트를 실제로 한 번 구동해보고, 그 과정에서 등록된 빈 정의·프록시·리플렉션 사용 지점을 분석해 GraalVM이 이해할 수 있는 힌트 파일(reachability metadata)로 미리 생성해두는 AOT 처리 단계를 도입했다. 즉 런타임에 컴포넌트 스캔이나 조건부 빈 등록을 동적으로 계산하는 대신, 빌드 시점에 이미 확정된 빈 그래프를 코드로 직접 생성해 Native Image 컴파일러에게 "이 클래스들은 리플렉션으로 접근될 것"이라고 미리 알려주는 구조다.

| 단계 | 기존 JVM 실행 | Native Image (Spring AOT 포함) |
|---|---|---|
| 컴포넌트 스캔 | 런타임에 매번 수행 | 빌드 시점에 1회 수행, 결과를 코드로 생성 |
| 프록시 생성 | 런타임에 동적 생성 | 빌드 시점에 필요한 프록시 클래스 사전 생성 |
| 리플렉션 접근 | 제약 없음 | reachability metadata에 명시된 것만 허용 |
| 시작 시간 | 수백 ms~수 초 | 수십 ms 이내 |

## 예제 — 커스텀 리플렉션 힌트 등록

```java
@Configuration
@ImportRuntimeHints(MyRuntimeHints.class)
public class AppConfig {
}

class MyRuntimeHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        hints.reflection().registerType(
            LegacyDto.class,
            builder -> builder.withMembers(
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.DECLARED_FIELDS
            )
        );
    }
}
```

서드파티 라이브러리가 내부적으로 리플렉션을 쓰는데 Spring AOT 처리기가 이를 자동으로 감지하지 못하는 경우, 이렇게 `RuntimeHintsRegistrar`로 수동 힌트를 등록해야 Native Image 빌드 후에도 런타임 에러 없이 동작한다.

## 실무 포인트

- **네이티브 빌드는 로컬에서 최소 한 번 반드시 통과시켜라.** 일반 JVM에서는 멀쩡히 동작하던 코드가 Native Image 빌드 후에만 리플렉션 에러로 실패하는 경우가 흔하므로, CI 파이프라인에 네이티브 빌드+통합 테스트 단계를 별도로 추가해야 한다.
- **Jackson 직렬화 대상 DTO는 특히 주의하라.** 기본 생성자와 필드를 리플렉션으로 접근하는 Jackson의 특성상, `@RegisterReflectionForBinding` 같은 애노테이션을 명시적으로 붙이지 않으면 빌드는 성공해도 런타임 역직렬화가 조용히 실패할 수 있다.
- **네이티브 빌드 시간 자체가 길다는 점을 배포 파이프라인에 반영하라.** 정적 분석 특성상 애플리케이션 규모가 커질수록 빌드 시간이 수 분 이상으로 늘어나므로, 매 커밋마다 네이티브 빌드를 돌리기보다는 배포 직전 단계에서만 수행하는 것이 현실적이다.

## 마무리 요약

- GraalVM Native Image는 닫힌 세계 가정 하에 빌드 시점 정적 분석으로 콜드 스타트를 근본적으로 줄이지만, 런타임 리플렉션·동적 프록시는 별도 힌트 없이는 조용히 깨질 수 있다.
- Spring Boot 3의 AOT 처리는 빈 그래프를 빌드 시점에 확정해 코드로 생성함으로써 이 간극을 상당 부분 메운다.
- 네이티브 빌드는 CI에서 별도로 검증하고, 서드파티 리플렉션 사용 지점은 `RuntimeHintsRegistrar`로 직접 등록해야 프로덕션에서 예상치 못한 실패를 피할 수 있다.

## 참고 자료

- [Spring Framework - AOT Processing](https://docs.spring.io/spring-framework/reference/core/aot.html)
- [GraalVM - Native Image Reference](https://www.graalvm.org/latest/reference-manual/native-image/)
