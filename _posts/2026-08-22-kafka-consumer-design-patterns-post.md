---
layout: single
title: "Kafka 컨슈머 설계 패턴 — 오프셋 커밋과 리밸런싱을 다루는 법"
date: 2026-08-22 12:25:00 +0530
categories: backend
tags: ["backend", "kafka", "consumer", "offset", "rebalancing", "spring-kafka"]
toc: true
toc_sticky: true
excerpt: "컨슈머가 죽었다 살아나거나 스케일아웃될 때 메시지를 중복 처리하거나 누락하지 않으려면, 오프셋 커밋 시점과 리밸런싱 동작을 정확히 이해해야 한다는 것을 정리한다."
---

Kafka 컨슈머를 처음 붙일 때는 대개 `enable.auto.commit=true` 기본값을 그대로 두고, 컨슈머 그룹만 지정하면 나머지는 카프카가 알아서 처리해준다고 생각하기 쉽다. 실제로 트래픽이 적고 파티션 수도 적을 때는 이 가정이 문제를 일으키지 않는다. 하지만 컨슈머 인스턴스를 늘려 스케일아웃하거나, 배포 중 컨슈머가 재시작되거나, 처리 중 예외로 컨슈머가 그룹에서 이탈하는 상황이 겹치면 오프셋 커밋 시점과 리밸런싱 동작이 정확히 맞물리지 않는 이상 메시지가 중복 처리되거나 통째로 유실되는 사고로 이어진다.

문제의 핵심은 "메시지를 처리했다"는 사실과 "오프셋을 커밋했다"는 사실이 별개의 이벤트라는 점이다. 두 이벤트 사이에는 항상 시간차가 있고, 그 사이에 컨슈머가 죽거나 파티션이 다른 인스턴스로 재할당되면 방금 처리한 메시지를 다시 읽게 되거나(중복), 반대로 처리하지 못한 메시지의 오프셋이 이미 커밋되어 다시는 읽지 못하게 되는(유실) 두 가지 실패 모드가 모두 가능해진다. 리밸런싱은 이 시간차 문제를 더 자주, 더 예측하기 어려운 시점에 발생시키는 요인이다.

이 글에서는 자동 커밋과 수동 커밋의 차이가 실제로 어떤 전달 보장(delivery guarantee)을 만드는지, 리밸런싱이 어떤 조건에서 왜 발생하는지, 그리고 리밸런싱 도중 처리 중이던 메시지가 왜 중복 처리 위험에 노출되는지를 정리한다.

## 핵심 개념 1: 자동 커밋 vs 수동 커밋

`enable.auto.commit=true`일 때 컨슈머는 `auto.commit.interval.ms`(기본 5초) 주기로, 그 시점까지 `poll()`로 가져온 레코드 중 가장 마지막 오프셋을 백그라운드에서 커밋한다. 문제는 이 커밋이 실제 처리 완료 여부와 무관하게 시간 기준으로만 일어난다는 점이다. 커밋 직후 애플리케이션이 아직 처리 중이던 메시지가 있는 상태에서 컨슈머가 크래시하면, 이미 커밋된 오프셋 때문에 그 메시지는 다시 읽히지 않고 그대로 유실된다. 즉 자동 커밋은 구현하기는 쉽지만 기본적으로 at-most-once에 가까운 성격을 갖기 쉽다.

수동 커밋(`enable.auto.commit=false`)은 메시지 처리가 끝난 뒤 애플리케이션이 직접 `commitSync()` 또는 `commitAsync()`를 호출해 오프셋을 올리는 방식이다. 처리를 마친 뒤에만 커밋하므로, 커밋 전에 컨슈머가 죽으면 같은 메시지를 재할당된 컨슈머가 다시 읽게 되어 최소한 한 번은 처리를 보장하는 at-least-once에 가까워진다. 다만 이 경우 "처리는 끝났는데 커밋 직전에 죽는" 경우가 여전히 남아 있어, 완전한 exactly-once를 자동으로 주지는 않는다. `commitSync()`는 브로커의 커밋 확인을 기다리므로 안전하지만 그만큼 처리량이 줄고, `commitAsync()`는 논블로킹이라 빠르지만 커밋 실패를 콜백에서 별도로 감지해야 한다.

