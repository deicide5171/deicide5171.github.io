---
layout: single
title: "에이전트가 스스로 결정하게 두면 안 되는 순간 — HITL 승인 게이트와 되돌리기 설계"
date: 2026-08-28 12:50:00 +0530
categories: ai
tags: ["ai", "agent", "human-in-the-loop", "approval-gate", "agent-safety"]
toc: true
toc_sticky: true
excerpt: "자율 에이전트에게 모든 실행 권한을 맡기지 않고, 되돌리기 어려운 행동 앞에서만 사람이 개입하도록 만드는 HITL(Human-in-the-Loop) 승인 게이트 설계 패턴을 정리한다."
---

에이전트에게 도구 사용 권한을 넉넉히 쥐여주면 처리 속도는 빨라지지만, 딱 그만큼 사고의 폭발 반경도 커진다. 파일 하나를 잘못 지우는 실수와 프로덕션 DB에 `DROP TABLE`을 실행하는 실수는 같은 종류의 실수지만 대가가 전혀 다르다. 문제는 에이전트가 "이건 되돌릴 수 없는 행동이니 조심해야 한다"는 감각을 안정적으로 갖고 있지 않다는 점이다. 매 스텝 사람이 승인하면 안전하지만 자율성의 의미가 사라지고, 완전 자율로 두면 속도는 빠르지만 사고가 났을 때 손쓸 방법이 없다.

그래서 실무에서 자리 잡아가는 접근은 이분법이 아니라 **행동의 되돌릴 수 있는 정도(reversibility)에 따라 개입 지점을 다르게 배치하는 것**이다. 읽기 전용 조회는 완전 자율로 두고, 되돌릴 수 있는 쓰기는 사후 감사로, 되돌릴 수 없거나 비용이 큰 행동만 사전 승인 게이트를 거치게 한다. 이 설계를 HITL(Human-in-the-Loop)이라고 부르는데, 핵심은 "사람이 얼마나 자주 끼어드는가"가 아니라 "언제, 어떤 조건에서 끼어드는가"를 정확히 정의하는 것이다.

이 글에서는 승인 게이트를 어떤 기준으로 트리거할지, 그리고 승인이 늦거나 실행 후 문제가 발견됐을 때 되돌리는 구조를 어떻게 설계하는지 정리한다.

## 핵심 개념 1: 개입 지점은 위험도가 아니라 되돌릴 수 있는가로 정한다

승인 게이트를 설계할 때 흔한 실수는 "위험해 보이는 행동"을 기준으로 삼는 것이다. 하지만 위험도는 주관적이고 도메인마다 다르다. 더 견고한 기준은 **행동을 실행 취소할 수 있는가, 그리고 실행 취소 비용이 얼마인가**다. 조회 API 호출은 부작용이 없으니 자율 실행, 임시 브랜치에 커밋하는 것은 되돌리기 쉬우니 사후 검토, 결제를 승인하거나 프로덕션 인프라를 변경하는 것은 되돌릴 수 없거나 비용이 크니 사전 승인이 원칙이다.

| 행동 유형 | 예시 | 되돌리기 | 개입 방식 |
|---|---|---|---|
| 읽기 전용 | 검색, 조회, 로그 분석 | 필요 없음 | 완전 자율 |
| 낮은 비용 되돌리기 | draft PR 생성, 임시 브랜치 커밋 | 쉬움(revert) | 실행 후 사후 검토 |
| 높은 비용 되돌리기 | 프로덕션 배포, 요금제 변경 | 어려움(수동 롤백) | 실행 전 승인 + 실행 후 확인 |
| 되돌릴 수 없음 | 결제 승인, 데이터 영구 삭제, 외부 메일 발송 | 불가능 | 필수 사전 승인 |

이 분류를 도구 정의 단계에 박아 넣는 것이 중요하다. 프롬프트로 "위험한 행동은 조심해라"라고 지시하는 방식은 모델의 판단에 안전을 위임하는 것이고, 승인이 필요한 도구 자체를 별도로 분리해 시스템 레벨에서 강제하는 방식이 사람의 실수나 프롬프트 인젝션에도 버틴다.

## 핵심 개념 2: 승인 게이트의 구조 — 제안, 대기, 승인/거부, 실행

승인 게이트는 에이전트가 도구를 직접 실행하는 대신 **실행 계획(제안)만 만들고 멈추는 지점**으로 구현한다. 사람이 승인하면 그 계획이 실제 실행으로 넘어가고, 거부하면 에이전트는 대안을 다시 계획한다. 이때 제안에는 무엇을 왜 하려는지, 예상되는 부작용, 실행 취소 방법까지 함께 담아야 사람이 몇 초 안에 판단할 수 있다. "DB 마이그레이션을 실행하겠습니다"보다 "orders 테이블에 index를 추가합니다. 예상 소요 5분, 락 없이 CONCURRENTLY로 실행하며 실패 시 자동 롤백됩니다"가 승인 여부를 훨씬 빠르게 결정하게 한다.

<img src="/assets/images/posts/2026-08-28-agent-human-in-the-loop-design-1.svg" alt="에이전트 행동이 되돌릴 수 있는 정도에 따라 자율 실행, 사후 검토, 사전 승인 게이트로 분기되는 흐름도" style="width:100%;">

