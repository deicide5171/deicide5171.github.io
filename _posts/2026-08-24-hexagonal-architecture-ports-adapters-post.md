---
layout: single
title: "도메인을 프레임워크에서 지켜라 — 헥사고날 아키텍처 실전 적용"
date: 2026-08-24 13:45:00 +0530
categories: system-design
tags: ["hexagonal-architecture", "ports-and-adapters", "clean-architecture", "spring", "domain-driven-design"]
toc: true
toc_sticky: true
excerpt: "비즈니스 로직이 JPA 엔티티와 컨트롤러 코드에 뒤섞여 테스트도, 프레임워크 교체도 어려워지는 문제를, 포트-어댑터로 도메인을 격리하는 헥사고날 아키텍처로 어떻게 푸는지 정리한다."
---

서비스 로직 안에 `@Transactional`, `HttpServletRequest`, JPA 연관관계 매핑이 뒤섞여 있는 코드는 흔하다. 문제는 이런 코드가 비즈니스 규칙을 테스트하려 해도 Spring 컨텍스트나 실제 DB 없이는 단위 테스트가 불가능해진다는 것이다. 프레임워크가 바뀌거나(예: Spring MVC → WebFlux), 저장소가 바뀌면(RDB → NoSQL) 도메인 로직까지 함께 뒤엎어야 하는 상황도 이 결합에서 비롯된다.

헥사고날 아키텍처(Ports and Adapters, Alistair Cockburn 제안)는 이 결합을 구조적으로 끊는다. 도메인 코어는 외부 세계와 오직 인터페이스(포트)로만 소통하고, 실제 기술(REST, JPA, 메시징)은 전부 그 인터페이스의 구현체(어댑터)로 코어 바깥에 둔다. 이 글에서는 포트/어댑터의 구분, 레이어드 아키텍처와의 차이, 그리고 과잉 설계를 피하는 실무 기준을 정리한다.

## 핵심 개념 1: 포트(Port)와 어댑터(Adapter)의 역할 분리

- **인바운드 포트(Inbound Port)**: 외부에서 도메인 코어로 들어오는 진입점을 정의하는 인터페이스. 예: `OrderUseCase` 인터페이스의 `placeOrder()` 메서드
- **인바운드 어댑터(Inbound Adapter)**: 인바운드 포트를 호출하는 실제 진입 기술. REST 컨트롤러, gRPC 서버, 메시지 컨슈머, CLI 등
- **아웃바운드 포트(Outbound Port)**: 도메인 코어가 외부 자원에 접근할 때 요구하는 인터페이스. 예: `OrderRepository` 인터페이스
- **아웃바운드 어댑터(Outbound Adapter)**: 아웃바운드 포트의 실제 구현. JPA Repository, 외부 API 클라이언트, 메시지 프로듀서 등

핵심은 의존성 방향이다. 어댑터는 포트(인터페이스)에 의존하고, 포트는 도메인 코어 안에 위치한다. 도메인 코어는 어댑터의 존재 자체를 모른다.

<img src="/assets/images/posts/2026-08-24-hexagonal-architecture-ports-adapters-1.svg" alt="헥사고날 아키텍처 구조도 — 도메인 코어를 중심으로 인바운드/아웃바운드 포트와 어댑터가 배치되고 의존성이 어댑터에서 코어 방향으로 흐르는 구조" style="width:100%;">

## 핵심 개념 2: 레이어드 아키텍처와 무엇이 다른가

| 구분 | 전통적 레이어드 아키텍처 | 헥사고날(포트-어댑터) |
|---|---|---|
| 의존 방향 | Controller → Service → Repository (단방향, DB가 최하단) | 모든 외부 요소 → 포트 → 도메인 코어 |
| DB 교체 영향 | Service가 Repository 구현 세부사항을 알기 쉬움 | Repository 인터페이스만 지키면 구현 교체 자유 |
| 테스트 방식 | 통합 테스트 위주가 되기 쉬움 | 코어는 순수 단위 테스트, 어댑터는 별도 통합 테스트 |
| 진입점 다양성 | Controller 계층에 종속적 | REST/CLI/메시징 등 어댑터만 추가하면 확장 |

레이어드 아키텍처의 근본적 문제는 "아래 계층에 의존한다"는 구조상 결국 최하단(DB)의 기술적 세부사항이 위 계층까지 스며든다는 점이다. 헥사고날은 도메인을 중심에 놓고 모든 기술적 요소를 바깥으로 밀어내, 의존성이 항상 코어를 향하게 뒤집는다.

