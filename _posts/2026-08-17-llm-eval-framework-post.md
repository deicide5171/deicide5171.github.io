---
layout: single
title: "감으로 배포하지 않기 — LLM 애플리케이션 Eval 프레임워크 설계하기"
date: 2026-08-17 13:50:00 +0530
categories: ai
tags: ["llm", "eval", "테스트자동화", "llm-as-judge", "ci-cd"]
toc: true
toc_sticky: true
excerpt: "프롬프트 한 줄만 바꿔도 품질이 널뛰는 LLM 애플리케이션을, 전통적인 단위 테스트가 아니라 골든 데이터셋과 LLM-as-judge로 구성된 Eval 파이프라인으로 회귀 없이 배포하는 방법을 정리한다."
---

## 왜 지금 Eval 프레임워크인가

프롬프트를 한 문장 다듬었더니 다른 케이스에서 답변 품질이 떨어지는 경험, LLM 애플리케이션을 다뤄봤다면 한 번쯤 겪었을 것이다. 출력이 비결정적이고 "정답"이 하나로 고정되지 않기 때문에, 전통적인 단위 테스트의 `assert actual == expected` 방식은 대부분 통하지 않는다. 그렇다고 매번 사람이 눈으로 응답을 확인하는 방식은 프롬프트나 모델 버전이 바뀔 때마다 확장이 안 된다.

이 문제를 구조적으로 푸는 방법이 **Eval(평가) 프레임워크**다. 정답이 하나가 아닌 출력을 여러 방식으로 채점하고, 변경 전후를 같은 데이터셋으로 비교해 회귀를 잡아내는 자동화 계층을 애플리케이션 파이프라인 안에 넣는 것이다. RAG 설계나 벡터DB 선택처럼 "무엇을 넣을지"에 대한 결정이 아니라, "지금 나온 결과가 이전보다 나빠지지 않았는지"를 검증하는 품질 게이트에 가깝다.

## 핵심 개념 1: 세 가지 평가 방식

Eval은 보통 한 가지 방법만으로는 충분하지 않고, 아래 세 가지를 조합해서 쓴다.

| 방식 | 설명 | 장점 | 한계 |
|---|---|---|---|
| 규칙 기반 | 정규식·JSON 스키마·키워드 포함 여부 검사 | 빠르고 결정적, 비용 없음 | 자유 형식 답변의 "의미"는 못 봄 |
| 유사도 기반 | 참조 답변과의 임베딩 코사인 유사도 | 문구가 달라도 의미 근접성 측정 | 임계값 튜닝이 필요, 미묘한 오류는 놓칠 수 있음 |
| LLM-as-judge | 별도 LLM이 루브릭 기준으로 채점 | 자유 서술형·복합 기준 평가 가능 | 채점 비용·지연, judge 자체의 편향 존재 |

실무에서는 규칙 기반으로 형식 오류를 걸러내고, 남은 케이스만 LLM-as-judge로 채점해 비용을 줄이는 조합이 흔하다.

## 핵심 개념 2: 골든 데이터셋 구성

평가기보다 먼저 갖춰야 하는 것이 테스트 케이스 자체다. 코드 리뷰하듯 데이터셋도 버전 관리하고 리뷰해야 한다.

- **정상 케이스**: 가장 흔한 사용자 요청 패턴
- **엣지 케이스**: 빈 입력, 아주 긴 입력, 모호한 질문
- **적대적 케이스**: 프롬프트 인젝션 시도, 정책 위반 유도
- **회귀 케이스**: 과거에 실제로 실패했던 사례 — 고칠 때마다 여기 추가

운영 로그에서 실패 사례를 발견할 때마다 회귀 케이스로 편입하면, 데이터셋이 실제 트래픽을 따라 계속 두꺼워진다.

