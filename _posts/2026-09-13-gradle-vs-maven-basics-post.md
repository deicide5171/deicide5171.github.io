---
layout: single
title: "Gradle vs Maven — 자바 빌드 도구 뭘 골라야 하나"
date: 2026-09-13 12:25:00 +0530
categories: backend
tags: ["gradle", "maven", "빌드도구", "java", "입문"]
toc: true
toc_sticky: true
excerpt: "자바 프로젝트에서 의존성 관리와 빌드를 담당하는 Gradle과 Maven의 차이와 선택 기준을 처음 배우는 사람 기준으로 정리했다."
---

## 빌드 도구가 왜 필요한가

자바 프로젝트는 외부 라이브러리(의존성)를 여럿 쓰고, 컴파일·테스트·패키징 단계를 거친다. 이걸 손으로 하면 지옥이다. **빌드 도구**는 **의존성 자동 다운로드, 컴파일, 테스트, 패키징(JAR)을 자동화**한다. 자바에서 대표적인 것이 **Maven**과 **Gradle**이다.

## Maven vs Gradle

| 구분 | Maven | Gradle |
|---|---|---|
| 설정 파일 | `pom.xml` (XML) | `build.gradle` (코드) |
| 문법 | 정형화된 XML | Groovy/Kotlin DSL |
| 빌드 속도 | 상대적으로 느림 | 캐시·병렬로 빠름 |
| 유연성 | 규약 중심 | 자유롭게 커스텀 |

## 설정 예시

```text
[Maven pom.xml]
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-web</artifactId>
</dependency>

[Gradle build.gradle]
dependencies {
  implementation 'org.springframework.boot:spring-boot-starter-web'
}
```

같은 의존성 추가도 Gradle이 훨씬 간결하다.

## 실무 포인트

- **새 프로젝트라면 Gradle이 무난.** 스프링 부트 신규 프로젝트는 Gradle을 많이 쓴다. 빌드가 빠르고 설정이 간결하며, 안드로이드 등에서도 표준이다. 단, 기존 프로젝트가 Maven이면 굳이 바꿀 이유는 없다.
- **XML이 익숙하면 Maven도 좋다.** Maven은 정형화돼 있어 프로젝트마다 구조가 비슷하고 배우기 쉽다. 규약을 따르면 되는 단순함이 장점이다.
- **버전은 한곳에서 관리하라.** 의존성 버전이 여기저기 흩어지면 충돌이 난다. Gradle의 버전 카탈로그나 Maven의 `<dependencyManagement>`로 버전을 한곳에서 관리하는 것이 좋다.

## 마무리 요약

- 빌드 도구는 의존성 관리·컴파일·테스트·패키징을 자동화하며, 자바에선 Maven과 Gradle이 대표적이다.
- Maven은 XML 기반 정형화, Gradle은 코드 기반으로 간결하고 빠르다.
- 신규 프로젝트는 Gradle이 무난하고, 버전은 한곳에서 관리하는 것이 좋다.

## 참고 자료

- [Gradle 공식 문서](https://docs.gradle.org/current/userguide/userguide.html)
