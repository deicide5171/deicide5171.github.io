---
layout: single
title: "CQRS 패턴 — 읽기와 쓰기 모델을 분리해야 하는 순간"
date: 2026-08-20 12:45:00 +0530
categories: system-design
tags: ["system-design", "cqrs", "event-sourcing", "scalability", "architecture"]
toc: true
toc_sticky: true
excerpt: "단일 모델로 읽기와 쓰기를 모두 감당하기 버거워질 때, CQRS로 두 경로를 분리하는 이유와 그로 인해 생기는 복잡도 트레이드오프를 정리한다."
---

서비스 초기에는 하나의 도메인 모델, 하나의 테이블 스키마로 읽기와 쓰기를 모두 처리하는 것이 자연스럽다. 엔티티 하나에 CRUD 메서드를 얹고, 조회 화면도 같은 엔티티를 그대로 직렬화해 내려주면 된다. 문제는 트래픽이 늘면서 읽기와 쓰기의 성격이 서로 다른 방향으로 벌어질 때 생긴다. 대시보드 하나를 그리기 위해 여러 테이블을 조인하고 집계하는 조회 쿼리가, 정작 그 데이터를 만든 쓰기 로직의 트랜잭션 성격과는 전혀 다른 최적화를 요구하는 경우가 흔하다.

전형적인 증상은 이렇다. 쓰기 경로는 정규화된 스키마와 강한 일관성이 필요한데, 읽기 경로는 비정규화된 형태로 빠르게 훑어볼 수 있어야 한다. 하나의 모델이 양쪽 요구를 동시에 만족시키려다 보면 결국 조회 성능을 위해 인덱스를 과도하게 늘리거나, 쓰기 로직에 조회 편의를 위한 필드를 억지로 끼워 넣는 타협이 쌓인다. CQRS(Command Query Responsibility Segregation)는 이 타협을 없애자는 것이 아니라, 애초에 읽기와 쓰기가 서로 다른 모델을 가져도 된다고 인정하는 접근이다.

다만 CQRS는 "일단 도입하면 좋은" 패턴이 아니라 특정 상황의 트레이드오프를 감수할 준비가 됐을 때 쓰는 도구에 가깝다. 이 글에서는 CQRS의 기본 구조, 이벤트 소싱과의 관계, 읽기 모델을 만드는 프로젝션 개념, 그리고 도입하지 말아야 할 상황까지 정리한다.

## 핵심 개념 1: CQRS 기본 구조

CQRS의 핵심은 하나다. 상태를 변경하는 커맨드(Command)와 상태를 조회하는 쿼리(Query)를 서로 다른 모델, 필요하다면 서로 다른 데이터 저장소로 처리한다는 것. 커맨드 쪽은 비즈니스 규칙과 불변식을 지키는 데 집중한 도메인 모델을 쓰고, 쿼리 쪽은 화면이나 API 응답 형태에 최적화된 읽기 전용 모델을 쓴다.

<img src="/assets/images/posts/2026-08-20-cqrs-read-write-separation-1.svg" alt="CQRS 커맨드 경로와 쿼리 경로 분리 구조도 - 쓰기 모델과 읽기 모델이 별도로 존재하고 동기화 메커니즘으로 연결됨" style="width:100%;">

여기서 자주 오해되는 지점은, CQRS가 반드시 서로 다른 데이터베이스를 요구하지는 않는다는 점이다. 같은 데이터베이스 안에서 쓰기용 테이블과 조회용 뷰(또는 별도 조회 테이블)만 나누는 가벼운 형태도 CQRS의 범주에 들어간다. 완전히 분리된 저장소를 쓰는 형태는 그중에서도 규모가 큰 축에 속하며, 두 모델 사이의 동기화 지연(읽기 모델이 최신 쓰기를 즉시 반영하지 못하는 최종 일관성)을 감수해야 한다.

## 핵심 개념 2: 이벤트 소싱과의 관계 및 차이

CQRS와 이벤트 소싱(Event Sourcing)은 함께 언급되는 경우가 많지만 서로 다른 개념이다. CQRS는 읽기와 쓰기 모델을 분리하자는 것이고, 이벤트 소싱은 엔티티의 현재 상태 대신 그 상태에 이르기까지의 이벤트 이력 전체를 저장하자는 것이다. 이벤트 소싱을 쓰지 않고도 CQRS를 적용할 수 있고, 반대로 이벤트 소싱을 도입했다고 해서 반드시 CQRS를 써야 하는 것도 아니다.

다만 두 패턴은 궁합이 좋다. 이벤트 소싱에서는 저장된 이벤트 스트림 자체가 조회에 적합한 형태가 아니기 때문에, 조회용 모델을 별도로 만들어야 할 필요성이 자연스럽게 생긴다. 이 조회용 모델을 만드는 과정이 바로 다음 절에서 다룰 프로젝션이며, 이벤트 소싱과 CQRS가 나란히 등장하는 이유가 대체로 여기에 있다.

## 핵심 개념 3: 읽기 모델 프로젝션

프로젝션(Projection)은 쓰기 쪽에서 발생한 변경(이벤트든 단순 업데이트든)을 구독해 읽기 모델을 갱신하는 과정이다. 커맨드가 처리되어 상태가 바뀌면 그 변경 사실이 어떤 형태로든 전파되고, 프로젝션 로직이 이를 받아 조회에 최적화된 형태(비정규화된 테이블, 검색 인덱스, 캐시 등)로 다시 써넣는다.

