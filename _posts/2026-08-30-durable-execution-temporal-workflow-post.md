---
layout: single
title: "서버가 재시작해도 워크플로는 이어진다 — Durable Execution과 Temporal 실전"
date: 2026-08-30 12:45:00 +0530
categories: system-design
tags: ["system-design", "durable-execution", "temporal", "workflow-orchestration", "saga", "reliability"]
toc: true
toc_sticky: true
excerpt: "며칠씩 걸리는 승인·결제·배치 워크플로를 코드로 그대로 짜되, 프로세스가 죽어도 마지막 지점부터 이어지게 만드는 Durable Execution의 원리를 Temporal을 중심으로 정리한다."
---

주문 생성 → 결제 승인 대기(최대 3일) → 재고 예약 → 배송 요청 → 실패 시 전체 보상, 같은 워크플로를 짜본 적이 있다면 알 것이다. 이걸 순수 코드로 짜면 상태 저장, 재시작 복구, 타임아웃, 재시도가 전부 수작업이 된다. 크론잡과 상태 테이블로 흉내 내면 "지금 이 주문이 어느 단계인지"를 조회 쿼리로 역추적해야 하고, 배포 중 서버가 재시작하면 그 사이 진행 중이던 워크플로의 상태를 어떻게 복구할지 매번 새로 고민하게 된다.

**Durable Execution**은 이 문제를 다른 각도에서 푼다. 워크플로 로직을 그냥 평범한 함수(순차 코드, `if`, `for`, `try/catch`)로 작성하게 하고, 그 실행 과정 전체를 이벤트 로그로 영속화해서 프로세스가 어느 지점에서 죽어도 정확히 그 지점부터 이어서 재개할 수 있게 만드는 실행 모델이다. Temporal, AWS Step Functions, Cadence 같은 도구가 이 모델을 구현한다. 이 글에서는 Temporal을 기준으로 동작 원리와 기존 오케스트레이션 방식과의 차이를 정리한다.

## 핵심 개념 1: 이벤트 소싱으로 만드는 재개 가능성

Durable Execution 엔진의 핵심 트릭은 워크플로 코드 자체가 아니라 **워크플로가 만든 이벤트 히스토리**를 영속화한다는 것이다. 워크플로 함수 안에서 "액티비티(외부 부작용이 있는 작업, 예: 결제 API 호출)"를 실행하면, 그 호출의 시작·완료·결과가 이벤트로 서버(Temporal의 경우 Temporal Server)에 기록된다. 워커 프로세스가 죽었다가 다시 뜨면, 워크플로 함수를 처음부터 다시 실행하되 이미 기록된 이벤트가 있는 지점까지는 실제로 액티비티를 재실행하지 않고 **저장된 결과를 그대로 반환(리플레이)**한다. 히스토리에 없는 지점, 즉 죽기 직전 실행 중이던 부분부터만 진짜로 재실행된다.

이 리플레이 모델 덕분에 개발자는 재시도·체크포인트 로직을 직접 짤 필요가 없다. 대신 워크플로 함수는 **결정적(deterministic)**이어야 한다는 제약이 붙는다 — 같은 히스토리를 주면 항상 같은 순서로 같은 액티비티를 호출해야 리플레이가 성립하기 때문이다. `Date.now()`, `Math.random()`, 스레드 스케줄링에 의존한 분기를 워크플로 코드에 직접 쓰면 안 되고, 대신 Temporal이 제공하는 결정적 API(예: `workflow.now()`)를 써야 한다.

## 핵심 개념 2: 워크플로와 액티비티의 역할 분리

Temporal은 "무엇을, 어떤 순서로 할지"를 정하는 **워크플로**와, 실제 부작용을 일으키는 **액티비티**를 명확히 분리한다. 워크플로는 결정적이어야 하므로 네트워크 호출·DB 쓰기 같은 비결정적 작업은 전부 액티비티로 뽑아내고, 워크플로는 그 액티비티를 어떤 순서·조건으로 호출할지만 오케스트레이션한다. 액티비티는 각각 독립적으로 재시도 정책(최대 횟수, 백오프, 타임아웃)을 가질 수 있고, 실패하면 워크플로 코드 안에서 `try/catch`로 그냥 잡아서 보상 로직을 실행하면 된다 — 별도의 사가 프레임워크 없이도 사가 패턴이 자연스럽게 코드로 표현된다.

| 구분 | 전통적 오케스트레이션(상태 테이블+크론) | Durable Execution(Temporal) |
|---|---|---|
| 워크플로 표현 | 상태 컬럼 + 각 단계별 핸들러 | 평범한 순차 코드 |
| 진행 상태 조회 | 커스텀 상태 테이블 쿼리 | 워크플로 히스토리 API |
| 장기 대기(며칠) | 별도 스케줄러·크론 필요 | `workflow.sleep()`로 코드에 표현 |
| 재시도·타임아웃 | 매 단계 수작업 구현 | 액티비티 옵션으로 선언 |
| 재시작 복구 | 상태 컬럼 기반 수동 복구 로직 | 이벤트 히스토리 리플레이로 자동 |

## 핵심 개념 3: 시그널·쿼리로 실행 중인 워크플로와 상호작용