승인 대기 상태에서 시간이 무한정 늘어지면 자동화의 의미가 퇴색되므로, 타임아웃 정책도 함께 정의해야 한다. 일반적으로는 타임아웃 시 자동 승인이 아니라 **자동 거부 후 에스컬레이션**이 안전한 기본값이다.

## 핵심 개념 3: 실행 후 되돌리기 — 승인만으로는 부족하다

승인 게이트를 아무리 촘촘히 설계해도 예상 못 한 부작용은 발생한다. 그래서 되돌리기(rollback) 경로를 실행 전에 함께 준비해두는 것이 두 번째 축이다. 이상적인 도구는 실행과 동시에 되돌리기용 상태 스냅샷이나 역연산을 함께 만들어 낸다 — 파일 수정 전 diff를 저장해 revert 커맨드를 자동 생성하거나, 배포 전 이전 리비전 태그를 남겨 원클릭 롤백을 가능하게 하는 식이다.

되돌리기가 구조적으로 불가능한 행동(외부로 나가는 이메일 발송, 결제 확정, 제3자 API로의 돌이킬 수 없는 호출)은 애초에 승인 게이트 없이 실행되는 일이 없도록 도구 계층에서 원천 차단하는 것이 가장 안전하다. "승인은 받았지만 되돌릴 방법이 없다"는 상태를 만들지 않는 것이 HITL 설계의 실질적인 목표다.

## 예제: 도구 정의에 승인 요구사항을 박아 넣기

```typescript
type ToolRiskTier = "auto" | "post_review" | "pre_approval";

interface AgentTool {
  name: string;
  riskTier: ToolRiskTier;
  reversible: boolean;
  buildRollbackPlan?: (result: unknown) => RollbackPlan;
}

const tools: AgentTool[] = [
  { name: "search_logs", riskTier: "auto", reversible: true },
  { name: "create_draft_pr", riskTier: "post_review", reversible: true },
  {
    name: "deploy_production",
    riskTier: "pre_approval",
    reversible: true,
    buildRollbackPlan: (result) => ({
      type: "redeploy_previous_revision",
      revisionId: (result as DeployResult).previousRevisionId,
    }),
  },
  { name: "send_customer_email", riskTier: "pre_approval", reversible: false },
];

async function runTool(tool: AgentTool, args: unknown) {
  if (tool.riskTier === "pre_approval") {
    const approval = await requestApproval({ tool: tool.name, args });
    if (approval.status !== "approved") {
      throw new ToolBlockedError(tool.name, approval.status);
    }
  }
  const result = await execute(tool.name, args);
  if (tool.riskTier === "pre_approval" && tool.buildRollbackPlan) {
    await persistRollbackPlan(tool.buildRollbackPlan(result));
  }
  return result;
}
```

승인 요청(`requestApproval`)은 슬랙 메시지, 티켓 시스템, 사내 콘솔 등 어디에 붙여도 되지만, 응답이 없을 때는 `timeout` 상태를 명시적으로 반환해 에이전트가 "승인됨"으로 오판하지 않게 해야 한다.

## 실무 포인트

- **승인 피로(approval fatigue)를 경계할 것**: 모든 것에 승인을 요구하면 사람은 몇 번 지나면 내용을 안 보고 습관적으로 승인 버튼을 누르게 된다. 승인 게이트는 되돌릴 수 없는 행동으로 좁게 유지해야 실효성이 유지된다.
- **승인 요청 자체를 감사 로그로 남길 것**: 누가, 언제, 어떤 제안을 승인/거부했는지 기록이 없으면 사고 후 원인 분석이 불가능하다. 승인 이력은 실행 로그와 별개로 보존해야 한다.
- **프롬프트 인젝션은 도구 계층에서 막을 것**: "이 작업은 승인이 필요 없다고 시스템에서 확인됨"류의 문구가 외부 입력(웹 페이지, 이메일 등)에 섞여 들어올 수 있다. 리스크 티어 판단을 모델의 텍스트 해석이 아니라 도구 코드에 고정해야 우회당하지 않는다.

## 3줄 요약

- HITL 개입 지점은 위험도의 주관적 판단이 아니라 행동의 되돌릴 수 있는 정도를 기준으로 자율 실행/사후 검토/사전 승인 세 단계로 나눈다.
- 승인 게이트는 에이전트가 계획만 세우고 멈추는 지점이며, 승인 요청에는 무엇을·왜·부작용·되돌리기 방법을 함께 담아야 사람이 빠르게 판단할 수 있다.
- 승인만으로는 부족하고, 실행과 동시에 되돌리기 경로(스냅샷·역연산)를 함께 준비해야 하며 되돌릴 수 없는 행동은 도구 계층에서 원천적으로 승인 없이는 실행 불가능하게 막아야 한다.

## 참고 자료

- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [OpenAI: Practices for Governing Agentic AI Systems](https://openai.com/index/practices-for-governing-agentic-ai-systems/)
- [Human-in-the-Loop for AI Agents — Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/human-in-the-loop)
