---
layout: single
title: "부팅 3초를 30ms로 — GraalVM Native Image로 Spring Boot 최적화"
date: 2026-08-24 13:25:00 +0530
categories: backend
tags: ["graalvm", "native-image", "spring-boot", "jvm", "cold-start", "aot"]
toc: true
toc_sticky: true
excerpt: "서버리스·컨테이너 환경에서 JVM의 부팅 시간과 메모리 사용량이 문제되는 지점을 짚고, GraalVM Native Image의 AOT 컴파일로 Spring Boot 애플리케이션의 시작 시간을 극적으로 줄이는 원리와 제약을 정리한다."
---

Kubernetes에서 파드가 스케일 아웃될 때, 또는 서버리스 함수가 콜드 스타트될 때 JVM 애플리케이션의 부팅 시간(보통 수 초)은 무시할 수 없는 지연이다. HotSpot JVM은 클래스 로딩, JIT 워밍업, Spring 컨텍스트 초기화가 전부 요청이 들어온 뒤에야 완료되므로, 트래픽이 몰리는 순간 새로 뜨는 인스턴스는 정상 인스턴스보다 훨씬 느리게 응답한다.

GraalVM Native Image는 이 문제를 근본적으로 다르게 접근한다. 애플리케이션 코드를 빌드 시점에 미리 분석해 네이티브 실행 파일로 통째로 컴파일(AOT, Ahead-Of-Time)한다. 결과물은 JVM 없이 바로 실행되는 바이너리이고, 부팅 시간은 수십 밀리초 단위로 떨어진다. 이 글에서는 AOT 컴파일의 원리, Spring Boot와의 통합 방식, 그리고 도입 시 반드시 알아야 할 제약을 정리한다.

## 핵심 개념 1: JIT과 AOT의 근본적 차이

일반 JVM은 바이트코드를 인터프리터로 먼저 실행하다가, 자주 실행되는 코드(hot path)를 실행 중에 프로파일링해 네이티브 코드로 컴파일(JIT)한다. 이 방식은 런타임 정보를 활용해 이론적으로 최적의 성능을 낼 수 있지만, 워밍업 기간 동안은 인터프리터 속도로 동작하고 클래스 로딩·JIT 컴파일 자체에도 시간이 든다.

GraalVM Native Image는 빌드 시점에 애플리케이션이 사용할 수 있는 모든 코드 경로를 정적으로 분석(closed-world assumption)해, 실행에 필요한 코드만 골라 하나의 네이티브 바이너리로 미리 컴파일한다. 런타임에는 클래스 로딩도, JIT 워밍업도 없다. 대신 "빌드 시점에 실제로 어떤 클래스가 리플렉션으로 로드될지" 같은 동적 정보를 정적으로 알아내야 하므로, 리플렉션·프록시·동적 클래스 로딩에 제약이 생긴다.

## 핵심 개념 2: JVM vs Native Image 비교

| 구분 | JVM (HotSpot) | GraalVM Native Image |
|---|---|---|
| 시작 시간 | 수백 ms ~ 수 초 | 수십 ms |
| 초기 메모리 사용량 | 상대적으로 높음(JVM 자체 오버헤드) | 낮음 |
| 피크 처리량(장시간 실행 시) | JIT 최적화로 더 높을 수 있음 | JIT 없이 고정된 최적화 수준 |
| 빌드 시간 | 빠름 | 느림(정적 분석·컴파일에 수 분 이상) |
| 리플렉션/동적 프록시 | 자유로움 | 빌드 시점 설정(reachability metadata) 필요 |
| 적합한 워크로드 | 장시간 실행되는 고처리량 서비스 | 콜드 스타트 민감, 단명 프로세스(서버리스, CLI, 배치) |

핵심 트레이드오프는 "빌드 시간과 런타임 유연성을 희생하고 시작 시간과 초기 자원 사용량을 얻는다"는 것이다. 장시간 실행되며 JIT의 프로파일 기반 최적화가 누적 이득을 주는 서비스라면 JVM이 여전히 유리할 수 있다.

