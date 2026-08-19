---
layout: single
title: "Kafka는 정말 정확히 한 번 처리할까 — Exactly-once와 트랜잭션 아웃박스 실전"
date: 2026-08-26 13:25:00 +0530
categories: backend
tags: ["backend", "kafka", "exactly-once", "outbox-pattern", "transaction", "spring"]
toc: true
toc_sticky: true
excerpt: "Kafka의 exactly-once semantics가 실제로 보장하는 범위와, DB 트랜잭션과 메시지 발행을 하나로 묶는 트랜잭션 아웃박스 패턴을 Kafka 프로듀서 트랜잭션 API와 함께 구현한다."
---

Kafka가 "exactly-once semantics(EOS)"를 지원한다는 말은 자주 오해를 낳는다. 이 보장은 **Kafka 클러스터 내부에서** 프로듀서의 재시도로 인한 중복 쓰기를 막고, 컨슈머가 트랜잭션 단위로 커밋된 메시지만 읽게 해준다는 뜻이지, "DB에 주문을 저장하는 것"과 "Kafka에 주문 생성 이벤트를 발행하는 것"이라는 서로 다른 시스템 두 개에 걸친 원자성까지 보장해주지는 않는다. DB 커밋은 성공했는데 Kafka 발행이 실패하거나, 반대로 Kafka 발행은 성공했는데 DB 커밋이 롤백되는 상황은 Kafka의 EOS 기능만으로는 막을 수 없다.

이 "DB 쓰기 + 메시지 발행"을 하나의 논리적 단위로 묶는 문제를 실무에서는 **트랜잭션 아웃박스 패턴(transactional outbox)**으로 푼다. 이 글에서는 Kafka의 EOS가 실제로 무엇을 보장하는지 먼저 정리하고, 아웃박스 패턴과 어떻게 결합해 "DB와 메시지 큐에 걸친 이중 쓰기 문제"를 해소하는지 구현 예제와 함께 살펴본다.

## 핵심 개념 1: Kafka EOS가 보장하는 세 가지와 보장하지 않는 것

| 항목 | Kafka EOS가 보장하는 것 |
|---|---|
| 프로듀서 중복 쓰기 | 멱등한 프로듀서(idempotent producer)가 네트워크 재시도로 인한 중복 메시지를 서버 측에서 제거 |
| 다중 파티션 원자적 쓰기 | 트랜잭션 API로 여러 파티션에 쓴 메시지를 모두 커밋하거나 모두 취소 |
| 컨슈머 읽기 격리 | `isolation.level=read_committed`로 설정하면 커밋되지 않은(취소된) 트랜잭션의 메시지를 컨슈머가 건너뜀 |
| DB와 Kafka 간 원자성 | **보장하지 않음** — 별도의 패턴(아웃박스)이 필요 |

즉 Kafka의 EOS는 "Kafka 안에서" 벌어지는 문제(네트워크 재시도로 인한 중복, 여러 파티션에 걸친 쓰기의 원자성)를 해결하는 것이지, 애플리케이션이 DB와 Kafka라는 서로 다른 저장소 두 개에 쓰는 것까지 하나의 트랜잭션으로 묶어주지 않는다. 이 둘을 하나로 묶으려면 DB 트랜잭션 안에서 실제 이벤트를 발행하는 대신, "발행하려는 이벤트를 DB에 함께 저장"하는 우회가 필요하다.

## 핵심 개념 2: 아웃박스 패턴 — DB 트랜잭션으로 발행 의도를 확정한다

트랜잭션 아웃박스 패턴은 비즈니스 데이터를 저장하는 트랜잭션 안에 "이 이벤트를 나중에 Kafka로 보내야 한다"는 레코드를 같은 트랜잭션으로 함께 저장한다. DB 트랜잭션은 원자적이므로 주문 저장과 아웃박스 레코드 저장은 항상 함께 성공하거나 함께 실패한다. 이후 별도의 릴레이 프로세스(또는 CDC, Debezium 등)가 아웃박스 테이블을 폴링하거나 변경 로그를 읽어 실제로 Kafka에 발행하고, 발행이 확인되면 아웃박스 레코드를 처리 완료로 표시한다.

<img src="/assets/images/posts/2026-08-26-kafka-exactly-once-transactional-outbox-1.svg" alt="트랜잭션 아웃박스 패턴 구조도 — DB 트랜잭션 내 주문 저장과 아웃박스 레코드 저장, 릴레이 프로세스가 Kafka로 발행하는 흐름" style="width:100%;">