이 갱신은 대부분 비동기로 이루어지므로, 쓰기 직후 곧바로 조회하면 아직 반영되지 않은 값을 볼 수 있다는 최종 일관성 문제가 뒤따른다. 프로젝션은 언제든 이벤트 이력이나 쓰기 모델의 상태로부터 처음부터 다시 만들어낼 수 있어야 하며, 실제로 운영 중 읽기 모델의 스키마를 바꾸거나 버그를 수정할 때는 기존 프로젝션을 버리고 재구성하는 경우가 드물지 않다.

## 핵심 개념 4: 언제 도입하면 안 되는지

CQRS의 대가는 명확하다. 모델이 두 개로 늘어나고, 그 사이를 잇는 동기화 메커니즘이 새로운 실패 지점이 되며, 최종 일관성으로 인한 사용자 경험 문제(방금 쓴 데이터가 조회에 안 보이는 상황)를 어딘가에서 처리해야 한다. 읽기와 쓰기 트래픽 패턴이 크게 다르지 않은 평범한 CRUD 서비스, 팀 규모가 작아 추가 복잡도를 감당하기 어려운 상황, 강한 일관성이 비즈니스 요구사항인 도메인(결제 잔액 확인 직후 즉시 반영이 필수인 경우 등)에서는 단일 모델을 유지하는 편이 낫다. CQRS는 "복잡해서 멋있어 보이는" 패턴이 아니라, 이미 단일 모델의 한계가 구체적인 성능·설계 문제로 나타난 다음에 검토할 선택지로 보는 편이 안전하다.

## 예제

아래는 Java 기반 의사 코드로, 커맨드 핸들러와 쿼리 핸들러를 물리적으로 분리한 구조 예시다.

```java
// 커맨드 쪽: 도메인 규칙을 지키며 상태를 변경
public class PlaceOrderCommandHandler {
    private final OrderRepository writeRepo;
    private final EventPublisher publisher;

    public void handle(PlaceOrderCommand cmd) {
        Order order = Order.create(cmd.customerId(), cmd.items());
        order.validateStock();          // 도메인 불변식 검증
        writeRepo.save(order);
        publisher.publish(new OrderPlacedEvent(order.id(), order.items()));
    }
}

// 조회 쪽: 비정규화된 읽기 모델에서 바로 가져옴
public class OrderSummaryQueryHandler {
    private final OrderReadModelRepository readRepo;

    public OrderSummaryView handle(GetOrderSummaryQuery query) {
        return readRepo.findSummaryByOrderId(query.orderId());
    }
}

// 프로젝션: 이벤트를 구독해 읽기 모델 갱신
public class OrderSummaryProjection {
    private final OrderReadModelRepository readRepo;

    @EventListener
    public void on(OrderPlacedEvent event) {
        readRepo.upsertSummary(event.orderId(), event.items());
    }
}
```

커맨드 핸들러는 `OrderRepository`(쓰기 모델)만 알고, 쿼리 핸들러는 `OrderReadModelRepository`(읽기 모델)만 안다. 두 저장소는 `OrderPlacedEvent`를 매개로 비동기로 연결되어 있어, 서로 직접 참조하지 않는다.

## 실무 포인트

- **동기화 지연을 화면 설계에 반영한다**: 주문 생성 직후 확인 화면처럼 즉시 최신 상태를 보여줘야 하는 곳은, 쓰기 응답에 결과를 그대로 담아 내려주는 방식으로 읽기 모델의 지연을 우회하는 편이 안전하다.
- **읽기 모델은 언제든 재구성 가능해야 한다**: 프로젝션 로직에 버그가 있었거나 스키마를 바꿔야 할 때 이벤트 이력이나 쓰기 모델로부터 처음부터 다시 만들 수 있도록 설계해 두면 운영 부담이 줄어든다.
- **부분 도입부터 검토한다**: 서비스 전체가 아니라 조회 부하가 큰 특정 도메인(상품 검색, 대시보드 집계 등)에만 먼저 CQRS를 적용해보고 범위를 넓히는 편이 리스크가 작다.
- **모니터링 대상에 동기화 지연을 포함시킨다**: 쓰기와 읽기 모델 사이의 지연 시간 자체를 관측 지표로 추적하지 않으면, 사용자가 겪는 최종 일관성 문제를 뒤늦게 알아차리게 된다.

## 3줄 요약

- CQRS는 읽기와 쓰기의 트래픽 패턴이 서로 다른 방향으로 벌어질 때, 두 경로를 별도 모델(필요하면 별도 저장소)로 분리하는 패턴이다.
- 이벤트 소싱과는 별개의 개념이지만, 이벤트 이력으로부터 조회용 읽기 모델을 만드는 프로젝션 과정에서 자연스럽게 함께 쓰인다.
- 모델 이원화와 최종 일관성이라는 복잡도를 감수할 구체적인 이유가 없다면, 평범한 CRUD 서비스에는 단일 모델을 유지하는 편이 낫다.

## 참고 자료

- [Martin Fowler — CQRS (bliki)](https://martinfowler.com/bliki/CQRS.html)
- [Microsoft Azure Architecture Center — CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
- [Martin Fowler — Event Sourcing (bliki)](https://martinfowler.com/eaaDev/EventSourcing.html)
