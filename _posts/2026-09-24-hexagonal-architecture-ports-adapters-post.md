---
layout: single
title: "헥사고날 아키텍처(포트와 어댑터)로 도메인 로직을 프레임워크에서 분리하기"
date: 2026-09-24 12:45:00 +0530
categories: system-design
tags: ["헥사고날아키텍처", "포트와어댑터", "도메인로직", "아키텍처패턴", "테스트용이성"]
toc: true
toc_sticky: true
excerpt: "Spring이나 특정 DB 라이브러리의 어노테이션이 도메인 서비스 코드 곳곳에 스며들어 프레임워크 교체는커녕 단위 테스트조차 어려워지는 문제를, 포트(인터페이스)와 어댑터로 의존 방향을 뒤집는 헥사고날 아키텍처로 정리했다."
---

## 왜 지금 헥사고날 아키텍처를 다시 봐야 하는가

전형적인 레이어드 아키텍처(Controller-Service-Repository)로 시작한 프로젝트는 시간이 지날수록 도메인 로직을 담당해야 할 서비스 클래스에 프레임워크 관심사가 스며드는 경향이 있다. `@Transactional` 어노테이션, 특정 ORM의 엔티티 클래스, 외부 API 클라이언트의 구체 타입이 서비스 메서드 시그니처에 직접 등장하기 시작하면, 그 서비스는 더 이상 순수한 비즈니스 규칙만 담은 코드가 아니라 특정 기술 스택에 종속된 코드가 된다. 이렇게 되면 단위 테스트를 하려 해도 실제 DB나 프레임워크 컨텍스트 없이는 테스트가 불가능해지고, 나중에 결제 대행사를 바꾸거나 DB를 교체하는 결정 하나가 도메인 로직 코드 전체를 건드리는 사태로 번진다. 헥사고날 아키텍처(포트와 어댑터, Ports and Adapters)는 이 문제를 "의존성의 방향을 강제로 뒤집는다"는 원칙으로 해결한다.

## 핵심 개념 1 — 포트: 도메인이 원하는 인터페이스를 도메인이 직접 정의한다

헥사고날 아키텍처의 핵심은 도메인(애플리케이션 코어)이 외부 세계와 소통하는 방식을 인터페이스, 즉 포트(port)로 정의하고 도메인 자신이 이 인터페이스를 소유한다는 것이다. 예를 들어 주문 도메인이 결제를 처리해야 한다면, 도메인 코드는 `PaymentGateway`라는 인터페이스만 알고 있으면 되며, 이 인터페이스는 특정 PG사의 SDK 타입을 전혀 참조하지 않는다. 중요한 것은 이 인터페이스가 "도메인이 필요로 하는 모양"으로 정의된다는 점이다 — 인프라 계층의 편의가 아니라 도메인의 필요가 인터페이스 설계를 주도한다. 이렇게 하면 의존성 방향이 "도메인 → 구체적인 기술"이 아니라 "구체적인 기술(어댑터) → 도메인이 정의한 포트"로 뒤집힌다.

## 핵심 개념 2 — 어댑터: 포트를 실제 기술로 구현하는 교체 가능한 껍데기

어댑터(adapter)는 포트 인터페이스를 실제 기술(특정 PG사 API, 특정 DB, 메시지 큐)로 구현하는 계층이다. 어댑터는 두 종류로 나뉜다 — 외부에서 도메인으로 들어오는 요청을 처리하는 인바운드(driving) 어댑터(REST 컨트롤러, 메시지 리스너)와, 도메인이 외부 시스템에 요청을 보낼 때 쓰는 아웃바운드(driven) 어댑터(DB 리포지토리 구현체, 외부 API 클라이언트)다. 도메인 코드는 어댑터의 존재 자체를 알지 못하며, 오직 포트 인터페이스만 호출한다. 그 덕분에 PG사를 바꾸거나 DB를 교체할 때는 새로운 어댑터 구현체 하나만 추가하면 되고, 도메인 코드는 한 줄도 건드릴 필요가 없다.

