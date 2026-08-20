---
layout: single
title: "Spring Bean이 뭔가요 — IoC 컨테이너 개념 처음 이해하기"
date: 2026-09-02 12:25:00 +0530
categories: backend
tags: ["spring", "bean", "ioc", "의존성주입", "입문"]
toc: true
toc_sticky: true
excerpt: "Spring을 배우면 가장 먼저 마주치는 Bean과 IoC 컨테이너 개념이 정확히 무엇을 의미하는지, new 키워드와 비교하며 기초부터 정리했다."
---

## 왜 직접 new로 객체를 만들지 않는가

일반 자바 코드에서는 객체가 필요하면 `new UserService()`처럼 직접 생성한다. 그런데 Spring 코드를 보면 `@Autowired`로 필드에 객체가 "알아서" 채워져 있다. 이 마법 같은 동작의 정체가 **IoC(Inversion of Control, 제어의 역전)**다. 객체를 개발자가 직접 만드는 대신, Spring이라는 컨테이너가 객체 생성과 연결을 대신 책임지는 방식이다.

## Bean과 IoC 컨테이너란

| 용어 | 의미 |
|---|---|
| Bean | Spring 컨테이너가 생성하고 관리하는 객체 |
| IoC 컨테이너 | Bean을 생성·관리·연결(의존성 주입)하는 Spring의 핵심 부품 |
| 의존성 주입(DI) | 필요한 객체를 직접 만들지 않고 컨테이너가 대신 넣어주는 것 |

## 코드로 보는 차이

```java
// IoC 없이: 직접 객체를 만들고 연결해야 한다
public class OrderService {
    private PaymentService paymentService = new PaymentService(); // 직접 생성
}

// Spring IoC 사용: @Autowired로 컨테이너가 대신 넣어준다
@Service
public class OrderService {
    private final PaymentService paymentService;

    @Autowired  // 생성자가 하나면 생략 가능
    public OrderService(PaymentService paymentService) {
        this.paymentService = paymentService;
    }
}

@Service
public class PaymentService { ... } // 이 클래스도 Bean으로 등록된다
```

`OrderService`는 `PaymentService`를 직접 만들지 않는다. `@Service`가 붙은 `PaymentService`는 Spring이 애플리케이션 시작 시점에 Bean으로 미리 만들어두고, `OrderService`가 필요로 할 때 그 인스턴스를 생성자를 통해 "주입"해준다.

## 왜 이렇게 번거로운 방식을 쓰는가

```text
직접 생성의 문제점:
- OrderService가 PaymentService의 구체적인 구현에 강하게 결합된다
- 테스트할 때 진짜 PaymentService 대신 가짜(Mock)로 바꿔 끼우기 어렵다
- PaymentService 생성 로직이 바뀌면 그것을 사용하는 모든 코드를 수정해야 한다

IoC/DI의 이점:
- OrderService는 PaymentService라는 "역할"에만 의존하고 구체적 구현은 몰라도 된다
- 테스트 시 Mock 객체를 쉽게 주입할 수 있다 (@MockBean 등)
- 객체 생성과 연결 로직이 한 곳(컨테이너)에 모여 관리가 쉬워진다
```

## 실무 포인트

- **모든 클래스가 Bean이 되는 것은 아니다.** `@Component`, `@Service`, `@Repository`, `@Controller` 같은 애노테이션이 붙거나 `@Bean`으로 명시적으로 등록한 것만 Spring이 관리하는 Bean이 된다.
- **필드 주입(`@Autowired`를 필드에 직접)보다 생성자 주입을 권장한다.** 생성자 주입은 필수 의존성을 명확히 드러내고, 테스트 코드에서 객체를 만들 때도 컨테이너 없이 생성자로 바로 조립할 수 있다.
- **Bean은 기본적으로 싱글톤(하나의 인스턴스를 공유)이다.** 상태를 갖는 필드를 Bean 클래스에 두면 여러 요청이 그 상태를 공유하게 되어 동시성 버그가 생길 수 있으므로 주의해야 한다.

## 마무리 요약

- IoC는 객체 생성과 연결을 개발자가 아니라 Spring 컨테이너가 대신 책임지는 원칙이다.
- Bean은 그 컨테이너가 관리하는 객체이며, 의존성 주입은 필요한 Bean을 컨테이너가 대신 넣어주는 과정이다.
- 생성자 주입을 기본으로 쓰고, Bean이 기본적으로 싱글톤이라는 점을 고려해 상태 관리에 주의해야 한다.

## 참고 자료

- [Spring 공식 문서 - IoC 컨테이너](https://docs.spring.io/spring-framework/reference/core/beans/basics.html)
