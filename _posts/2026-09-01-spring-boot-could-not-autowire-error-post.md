---
layout: single
title: "Spring Boot 'Could not autowire' 에러 해결하기 — 빈 등록 문제 잡는 법"
date: 2026-09-01 13:25:00 +0530
categories: backend
tags: ["spring boot", "autowire", "의존성주입", "트러블슈팅", "빈등록"]
toc: true
toc_sticky: true
excerpt: "Spring Boot에서 'Could not autowire. No beans of type found' 에러가 날 때, 빈 등록과 컴포넌트 스캔 관점에서 원인을 좁히는 방법을 정리했다."
---

## 이 에러가 말하는 것: 빈을 찾을 수 없다

`Could not autowire. No beans of 'XxxService' type found`는 Spring 컨테이너가 해당 타입의 빈을 하나도 찾지 못했다는 뜻이다. 클래스는 분명히 존재하는데도 이 에러가 난다면, 클래스 자체가 문제가 아니라 **Spring이 그 클래스를 빈으로 등록하지 않았다**는 뜻이다.

## 원인 후보 4가지

| 원인 | 확인 방법 |
|---|---|
| `@Service`, `@Component` 등 애노테이션 누락 | 클래스 선언부 확인 |
| 컴포넌트 스캔 범위 밖에 위치 | 메인 클래스 패키지 기준 하위 패키지인지 확인 |
| 인터페이스 구현체가 여러 개인데 어떤 것인지 특정 안 됨 | `@Qualifier` 또는 `@Primary` 필요 여부 확인 |
| 순환 참조(Circular Dependency)로 빈 생성 자체가 실패 | 에러 로그에서 다른 원인 예외가 함께 있는지 확인 |

## 가장 흔한 원인: 컴포넌트 스캔 범위

```java
// 메인 클래스 위치: com.example.app.Application
@SpringBootApplication
public class Application { ... }

// 이 서비스는 com.example.other 패키지에 있다면 스캔 대상이 아니다!
package com.example.other;

@Service
public class PaymentService { ... }
```

`@SpringBootApplication`은 그 클래스가 위치한 패키지의 **하위 패키지만** 자동으로 컴포넌트 스캔한다. 다른 패키지 트리에 있는 클래스는 아무리 `@Service`를 붙여도 스캔되지 않는다.

## 해결 방법

```java
// 방법 1: 패키지 구조를 메인 클래스 하위로 통일 (가장 권장)

// 방법 2: 스캔 범위를 명시적으로 확장
@SpringBootApplication(scanBasePackages = {"com.example.app", "com.example.other"})
public class Application { ... }

// 방법 3: 인터페이스 구현체가 여러 개일 때 구체적으로 지정
@Autowired
@Qualifier("kakaoPayService")
private PaymentService paymentService;
```

## 실무 포인트

- **에러 로그를 끝까지 읽지 않고 첫 줄만 보고 판단하면 진짜 원인을 놓친다.** `Could not autowire` 에러는 종종 그 아래에 순환 참조나 다른 빈 생성 실패가 진짜 원인으로 깔려 있는 경우가 많다.
- **테스트 코드에서만 이 에러가 난다면, `@SpringBootTest`의 스캔 범위나 `@MockBean` 설정 누락을 의심해야 한다.** 프로덕션 코드는 멀쩡한데 테스트 설정에서만 빈이 안 뜨는 경우가 흔하다.
- **멀티모듈 프로젝트에서는 모듈 간 패키지 구조가 서로 다른 트리에 있을 수 있다.** 이 경우 `scanBasePackages`를 명시적으로 지정하는 것이 컨벤션을 지키는 것보다 실용적인 해법이다.

## 마무리 요약

- `Could not autowire` 에러는 클래스 문제가 아니라 Spring이 그 클래스를 빈으로 인식하지 못했다는 신호다.
- 가장 흔한 원인은 메인 클래스의 패키지 하위가 아닌 곳에 컴포넌트가 위치한 경우다.
- 인터페이스 구현체가 여럿이라면 `@Qualifier`나 `@Primary`로 명확히 지정해야 한다.

## 참고 자료

- [Spring 공식 문서 - 컴포넌트 스캐닝](https://docs.spring.io/spring-framework/reference/core/beans/classpath-scanning.html)
- [Spring 공식 문서 - 의존성 주입](https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html)
