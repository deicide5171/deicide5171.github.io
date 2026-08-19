---
layout: single
title: "정답만 보지 마라 — 에이전트 궤적(Trajectory) 평가로 진짜 실패 지점 찾기"
date: 2026-08-24 12:50:00 +0530
categories: ai
tags: ["ai-agent", "evaluation", "llm-eval", "trajectory", "tool-use", "observability"]
toc: true
toc_sticky: true
excerpt: "에이전트 평가를 최종 출력물의 정답 여부만으로 판단하면 놓치는 것들을 짚고, 단계별 도구 호출과 중간 추론까지 채점하는 궤적(trajectory) 평가 방법론을 정리한다."
---

에이전트가 정답을 냈다고 해서 잘 작동한 것은 아니다. 불필요한 도구를 세 번 호출하고, 같은 API를 재시도 로직 없이 반복 호출해 비용을 태우고, 중간에 엉뚱한 파일을 삭제했다가 우연히 다음 단계에서 복구했는데도 최종 출력만 보면 "성공"으로 채점된다. 반대로 논리적으로 완벽한 경로를 밟았지만 마지막 포맷팅 하나 때문에 "실패"로 채점되는 경우도 흔하다. 단일 출력(output) 채점만으로는 에이전트가 실제로 신뢰할 만한지 판단할 수 없다.

그래서 등장한 것이 궤적(trajectory) 평가다. 에이전트가 최종 답에 도달하기까지 거친 단계별 도구 호출, 중간 추론, 상태 변화 전체를 하나의 시퀀스로 보고 채점한다. LangSmith, Arize Phoenix, OpenAI Evals 같은 도구들이 최근 이 방향으로 무게중심을 옮기고 있는 이유이기도 하다.

이 글에서는 궤적 평가가 필요한 이유, 무엇을 어떻게 채점하는지, 그리고 실무에서 마주치는 함정을 정리한다.

## 핵심 개념 1: 출력 평가와 궤적 평가는 다른 질문에 답한다

출력 평가는 "정답인가?"를 묻는다. 궤적 평가는 "이 경로가 안전하고 효율적이며 재현 가능한가?"를 묻는다. 같은 최종 답이라도 궤적은 천차만별일 수 있다.

| 구분 | 출력 평가 | 궤적 평가 |
|---|---|---|
| 채점 대상 | 최종 응답 텍스트/값 | 도구 호출 시퀀스 + 중간 추론 |
| 잡아내는 문제 | 오답, 포맷 오류 | 비효율, 위험 행동, 우연한 성공 |
| 대표 지표 | 정확도, BLEU/ROUGE류 | 도구 선택 정확도, 스텝 수, 복구율 |
| 필요 인프라 | 응답 로그 | 전체 트레이스(스팬) 로깅 |

궤적 평가가 특히 중요해지는 지점은 다단계 에이전트다. 코드 수정, 검색, 파일 조작이 섞인 워크플로에서는 "결과는 맞았지만 과정에서 프로덕션 DB에 쓰기 쿼리를 날렸다"는 식의 사고가 출력만으로는 절대 드러나지 않는다.

## 핵심 개념 2: 무엇을 채점할 것인가 — 스텝 단위 지표

궤적 평가는 보통 아래 축을 조합한다.

- **도구 선택 정확도**: 골든 궤적과 비교해 올바른 도구를 올바른 순서로 호출했는가 (완전 일치보다는 "동등한 대안 경로 허용"이 현실적)
- **불필요/중복 호출 비율**: 같은 정보를 얻기 위해 도구를 몇 번 반복 호출했는가
- **오류 복구 능력**: 도구 호출이 실패했을 때 스스로 진단하고 다른 경로를 시도했는가, 아니면 같은 실패를 반복했는가
- **중간 추론의 일관성**: LLM-as-judge로 각 단계의 "생각"이 다음 행동과 논리적으로 이어지는지 채점
- **위험 행동 탐지**: 되돌릴 수 없는 작업(삭제, 결제, 프로덕션 배포) 이전에 확인 절차를 거쳤는가

## 예제: 트레이스 기반 궤적 채점 하네스 (Python)

```python
from dataclasses import dataclass

@dataclass
class Step:
    tool: str
    args: dict
    observation: str
    reasoning: str

def score_trajectory(steps: list[Step], golden_tools: list[str], judge_fn) -> dict:
    # 1. 도구 시퀀스 유사도 (순서 무관, 집합 기반으로 완화)
    used_tools = [s.tool for s in steps]
    overlap = len(set(used_tools) & set(golden_tools))
    tool_precision = overlap / max(len(used_tools), 1)

    # 2. 중복 호출 탐지
    seen = set()
    redundant = 0
    for s in steps:
        key = (s.tool, tuple(sorted(s.args.items())))
        if key in seen:
            redundant += 1
        seen.add(key)

    # 3. LLM 판사에게 각 스텝의 추론-행동 일관성 채점 위임
    coherence_scores = [
        judge_fn(step.reasoning, step.tool, step.args) for step in steps
    ]

    return {
        "tool_precision": tool_precision,
        "redundant_calls": redundant,
        "avg_coherence": sum(coherence_scores) / len(coherence_scores),
        "step_count": len(steps),
    }
```

이 구조의 핵심은 최종 답을 아예 채점 대상에 넣지 않는다는 점이다. 출력 정확도는 별도 평가에서 따로 측정하고, 이 하네스는 순전히 "과정"만 본다.

## 실무 포인트

- **골든 궤적을 유일한 정답으로 강제하지 말 것**: 같은 문제를 푸는 유효한 경로가 여러 개인 경우가 많다. 완전 일치 대신 "허용 가능한 대안 경로 집합"을 정의하고 그 안에 들면 통과시키는 것이 과적합을 피하는 방법이다.
- **LLM 판사 비용과 비결정성을 관리한다**: 스텝마다 판사를 호출하면 채점 비용이 원래 에이전트 실행 비용을 넘어설 수 있다. 저비용 규칙 기반 필터(중복 호출, 금지 도구 호출)로 1차 필터링한 뒤, 애매한 케이스만 LLM 판사에 넘기는 계층화가 실용적이다.
- **트레이스 로깅을 나중에 추가하려 하지 말 것**: 궤적 평가는 배포 후 프로덕션 로그를 그대로 재사용할 수 있을 때 가치가 커진다. 처음부터 OpenTelemetry 스팬 형태로 도구 호출·추론을 구조화해서 남겨야, 평가 파이프라인과 운영 관측성을 동시에 얻는다.

## 3줄 요약

- 최종 출력만 채점하면 우연한 성공과 위험한 중간 행동을 놓치므로, 다단계 에이전트는 도구 호출·중간 추론까지 포함한 궤적 평가가 필요하다.
- 궤적 평가는 도구 선택 정확도, 중복 호출, 오류 복구율, 추론 일관성을 축으로 삼되 골든 궤적 완전 일치보다는 허용 가능한 대안 경로 집합으로 완화하는 것이 현실적이다.
- LLM 판사 비용을 관리하려면 규칙 기반 1차 필터 뒤에 애매한 케이스만 판사에 넘기는 계층화 전략과, 처음부터 구조화된 트레이스 로깅이 필요하다.

## 참고 자료

- [LangSmith 공식 문서: Evaluate an agent's trajectory](https://docs.smith.langchain.com/evaluation)
- [Arize Phoenix 공식 문서: Agent Evaluation](https://docs.arize.com/phoenix)
- [OpenAI Evals GitHub 저장소](https://github.com/openai/evals)
- [Anthropic 엔지니어링 블로그: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