며칠씩 대기하는 워크플로는 중간에 외부 이벤트(사용자가 승인 버튼을 누름, 결제 게이트웨이 웹훅 도착)를 받아야 한다. Temporal은 이를 **시그널(signal)**로 처리한다 — 실행 중인 워크플로 인스턴스에 비동기 메시지를 보내면, 워크플로 코드 안의 `workflow.await()` 같은 대기 지점이 깨어나 처리를 계속한다. 반대로 워크플로의 현재 상태를 외부에서 들여다보고 싶으면 **쿼리(query)**를 쓴다 — 워크플로 상태를 변경하지 않고 읽기만 하는 요청으로, 별도의 상태 조회 API를 만들 필요가 없다.

<img src="/assets/images/posts/2026-08-30-durable-execution-temporal-workflow-1.svg" alt="워커가 죽었다가 재시작할 때 이벤트 히스토리를 리플레이해 이미 완료된 액티비티는 재실행하지 않고 중단 지점부터 이어가는 Durable Execution 흐름도" style="width:100%;">

## 예제: TypeScript Temporal 워크플로

```typescript
// order-workflow.ts — 주문 처리 워크플로 (결정적 코드)
import { proxyActivities, sleep, condition, defineSignal, setHandler } from '@temporalio/workflow';
import type * as activities from './activities';

const { chargePayment, reserveInventory, shipOrder, refundPayment } =
  proxyActivities<typeof activities>({
    startToCloseTimeout: '1 minute',
    retry: { maximumAttempts: 5, backoffCoefficient: 2 },
  });

export const cancelSignal = defineSignal('cancel');

export async function orderWorkflow(orderId: string): Promise<string> {
  let cancelled = false;
  setHandler(cancelSignal, () => { cancelled = true; });

  // 결제 승인 대기 — 최대 3일, 코드에 그대로 표현
  await condition(() => cancelled, '3 days');
  if (cancelled) return 'cancelled-before-payment';

  const charge = await chargePayment(orderId);
  try {
    await reserveInventory(orderId);
    await shipOrder(orderId);
    return 'completed';
  } catch (err) {
    // 실패 시 보상 트랜잭션 — 별도 사가 프레임워크 불필요
    await refundPayment(charge.id);
    throw err;
  }
}
```

이 코드는 워커가 재시작해도 `await condition(...)`이나 `reserveInventory` 실행 도중이었던 지점을 정확히 기억해 이어서 실행한다 — 별도의 상태 저장 코드가 코드베이스 어디에도 없다.

## 실무 포인트

- **결정성 제약을 어기면 리플레이가 조용히 어긋난다.** 워크플로 코드에서 시스템 시간·랜덤값·외부 라이브러리의 비결정적 동작을 직접 쓰면, 배포 후 리플레이 시 히스토리와 실제 코드 실행 경로가 갈라지는 "non-deterministic workflow" 에러가 난다. 워크플로 코드는 순수 오케스트레이션 로직만 담고, 부작용과 비결정성은 반드시 액티비티로 격리해야 한다.
- **워크플로 코드 변경은 버저닝이 필요하다.** 이미 진행 중인 워크플로 인스턴스가 있는 상태에서 워크플로 함수의 로직을 바꾸면 그 인스턴스의 리플레이가 깨질 수 있다. Temporal은 `patched()` API로 신·구 로직을 분기해 진행 중인 인스턴스와 새 인스턴스가 각자 맞는 경로를 타도록 지원한다.
- **모든 워크플로가 Durable Execution을 필요로 하진 않는다.** 초 단위로 끝나는 짧은 요청-응답 흐름이라면 이 모델의 이점(장기 대기, 재시작 복구)보다 인프라 복잡도(별도 서버, 워커 클러스터 운영)가 더 클 수 있다. 이 패턴은 실행 시간이 길거나(분~일 단위), 외부 이벤트 대기가 있거나, 실패 시 정교한 보상이 필요한 워크플로에 맞는 도구다.

## 3줄 요약

- Durable Execution은 워크플로를 평범한 순차 코드로 짜게 하고, 실행 과정을 이벤트 히스토리로 영속화해 프로세스가 죽어도 정확히 그 지점부터 재개하게 만드는 실행 모델이다.
- 워크플로(결정적 오케스트레이션)와 액티비티(비결정적 부작용)를 분리하는 것이 핵심 제약이며, 이 제약 덕분에 재시도·보상·장기 대기가 별도 프레임워크 없이 코드로 자연스럽게 표현된다.
- 짧은 요청-응답 흐름보다는 실행 시간이 길고 외부 이벤트 대기·복잡한 보상 로직이 필요한 워크플로에 적합하며, 워크플로 코드 변경 시 버저닝(`patched()`) 없이는 진행 중인 인스턴스의 리플레이가 깨질 수 있다.

## 참고 자료

- [Temporal 공식 문서: Core Application](https://docs.temporal.io/temporal)
- [Temporal 공식 문서: Workflow Determinism](https://docs.temporal.io/workflows#deterministic-constraints)
- [Temporal 공식 문서: Versioning](https://docs.temporal.io/develop/typescript/versioning)
- [AWS 공식 문서: AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
