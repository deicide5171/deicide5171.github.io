---
layout: single
title: "트랜잭션은 지켰는데 메시지는 안 갔다 — 아웃박스 패턴으로 이중 쓰기 문제 해결하기"
date: 2026-08-16 13:45:00 +0530
categories: system-design
tags: ["outbox-pattern", "dual-write", "cdc", "kafka", "spring-boot"]
toc: true
toc_sticky: true
excerpt: "DB 커밋과 메시지 발행을 각각 따로 호출하면 둘 중 하나만 성공하는 이중 쓰기 문제가 생긴다. 아웃박스 테이블로 이 둘을 하나의 로컬 트랜잭션에 묶는 방법을 정리한다."
---

## 왜 지금 이 문제인가

"주문을 저장한 뒤 재고 서비스에 이벤트를 발행한다" — 마이크로서비스에서 셀 수 없이 반복되는 패턴이다. 코드는 대개 이렇게 생겼다. 먼저 `INSERT INTO orders`로 DB에 커밋하고, 그다음 Kafka 프로듀서로 `OrderPlaced` 이벤트를 보낸다. 문제는 이 두 호출이 서로 다른 시스템(RDBMS와 메시지 브로커)을 대상으로 하는 별개의 원자적 연산이라는 점이다. DB 커밋은 성공했는데 그 직후 네트워크 장애나 브로커 다운으로 메시지 발행이 실패하면, 주문은 저장됐지만 재고 서비스는 영원히 이 사실을 모른다. 반대로 발행을 먼저 하고 DB 커밋이 실패하면 있지도 않은 주문에 대한 이벤트가 돌아다니게 된다.

이것이 **이중 쓰기(Dual Write) 문제**다. 서로 다른 두 저장소에 대한 쓰기를 애플리케이션 코드 레벨에서 "순서대로 호출"하는 것만으로는 원자성을 얻을 수 없다. 두 시스템에 걸친 분산 트랜잭션(XA, 2PC)으로 풀어보려는 시도도 있지만, 메시지 브로커 대부분이 XA를 지원하지 않거나 지원하더라도 가용성 비용이 커서 실무에서 거의 쓰이지 않는다. 이 글에서는 이 문제를 DB 트랜잭션 하나로 환원해 풀어내는 **트랜잭셔널 아웃박스(Transactional Outbox) 패턴**을 다룬다.

## 핵심 개념 1: 이중 쓰기 실패 시나리오

이중 쓰기가 왜 위험한지는 실패 순서를 나눠보면 분명해진다.

| 순서 | 실행 결과 | 결과적 문제 |
|---|---|---|
| DB 커밋 성공 → 메시지 발행 실패 | 주문은 존재, 이벤트는 없음 | 재고 차감 누락, 데이터 불일치 |
| DB 커밋 실패 → 메시지 발행(먼저) 성공 | 주문은 없음, 이벤트는 존재 | 존재하지 않는 주문에 대한 이벤트 처리 |
| 메시지 발행 후 DB 커밋 대기 중 프로세스 종료 | 상태 불확실 | 재시도 시 중복 발행 또는 완전 유실 |

애플리케이션 재시도로 일부는 완화할 수 있지만, "재시도 자체가 또 실패하면" 문제는 그대로 남는다. 근본 원인은 커밋 지점이 두 개라는 것이다. 아웃박스 패턴은 이 커밋 지점을 하나로 줄인다.

## 핵심 개념 2: 트랜잭셔널 아웃박스 패턴

아이디어는 단순하다. 메시지를 브로커로 직접 보내는 대신, **같은 데이터베이스 안에 `outbox`라는 테이블을 두고 비즈니스 데이터와 이벤트 행을 같은 트랜잭션 안에서 함께 INSERT한다.** RDBMS의 트랜잭션은 이미 원자성을 보장하므로, `orders` 테이블과 `outbox` 테이블에 대한 쓰기는 둘 다 성공하거나 둘 다 롤백된다 — 이중 쓰기 문제 자체가 발생할 수 없는 구조가 된다.

이벤트를 실제 브로커로 전달하는 일은 별도의 **릴레이(relay)** 프로세스가 맡는다. 이 릴레이가 outbox 테이블을 읽어 Kafka 등으로 발행하고, 발행이 끝난 행을 표시하거나 삭제한다. 애플리케이션 트랜잭션과 메시지 발행이 시간적으로 분리되므로, 발행이 지연되거나 재시도되더라도 "원본 데이터의 정합성"은 항상 보장된다.

<img src="/assets/images/posts/2026-08-16-outbox-pattern-dual-write-1.svg" alt="트랜잭셔널 아웃박스 패턴 구조도 - 하나의 트랜잭션에 묶인 orders/outbox 테이블과 CDC 또는 폴링 릴레이를 통한 Kafka 발행 흐름" style="width:100%;">

## 핵심 개념 3: 릴레이 방식 비교 — 폴링 발행자 vs CDC