<img src="/assets/images/posts/2026-08-17-llm-eval-framework-1.svg" alt="LLM Eval 파이프라인 - 골든 데이터셋에서 후보 응답 생성, 병렬 평가기 채점, 점수 집계, 배포 게이트까지의 흐름" style="width:100%;">

## 핵심 개념 3: 배포 파이프라인에 게이트로 넣기

Eval을 한 번 실행하고 끝내는 것이 아니라, 프롬프트·모델·RAG 설정이 바뀔 때마다 CI에서 자동으로 돌리고 임계값 미달 시 배포를 막는 게 핵심이다. 이렇게 하면 "왜 갑자기 답변이 이상해졌지"를 배포 후 사용자 문의로 알게 되는 대신, 머지 전에 잡을 수 있다.

## 예제 1: LLM-as-judge 채점 스크립트 (Python)

```python
import anthropic

client = anthropic.Anthropic()

RUBRIC = """다음 기준으로 1~5점을 매기고 이유를 한 문장으로 설명하라.
- 질문에 직접 답했는가
- 근거 없는 사실을 지어내지 않았는가
- 톤이 요청된 형식(공손함/간결함)을 지켰는가"""

def judge(question: str, candidate_answer: str) -> dict:
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        messages=[{
            "role": "user",
            "content": f"{RUBRIC}\n\n질문: {question}\n답변: {candidate_answer}",
        }],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return text  # JSON 문자열 — json.loads로 파싱해 score/reason 사용
```

`output_config.format`으로 JSON 스키마를 강제하면 채점 결과를 파싱 실패 걱정 없이 그대로 집계할 수 있다.

## 예제 2: 테스트 케이스 스키마 (JSON)

```json
{
  "id": "refund-policy-edge-001",
  "category": "edge_case",
  "input": "환불 규정이 애매한 상황에서 사용자가 재차 물어볼 때",
  "reference_answer": "환불 가능 기간과 예외 조건을 명확히 안내",
  "must_not_contain": ["확실합니다", "100% 보장"]
}
```

`must_not_contain` 같은 규칙 기반 필드와 `reference_answer` 같은 LLM-judge용 필드를 한 스키마에 함께 두면, 평가기마다 데이터셋을 따로 관리하지 않아도 된다.

## 실무 포인트

- **judge 모델은 평가 대상 모델과 같거나 더 강한 모델을 쓴다.** 약한 judge는 미묘한 오류를 못 잡는다.
- **judge의 채점 편향을 의심한다.** 특정 문체나 답변 길이를 선호하는 경향이 있을 수 있으므로, 일부 샘플은 사람이 주기적으로 교차 검수한다.
- **전체 데이터셋을 매번 다 돌릴지, 샘플링할지는 비용과 트레이드오프다.** 회귀 케이스는 항상 전수 실행하고, 정상 케이스는 샘플링하는 절충이 흔하다.
- **임계값은 한 번 정하고 끝내지 않는다.** 데이터셋이 커지고 케이스 구성이 바뀌면 통과 기준도 재검토가 필요하다.

## 3줄 요약

- LLM 응답은 비결정적이라 전통적 단위 테스트로는 검증이 안 되므로, 규칙 기반·유사도·LLM-as-judge를 조합한 Eval 프레임워크가 필요하다.
- 정상·엣지·적대적·회귀 케이스로 구성된 골든 데이터셋을 코드처럼 버전 관리하고, 실패 사례가 나올 때마다 회귀 케이스로 편입한다.
- 프롬프트나 모델이 바뀔 때마다 CI에서 자동 실행하고 임계값 미달 시 배포를 막는 게이트로 운영해야 회귀를 배포 전에 잡을 수 있다.

## 참고 자료

- [Anthropic Docs — Test & Evaluate](https://platform.claude.com/docs/en/test-and-evaluate/overview)
- [promptfoo — LLM Eval 오픈소스 문서](https://www.promptfoo.dev/docs/intro/)
- [OpenAI Evals — 오픈소스 평가 프레임워크](https://github.com/openai/evals)
