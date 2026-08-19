---
layout: single
title: "생각하고 움직일까, 계획부터 세울까 — ReAct vs Plan-and-Execute vs 리플렉션"
date: 2026-08-24 13:50:00 +0530
categories: ai
tags: ["ai-agent", "react-pattern", "plan-and-execute", "reflexion", "agent-planning", "llm"]
toc: true
toc_sticky: true
excerpt: "AI 에이전트가 다단계 문제를 풀 때 선택할 수 있는 세 가지 대표 플래닝 패턴 — ReAct, Plan-and-Execute, 리플렉션(Reflexion)의 동작 방식과 비용·정확도 트레이드오프를 비교한다."
---

에이전트에게 "이 버그를 고쳐줘"라고 시키면, 내부적으로 어떤 순서로 생각하고 행동해야 할까? 매 단계마다 관찰 결과를 보고 다음 행동을 즉흥적으로 정할 수도 있고, 처음부터 전체 단계를 계획한 뒤 순서대로 실행할 수도 있다. 이 설계 선택이 에이전트의 비용, 지연 시간, 실패 복구 능력을 크게 좌우한다.

가장 널리 쓰이는 세 패턴이 ReAct, Plan-and-Execute, 그리고 리플렉션(Reflexion) 기반 접근이다. 셋은 경쟁 관계가 아니라 실제로는 서로 다른 상황에 맞는 도구이며, 프로덕션 에이전트는 이들을 조합해서 쓰는 경우가 많다. 이 글에서는 각 패턴의 동작 원리와 실무 선택 기준을 정리한다.

## 핵심 개념 1: ReAct — 생각과 행동을 매 스텝 인터리빙

ReAct(Reasoning + Acting)는 "Thought → Action → Observation"을 한 스텝씩 반복하는 구조다. LLM은 매번 지금까지의 관찰 결과를 보고 다음에 무엇을 할지 즉석에서 판단한다. 사전에 정해진 계획이 없으므로 환경 변화나 예상치 못한 도구 응답에 유연하게 반응할 수 있다.

단점은 근시안적이라는 것이다. 각 스텝이 직전 관찰에만 의존하다 보니, 여러 단계를 내다봐야 하는 문제(예: "A를 먼저 해야 B가 가능하다"는 의존관계가 복잡한 작업)에서는 비효율적인 경로를 택하거나 같은 실수를 반복하기 쉽다.

## 핵심 개념 2: Plan-and-Execute — 먼저 전체 그림을 그린다

Plan-and-Execute는 이름 그대로 두 단계로 나뉜다. 플래너가 목표를 하위 작업 목록으로 먼저 분해하고, 이그제큐터가 그 목록을 순서대로 실행한다. 중간에 예상과 다른 결과가 나오면 플래너가 남은 계획을 다시 세우는(re-plan) 루프가 추가되는 것이 일반적이다.

이 구조의 장점은 토큰 비용이다. 매 스텝 전체 맥락을 다시 추론하는 ReAct와 달리, 계획 수립은 한 번(또는 재계획 시점에만) 일어나고 각 하위 작업의 실행은 더 작은 컨텍스트로 처리할 수 있다. 복잡하지만 구조가 예측 가능한 작업(다단계 데이터 파이프라인 구축 등)에 유리하다.

## 핵심 개념 3: 리플렉션(Reflexion) — 실패에서 배우는 루프

리플렉션 계열 접근은 ReAct나 Plan-and-Execute 위에 "자기 평가" 레이어를 추가한다. 작업이 실패하거나 목표에 못 미치면, 에이전트가 스스로 무엇이 잘못됐는지 언어로 비평(self-critique)을 생성하고, 이를 다음 시도의 맥락(메모리)에 포함시켜 같은 실수를 반복하지 않도록 한다.

핵심은 파라미터를 업데이트하는 학습이 아니라, 텍스트 형태의 반성 기록을 컨텍스트에 누적하는 방식이라는 점이다. 별도 파인튜닝 없이도 시행착오를 거치며 개선되는 효과를 낼 수 있지만, 반성 기록이 쌓일수록 컨텍스트가 길어지는 비용이 따른다.

