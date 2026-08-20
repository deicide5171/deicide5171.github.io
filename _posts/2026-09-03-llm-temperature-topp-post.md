---
layout: single
title: "temperature, top_p가 뭔가요 — LLM 응답을 조절하는 파라미터"
date: 2026-09-03 13:50:00 +0530
categories: ai
tags: ["temperature", "top_p", "llm", "파라미터", "입문"]
toc: true
toc_sticky: true
excerpt: "LLM API에서 응답의 창의성과 일관성을 조절하는 temperature와 top_p 파라미터가 각각 무엇을 하는지 예제로 정리했다."
---

## 같은 프롬프트인데 매번 답이 다른 이유

LLM에게 같은 질문을 여러 번 하면 조금씩 다른 답이 나온다. 이는 모델이 다음 단어를 고를 때 "가장 확률 높은 하나"만 고르는 것이 아니라, 확률 분포에서 어느 정도 무작위로 뽑기 때문이다. 이 무작위성의 정도를 조절하는 것이 **temperature**와 **top_p** 파라미터다.

## temperature: 무작위성의 세기

| 값 | 특성 | 적합한 용도 |
|---|---|---|
| 0에 가까움 | 거의 항상 가장 확률 높은 단어 선택(결정적) | 코드 생성, 사실 추출, 분류 |
| 0.7 정도 | 적당한 다양성(기본값 근처) | 일반 대화, 요약 |
| 1.0 이상 | 다양하고 창의적이지만 엉뚱해질 위험 | 브레인스토밍, 창작 |

temperature가 낮을수록 매번 비슷하고 안정적인 답이 나오고, 높을수록 다양하지만 예측 불가능해진다. **정답이 정해진 작업(코드, 계산)에는 낮게, 창의성이 필요한 작업에는 높게** 잡는 것이 기본 원칙이다.

## top_p: 후보 단어의 범위

top_p(뉴클리어스 샘플링)는 다른 방식으로 무작위성을 조절한다. 확률이 높은 순서대로 후보 단어를 모으다가 **누적 확률이 top_p에 도달하면 그 안에서만 선택**한다.

```text
top_p = 0.1 -> 가장 확률 높은 소수의 단어만 후보 (거의 결정적)
top_p = 0.9 -> 누적 90%에 해당하는 넓은 후보 (다양함)
```

## 코드 예제

```python
# 코드 생성: 일관성이 중요하므로 낮게
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "이진 탐색 함수를 작성해줘"}],
    temperature=0.2,  # 안정적이고 재현 가능한 코드
)

# 아이디어 브레인스토밍: 다양성이 중요하므로 높게
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "앱 이름 20개 제안해줘"}],
    temperature=1.0,  # 다양한 후보
)
```

## 실무 포인트

- **temperature와 top_p를 동시에 극단적으로 조절하는 것은 권장되지 않는다.** 공식 문서들은 보통 둘 중 하나만 조절하라고 안내한다. 둘 다 건드리면 상호작용이 예측하기 어려워진다.
- **완전히 똑같은 답을 원한다면 temperature를 0으로 낮춰도 100% 동일하지는 않을 수 있다.** 모델 내부 구현과 부동소수점 연산 특성상 미세한 차이가 날 수 있으므로, 완벽한 재현이 필요하면 별도의 seed 파라미터(지원하는 경우)를 함께 써야 한다.
- **RAG나 사실 기반 응답에는 낮은 temperature가 환각을 줄이는 데도 도움이 된다.** 높은 temperature는 창의성을 높이는 만큼 없는 사실을 지어낼 여지도 키운다.

## 마무리 요약

- temperature와 top_p는 LLM이 다음 단어를 고를 때의 무작위성을 조절하는 파라미터다.
- 정답이 정해진 작업(코드·분류)은 낮게, 창의성이 필요한 작업(창작·브레인스토밍)은 높게 잡는 것이 기본이다.
- 둘을 동시에 극단적으로 조절하지 말고 하나만 조절하는 것이 권장되며, 낮은 temperature는 환각 감소에도 도움이 된다.

## 참고 자료

- [OpenAI API 레퍼런스 - 파라미터](https://platform.openai.com/docs/api-reference/chat/create)
- [Anthropic API 문서 - temperature](https://docs.anthropic.com/en/api/messages)
