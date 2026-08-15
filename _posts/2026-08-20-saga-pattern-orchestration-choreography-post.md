---
layout: single
title: "사가(Saga) 패턴 — 마이크로서비스 분산 트랜잭션을 조율하는 두 가지 방법"
date: 2026-08-20 13:45:00 +0530
categories: system-design
tags: ["system-design", "saga", "microservices", "distributed-transaction", "orchestration"]
toc: true
toc_sticky: true
excerpt: "2PC 없이 마이크로서비스 간 분산 트랜잭션을 완성하는 Saga 패턴을, 오케스트레이션 방식과 코레오그래피 방식으로 나눠 비교한다."
---

모놀리스에서는 주문 생성, 재고 차감, 결제 처리를 하나의 DB 트랜잭션으로 묶어 커밋하거나 롤백하면 그만이었다. 하지만 이 세 기능이 서로 다른 마이크로서비스로 쪼개지고 각자 독립된 데이터베이스를 가지는 순간, 단일 트랜잭션이라는 전제 자체가 무너진다. 교과서적으로는 2PC(2단계 커밋, Two-Phase Commit)를 떠올릴 수 있지만, 2PC는 커밋 준비가 끝난 참여자가 코디네이터의 최종 지시를 기다리는 동안 관련 리소스에 락을 걸어 둔 채 블로킹된다는 근본적인 한계가 있다.

이 락은 서비스 하나가 응답하지 않거나 네트워크가 잠깐 끊기기만 해도 전체 트랜잭션을 장시간 붙잡아 둘 수 있고, 마이크로서비스처럼 서비스마다 배포 주기와 가용성 목표가 다른 환경에서는 이 결합이 곧 장애 전파 경로가 된다. 그래서 실무에서는 강한 일관성을 희생하는 대신 가용성과 서비스 간 느슨한 결합을 지키는 방향으로 타협하는 경우가 많고, 이 타협을 구조화한 대표적 패턴이 **Saga**다.

Saga는 하나의 비즈니스 트랜잭션을 여러 개의 로컬 트랜잭션으로 쪼개고, 각 로컬 트랜잭션이 실패했을 때 이전 단계들을 되돌리는 **보상 트랜잭션(compensating transaction)**을 미리 정의해 두는 방식으로 일관성 문제를 해결한다. 이 아이디어 자체는 1987년 헥터 가르시아몰리나(Hector Garcia-Molina)와 케네스 살렘(Kenneth Salem)의 논문에서 장기 실행 트랜잭션(long-lived transaction)을 다루기 위해 제안된 것으로, 마이크로서비스가 등장하며 분산 트랜잭션 문제에 다시 소환된 개념이다.

## 핵심 개념 1: 로컬 트랜잭션 연쇄와 보상 트랜잭션

Saga의 기본 골격은 단순하다. 전체 비즈니스 트랜잭션 T가 T1, T2, ..., Tn이라는 로컬 트랜잭션의 순차 실행으로 구성된다고 할 때, 각 Ti는 자신이 속한 서비스의 로컬 DB에서만 커밋되는 일반적인 ACID 트랜잭션이다. 문제는 Tk가 실패했을 때다. 이미 커밋된 T1부터 Tk-1까지는 물리적으로 롤백할 수 없으므로(다른 서비스, 다른 DB에서 이미 커밋됐기 때문), 대신 각 Ti에 대응하는 보상 트랜잭션 Ci를 실행해 그 효과를 의미적으로 상쇄한다.

즉 "커밋을 취소한다"가 아니라 "커밋된 결과를 지우는 새로운 트랜잭션을 실행한다"는 접근이다. 재고를 차감했다면 되돌리는 보상은 재고를 다시 늘리는 별도의 트랜잭션이고, 결제를 승인했다면 보상은 환불 트랜잭션이다. 이 때문에 Saga는 원자성(Atomicity)을 전통적 의미가 아니라 "결국에는 모든 단계가 성공하거나, 실패한 단계까지의 효과가 모두 보상된다"는 완화된 의미로 보장한다.

## 핵심 개념 2: 오케스트레이션 vs 코레오그래피