| 구분 | ReAct | Plan-and-Execute | 리플렉션(Reflexion) |
|---|---|---|---|
| 계획 시점 | 매 스텝 즉흥 | 사전 일괄 계획 | 실패 후 재시도 시 |
| 토큰/지연 비용 | 스텝 수에 비례해 누적 | 계획 1회 + 실행 병렬화 가능 | 반성 기록 누적으로 증가 |
| 예상 밖 상황 대응 | 강함(즉시 반응) | 재계획 루프 필요 | 실패를 명시적으로 학습 |
| 적합한 작업 | 탐색적, 예측 불가한 환경 | 구조화된 다단계 작업 | 반복 가능한 유사 작업 |
| 대표 실패 모드 | 근시안적 비효율 경로 | 초기 계획의 오류가 전파 | 반성 자체가 부정확할 위험 |

## 예제: Plan-and-Execute 루프의 최소 구현 (Python 의사코드)

```python
def plan_and_execute(goal, llm, tools):
    plan = llm.generate_plan(goal)  # ["웹 검색", "결과 요약", "파일 저장"]
    results = []

    for i, step in enumerate(plan):
        try:
            result = execute_step(step, tools, context=results)
            results.append(result)
        except StepFailure as e:
            # 실패 지점부터 남은 계획을 다시 세운다
            remaining = plan[i:]
            plan = plan[:i] + llm.replan(goal, remaining, error=e, context=results)
            continue

    return llm.synthesize_final_answer(goal, results)
```

재계획(`replan`)이 전체 재시작이 아니라 실패 지점 이후 구간만 다시 세운다는 점이 비용 효율의 핵심이다.

## 실무 포인트

- **작업의 예측 가능성으로 패턴을 고른다**: 환경이 예측 불가능하고 매 단계 관찰이 결정적으로 다음 행동을 바꾸는 작업(고객 응대, 웹 탐색)은 ReAct가 적합하고, 단계 구조가 미리 그려지는 작업(ETL 파이프라인, 코드 리팩터링)은 Plan-and-Execute의 비용 이점이 크다.
- **리플렉션은 반복 실행되는 작업에서 가치가 커진다**: 일회성 작업에는 반성 기록을 쌓을 기회 자체가 없으므로 이점이 제한적이다. 같은 유형의 작업을 여러 번 수행하는 배치·에이전트 파이프라인에서 반성 메모리를 누적할 때 효과가 뚜렷하다.
- **셋을 계층적으로 조합하는 것이 실전에 가깝다**: 상위 레벨은 Plan-and-Execute로 하위 작업을 분해하고, 각 하위 작업 내부는 ReAct 루프로 유연하게 실행하며, 전체 실패 시 리플렉션으로 다음 실행의 계획 자체를 개선하는 3단 조합이 실제 프로덕션 에이전트 프레임워크(LangGraph, AutoGPT 계열)에서 흔히 관찰된다.

## 3줄 요약

- ReAct는 매 스텝 관찰에 즉흥적으로 반응해 유연하지만 근시안적이고, Plan-and-Execute는 전체 계획을 먼저 세워 비용 효율적이지만 초기 계획 오류에 취약하다.
- 리플렉션은 실패를 언어화한 반성으로 다음 시도에 반영하는 방식으로, 반복 가능한 작업에서 효과가 크다.
- 실전에서는 세 패턴을 계층적으로 조합해, 상위 계획-하위 유연 실행-실패 시 반성이라는 구조로 함께 쓰는 경우가 많다.

## 참고 자료

- [ReAct: Synergizing Reasoning and Acting in Language Models (arXiv)](https://arxiv.org/abs/2210.03629)
- [Plan-and-Solve Prompting (arXiv)](https://arxiv.org/abs/2305.04091)
- [Reflexion: Language Agents with Verbal Reinforcement Learning (arXiv)](https://arxiv.org/abs/2303.11366)
- [LangGraph 공식 문서: Plan-and-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/)
