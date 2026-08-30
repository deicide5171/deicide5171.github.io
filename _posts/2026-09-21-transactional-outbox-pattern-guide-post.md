---
layout: single
title: "트랜잭셔널 아웃박스 패턴 — DB 변경과 이벤트 발행을 안전하게 묶기"
date: 2026-09-21 12:45:00 +0530
categories: system-design
tags: ["outbox패턴", "이벤트기반아키텍처", "분산트랜잭션", "메시지큐", "마이크로서비스"]
toc: true
toc_sticky: true
excerpt: "DB에 데이터를 저장하고 메시지 큐에 이벤트를 발행하는 두 단계가 어긋날 때 생기는 정합성 문제를, 트랜잭셔널 아웃박스 패턴으로 해결하는 방법을 정리했다."
---

## 왜 지금 이 패턴이 필요한가

주문을 생성하면서 "주문 완료" 이벤트를 카프카나 RabbitMQ에 발행하는 서비스를 만든다고 하자. 가장 직관적인 코드는 이렇다.

```java
@Transactional
public void createOrder(OrderRequest req) {
    orderRepository.save(new Order(req));   // DB 커밋
    kafkaTemplate.send("order.created", req.orderId());  // 메시지 발행
}
```

이 코드는 두 개의 서로 다른 시스템(DB, 메시지 브로커)에 걸친 작업을 마치 하나의 원자적 작업처럼 다룬다. 하지만 실제로는 그렇지 않다. DB 커밋은 성공했는데 카프카 전송 도중 네트워크가 끊기면 주문은 저장됐지만 이벤트는 유실된다. 반대로 카프카 전송 로직을 트랜잭션 커밋 전에 두면, 이벤트는 나갔는데 DB 트랜잭션이 롤백되는 상황도 생긴다. 재고 차감, 알림 발송, 결제 정산처럼 이벤트 하나가 여러 후속 시스템을 움직이는 구조에서는 이 어긋남이 곧바로 데이터 불일치 사고로 이어진다.

## 잘못된 해결 시도들

가장 먼저 떠오르는 해법은 분산 트랜잭션(2PC)이다. DB와 메시지 브로커를 하나의 트랜잭션 매니저로 묶으면 되지 않을까 싶지만, 카프카 같은 현대 메시지 브로커는 애초에 2PC 프로토콜을 지원하지 않는 경우가 많고, 지원하더라도 코디네이터가 단일 장애점이 되면서 지연시간이 크게 늘어난다. 성능과 가용성을 희생하면서까지 쓸 만한 해법이 아니다.

두 번째 시도는 "메시지 발행을 먼저 하고 실패하면 DB를 롤백"하는 순서 뒤집기다. 하지만 메시지는 한 번 브로커에 들어가면 소비자가 이미 처리를 시작했을 수 있어 되돌릴 수 없다. 순서를 어떻게 배치해도 "DB 커밋"과 "메시지 발행"이라는 서로 다른 두 리소스를 하나의 원자적 단위로 묶을 수 없다는 근본 문제는 남는다.

## 트랜잭셔널 아웃박스 패턴

<img src="/assets/images/posts/2026-09-21-transactional-outbox-pattern-guide-1.svg" alt="아웃박스 패턴 구조도: 애플리케이션이 비즈니스 테이블과 outbox 테이블에 같은 트랜잭션으로 쓰고, 별도 릴레이가 outbox를 읽어 메시지 브로커로 전달한다" style="width:100%;">

핵심 아이디어는 단순하다. **메시지를 외부 브로커로 직접 보내지 않고, 같은 DB 트랜잭션 안에 있는 "아웃박스 테이블"에 먼저 기록한다.** 이렇게 하면 비즈니스 데이터 저장과 이벤트 기록이 하나의 로컬 트랜잭션이 되므로 원자성이 보장된다. 그 다음 별도의 프로세스(릴레이, 혹은 CDC 도구)가 아웃박스 테이블을 읽어 실제 메시지 브로커로 전달한다.

```sql
CREATE TABLE outbox (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(50),
    aggregate_id VARCHAR(50),
    event_type VARCHAR(50),
    payload JSONB,
    created_at TIMESTAMP DEFAULT now(),
    published BOOLEAN DEFAULT false
);
```

```java
@Transactional
public void createOrder(OrderRequest req) {
    Order order = orderRepository.save(new Order(req));
    outboxRepository.save(new OutboxEvent("Order", order.getId(), "OrderCreated", toJson(order)));
    // 둘 다 같은 트랜잭션 — 하나라도 실패하면 둘 다 롤백
}
```

## 아웃박스를 실제로 발행하는 두 가지 방식

| 방식 | 동작 | 장단점 |
|---|---|---|
| 폴링 발행 | 스케줄러가 주기적으로 `published=false` 행을 조회해 전송 | 구현 간단, 폴링 주기만큼 지연 발생 |
| CDC(Debezium 등) | DB 트랜잭션 로그(binlog/WAL)를 읽어 즉시 전달 | 지연 최소화, 인프라 구성 요소가 늘어남 |

소규모 서비스는 폴링 방식으로 시작해도 충분하다. 초당 이벤트 수가 많거나 지연시간에 민감하다면 Debezium 같은 CDC 도구로 트랜잭션 로그를 직접 읽는 방식이 유리하다.

## 실무 포인트

- **메시지는 최소 한 번(at-least-once) 전달을 전제로 소비자를 짜라.** 아웃박스 릴레이가 전송 후 "발행 완료" 표시 전에 죽으면 같은 메시지가 중복 발행될 수 있다. 소비자 쪽에서 이벤트 ID 기준 멱등 처리를 반드시 갖춰야 한다.
- **아웃박스 테이블은 주기적으로 정리하라.** 발행 완료된 행을 무한정 쌓아두면 테이블이 비대해져 폴링 쿼리 성능이 나빠진다. 배치로 오래된 행을 삭제하거나 별도 아카이브 테이블로 옮긴다.
- **순서 보장이 필요하면 파티션 키를 신경 써라.** 카프카를 쓴다면 aggregate_id를 파티션 키로 사용해 같은 엔티티의 이벤트가 순서대로 처리되게 한다.
- **2PC와 혼동하지 말 것.** 아웃박스는 "로컬 트랜잭션의 원자성"만 보장한다. 브로커로의 전달은 여전히 비동기이고 지연이 있을 수 있다는 점을 소비자 설계에 반영해야 한다.

## 마무리 요약

- DB 저장과 메시지 발행을 각각 따로 하면 한쪽만 성공하는 정합성 문제가 생긴다.
- 트랜잭셔널 아웃박스는 이벤트를 같은 DB 트랜잭션 안의 아웃박스 테이블에 먼저 기록해 원자성을 확보한다.
- 폴링 또는 CDC로 아웃박스를 실제 브로커에 전달하며, 소비자는 반드시 멱등 처리를 갖춰야 한다.

## 참고 자료

- [Debezium - Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [microservices.io - Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
