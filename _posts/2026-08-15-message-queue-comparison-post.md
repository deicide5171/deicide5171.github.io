---
layout: single
title: "메시지 큐 선택 가이드 — Kafka vs RabbitMQ vs SQS"
date: 2026-08-15 18:40:00 +0530
categories: system-design
tags: ["메시지큐", "Kafka", "RabbitMQ", "SQS"]
toc: true
toc_sticky: true
excerpt: "로그 기반, 브로커 기반, 관리형 큐라는 세 가지 설계 철학을 기준으로 Kafka, RabbitMQ, SQS의 처리량·순서보장·전달보장을 비교한다."
---

## 왜 지금 이 이야기인가

시스템이 커지면서 서비스 간 통신을 동기 API 호출에서 비동기 메시징으로 옮기는 팀이 늘고 있다. 그런데 막상 "메시지 큐를 도입하자"는 결정이 내려진 뒤에는 Kafka, RabbitMQ, SQS 중 무엇을 쓸지에서 의견이 갈리는 경우가 많다. 세 시스템은 이름만 같은 "메시지 큐"일 뿐 설계 철학이 근본적으로 다르기 때문에, 유행이나 사내 관성으로 고르면 나중에 재작업 비용이 크게 발생할 수 있다.

이 글에서는 세 시스템을 로그 기반, 브로커 기반, 관리형 큐라는 설계 철학의 차이로 나누어 비교하고, 실무에서 어떤 기준으로 선택해야 하는지 정리한다.

## 핵심 개념

### 설계 철학 차이

| 시스템 | 설계 철학 | 핵심 비유 |
|---|---|---|
| Kafka | 분산 커밋 로그. 메시지는 삭제되지 않고 보존 기간 동안 남아 여러 컨슈머가 각자 위치(오프셋)를 관리 | append-only 로그 파일 |
| RabbitMQ | 전통적인 브로커. 큐가 메시지를 보관하고 컨슈머에게 전달·확인(ack) 받으면 제거 | 우체국 사서함 |
| SQS | AWS가 완전관리형으로 제공하는 큐. 인프라 운영 부담이 거의 없음 | 완전관리형 사서함 |

### 처리량 / 순서보장 / 전달보장 비교

| 항목 | Kafka | RabbitMQ | SQS (Standard) |
|---|---|---|---|
| 처리량 | 매우 높음 (파티션 병렬 처리) | 중간 (라우팅 로직 복잡도에 따라 변동) | 높음 (관리형 확장, 세부 튜닝은 제한적) |
| 순서 보장 | 파티션 단위로 보장, 전체 토픽 단위는 보장 안 됨 | 큐 단위로 기본적으로 순서 보장 | Standard는 순서 보장 안 함, FIFO 큐를 별도로 사용해야 순서 보장 (처리량은 상대적으로 낮아짐) |
| 전달 보장 | at-least-once가 기본, 설정에 따라 exactly-once에 가깝게 구성 가능 | at-least-once 또는 at-most-once 선택 가능 | at-least-once가 기본 |
| 운영 부담 | 직접 운영 시 높음 (또는 관리형 서비스 이용) | 직접 운영 필요, 상대적으로 가벼움 | 거의 없음 (완전관리형) |

## 예제

```yaml
# Kafka 토픽 생성 예시 (개념적 설정, 실제 값은 클러스터 규모에 맞게 조정)
topic:
  name: order-events
  partitions: 12
  replication-factor: 3
  configs:
    retention.ms: 604800000   # 7일
    cleanup.policy: delete
```

```python
# boto3로 SQS FIFO 큐에 메시지 전송 (순서 보장이 필요한 경우)
import boto3

sqs = boto3.client("sqs", region_name="ap-northeast-2")

sqs.send_message(
    QueueUrl="https://sqs.ap-northeast-2.amazonaws.com/123456789012/order-events.fifo",
    MessageBody='{"order_id": "A1001", "status": "created"}',
    MessageGroupId="order-A1001",       # 같은 그룹 ID 내에서만 순서 보장
    MessageDeduplicationId="A1001-created",
)
```

## 실무 포인트와 주의사항

- 이벤트를 여러 컨슈머가 재생(replay)해야 하거나 스트림 처리(집계, 조인 등)가 필요하면 Kafka 쪽이 자연스럽다.
- 라우팅 로직(토픽 교환, 헤더 기반 라우팅 등)이 복잡하고 큐 개수가 유동적이라면 RabbitMQ의 유연한 익스체인지 모델이 유리하다.
- 인프라 운영 인력이 부족하고 AWS 생태계 안에서 단순 작업 큐가 필요하다면 SQS가 가장 적은 운영 비용으로 시작할 수 있다.
- "순서 보장"은 시스템 전체가 아니라 특정 단위(Kafka는 파티션, SQS는 메시지 그룹)에 한정된다는 점을 팀 전체가 정확히 이해하고 설계해야 한다.
- exactly-once는 어떤 시스템에서도 완전히 공짜로 얻어지지 않으며, 컨슈머 측 멱등성 처리가 사실상 필수라는 점을 전제로 설계해야 한다.

## 3줄 요약

- Kafka는 로그 기반으로 재생과 스트림 처리에 강하고, RabbitMQ는 브로커 기반으로 유연한 라우팅에 강하며, SQS는 관리형으로 운영 부담이 가장 적다.
- 순서 보장과 전달 보장은 시스템마다 적용 단위와 트레이드오프가 다르므로 표면적 스펙만 보고 선택하면 안 된다.
- 선택 기준은 유행이 아니라 재생 필요성, 라우팅 복잡도, 운영 인력 규모 세 가지로 판단하는 것이 안전하다.

## 참고 자료

- [Apache Kafka 공식 문서](https://kafka.apache.org/documentation/)
- [RabbitMQ 공식 문서](https://www.rabbitmq.com/docs)
- [Amazon SQS 개발자 가이드](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)