## 예제: Spring에서 아웃박스 저장 + Kafka 트랜잭션 릴레이

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final OutboxRepository outboxRepository;

    @Transactional
    public void createOrder(OrderRequest request) {
        Order order = orderRepository.save(Order.from(request));

        // 같은 DB 트랜잭션 안에서 아웃박스 레코드 저장 — 주문 저장과 원자적으로 묶인다
        OutboxEvent event = OutboxEvent.builder()
                .aggregateId(order.getId())
                .eventType("OrderCreated")
                .payload(toJson(order))
                .status(OutboxStatus.PENDING)
                .build();
        outboxRepository.save(event);
        // 이 시점에는 아직 Kafka로 실제 발행하지 않는다
    }
}
```

```java
@Component
@RequiredArgsConstructor
public class OutboxRelay {

    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    @Scheduled(fixedDelay = 500)
    @Transactional
    public void relay() {
        List<OutboxEvent> pending = outboxRepository.findTop100ByStatusOrderByCreatedAtAsc(OutboxStatus.PENDING);

        // Kafka 프로듀서 트랜잭션으로 여러 이벤트를 원자적으로 발행
        kafkaTemplate.executeInTransaction(operations -> {
            for (OutboxEvent event : pending) {
                operations.send("order-events", event.getAggregateId().toString(), event.getPayload());
            }
            return true;
        });

        pending.forEach(e -> e.markPublished());
        outboxRepository.saveAll(pending);
    }
}
```

릴레이 프로세스가 죽거나 재시작돼도 아웃박스 테이블에 `PENDING` 상태로 남은 레코드는 그대로 유지되므로, 다음 실행에서 누락 없이 재발행을 시도한다. 이 방식은 "적어도 한 번(at-least-once)" 발행을 보장하며, 완전한 정확히 한 번을 원한다면 컨슈머 쪽에서 이벤트 ID 기준 멱등 처리를 추가로 갖춰야 한다.

## 실무 포인트

- **폴링 대신 CDC를 고려한다**: 위 예제의 스케줄러 폴링은 구현이 간단하지만 폴링 주기만큼 지연이 생기고 DB 부하가 늘어난다. Debezium 같은 CDC 도구로 아웃박스 테이블의 WAL 변경을 직접 스트리밍하면 지연을 훨씬 줄일 수 있다.
- **"Kafka EOS"라는 이름에 안심하지 않는다**: `enable.idempotence=true`와 트랜잭션 API를 켰다고 해서 DB-Kafka 이중 쓰기 문제가 사라지는 게 아니다. 아웃박스 패턴 없이 서비스 로직 안에서 `save()`와 `kafkaTemplate.send()`를 나란히 호출하는 코드는 여전히 두 시스템 사이의 원자성이 깨질 수 있다.
- **컨슈머 쪽 멱등성도 함께 설계한다**: 아웃박스+CDC 조합도 드물게 같은 이벤트를 중복 발행할 수 있다(릴레이 재시작 타이밍 등). 컨슈머가 이벤트 ID를 기준으로 이미 처리한 이벤트인지 확인하는 멱등 처리를 갖춰야 진짜 "정확히 한 번 처리"에 가까워진다.

## 3줄 요약

- Kafka의 exactly-once semantics는 Kafka 클러스터 내부의 중복 쓰기·다중 파티션 원자성·읽기 격리를 보장할 뿐, DB와 Kafka 사이의 이중 쓰기 문제는 해결하지 않는다.
- 트랜잭션 아웃박스 패턴은 DB 트랜잭션 안에 이벤트 발행 의도를 함께 저장해 비즈니스 데이터와 이벤트가 항상 함께 성공·실패하게 만든다.
- 아웃박스는 적어도 한 번 발행을 보장할 뿐이므로, 완전한 정확히 한 번 처리를 원한다면 컨슈머 쪽 멱등 처리를 함께 갖춰야 한다.

## 참고 자료

- [Confluent 공식 문서: Exactly-once Semantics](https://docs.confluent.io/platform/current/clients/producer.html#exactly-once-semantics)
- [Debezium 공식 문서: Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Spring for Apache Kafka 공식 문서: Transactions](https://docs.spring.io/spring-kafka/reference/kafka/transactions.html)
