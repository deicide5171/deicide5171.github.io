---
layout: single
title: "Saga 패턴 — Choreography vs Orchestration, 분산 트랜잭션을 나눠서 처리하기"
date: 2026-09-21 12:45:00 +0530
categories: system-design
tags: ["saga패턴", "분산트랜잭션", "마이크로서비스", "이벤트기반아키텍처", "보상트랜잭션"]
toc: true
toc_sticky: true
excerpt: "여러 마이크로서비스에 걸친 하나의 비즈니스 트랜잭션을 안전하게 처리하는 Saga 패턴을, Choreography와 Orchestration 두 구현 방식으로 비교하고 실전 선택 기준을 정리했다."
---

## 왜 이 문제가 마이크로서비스에서 반드시 나타나는가

주문 서비스, 재고 서비스, 결제 서비스가 각각 독립된 DB를 가진 마이크로서비스 구조를 생각해보자. "주문 생성 → 재고 차감 → 결제 승인"이라는 하나의 비즈니스 흐름은 모놀리식 애플리케이션이었다면 단일 DB 트랜잭션으로 묶어 처리했을 일이다. 하지만 서비스마다 DB가 분리되어 있으면, 이 세 단계를 하나의 ACID 트랜잭션으로 묶을 방법이 없다. 재고 차감까지는 성공했는데 결제가 실패하면, 이미 차감된 재고를 누군가는 되돌려놔야 한다.

**Saga 패턴**은 이 문제를 "하나의 큰 트랜잭션"이 아니라 "각 서비스의 로컬 트랜잭션을 순서대로 실행하고, 중간에 실패하면 이미 실행된 단계들을 역순으로 되돌리는 보상 트랜잭션(compensating transaction)을 실행하는 것"으로 해결한다. 결제가 실패하면 "재고 차감 취소"라는 보상 트랜잭션이 뒤이어 실행되는 식이다.

## 잘못된 접근: 분산 락이나 2PC로 억지로 묶기

Saga를 모르는 상태에서 이 문제를 처음 만나면, 분산 락으로 여러 서비스의 상태 변경을 순차적으로 잠그거나, 2단계 커밋(2PC)으로 모든 서비스를 하나의 트랜잭션 코디네이터 아래 묶으려는 시도를 한다. 두 방법 모두 서비스 간 강한 결합을 만들고, 코디네이터나 락이 걸린 동안 다른 요청이 대기해야 해서 처리량이 크게 떨어진다. 서비스 하나가 응답하지 않으면 전체 트랜잭션이 멈춘다는 것도 큰 약점이다. 마이크로서비스를 도입한 이유(독립적인 배포·확장)가 이 지점에서 무색해진다.

## Choreography 방식: 중앙 지휘자 없이 이벤트로 연쇄

```
주문 서비스: 주문 생성 → "OrderCreated" 이벤트 발행
재고 서비스: "OrderCreated" 수신 → 재고 차감 → "StockReserved" 이벤트 발행
결제 서비스: "StockReserved" 수신 → 결제 시도 → 실패 시 "PaymentFailed" 이벤트 발행
재고 서비스: "PaymentFailed" 수신 → 재고 차감 취소(보상 트랜잭션)
```

각 서비스가 이전 서비스의 이벤트를 구독하고, 자신의 작업이 끝나면 다음 이벤트를 발행하는 방식이다. 중앙에서 흐름을 지시하는 주체가 없고, 서비스들이 이벤트를 통해 느슨하게 연결된다.

## Orchestration 방식: 중앙 오케스트레이터가 순서를 지휘

```java
public class OrderSagaOrchestrator {
    public void execute(OrderRequest request) {
        try {
            inventoryClient.reserveStock(request);
            paymentClient.charge(request);
            orderClient.confirmOrder(request);
        } catch (PaymentFailedException e) {
            inventoryClient.releaseStock(request);  // 보상 트랜잭션
            orderClient.cancelOrder(request);
        }
    }
}
```

별도의 오케스트레이터 컴포넌트가 각 서비스를 순서대로 호출하고, 실패 시 어떤 보상 트랜잭션을 실행할지도 오케스트레이터가 직접 관리한다.

## 두 방식 비교

| 항목 | Choreography | Orchestration |
|---|---|---|
| 흐름 제어 | 각 서비스가 이벤트로 분산 판단 | 중앙 오케스트레이터가 명시적 지휘 |
| 결합도 | 서비스 간 느슨함 | 오케스트레이터에 로직 집중 |
| 흐름 파악 | 이벤트 발행/구독 관계를 추적해야 함 | 오케스트레이터 코드만 보면 전체 흐름 파악 가능 |
| 신규 단계 추가 | 새 서비스가 이벤트만 구독하면 됨 | 오케스트레이터 코드 수정 필요 |
| 단일 장애점 | 없음 | 오케스트레이터가 죽으면 흐름 전체가 막힘(이중화 필요) |

단계가 2~3개로 단순하면 Choreography가 가볍고 서비스 간 결합도 낮게 유지된다. 하지만 단계가 5개, 10개로 늘어나면 "지금 이 주문이 어느 단계에 있는지" 파악하려고 여러 서비스의 로그를 오가며 이벤트 발행/구독 관계를 추적해야 해서 디버깅이 급격히 어려워진다. 이 시점부터는 전체 흐름을 한 곳에서 관리하는 Orchestration이 유리해진다.

## 실무 포인트

- **보상 트랜잭션은 반드시 멱등하게 설계하라.** 네트워크 재시도로 같은 보상 트랜잭션이 두 번 실행돼도 결과가 같아야 한다. "재고를 10개 늘려라"가 아니라 "이 주문의 예약을 취소하라"처럼 상태 기반으로 설계한다.
- **Choreography는 이벤트 발행 실패도 고려해야 한다.** 이벤트 발행 자체가 실패하면 사가 전체가 멈춘 채 아무도 모르는 상태가 될 수 있으므로, 트랜잭셔널 아웃박스 패턴과 함께 쓰는 것이 안전하다.
- **Saga의 진행 상태를 별도로 영속화하라.** Orchestration 방식이라면 오케스트레이터가 재시작되어도 "어느 단계까지 진행됐는지" 복구할 수 있도록 사가 상태를 DB에 기록해야 한다.
- **모든 단계가 보상 가능한 것은 아니다.** 이메일 발송처럼 되돌릴 수 없는 작업은 Saga의 마지막 단계로 배치하거나, 실패 시 별도 알림·수동 개입 절차를 마련해야 한다.

## 마무리 요약

- 서비스별 DB가 분리된 마이크로서비스에서는 2PC 대신 로컬 트랜잭션과 보상 트랜잭션으로 흐름을 관리하는 Saga 패턴이 표준적인 해법이다.
- Choreography는 단순한 흐름에 적합하고, Orchestration은 단계가 많고 전체 흐름 파악이 중요할 때 유리하다.
- 보상 트랜잭션의 멱등성과 사가 진행 상태의 영속화를 반드시 함께 설계해야 실제 장애 상황에서 안전하게 동작한다.

## 참고 자료

- [microservices.io - Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [AWS - Saga pattern documentation](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga.html)