## 핵심 개념 2: 리밸런싱이 발생하는 조건과 파티션 재할당 과정

컨슈머 그룹 리밸런싱은 그룹에 속한 컨슈머와 파티션의 대응 관계를 다시 계산하는 과정으로, 대표적으로 다음 조건에서 트리거된다. 첫째, 새로운 컨슈머가 그룹에 합류하거나 기존 컨슈머가 그룹을 명시적으로 떠날 때다. 둘째, 컨슈머가 `session.timeout.ms` 내에 하트비트를 보내지 못해 그룹 코디네이터가 죽었다고 판단할 때다. 셋째, 컨슈머가 `max.poll.interval.ms` 안에 다음 `poll()`을 호출하지 못해(처리 로직이 너무 오래 걸리는 경우) 코디네이터가 해당 컨슈머를 그룹에서 축출할 때다. 넷째, 구독 중인 토픽의 파티션 수가 늘어나는 등 토픽 메타데이터가 변경될 때다.

리밸런싱이 시작되면 그룹 코디네이터(브로커 중 하나)가 그룹의 리더 컨슈머에게 파티션 할당 전략(Range, RoundRobin, Sticky, Cooperative Sticky 등)에 따라 새 할당안을 계산하게 하고, 이를 그룹 전체에 전파한다. 전통적인 eager 리밸런싱 방식에서는 이 과정에서 모든 컨슈머가 자신이 갖고 있던 파티션 소유권을 일단 전부 반납(revoke)한 뒤 새 할당을 받는다. 즉 리밸런싱이 진행되는 동안에는 그룹 전체의 컨슈밍이 잠시 멈추는 stop-the-world 구간이 생긴다.

## 핵심 개념 3: 리밸런싱 중 처리 중이던 메시지의 중복 처리 위험

리밸런싱이 시작되면 각 컨슈머에는 `ConsumerRebalanceListener`의 `onPartitionsRevoked()` 콜백이 먼저 호출되어, 자신이 반납해야 할 파티션 목록을 통보받는다. 이 시점에 애플리케이션이 아직 커밋하지 않은 오프셋이 남아 있다면, 해당 파티션은 다른 컨슈머에게 재할당되고 그 컨슈머는 마지막 커밋 오프셋부터 다시 읽기 시작한다. 결국 리밸런싱 직전까지 이미 처리했지만 커밋되지 않은 메시지는 재할당된 컨슈머에 의해 한 번 더 처리된다.

이 위험은 처리 로직의 실행 시간이 커밋 주기보다 길거나, 배치 단위로 여러 메시지를 모아 처리한 뒤 한 번에 커밋하는 구조일 때 특히 커진다. 배치가 끝나기 전에 리밸런싱이 끼어들면 배치 안의 모든 메시지가 재처리 대상이 될 수 있기 때문이다. 그래서 `onPartitionsRevoked()` 콜백 안에서 그 시점까지 처리가 끝난 오프셋을 동기적으로 커밋해, 반납 직전까지의 진행 상황을 최대한 반영해두는 것이 일반적인 대응이다.

<img src="/assets/images/posts/2026-08-22-kafka-consumer-design-patterns-1.svg" alt="컨슈머 그룹과 파티션 재할당 구조도: 리밸런싱 전후로 파티션 소유권이 컨슈머 간에 어떻게 이동하는지 보여준다" style="width:100%;">

## 예제

아래는 Spring Kafka에서 수동 커밋(`AckMode.MANUAL`)과 리밸런스 리스너를 함께 설정하는 예시다.