## 예제: Java/Spring 패키지 구조와 포트 인터페이스

```
com.example.order
├── domain
│   ├── Order.java                  // 순수 도메인 엔티티 (JPA 애너테이션 없음)
│   └── OrderPolicy.java            // 도메인 규칙
├── application
│   ├── port.in
│   │   └── PlaceOrderUseCase.java   // 인바운드 포트
│   └── port.out
│       └── OrderRepository.java     // 아웃바운드 포트
│   └── PlaceOrderService.java       // 유스케이스 구현 (도메인 코어)
└── adapter
    ├── in.web
    │   └── OrderController.java     // 인바운드 어댑터
    └── out.persistence
        ├── OrderJpaRepository.java  // Spring Data 인터페이스
        └── OrderRepositoryAdapter.java // 아웃바운드 어댑터, port.out 구현
```

```java
// application/port.out/OrderRepository.java — 아웃바운드 포트
public interface OrderRepository {
    Order save(Order order);
    Optional<Order> findById(OrderId id);
}

// adapter/out.persistence/OrderRepositoryAdapter.java — 아웃바운드 어댑터
@Component
public class OrderRepositoryAdapter implements OrderRepository {
    private final OrderJpaRepository jpaRepository;

    public OrderRepositoryAdapter(OrderJpaRepository jpaRepository) {
        this.jpaRepository = jpaRepository;
    }

    @Override
    public Order save(Order order) {
        return jpaRepository.save(OrderEntity.from(order)).toDomain();
    }

    @Override
    public Optional<Order> findById(OrderId id) {
        return jpaRepository.findById(id.value()).map(OrderEntity::toDomain);
    }
}
```

`PlaceOrderService`(유스케이스 구현체)는 `OrderRepository` 인터페이스만 참조하므로, 테스트에서는 인메모리 가짜 구현으로 대체해 Spring 컨텍스트 없이 순수 단위 테스트를 실행할 수 있다.

## 실무 포인트

- **작은 CRUD 서비스에 무리하게 적용하지 않는다**: 도메인 로직이 거의 없이 단순 CRUD만 하는 서비스에 포트/어댑터 계층을 억지로 나누면, 파일 수만 늘고 실질적인 격리 이점은 거의 없다. 도메인 규칙이 복잡하거나 여러 진입점/저장소를 지원해야 하는 서비스에 우선 적용하는 것이 합리적이다.
- **도메인 엔티티와 영속성 엔티티를 분리한다**: JPA `@Entity`를 도메인 객체로 그대로 쓰면 결국 프레임워크 의존성이 도메인에 스며든다. `OrderEntity`(영속성)와 `Order`(도메인)를 분리하고 어댑터에서 상호 변환하는 매핑 계층을 둬야 헥사고날의 격리 효과가 실제로 발생한다.
- **포트 인터페이스를 지나치게 잘게 쪼개지 않는다**: 메서드 하나짜리 인터페이스를 남발하면 오히려 코드 탐색이 어려워진다. 유스케이스 단위로 응집력 있게 포트를 설계하는 것이 유지보수에 유리하다.

## 3줄 요약

- 헥사고날 아키텍처는 도메인 코어가 포트(인터페이스)만 알고 실제 기술은 모두 어댑터로 밀어내, 의존성이 항상 코어를 향하도록 구조를 뒤집는다.
- 레이어드 아키텍처와 달리 DB나 진입 방식 교체가 어댑터 교체만으로 가능해지고, 코어 로직은 프레임워크 없이 순수 단위 테스트가 가능해진다.
- 도메인 로직이 단순한 CRUD 서비스에는 과잉 설계가 될 수 있으므로, 복잡한 비즈니스 규칙이나 다중 진입점이 필요한 곳에 선택적으로 적용하는 것이 실무적이다.

## 참고 자료

- [Alistair Cockburn: Hexagonal Architecture 원문](https://alistair.cockburn.us/hexagonal-architecture/)
- [Spring 공식 가이드: Structuring your code](https://docs.spring.io/spring-boot/reference/using/structuring-your-code.html)
- [Baeldung: Hexagonal Architecture with Java and Spring](https://www.baeldung.com/hexagonal-architecture-ddd-spring)