Saga를 구현하는 방식은 크게 두 가지로 나뉜다.

**오케스트레이션(Orchestration)** 방식은 중앙의 오케스트레이터(orchestrator)가 각 서비스에게 다음에 무엇을 할지 명령을 내리고 결과를 받아 다음 단계를 결정하는 구조다. 오케스트레이터는 Saga 전체의 상태 기계(state machine)를 소유하며, 어느 단계까지 진행했는지, 실패 시 어떤 보상을 어떤 순서로 호출해야 하는지를 스스로 알고 있다.

**코레오그래피(Choreography)** 방식은 중앙 조정자 없이, 각 서비스가 이벤트 브로커(메시지 큐 등)를 통해 이벤트를 발행(publish)하고 구독(subscribe)하며 다음 행동을 스스로 결정한다. 주문 서비스가 "주문 생성됨" 이벤트를 발행하면 결제 서비스가 이를 구독해 결제를 처리한 뒤 "결제 완료" 이벤트를 발행하고, 재고 서비스가 다시 이를 구독하는 식으로 트랜잭션이 서비스 사이를 이어 달리듯 전파된다.

## 핵심 개념 3: 두 방식 비교

<img src="/assets/images/posts/2026-08-20-saga-pattern-orchestration-choreography-1.svg" alt="Saga 패턴의 오케스트레이션 방식과 코레오그래피 방식 구조 비교도" style="width:100%;">

| 구분 | 오케스트레이션 | 코레오그래피 |
|---|---|---|
| 흐름 제어 | 중앙 오케스트레이터가 전체 순서를 명령 | 각 서비스가 이벤트를 보고 자율적으로 판단 |
| 서비스 간 결합도 | 오케스트레이터-서비스 간 결합은 있으나 서비스끼리는 분리 | 이벤트 스키마를 통한 암묵적 결합, 직접 호출은 없음 |
| 전체 흐름 파악 | 오케스트레이터 코드 하나만 보면 됨 | 여러 서비스의 이벤트 핸들러를 추적해야 함 |
| 신규 단계 추가 | 오케스트레이터만 수정 | 관련된 모든 서비스의 이벤트 구독 로직에 영향 가능 |
| 단일 장애점 우려 | 오케스트레이터 자체가 병목·장애점이 될 수 있음 | 특정 서비스에 집중된 장애점은 없으나 이벤트 유실 시 추적이 어려움 |
| 적합한 규모 | 단계 수가 많고 분기 로직이 복잡한 트랜잭션 | 단계 수가 적고 서비스 간 결합을 최소화하려는 경우 |

실무에서는 참여 서비스 수가 늘고 실패 시 분기 로직(부분 실패, 재시도, 타임아웃 처리)이 복잡해질수록 오케스트레이션 쪽이 전체 흐름을 추적하기 쉬워 선호되는 경향이 있고, 반대로 단계가 단순하고 서비스 간 결합을 최소화하는 것이 우선이라면 코레오그래피가 자연스럽다는 것이 일반적으로 언급되는 경험칙이다. 다만 이는 팀과 조직 구조, 관측 가능성(observability) 인프라 성숙도에 따라 달라질 수 있어 절대적인 기준은 아니다.

## 예제

아래는 "주문 생성 → 결제 승인 → 재고 차감" 순서로 진행되다가 재고 차감 단계에서 실패했을 때, 오케스트레이터가 보상 트랜잭션을 역순으로 호출하는 흐름을 의사코드로 표현한 것이다.

```python
# 오케스트레이션 방식 Saga 의사코드
def order_saga(order):
    completed_steps = []
    try:
        order_id = order_service.create_order(order)
        completed_steps.append(("order", order_id))

        payment_id = payment_service.charge(order.customer, order.amount)
        completed_steps.append(("payment", payment_id))

        inventory_service.reserve_stock(order.items)  # 여기서 재고 부족으로 실패했다고 가정
        completed_steps.append(("inventory", order.items))

    except SagaStepFailed as e:
        # 성공했던 단계를 역순으로 보상
        for step_name, step_data in reversed(completed_steps):
            if step_name == "payment":
                payment_service.refund(step_data)       # 보상: 결제 취소(환불)
            elif step_name == "order":
                order_service.cancel_order(step_data)   # 보상: 주문 취소 상태로 전환
        raise
```