outbox 테이블을 브로커로 실어 나르는 방식은 크게 두 갈래로 나뉜다.

| 구분 | 폴링 발행자(Polling Publisher) | CDC 기반 발행(Debezium 등) |
|---|---|---|
| 동작 원리 | 별도 스케줄러가 주기적으로 `SELECT ... WHERE published = false` 실행 | DB 트랜잭션 로그(binlog/WAL)를 실시간으로 읽어 변경분을 스트리밍 |
| 지연 시간 | 폴링 주기에 종속(수백 ms~수 초) | 로그 커밋 직후 거의 즉시 |
| DB 부하 | 반복 쿼리로 인한 부하 존재 | 로그 스트리밍이라 쿼리 부하 거의 없음 |
| 구현 난이도 | 낮음(애플리케이션 코드만으로 구현 가능) | Debezium, 커넥터 인프라 구축 필요 |
| 운영 도구 | 자체 스케줄러 | Kafka Connect + Debezium outbox event router |

소규모 서비스나 빠르게 도입하고 싶은 경우 폴링 발행자로 시작하고, 지연 시간과 DB 부하가 문제가 되기 시작하면 Debezium 같은 CDC 기반 릴레이로 전환하는 흐름이 흔하다. 이 릴레이 계층이 CDC를 채택할 뿐, 이 패턴 자체가 CDC와 동일한 것은 아니라는 점은 구분해서 이해할 필요가 있다 — 핵심은 어디까지나 "쓰기를 하나의 트랜잭션으로 묶는 것"이다.

## 예제: outbox 테이블 스키마와 저장 트랜잭션

```sql
CREATE TABLE outbox (
    id              UUID PRIMARY KEY,
    aggregate_type  VARCHAR(50)  NOT NULL,   -- 'Order'
    aggregate_id    VARCHAR(50)  NOT NULL,   -- 주문 ID
    event_type      VARCHAR(50)  NOT NULL,   -- 'OrderPlaced'
    payload         JSONB        NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT now(),
    published       BOOLEAN      NOT NULL DEFAULT false
);
```

Spring에서 주문 저장과 outbox 기록을 같은 트랜잭션으로 묶는 예:

```java
@Transactional
public void placeOrder(OrderRequest request) {
    Order order = orderRepository.save(Order.from(request));

    OutboxEvent event = new OutboxEvent(
        "Order", order.getId().toString(),
        "OrderPlaced", toJson(order)
    );
    outboxRepository.save(event); // 같은 트랜잭션 — 커밋/롤백 함께

} // 메서드 종료 시 하나의 트랜잭션으로 COMMIT
```

`orderRepository.save`와 `outboxRepository.save`는 같은 `@Transactional` 경계 안에 있으므로, DB 커밋이 실패하면 주문 저장과 이벤트 기록 모두 롤백된다. 릴레이는 이 트랜잭션과 무관하게 이후 시점에 `outbox` 테이블을 읽어 Kafka로 발행하면 된다.

## 실무 포인트

- **outbox 테이블은 계속 커진다**: 발행 완료된 행을 삭제하거나 별도 아카이브 테이블로 옮기는 정리 배치를 함께 설계해야 한다. `published` 컬럼과 `created_at` 인덱스로 미발행 행 조회 성능을 유지한다.
- **최소 한 번(at-least-once) 전달이 기본값**: 릴레이가 발행 후 완료 표시 직전에 죽으면 같은 이벤트가 중복 발행될 수 있다. 컨슈머는 이벤트 ID 기준으로 멱등하게 처리하도록 설계해야 한다.
- **이벤트 순서 보장이 필요하면 파티션 키를 aggregate ID로 고정한다**: Kafka 파티션 키를 `aggregate_id`로 두면 같은 엔티티에 대한 이벤트는 순서가 보장된다.
- **CDC로 전환할 때는 outbox 테이블을 CDC 전용으로 좁게 유지한다**: Debezium outbox event router는 표준화된 컬럼 구조(aggregate_type, aggregate_id, payload 등)를 기대하므로 스키마를 임의로 확장하지 않는 편이 연동이 단순하다.

## 3줄 요약

- DB 커밋과 메시지 발행을 별개로 호출하면 한쪽만 성공하는 이중 쓰기 문제가 생기며, 애플리케이션 재시도만으로는 근본 해결이 안 된다.
- 아웃박스 패턴은 이벤트를 브로커로 직접 보내지 않고 같은 트랜잭션 안에서 outbox 테이블에 기록해, DB 트랜잭션의 원자성을 그대로 물려받는다.
- 실제 발행은 폴링 발행자나 CDC(Debezium) 릴레이가 맡으며, 컨슈머 측 멱등 처리와 outbox 테이블 정리 배치를 함께 설계해야 운영에서 안정적이다.

## 참고 자료

- [Transactional Outbox — microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)
- [Debezium — Reliable Microservices Data Exchange With the Outbox Pattern](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/)
- [Debezium Outbox Event Router 공식 문서](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
