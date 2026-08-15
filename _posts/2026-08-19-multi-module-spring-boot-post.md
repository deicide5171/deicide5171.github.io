---
layout: single
title: "Spring Boot 멀티모듈 아키텍처, 언제 나누고 어떻게 설계할까"
date: 2026-08-19 13:25:00 +0530
categories: backend
tags: ["spring-boot", "gradle", "multi-module", "java", "architecture"]
toc: true
toc_sticky: true
excerpt: "단일 모듈 Spring Boot 프로젝트가 커지면서 빌드 시간과 의존성 경계가 애매해질 때, Gradle 멀티모듈로 domain·infra·api를 분리하는 구조와 실무 설정을 정리한다."
---

## 왜 지금 멀티모듈인가

Spring Boot로 서비스를 시작할 때는 대부분 단일 모듈(`src/main/java` 하나)로 충분하다. 컨트롤러, 서비스, 리포지토리가 한 모듈 안에 있어도 빌드는 빠르고 의존성 그래프도 단순하다. 문제는 서비스가 커지면서 시작된다. 팀이 늘고 도메인이 여러 개로 쪼개지고, 배치 잡이나 어드민 콘솔처럼 진입점이 다른 애플리케이션이 하나둘 붙기 시작하면, 단일 모듈은 "아무 클래스나 아무 클래스를 참조할 수 있는" 무경계 상태가 된다. 컴파일러가 계층 간 의존 방향을 강제해주지 않으니, 코드 리뷰만으로 레이어 경계를 지키는 데는 한계가 있다.

멀티모듈은 이 문제를 빌드 도구 수준에서 해결한다. Gradle의 모듈 단위 의존성 선언은 "이 모듈은 저 모듈을 볼 수 없다"를 컴파일 타임에 강제하는 가장 저렴한 방법이다. 최근 Gradle 8.x의 버전 카탈로그(`libs.versions.toml`)와 컨벤션 플러그인(`build-logic` 서브프로젝트) 조합이 자리잡으면서, 모듈이 늘어나도 빌드 설정 중복 없이 관리하는 패턴이 실무 표준처럼 쓰이고 있다. 마이크로서비스로 완전히 쪼개기 전 단계에서, 하나의 배포 단위 안에서도 코드 경계를 지키고 싶을 때 멀티모듈은 여전히 합리적인 선택이다.

## 핵심 개념 1: 모듈을 나누는 기준

모듈 분리는 "폴더를 나누는 것"이 아니라 "의존 방향을 강제하는 것"이 목적이다. 흔히 쓰이는 기준은 계층(layer)과 실행 가능 여부다.

| 모듈 유형 | 예시 | 의존 대상 | 특징 |
|---|---|---|---|
| 실행 모듈 | `api-server`, `batch` | domain, infra, common | `bootJar` 생성, `@SpringBootApplication` 위치 |
| 도메인 모듈 | `domain` | common | 엔티티·도메인 서비스, 프레임워크 의존 최소화 |
| 인프라 모듈 | `infra` | domain, common | JPA 구현체, 외부 API 클라이언트 등 기술 세부사항 |
| 계약 모듈 | `api`(contract) | 거의 없음 | DTO·인터페이스만 정의, 다른 모듈이 참조만 함 |
| 공통 모듈 | `common` | 없음(최하단) | 유틸리티, 공통 예외, 상수 |

핵심 규칙은 **의존 방향이 항상 한쪽으로만 흐르게 하는 것**이다. `domain`이 `infra`를 알면 안 되고, `common`은 아무것도 몰라야 한다. 이 방향을 반대로 만드는 순환 의존이 생기면 Gradle이 즉시 빌드 에러로 알려주기 때문에, 리뷰어가 매번 "이거 레이어 위반 아닌가요"를 수작업으로 확인할 필요가 없어진다.

<img src="/assets/images/posts/2026-08-19-multi-module-spring-boot-1.svg" alt="멀티모듈 Spring Boot 프로젝트 의존 관계도 - api-server와 batch가 domain·infra·common을 참조하고, domain과 infra가 api 계약 모듈에 의존하는 구조" style="width:100%;">

## 핵심 개념 2: 실행 모듈과 라이브러리 모듈의 차이

