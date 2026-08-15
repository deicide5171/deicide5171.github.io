---
layout: single
title: "Spring Boot AOT와 GraalVM 네이티브 이미지"
date: 2026-08-15 19:30:00 +0530
categories: web-dev
tags: ["SpringBoot", "GraalVM", "네이티브이미지", "JVM"]
toc: true
toc_sticky: true
excerpt: "Spring Boot AOT 처리와 GraalVM 네이티브 이미지의 이점과 제약을 실무 관점에서 정리한다."
---

## 왜 지금 이 이야기인가

서버리스와 컨테이너 오케스트레이션 환경이 표준이 되면서 애플리케이션의 시작 시간과 메모리 사용량이 다시 중요한 지표로 떠올랐다. 기존 JVM 애플리케이션은 JIT 워밍업 때문에 콜드스타트가 느리고 메모리도 넉넉히 잡아야 했는데, 이런 특성은 오토스케일링이 빈번한 환경이나 서버리스 함수에서 비용과 응답성 모두에 불리하게 작용한다.

Spring Boot 3.x부터는 AOT(Ahead-Of-Time) 처리와 GraalVM 네이티브 이미지 지원이 정식으로 포함되면서, 스프링 애플리케이션도 네이티브 바이너리로 컴파일해 밀리초 단위로 기동시키는 것이 현실적인 선택지가 됐다. 다만 이 접근이 모든 상황에 정답은 아니며, 리플렉션 제약과 빌드 시간 증가라는 트레이드오프를 이해하고 도입해야 한다.

## Spring Boot AOT와 네이티브 이미지 개념

| 개념 | 설명 |
|---|---|
| AOT 처리 | 빌드 타임에 빈 정의, 프록시, 리플렉션 사용 정보를 미리 분석해 코드/설정으로 생성 |
| GraalVM Native Image | 자바 바이트코드를 정적 분석해 OS 네이티브 실행 파일로 컴파일 |
| Closed-world assumption | 네이티브 이미지는 빌드 시점에 도달 가능한 코드만 포함한다는 전제로 동작 |
| reflect-config.json | 런타임 리플렉션 대상 클래스를 빌드 타임에 미리 등록하는 힌트 파일 |

Spring의 AOT 엔진은 런타임에 클래스패스를 스캔하고 리플렉션으로 빈을 등록하던 기존 방식 대신, 빌드 시점에 애플리케이션 컨텍스트를 미리 계산해 자바 소스/바이트코드로 굳혀버린다. 이 결과물을 GraalVM Native Image가 다시 정적 분석해 하나의 실행 파일로 컴파일하는 구조다.

## 빌드 방법 예제

```yaml
# build.gradle.kts 발췌 (Gradle 기준)
plugins {
    id("org.springframework.boot") version "3.3.0"
    id("org.graalvm.buildtools.native") version "0.10.2"
}
```

```bash
# 네이티브 이미지 빌드
./gradlew nativeCompile

# 생성된 바이너리 실행
./build/native/nativeCompile/app
```

시작 시간은 기존 JVM 방식 대비 체감상 훨씬 빠르며(수십 밀리초~수백 밀리초 수준으로 보고되는 사례가 많다), 메모리 사용량도 눈에 띄게 줄어드는 경향이 있다고 알려져 있다. 다만 정확한 수치는 애플리케이션 구성과 GraalVM 버전에 따라 크게 달라지므로, 도입 전 자신의 워크로드로 직접 벤치마크하는 것이 안전하다.

## 리플렉션 제약과 힌트 설정

네이티브 이미지의 가장 큰 제약은 "closed-world assumption"이다. 런타임에 동적으로 클래스를 로딩하거나 리플렉션으로 접근하는 코드는 빌드 시점에 정적 분석기가 미리 알지 못하면 네이티브 이미지에서 누락되어 런타임 오류로 이어질 수 있다. Jackson 직렬화, 프록시 기반 AOP, 동적 프록시를 많이 쓰는 라이브러리에서 특히 이 문제가 자주 발생한다.

```json
// reflect-config.json 예시
[
  {
    "name": "com.example.dto.UserDto",
    "allDeclaredFields": true,
    "allDeclaredMethods": true,
    "allDeclaredConstructors": true
  }
]
```

Spring Framework와 Spring Boot는 자체적으로 상당 부분의 힌트를 `@RegisterReflectionForBinding`, `RuntimeHintsRegistrar` 등을 통해 자동 등록해주지만, 직접 작성한 DTO나 서드파티 라이브러리에 대해서는 개발자가 힌트를 수동으로 추가해야 하는 경우가 여전히 남아 있다.

## 실무 도입 시 트레이드오프

| 항목 | 설명 |
|---|---|
| 빌드 시간 | 네이티브 이미지 빌드는 JVM 빌드보다 수 분~수십 분 더 걸릴 수 있어 CI 파이프라인 재설계가 필요할 수 있다 |
| 호환성 | 동적 클래스 로딩, 일부 에이전트(APM 등)가 네이티브 이미지와 호환되지 않을 수 있다 |
| 디버깅 | 스택트레이스나 프로파일링 도구 지원이 JVM만큼 성숙하지 않은 부분이 있다 |
| 런타임 성능 | 장시간 실행되는 처리량 중심 워크로드에서는 JIT의 적응 최적화가 없어 피크 처리량이 JVM보다 낮게 나올 수 있다 |

## 실무 포인트와 주의사항

- 네이티브 이미지는 "빠른 시작"이 중요한 서버리스/배치/CLI성 워크로드에 특히 유리하며, 장시간 실행되는 고처리량 서비스에서는 이점이 상대적으로 작을 수 있다.
- CI에서 네이티브 이미지 빌드는 시간이 오래 걸리므로 별도 빌드 파이프라인이나 캐싱 전략을 마련해야 한다.
- 리플렉션/동적 프록시를 쓰는 서드파티 라이브러리 도입 전에는 GraalVM 호환성 여부를 먼저 확인해야 한다.
- 첫 도입 시 통합 테스트를 반드시 네이티브 바이너리로도 실행해 빌드 타임에 잡히지 않는 런타임 오류를 조기에 발견해야 한다.

## 3줄 요약

- Spring Boot 3.x의 AOT 처리는 빈 정의와 리플렉션 정보를 빌드 타임에 미리 계산해 네이티브 이미지 컴파일을 가능하게 한다.
- GraalVM 네이티브 이미지는 시작 시간과 메모리 사용량에서 이점이 있지만 closed-world assumption 때문에 리플렉션 힌트 관리가 필요하다.
- 빌드 시간 증가와 호환성 문제를 감안해 워크로드 특성에 맞는지 먼저 검증하고 도입해야 한다.

## 참고 자료

- [Spring Boot 공식 문서 - GraalVM Native Image](https://docs.spring.io/spring-boot/reference/native-image/introducing-graalvm-native-images.html)
- [GraalVM Native Image 공식 문서](https://www.graalvm.org/latest/reference-manual/native-image/)
- [Spring Framework AOT 문서](https://docs.spring.io/spring-framework/reference/core/aot.html)
