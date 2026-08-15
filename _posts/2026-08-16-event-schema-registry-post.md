---
layout: single
title: "이벤트 하나가 시스템 전체를 깨뜨리기 전에 — 스키마 레지스트리로 스키마 진화 관리하기"
date: 2026-08-16 12:45:00 +0530
categories: system-design
tags: ["schema-registry", "event-driven-architecture", "kafka", "avro", "schema-evolution"]
toc: true
toc_sticky: true
excerpt: "이벤트 기반 아키텍처에서 프로듀서가 필드 하나만 바꿔도 여러 컨슈머가 동시에 죽는 이유와, 스키마 레지스트리·호환성 모드로 이를 안전하게 관리하는 방법을 정리한다."
---

## 왜 지금 스키마 진화 문제인가

이벤트 기반 아키텍처는 서비스 간 결합을 낮추기 위해 도입한다. 프로듀서는 이벤트를 브로커에 던지고, 컨슈머는 각자의 속도로 읽어 처리한다. 문제는 이 구조가 "런타임 결합"은 없애지만 "스키마 결합"은 그대로 남긴다는 점이다. 프로듀서가 이벤트 필드 하나를 바꾸면, 그 이벤트를 구독하는 모든 컨슈머가 같은 순간에 영향을 받는다. 서비스는 독립적으로 배포되는데 계약(스키마)은 암묵적으로 공유되고 있는 셈이다.

이 문제는 서비스 수가 늘어날수록 커진다. 주문 이벤트 하나를 결제, 배송, 정산, 알림 서비스가 각각 구독하고 있다면, 주문 서비스 팀이 필드 이름을 바꾸거나 타입을 변경하는 순간 네 팀이 동시에 장애 대응에 들어가야 할 수 있다. REST API였다면 버전 경로(`/v2/orders`)로 분리하면 그만이지만, 이벤트 스트림은 과거 이벤트와 미래 이벤트가 같은 토픽에 계속 섞여 쌓인다는 점에서 더 까다롭다.

**스키마 레지스트리(Schema Registry)** 는 이 문제를 "합의 없는 변경"에서 "검증된 진화"로 바꾸는 인프라다. 이벤트 스키마를 중앙에 저장하고 버전을 관리하며, 새 버전을 등록할 때마다 이전 버전과의 호환성을 기계적으로 검사한다.

## 핵심 개념 1: 스키마 레지스트리가 하는 일

스키마 레지스트리는 Kafka 같은 메시지 브로커와 함께 쓰이는 별도 서버(또는 관리형 서비스)로, 크게 세 가지 역할을 한다.

- **스키마 저장소**: 토픽(정확히는 subject)별로 스키마 버전 이력을 저장한다.
- **호환성 검사기**: 새 스키마를 등록할 때 설정된 호환성 모드에 맞는지 자동으로 검증하고, 위반 시 등록 자체를 거부한다.
- **직렬화 프로토콜 제공**: 프로듀서는 메시지 앞에 스키마 id(4바이트)만 붙여 보내고, 컨슈머는 그 id로 레지스트리에서 정확한 스키마를 조회해 역직렬화한다. 메시지마다 전체 스키마를 실어 보낼 필요가 없다.

| 방식 | 스키마 검증 시점 | 버전 이력 관리 | 페이로드 크기 |
|---|---|---|---|
| JSON + 스키마 없음 | 없음(런타임에 파싱 실패로 발견) | 없음 | 필드명 반복으로 큼 |
| 코드 내 DTO만 공유 | 컴파일 타임(같은 레포일 때만) | Git 히스토리에 암묵적으로 존재 | 보통 |
| 스키마 레지스트리 + Avro/Protobuf | 등록 시점(배포 전 차단 가능) | subject-version으로 명시적 관리 | schema id만 포함, 작음 |

## 핵심 개념 2: 호환성 모드 — 무엇을, 누구 기준으로 검사하는가

호환성 모드는 "새 스키마가 기존 스키마와 비교해 무엇을 깨뜨리면 안 되는가"를 정의한다. 이 선택이 배포 순서 제약을 결정하기 때문에 팀 전체가 이해하고 있어야 한다.

| 모드 | 검사 기준 | 허용되는 대표 변경 | 배포 순서 제약 |
|---|---|---|---|
| BACKWARD | 새 스키마로 이전 데이터를 읽을 수 있는가 | 필드 삭제, 기본값 있는 필드 추가 | 컨슈머를 먼저 업데이트 |
| FORWARD | 이전 스키마로 새 데이터를 읽을 수 있는가 | 필드 추가, 기본값 있는 필드 삭제 | 프로듀서를 먼저 업데이트 |
| FULL | BACKWARD와 FORWARD 모두 충족 | 기본값 있는 필드의 추가·삭제만 | 순서 무관하지만 변경 폭이 가장 좁음 |
| NONE | 검사하지 않음 | 제한 없음(위험) | 팀 간 수동 조율 필요 |

실무에서 가장 널리 쓰이는 기본값은 **BACKWARD**다. 컨슈머가 새 스키마를 먼저 받아도 과거에 쌓인 이벤트를 계속 읽을 수 있어야 하는 상황(재처리, 리플레이)이 흔하기 때문이다.

