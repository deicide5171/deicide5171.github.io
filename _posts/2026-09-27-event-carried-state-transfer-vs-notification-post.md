---
layout: single
title: "이벤트 설계의 갈림길 — Event Notification과 Event-Carried State Transfer"
date: 2026-09-27 13:45:00 +0530
categories: system-design
tags: ["이벤트기반아키텍처", "EventCarriedStateTransfer", "EventNotification", "이벤트설계", "MSA"]
toc: true
toc_sticky: true
excerpt: "이벤트에 ID 하나만 담을지, 관련 데이터 전체를 담을지는 사소한 구현 디테일이 아니라 컨슈머와 프로듀서의 결합도를 결정하는 아키텍처 선택이다. Thin 이벤트와 Fat 이벤트의 트레이드오프를 정리했다."
---

## 왜 이벤트에 뭘 담을지가 사소한 문제가 아닌가

이벤트 기반 아키텍처를 도입할 때 놓치기 쉬운 결정이 하나 있다. "주문이 완료됐다"는 이벤트를 발행할 때, 이벤트 페이로드에 주문 ID만 넣을 것인가, 아니면 주문 상품 목록·금액·배송지까지 전부 넣을 것인가다. 이 선택은 단순한 스키마 디테일이 아니라, 컨슈머가 그 데이터를 다시 얻기 위해 프로듀서에게 동기 호출을 해야 하는지 여부를 결정하고, 결과적으로 이벤트 기반 아키텍처가 애초에 추구했던 느슨한 결합이 실제로 달성되는지를 좌우한다. 이 두 접근을 각각 **Event Notification**(얇은 이벤트, thin event)과 **Event-Carried State Transfer**(두꺼운 이벤트, fat event)라고 부른다.

## 핵심 개념 1 — Event Notification: "무슨 일이 있었다"만 알린다

Event Notification은 이벤트에 최소한의 정보(무슨 일이 일어났는지, 어떤 엔티티의 ID인지)만 담는다. 컨슈머는 이 이벤트를 받으면 "아, 주문 12345가 완료됐구나"까지만 알고, 상세 정보가 필요하면 프로듀서(주문 서비스)의 API를 다시 호출해서 가져와야 한다. 장점은 이벤트가 작고 단순해서 스키마 진화 부담이 적다는 것이다. 단점은 컨슈머가 결국 프로듀서에 대한 동기 의존성을 갖게 된다는 점인데, 이벤트를 비동기로 받았지만 처리를 위해 동기 호출이 필요하다면 프로듀서가 다운되면 컨슈머도 이벤트를 처리하지 못하는, 이벤트 기반 아키텍처의 핵심 이점(느슨한 결합)이 무색해지는 상황이 생긴다.

## 핵심 개념 2 — Event-Carried State Transfer: 필요한 데이터를 통째로 옮긴다

Event-Carried State Transfer는 반대로 컨슈머가 필요로 할 만한 데이터를 이벤트 자체에 전부 실어 보낸다. 컨슈머는 이벤트만으로 필요한 작업을 완결할 수 있으므로 프로듀서에 대한 런타임 의존성이 완전히 사라진다. 프로듀서가 다운돼도 이미 발행된 이벤트들은 컨슈머가 문제없이 처리할 수 있다. 대신 대가가 있다. 이벤트가 커지고, 프로듀서의 내부 데이터 모델이 사실상 이벤트 스키마를 통해 외부에 노출되므로 스키마 진화 부담이 커지며, 여러 컨슈머가 각자 필요한 필드가 다르면 결국 모든 컨슈머의 요구를 만족하는 거대한 이벤트가 만들어지는 경향이 생긴다. 또한 데이터 중복(컨슈머가 로컬 복제본을 유지하는 것과 유사한 구조)이 발생하므로, 원본과 복제본 사이의 최종 일관성(eventual consistency)을 감수해야 한다.

| 항목 | Event Notification | Event-Carried State Transfer |
|---|---|---|
| 페이로드 크기 | 작음(ID 위주) | 큼(전체 상태) |
| 런타임 결합도 | 프로듀서 API에 동기 의존 | 완전히 독립적 |
| 스키마 진화 부담 | 낮음 | 높음(내부 모델이 곧 외부 계약) |
| 데이터 중복 | 없음 | 있음(최종 일관성 필요) |
| 적합한 경우 | 프로듀서 가용성이 높고 조회 빈도가 낮음 | 컨슈머가 프로듀서와 독립적으로 동작해야 함 |

## 코드 예제 — 같은 이벤트를 두 방식으로 설계하기

```json
// Event Notification: ID만 담아 얇게 유지
{
  "eventType": "OrderCompleted",
  "orderId": "12345",
  "occurredAt": "2026-09-27T12:00:00Z"
}

// Event-Carried State Transfer: 컨슈머가 필요로 할 데이터를 통째로 포함
{
  "eventType": "OrderCompleted",
  "orderId": "12345",
  "occurredAt": "2026-09-27T12:00:00Z",
  "customerId": "cust-9981",
  "items": [
    {"sku": "SKU-001", "quantity": 2, "price": 15000}
  ],
  "totalAmount": 30000,
  "shippingAddress": { "city": "서울", "zipcode": "04524" }
}
```

두 번째 방식이라면 배송 서비스가 이 이벤트 하나만으로 배송 준비를 시작할 수 있고, 주문 서비스가 잠시 다운되어도 영향을 받지 않는다.

## 실무 포인트

- **컨슈머 수와 조회 패턴을 먼저 파악하라.** 컨슈머가 하나뿐이고 조회 빈도가 낮다면 Event Notification으로 충분하지만, 컨슈머가 여러 개이고 각자 독립적인 가용성을 필요로 한다면 Event-Carried State Transfer의 복잡도가 정당화된다.
- **혼합 전략도 실무에서 흔하다.** 자주 필요한 핵심 필드는 이벤트에 포함하고, 드물게 필요한 상세 정보는 별도 조회 API로 남겨두는 절충안이 두 극단의 장점을 취할 수 있다.
- **Fat 이벤트를 선택했다면 스키마 계약을 명시적으로 관리하라.** 내부 도메인 모델을 그대로 이벤트로 노출하면 내부 리팩터링이 곧 컨슈머에게 영향을 주는 결합이 생기므로, 이벤트 전용 DTO를 별도로 두고 내부 모델과 분리하는 것이 안전하다.

## 마무리 요약

- 이벤트에 ID만 담을지 전체 상태를 담을지는 컨슈머-프로듀서 간 런타임 결합도를 결정하는 아키텍처 선택이다.
- Event Notification은 가볍지만 컨슈머가 프로듀서에 동기 의존하게 되고, Event-Carried State Transfer는 독립성을 얻는 대신 스키마 진화 부담과 데이터 중복을 감수해야 한다.
- 컨슈머 수와 가용성 요구사항을 기준으로 선택하되, 핵심 필드만 포함하는 혼합 전략도 현실적인 절충안이다.

## 참고 자료

- [Martin Fowler — What do you mean by "Event-Driven"?](https://martinfowler.com/articles/201701-event-driven.html)
- [Confluent — Event-Carried State Transfer 설명](https://www.confluent.io/blog/data-dichotomy-rethinking-the-way-we-treat-data-and-services/)