```text
# 코레오그래피 방식 이벤트 흐름 (동일 시나리오)
1. OrderService  --publish--> "OrderCreated"
2. PaymentService --subscribe "OrderCreated"--> 결제 승인 --publish--> "PaymentCompleted"
3. InventoryService --subscribe "PaymentCompleted"--> 재고 확인 --재고 부족--> --publish--> "InventoryReservationFailed"
4. PaymentService --subscribe "InventoryReservationFailed"--> 환불 처리 --publish--> "PaymentRefunded"
5. OrderService   --subscribe "PaymentRefunded"--> 주문 상태를 '취소'로 전환
```

두 코드는 같은 결과(재고 부족 시 결제 환불, 주문 취소)를 만들지만, 오케스트레이션은 실패 처리 순서가 한 함수 안에 명시적으로 드러나는 반면 코레오그래피는 그 순서가 여러 서비스의 이벤트 구독 관계에 흩어져 있다는 차이가 코드 형태로도 그대로 드러난다.

## 실무 포인트

- **멱등성(idempotency)은 선택이 아니라 전제 조건이다**: 메시지 브로커는 대부분 최소 한 번 전달(at-least-once delivery)을 보장하므로 같은 이벤트나 명령이 중복 도착할 수 있다. 재고 차감, 결제 승인 같은 각 로컬 트랜잭션과 보상 트랜잭션 모두 같은 요청이 여러 번 들어와도 결과가 달라지지 않도록 설계해야 한다.
- **보상 트랜잭션은 항상 완벽하게 되돌릴 수 있는 것이 아니다**: 이미 발송된 이메일이나 실제로 출고된 배송 건처럼 물리적으로 되돌릴 수 없는 부작용도 있다. 이런 경우 보상은 "취소"가 아니라 "사후 조치"(환불 안내 발송, 반품 절차 개시)에 가까워지고, 이는 설계 단계에서부터 별도로 고려해야 한다.
- **Saga 진행 중에는 다른 트랜잭션이 중간 상태를 볼 수 있다**: 각 단계가 별도 커밋이므로 격리성(Isolation)이 전통적 ACID 트랜잭션만큼 보장되지 않는다. 조회 API에 "처리 중" 같은 상태를 노출하거나, 세마포릭 락(semantic lock) 같은 보완 기법을 함께 고려해야 하는 경우가 많다.
- **오케스트레이터 자체의 상태 영속화가 필요하다**: 오케스트레이션 방식에서 오케스트레이터 프로세스가 중간에 죽으면 진행 상태를 잃을 수 있으므로, 오케스트레이터도 자신의 상태 기계 진행 상황을 DB 등에 기록해 재시작 시 복구할 수 있어야 한다.

## 3줄 요약

- Saga는 2PC의 블로킹 문제를 피하기 위해 하나의 비즈니스 트랜잭션을 로컬 트랜잭션들로 쪼개고, 실패 시 보상 트랜잭션으로 앞선 단계의 효과를 상쇄하는 패턴이다.
- 오케스트레이션은 중앙 오케스트레이터가 전체 흐름을 명령·추적해 복잡한 분기 처리에 유리하고, 코레오그래피는 이벤트 기반으로 서비스가 자율적으로 반응해 결합도를 낮추지만 전체 흐름 파악이 어려워진다.
- 실무 적용 시 멱등성 보장과 보상 트랜잭션 설계(특히 되돌릴 수 없는 부작용 처리)가 패턴 자체보다 더 까다로운 문제인 경우가 많다.

## 참고 자료

- [Chris Richardson, microservices.io — Pattern: Saga](https://microservices.io/patterns/data/saga.html)
- [Martin Fowler's Bliki — 관련 분산 트랜잭션·마이크로서비스 아티클 모음](https://martinfowler.com/articles/patterns-of-distributed-systems/)
- [AWS Prescriptive Guidance — Saga pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-pattern.html)
