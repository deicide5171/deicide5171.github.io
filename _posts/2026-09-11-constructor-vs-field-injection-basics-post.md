---
layout: single
title: "생성자 주입 vs 필드 주입 — 스프링에서 뭘 써야 하나"
date: 2026-09-11 13:25:00 +0530
categories: backend
tags: ["의존성주입", "di", "spring", "생성자주입", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 의존성을 주입하는 생성자 주입과 필드 주입의 차이, 왜 생성자 주입이 권장되는지 처음 배우는 사람 기준으로 정리했다."
---

## @Autowired를 필드에 붙이면 안 되나

스프링에서 다른 빈(bean)을 가져다 쓰는 것을 **의존성 주입(DI)**이라 한다. 주입 방식은 크게 **필드 주입**(필드에 `@Autowired`)과 **생성자 주입**(생성자로 받기) 두 가지다. 둘 다 동작하지만, 실무에서는 **생성자 주입**을 권장한다.

## 두 방식 비교

| 구분 | 필드 주입 | 생성자 주입 |
|---|---|---|
| 코드 | `@Autowired` 필드 | 생성자 파라미터 |
| final 가능 | 불가 | 가능(불변) |
| 테스트 | 프레임워크 필요 | new로 쉽게 주입 |
| 순환 참조 | 런타임에 발견 | 시작 시 발견 |

## 코드로 비교

```java
// 필드 주입 (권장 X)
@Service
public class OrderService {
    @Autowired
    private PaymentClient payment;
}

// 생성자 주입 (권장 O)
@Service
public class OrderService {
    private final PaymentClient payment;
    public OrderService(PaymentClient payment) {
        this.payment = payment;
    }
}
```

## 실무 포인트

- **생성자 주입은 `final`을 쓸 수 있다.** 의존성을 `final`로 두면 한 번 주입 후 바뀌지 않음이 보장되고, 주입이 누락되면 컴파일·시작 단계에서 바로 드러난다. 안정성이 높다.
- **테스트가 쉽다.** 생성자 주입은 테스트에서 `new OrderService(mockPayment)`처럼 직접 주입할 수 있다. 필드 주입은 스프링 컨텍스트나 리플렉션이 필요해 단위 테스트가 번거롭다.
- **롬복으로 간결하게.** 생성자가 길어지는 것이 부담이면 롬복 `@RequiredArgsConstructor`를 쓰면 `final` 필드에 대한 생성자를 자동 생성해준다. 실무에서 흔한 패턴이다.

## 마무리 요약

- 의존성 주입 방식엔 필드 주입과 생성자 주입이 있고, 실무에선 생성자 주입을 권장한다.
- 생성자 주입은 `final`로 불변 보장, 순환 참조 조기 발견, 테스트 용이라는 장점이 있다.
- 롬복 `@RequiredArgsConstructor`로 생성자 코드를 줄일 수 있다.

## 참고 자료

- [Spring 공식 문서 - Dependency Injection](https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html)