## 핵심 개념 3: 안전한 변경과 위험한 변경 구분하기

호환성 모드를 지켜도 "안전한 변경"의 범위를 팀이 감으로 판단하면 사고가 난다. 자주 부딪히는 변경 유형은 다음과 같다.

- **안전**: 기본값이 있는 선택 필드 추가, 사용하지 않는 필드를 기본값과 함께 남기고 deprecated 표시만 하기
- **주의(모드에 따라 갈림)**: 필드 삭제(BACKWARD는 허용, FORWARD는 위반), 필드 이름 변경(대부분 포맷에서 삭제+추가로 취급됨)
- **위험(대부분 차단)**: 필드 타입 변경(string → int 등), 필수 필드를 기본값 없이 추가, enum 값 삭제

## 예제: Avro 스키마 진화와 Compatibility 설정

아래는 주문 이벤트 스키마에 배송 요청사항 필드를 추가하는 예시다. 기존 컨슈머가 계속 동작하도록 기본값을 반드시 지정한다.

```json
// order-event-v1.avsc
{
  "type": "record",
  "name": "OrderEvent",
  "fields": [
    { "name": "orderId", "type": "string" },
    { "name": "amount", "type": "double" },
    { "name": "status", "type": "string" }
  ]
}
```

```json
// order-event-v2.avsc — BACKWARD 호환 유지
{
  "type": "record",
  "name": "OrderEvent",
  "fields": [
    { "name": "orderId", "type": "string" },
    { "name": "amount", "type": "double" },
    { "name": "status", "type": "string" },
    { "name": "deliveryNote", "type": ["null", "string"], "default": null }
  ]
}
```

레지스트리 API로 subject의 호환성 모드를 확인·설정하는 예는 다음과 같다.

```bash
# 현재 subject의 호환성 모드 조회
curl -s http://schema-registry:8081/config/order-events

# BACKWARD로 명시 설정
curl -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"compatibility": "BACKWARD"}' \
  http://schema-registry:8081/config/order-events

# v2 스키마 등록 전, 호환성 사전 검증(등록하지 않고 검사만)
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @order-event-v2-request.json \
  http://schema-registry:8081/compatibility/subjects/order-events/versions/latest
```

이 compatibility 검사 API를 CI 파이프라인에 넣어두면, 스키마 변경 PR을 머지하기 전에 호환성 위반을 자동으로 잡아낼 수 있다.

<img src="/assets/images/posts/2026-08-16-event-schema-registry-1.svg" alt="스키마 레지스트리를 통한 스키마 진화 흐름 - 프로듀서의 새 스키마 등록, 호환성 검사, 컨슈머의 버전별 역직렬화 과정" style="width:100%;">

## 실무 포인트

- **CI에 호환성 검사를 반드시 넣는다**: 스키마 파일이 바뀌는 PR마다 레지스트리의 compatibility 검사 API를 호출해, 위반 시 머지를 막는다. 사람이 리뷰로 잡기엔 필드 하나하나의 하위 호환 여부를 놓치기 쉽다.
- **필드 삭제보다 deprecated 표시를 우선한다**: 당장 쓰지 않는 필드라도 소비 중인 컨슈머가 남아 있을 수 있으므로, 삭제 전에 사용률을 먼저 확인하는 절차를 둔다.
- **subject 네이밍 전략을 팀 차원에서 통일한다**: 토픽 하나에 여러 이벤트 타입이 섞이는 경우(TopicRecordNameStrategy)와 토픽당 한 스키마인 경우(TopicNameStrategy)는 버전 관리 단위가 달라지므로, 초기 설계 단계에서 정해야 나중에 마이그레이션 비용이 없다.
- **레지스트리 자체의 가용성도 설계에 포함한다**: 컨슈머가 스키마 id 조회에 실패하면 역직렬화 자체가 막힌다. 레지스트리 장애가 곧 전체 이벤트 파이프라인 장애로 번질 수 있으므로, 클라이언트 캐싱과 레지스트리 이중화를 함께 고려한다.

## 3줄 요약

- 이벤트 기반 아키텍처는 런타임 결합은 낮추지만 스키마 결합은 그대로 남기므로, 필드 변경 하나가 여러 컨슈머를 동시에 깨뜨릴 수 있다.
- 스키마 레지스트리는 스키마 버전을 중앙에서 관리하고, BACKWARD/FORWARD/FULL 같은 호환성 모드로 새 스키마 등록 시점에 위반을 기계적으로 차단한다.
- 실무에서는 기본값 있는 필드 추가를 원칙으로 삼고, CI 단계의 자동 호환성 검사와 레지스트리 자체의 가용성 설계까지 함께 챙겨야 안전하게 정착한다.

## 참고 자료

- [Confluent — Schema Registry Overview](https://docs.confluent.io/platform/current/schema-registry/index.html)
- [Confluent — Schema Evolution and Compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
- [Apache Avro Specification](https://avro.apache.org/docs/current/specification/)
