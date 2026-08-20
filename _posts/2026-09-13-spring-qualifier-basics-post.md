---
layout: single
title: "@Qualifier가 뭔가요 — 같은 타입 빈이 여러 개일 때 고르기"
date: 2026-09-13 13:25:00 +0530
categories: backend
tags: ["qualifier", "spring", "빈", "di", "입문"]
toc: true
toc_sticky: true
excerpt: "같은 타입의 빈이 여러 개라 주입이 애매할 때 어느 것을 쓸지 지정하는 @Qualifier와 @Primary를 처음 배우는 사람 기준으로 정리했다."
---

## "어느 빈을 주입할지 모르겠다"는 오류

스프링에서 인터페이스 하나에 구현체가 둘(예: `KakaoPay`, `NaverPay`가 모두 `PayService`) 있으면, `PayService`를 주입하려 할 때 "어느 것을 넣을지 모른다"는 오류(`NoUniqueBeanDefinitionException`)가 난다. **@Qualifier**는 **여러 후보 중 어느 빈을 쓸지 이름으로 지정**해 이 문제를 푼다.

## 해결 방법 두 가지

| 방법 | 설명 |
|---|---|
| `@Qualifier("이름")` | 주입 지점에서 특정 빈 이름 지정 |
| `@Primary` | 여러 개 중 "기본으로 쓸 것" 하나 표시 |

## 예시

```java
@Service("kakao")
public class KakaoPay implements PayService {}

@Service("naver")
public class NaverPay implements PayService {}

// 주입할 때 어느 것인지 지정
@Service
public class OrderService {
    public OrderService(@Qualifier("kakao") PayService pay) {
        // KakaoPay가 주입됨
    }
}
```

## 실무 포인트

- **`@Primary`는 기본값, `@Qualifier`는 개별 선택.** 대부분 하나를 기본으로 쓰고 가끔 다른 걸 쓴다면, 기본에 `@Primary`를 붙이고 예외 상황에서만 `@Qualifier`로 다른 것을 지정하면 깔끔하다.
- **이름을 명확히.** `@Qualifier("kakao")`처럼 이름으로 고르므로, 빈 이름이 모호하면 헷갈린다. 구현체마다 의미 있는 이름을 붙인다.
- **전략 패턴과 잘 어울린다.** 같은 인터페이스의 여러 구현을 상황에 따라 바꿔 끼우는 전략 패턴에서, `@Qualifier`나 `Map<String, PayService>` 주입으로 구현을 선택하는 방식이 자주 쓰인다.

## 마무리 요약

- 같은 타입 빈이 여러 개면 주입이 애매해져 오류가 나는데, `@Qualifier`로 어느 빈을 쓸지 지정한다.
- `@Primary`는 기본으로 쓸 빈 하나를 표시하고, `@Qualifier`는 개별 주입 지점에서 선택한다.
- 기본은 `@Primary`, 예외는 `@Qualifier`로 조합하면 깔끔하며 전략 패턴에 유용하다.

## 참고 자료

- [Spring 공식 문서 - @Qualifier](https://docs.spring.io/spring-framework/reference/core/beans/annotation-config/autowired-qualifiers.html)
