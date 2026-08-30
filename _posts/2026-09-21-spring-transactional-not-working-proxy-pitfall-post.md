---
layout: single
title: "Spring @Transactional이 동작하지 않는 흔한 이유 — 프록시 함정"
date: 2026-09-21 12:25:00 +0530
categories: backend
tags: ["spring", "transactional", "aop프록시", "자기호출", "스프링트랜잭션"]
toc: true
toc_sticky: true
excerpt: "분명히 @Transactional을 붙였는데 롤백이 안 되거나 커밋이 안 되는 문제의 대부분은 같은 클래스 안에서 메서드를 직접 호출하는 자기 호출 함정 때문이다. 원인과 해결법을 정리했다."
---

## 왜 이 문제가 계속 반복되나

Spring에서 `@Transactional`은 메서드에 애노테이션 하나만 붙이면 트랜잭션이 알아서 시작·커밋·롤백되는 마법처럼 느껴진다. 그런데 실무에서 다음과 같은 코드를 짜고 나서 "분명히 예외가 났는데 DB에 데이터가 남아있다"거나 "새 트랜잭션으로 분리했는데 기존 트랜잭션과 묶여서 처리된다"는 버그 리포트를 받는 경우가 매우 흔하다.

```java
@Service
public class OrderService {

    public void placeOrder(OrderRequest request) {
        validateStock(request);
        saveOrder(request);   // 이 메서드에만 @Transactional이 붙어있다
    }

    @Transactional
    public void saveOrder(OrderRequest request) {
        orderRepository.save(new Order(request));
        if (request.getAmount() > 1_000_000) {
            throw new IllegalArgumentException("한도 초과");
        }
    }
}
```

`placeOrder()`에서 `saveOrder()`를 호출했으니 예외가 나면 롤백될 것 같지만, 실제로는 **`saveOrder()`의 `@Transactional`이 아예 적용되지 않는다.** 이유는 Spring의 트랜잭션이 AOP 프록시로 구현되어 있기 때문이다.

## AOP 프록시가 트랜잭션을 처리하는 방식

Spring은 `@Transactional`이 붙은 빈을 감싸는 프록시 객체를 만든다. 외부에서 `orderService.saveOrder()`를 호출하면 실제로는 이 프록시가 먼저 호출을 가로채, 트랜잭션을 시작하고 나서 원본 메서드를 호출한다. 문제는 **같은 클래스 안에서 `this.saveOrder()`처럼(또는 그냥 `saveOrder()`로) 호출하면 프록시를 거치지 않고 원본 객체의 메서드가 직접 호출된다는 점**이다. 프록시가 개입할 기회 자체가 없으므로 `@Transactional`이 붙어 있어도 아무 효과가 없다. 이를 흔히 **자기 호출(self-invocation) 문제**라고 부른다.

## 잘못된 접근: 애노테이션을 더 세게(?) 붙이기

이 문제를 처음 마주친 개발자는 `@Transactional(propagation = Propagation.REQUIRES_NEW)`를 붙이면 해결될 거라 생각하기 쉽다. 하지만 전파 옵션은 트랜잭션이 실제로 시작된 이후의 동작(새 트랜잭션을 만들지, 기존 것에 참여할지)을 결정하는 것이지, 애초에 프록시를 거치지 않는 자기 호출 상황 자체를 해결해주지 않는다. 전파 옵션을 아무리 바꿔도 자기 호출이면 트랜잭션이 아예 시작되지 않는다.

## 올바른 접근

**1) 트랜잭션이 필요한 메서드를 별도의 빈으로 분리한다.**

```java
@Service
public class OrderService {
    private final OrderTransactionService orderTransactionService;

    public void placeOrder(OrderRequest request) {
        validateStock(request);
        orderTransactionService.saveOrder(request);  // 다른 빈을 통한 호출
    }
}

@Service
public class OrderTransactionService {
    @Transactional
    public void saveOrder(OrderRequest request) {
        // ...
    }
}
```

다른 빈을 거쳐 호출하면 반드시 프록시를 통과하게 되므로 트랜잭션이 정상적으로 시작된다. 가장 확실하고 널리 권장되는 방법이다.

**2) 자기 자신을 프록시로 주입받아 호출한다.**

```java
@Service
public class OrderService {
    @Autowired
    private OrderService self;  // 프록시로 주입되는 자기 자신

    public void placeOrder(OrderRequest request) {
        self.saveOrder(request);
    }

    @Transactional
    public void saveOrder(OrderRequest request) { /* ... */ }
}
```

동작은 하지만 자기 자신을 주입받는 코드는 읽는 사람 입장에서 부자연스럽고 순환 참조처럼 보여 유지보수성이 떨어지므로, 가능하면 1번처럼 책임을 아예 다른 클래스로 분리하는 편이 낫다.

## 함께 자주 나오는 두 가지 함정

| 함정 | 증상 | 원인 |
|---|---|---|
| 자기 호출 | 예외가 나도 롤백 안 됨 | 프록시를 거치지 않는 내부 호출 |
| private 메서드에 @Transactional | 아예 적용 안 됨 | JDK 동적 프록시·CGLIB 모두 private 메서드를 오버라이드할 수 없음 |
| Checked Exception 발생 | 예외가 나도 커밋됨 | 기본 설정은 RuntimeException만 롤백 대상 |

`private` 메서드에 `@Transactional`을 붙이는 것도 흔한 실수다. 프록시는 상속이나 인터페이스 구현으로 메서드를 오버라이드하는 방식으로 동작하는데, `private` 메서드는 오버라이드 자체가 불가능해 애노테이션이 조용히 무시된다. 또한 기본적으로 Spring은 `RuntimeException`과 `Error`만 롤백 대상으로 삼으므로, 체크 예외(`IOException` 등)를 던지는 코드는 `rollbackFor = Exception.class`를 명시하지 않으면 예외가 나도 그대로 커밋된다.

## 실무 포인트

- **트랜잭션 관련 버그는 로그로 눈에 잘 안 보인다.** `spring.jpa.show-sql`이나 트랜잭션 로그 레벨(`org.springframework.transaction`)을 DEBUG로 켜서 실제로 트랜잭션이 시작·커밋되는지 확인하는 습관이 문제를 훨씬 빨리 찾게 해준다.
- **테스트에서 `@Transactional`을 테스트 클래스에 붙이면 각 테스트가 끝난 뒤 자동 롤백된다.** 이 편의 기능과 실제 서비스 코드의 트랜잭션 동작을 혼동하지 않도록 주의한다.
- **AOP 프록시 자체를 이해하지 않고 트랜잭션 설정만 바꾸는 시행착오는 시간 낭비다.** 이 자기 호출 개념 하나만 정확히 알아도 관련 버그의 대부분을 예방할 수 있다.

## 마무리 요약

- Spring의 `@Transactional`은 AOP 프록시로 구현되어 있어, 같은 클래스 내부에서의 메서드 호출(자기 호출)에는 적용되지 않는다.
- 트랜잭션이 필요한 로직은 별도의 빈으로 분리해 외부 호출로 프록시를 거치게 하는 것이 가장 안전한 해결책이다.
- private 메서드 사용 금지, 체크 예외에 대한 rollbackFor 명시까지 함께 챙겨야 트랜잭션 관련 버그를 예방할 수 있다.

## 참고 자료

- [Spring 공식 문서 - Transaction Management](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html)
- [Spring 공식 문서 - AOP Proxies](https://docs.spring.io/spring-framework/reference/core/aop/proxying.html)