## 예제: Spring Boot 3 Native Image 빌드

```bash
# Spring Boot의 AOT 처리(빈 정의를 빌드 시점에 미리 생성)를 거쳐 네이티브 이미지 빌드
./gradlew nativeCompile

# 또는 Maven
./mvnw -Pnative native:compile
```

```java
// 리플렉션으로 접근하는 클래스는 빌드 시점에 힌트를 등록해야 한다
@RegisterReflectionForBinding(OrderDto.class)
@Configuration
public class NativeHintsConfig {

    @Bean
    public RuntimeHintsRegistrar customHints() {
        return (hints, classLoader) -> {
            hints.reflection().registerType(OrderDto.class,
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.DECLARED_FIELDS);
        };
    }
}
```

Spring Boot 3부터는 `spring-boot:process-aot` 단계가 애플리케이션 컨텍스트를 빌드 시점에 미리 초기화 가능한 형태로 정적 코드로 생성해주고, 대부분의 표준 Spring 빈은 자동으로 리플렉션 힌트가 등록된다. 커스텀 라이브러리나 직접 리플렉션을 쓰는 코드만 위와 같은 수동 힌트가 필요하다.

## 실무 포인트

- **모든 워크로드가 Native Image로 이득을 보는 것은 아니다**: 장시간 실행되며 트래픽이 꾸준한 백엔드 서비스는 JIT의 적응형 최적화가 누적되어 오히려 더 나은 피크 처리량을 낼 수 있다. Native Image는 콜드 스타트 지연이 SLA에 직접 영향을 주는 환경(서버리스, 오토스케일링이 잦은 K8s, 배치성 CLI)에서 이점이 명확하다.
- **빌드 파이프라인에 네이티브 빌드 시간을 반드시 포함시켜 검증한다**: 네이티브 이미지 빌드는 프로젝트 규모에 따라 수 분에서 십수 분까지 걸릴 수 있어, CI 파이프라인 시간과 비용에 영향을 준다. 매 커밋마다 네이티브 빌드를 돌릴지, 배포 직전 단계에서만 돌릴지 전략을 미리 정해야 한다.
- **리플렉션·동적 프록시 이슈는 통합 테스트로 조기에 잡는다**: JVM에서는 멀쩡히 동작하던 코드가 네이티브 이미지에서만 `ClassNotFoundException`류 오류를 내는 경우가 흔하다. 네이티브 이미지 자체로 통합 테스트를 도는 CI 단계를 별도로 두어, 프로덕션 배포 전에 이런 문제를 미리 발견해야 한다.

## 3줄 요약

- GraalVM Native Image는 애플리케이션을 빌드 시점에 정적으로 분석해 네이티브 바이너리로 미리 컴파일해, JVM 클래스 로딩·JIT 워밍업 없이 수십 밀리초의 시작 시간을 실현한다.
- 이 대가로 리플렉션·동적 클래스 로딩에 빌드 시점 힌트가 필요하고 빌드 시간이 늘어나며, 장시간 실행 워크로드에서는 JIT 기반 JVM이 더 나은 피크 성능을 낼 수도 있다.
- Spring Boot 3의 AOT 처리가 대부분의 표준 빈을 자동 지원하지만, 커스텀 리플렉션 코드는 수동 힌트 등록과 네이티브 이미지 전용 통합 테스트로 검증해야 한다.

## 참고 자료

- [GraalVM 공식 문서: Native Image](https://www.graalvm.org/latest/reference-manual/native-image/)
- [Spring 공식 문서: GraalVM Native Image Support](https://docs.spring.io/spring-boot/reference/packaging/native-image/introducing-graalvm-native-images.html)
- [Spring 공식 문서: AOT Processing](https://docs.spring.io/spring-framework/reference/core/aot.html)