| 구성 요소 | 역할 | 예시 |
|---|---|---|
| 도메인(애플리케이션 코어) | 순수 비즈니스 규칙, 프레임워크 무관 | 주문 생성·검증 로직 |
| 포트(인터페이스) | 도메인이 정의한, 외부와의 계약 | `PaymentGateway`, `OrderRepository` |
| 인바운드 어댑터 | 외부 요청을 도메인 호출로 변환 | REST 컨트롤러, 메시지 리스너 |
| 아웃바운드 어댑터 | 도메인 요청을 실제 기술로 실행 | JPA 리포지토리, PG사 API 클라이언트 |

## 예제 — 포트 정의와 두 개의 아웃바운드 어댑터

```java
// 포트: 도메인이 정의한 인터페이스 (도메인 패키지에 위치)
public interface PaymentGateway {
    PaymentResult charge(OrderId orderId, Money amount);
}

// 도메인 서비스: PaymentGateway 인터페이스만 알고 있음
public class OrderService {
    private final PaymentGateway paymentGateway;

    public OrderService(PaymentGateway paymentGateway) {
        this.paymentGateway = paymentGateway; // 구체 타입이 아니라 포트에 의존
    }

    public void completeOrder(Order order) {
        PaymentResult result = paymentGateway.charge(order.getId(), order.getTotal());
        // 순수 도메인 로직만 존재, PG사 SDK 타입은 등장하지 않음
    }
}

// 아웃바운드 어댑터 A: 실제 PG사 SDK를 감싼 구현체
public class TossPaymentAdapter implements PaymentGateway {
    private final TossPaymentClient tossClient; // 특정 벤더 SDK

    public PaymentResult charge(OrderId orderId, Money amount) {
        var tossResponse = tossClient.requestPayment(orderId.value(), amount.toWon());
        return PaymentResult.from(tossResponse); // 벤더 응답을 도메인 타입으로 변환
    }
}

// 아웃바운드 어댑터 B: 테스트용 스텁 (실제 결제 없이 도메인 로직만 검증)
public class StubPaymentAdapter implements PaymentGateway {
    public PaymentResult charge(OrderId orderId, Money amount) {
        return PaymentResult.success(); // 항상 성공 응답, 빠른 단위 테스트용
    }
}
```

`OrderService`는 `TossPaymentAdapter`를 쓰든 `StubPaymentAdapter`를 쓰든 코드 변경 없이 동작하며, 이 덕분에 단위 테스트에서 실제 PG사 연동 없이도 도메인 로직만 빠르게 검증할 수 있다.

## 실무 포인트

- **모든 계층에 헥사고날을 도그마처럼 적용하지 마라.** 단순 CRUD가 전부인 화면까지 포트·어댑터로 나누면 오히려 파일 수만 늘어나는 과잉 설계가 된다. 도메인 규칙이 복잡하고 외부 의존성이 자주 바뀌는 핵심 도메인에 우선 적용하는 것이 실용적이다.
- **포트 인터페이스의 이름과 시그니처는 인프라 용어가 아니라 도메인 용어로 지어라.** `JpaOrderRepository` 같은 이름이 포트에 등장하면 이미 의존 방향이 뒤집힌 것이며, `OrderRepository`처럼 도메인 관점의 이름이어야 한다.
- **아웃바운드 어댑터의 예외를 도메인 예외로 반드시 변환하라.** DB 드라이버나 PG사 SDK가 던지는 구체적인 예외 타입이 도메인 계층까지 그대로 전파되면, 그 순간 도메인은 다시 특정 기술에 종속된다.

## 마무리 요약

- 헥사고날 아키텍처는 도메인이 필요로 하는 인터페이스(포트)를 도메인 자신이 정의하게 해, 의존성 방향을 "도메인 → 기술"에서 "기술(어댑터) → 도메인"으로 뒤집는다.
- 인바운드 어댑터는 외부 요청을 도메인 호출로, 아웃바운드 어댑터는 도메인 요청을 실제 기술 호출로 변환하며, 도메인 코드는 어댑터의 존재를 전혀 알지 못한다.
- 이 구조 덕분에 기술 스택 교체가 어댑터 추가만으로 끝나고, 테스트용 스텁 어댑터로 외부 의존성 없는 빠른 단위 테스트가 가능해진다.

## 참고 자료

- [Alistair Cockburn - Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Netflix Tech Blog - Ready for changes with Hexagonal Architecture](https://netflixtechblog.com/ready-for-changes-with-hexagonal-architecture-b315ec967749)