멀티모듈에서 자주 놓치는 부분은 "모든 모듈이 Spring Boot 플러그인을 그대로 쓰면 안 된다"는 점이다. `domain`, `infra`, `common`처럼 실행되지 않는 모듈에서 `bootJar`를 만들 이유는 없다. 대신 일반 `jar`만 생성하고, 실행 모듈만 `bootJar`를 활성화해야 빌드 결과물이 불필요하게 커지는 것을 막을 수 있다.

## 예제: 루트/서브모듈 Gradle 설정 (Kotlin DSL)

```kotlin
// settings.gradle.kts
rootProject.name = "my-service"
include("api-server", "domain", "infra", "common", "api")

// build.gradle.kts (루트, 공통 설정)
plugins {
    id("org.springframework.boot") version "3.5.0" apply false
    id("io.spring.dependency-management") version "1.1.6" apply false
    kotlin("jvm") version "2.0.21" apply false
}

subprojects {
    apply(plugin = "java")
    apply(plugin = "io.spring.dependency-management")

    java {
        toolchain { languageVersion.set(JavaLanguageVersion.of(21)) }
    }

    repositories { mavenCentral() }
}

// domain/build.gradle.kts — 라이브러리 모듈: bootJar 비활성화
tasks.named("bootJar") { enabled = false }
tasks.named("jar") { enabled = true }

dependencies {
    implementation(project(":common"))
}

// api-server/build.gradle.kts — 실행 모듈
plugins {
    id("org.springframework.boot")
}

dependencies {
    implementation(project(":domain"))
    implementation(project(":infra"))
    implementation(project(":common"))
    implementation("org.springframework.boot:spring-boot-starter-web")
}
```

`domain`, `infra`, `common`처럼 재사용되는 모듈은 `bootJar`를 끄고 `jar`만 켜서 순수 라이브러리 산출물로 남기고, 실제 배포 단위가 되는 `api-server`, `batch`만 Spring Boot 플러그인을 온전히 적용한다. 이렇게 하면 같은 `domain` 코드를 `api-server`와 `batch` 양쪽에서 재사용하면서도, 각 실행 모듈은 자신에게 필요한 스타터 의존성만 선택적으로 가져갈 수 있다.

## 실무 포인트

- **처음부터 모듈을 잘게 쪼개지 않는다.** 도메인 경계가 아직 불확실한 초기 단계에서 과도하게 나누면 모듈 간 리팩터링 비용이 오히려 커진다. 실행 모듈과 도메인/인프라 정도의 최소 분리로 시작해, 필요할 때 점진적으로 쪼개는 편이 안전하다.
- **버전 카탈로그로 의존성 버전을 한 곳에서 관리한다.** `gradle/libs.versions.toml`에 버전을 선언해두면 모듈이 늘어나도 각 `build.gradle.kts`에서 버전 문자열을 중복 관리할 필요가 없다.
- **컨벤션 플러그인으로 반복 설정을 제거한다.** `build-logic` 서브프로젝트에 공통 Java 툴체인, 테스트 설정 등을 플러그인으로 뽑아두면, 모듈이 늘어나도 `subprojects {}` 블록이 비대해지지 않는다.
- **순환 의존은 설계 신호로 받아들인다.** 두 모듈이 서로를 참조해야 하는 상황이 생기면, 대개는 공통 부분을 하위 모듈로 뽑아내야 한다는 신호다. 억지로 순환을 허용하는 설정을 찾기보다 구조를 다시 살펴보는 편이 낫다.

## 3줄 요약

- 멀티모듈은 컴파일러 수준에서 레이어 간 의존 방향을 강제해, 서비스가 커져도 "아무 클래스나 참조하는" 무경계 상태를 막아준다.
- 실행 모듈(`bootJar`)과 라이브러리 모듈(`jar`)을 구분하고, `domain → common`처럼 의존이 한 방향으로만 흐르도록 설계하는 것이 핵심이다.
- 처음부터 잘게 쪼개기보다 최소 분리로 시작해 버전 카탈로그·컨벤션 플러그인으로 반복 설정을 줄이며 점진적으로 확장하는 것이 실무적으로 안전하다.

## 참고 자료

- [Spring Boot Reference — Build Systems](https://docs.spring.io/spring-boot/gradle-plugin/index.html)
- [Gradle Docs — Sharing Build Logic between Subprojects](https://docs.gradle.org/current/userguide/sharing_build_logic_between_subprojects.html)
- [Gradle Docs — Version Catalogs](https://docs.gradle.org/current/userguide/version_catalogs.html)