```java
@Bean
public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory(
        ConsumerFactory<String, String> consumerFactory) {

    ConcurrentKafkaListenerContainerFactory<String, String> factory =
            new ConcurrentKafkaListenerContainerFactory<>();
    factory.setConsumerFactory(consumerFactory);

    // 처리 완료 후 리스너가 명시적으로 ack()를 호출할 때만 커밋
    factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL);

    // 리밸런싱 시점에 진행 상황을 커밋하기 위한 리스너 등록
    factory.getContainerProperties().setConsumerRebalanceListener(
        new ConsumerAwareRebalanceListener() {
            @Override
            public void onPartitionsRevokedBeforeCommit(
                    Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
                // 반납 직전까지 처리된 오프셋을 동기 커밋해 재처리 범위를 최소화
                consumer.commitSync();
            }

            @Override
            public void onPartitionsAssigned(
                    Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
                // 새로 할당받은 파티션에 대한 초기화가 필요하면 여기서 처리
            }
        }
    );

    return factory;
}

@KafkaListener(topics = "order-events", groupId = "order-service")
public void onMessage(ConsumerRecord<String, String> record, Acknowledgment ack) {
    try {
        processOrderEvent(record.value());
        ack.acknowledge(); // 처리 성공 후에만 오프셋 커밋
    } catch (Exception e) {
        // 커밋하지 않으면 다음 poll에서 같은 오프셋부터 다시 읽힘
        log.error("event processing failed, offset={}", record.offset(), e);
    }
}
```

`AckMode.MANUAL`은 리스너가 반환된 뒤 별도 배치 시점에 커밋을 위임하는 반면, `AckMode.MANUAL_IMMEDIATE`는 `ack.acknowledge()` 호출 즉시 커밋을 트리거한다. 커밋 빈도와 처리량 사이의 트레이드오프를 고려해 둘 중 하나를 선택하면 된다.

## 실무 포인트

- **멱등성 처리와 반드시 함께 설계한다**: 수동 커밋으로 at-least-once를 확보해도 리밸런싱이나 재시작 상황에서 동일 메시지가 두 번 이상 전달될 가능성은 완전히 없앨 수 없다. 메시지 키나 이벤트 ID 기준으로 중복 처리를 감지해 무시하거나, DB 쓰기를 `UPSERT`/유니크 제약으로 멱등하게 만드는 등 애플리케이션 레벨의 멱등성 보장을 함께 설계해야 카프카의 전달 보장 한계를 실질적으로 메울 수 있다.
- **Cooperative Sticky Assignor로 stop-the-world 구간을 줄인다**: 전통적인 eager 리밸런싱은 리밸런싱 시작 시 모든 파티션 소유권을 일괄 반납하지만, `CooperativeStickyAssignor`를 사용하면 실제로 재할당이 필요한 파티션만 점진적으로(incremental) 반납·재할당하고 나머지 컨슈머는 계속 처리를 이어갈 수 있다. 그 결과 그룹 전체가 멈추는 구간이 줄어들고, 기존에 할당받은 파티션을 그대로 유지하는 컨슈머 입장에서는 재처리 위험도 함께 줄어든다.
- **`max.poll.interval.ms`와 처리 시간을 맞춰본다**: 배치 처리나 외부 API 호출이 포함된 리스너는 처리 시간이 길어지기 쉽고, 이 값을 초과하면 컨슈머가 살아있는데도 그룹에서 축출되어 불필요한 리밸런싱이 발생한다. 처리 로직의 최대 소요 시간을 실측해 여유 있게 설정값을 잡는 편이 안전하다.

## 3줄 요약

- 자동 커밋은 시간 기준으로 오프셋을 올리기 때문에 처리 완료 여부와 어긋나 유실 위험이 있고, 수동 커밋은 처리 후 커밋하므로 at-least-once에 가깝지만 커밋 직전 장애에는 여전히 취약하다.
- 리밸런싱은 컨슈머 합류/이탈, 하트비트 타임아웃, 처리 지연으로 인한 축출, 파티션 수 변경 등으로 발생하며, 전통적인 eager 방식은 전체 파티션 소유권을 일괄 반납했다가 재할당한다.
- 리밸런싱 도중 커밋되지 않은 처리 결과는 재할당된 컨슈머에 의해 재처리될 수 있으므로, `onPartitionsRevoked` 시점의 동기 커밋과 애플리케이션 레벨 멱등성 처리, Cooperative Sticky Assignor를 함께 고려해야 한다.

## 참고 자료

- [Apache Kafka 공식 문서: Consumer Configs](https://kafka.apache.org/documentation/#consumerconfigs)
- [Apache Kafka 공식 문서: The Consumer](https://kafka.apache.org/documentation/#consumerapi)
- [KIP-429: Kafka Consumer Incremental Rebalance Protocol](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol)
- [Spring for Apache Kafka 공식 문서: Committing Offsets](https://docs.spring.io/spring-kafka/reference/kafka/receiving-messages/ack-mode.html)
