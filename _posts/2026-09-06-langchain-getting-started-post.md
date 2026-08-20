---
layout: single
title: "LangChain 시작하기 — LLM 앱 개발 프레임워크 첫걸음"
date: 2026-09-06 12:50:00 +0530
categories: ai
tags: ["langchain", "llm", "ai개발", "프레임워크", "입문"]
toc: true
toc_sticky: true
excerpt: "LLM 애플리케이션 개발에서 자주 쓰이는 LangChain이 무엇을 해주는지, 왜 직접 API를 호출하는 것과 다른지 입문자 기준으로 정리했다."
---

## LangChain은 무슨 문제를 풀어주나

LLM API를 직접 호출하는 것은 어렵지 않다. 그런데 실제 앱을 만들다 보면 "프롬프트 템플릿 관리", "여러 단계 연결", "외부 데이터 검색(RAG)", "대화 기록 유지" 같은 반복되는 패턴이 생긴다. **LangChain**은 이런 공통 패턴을 부품으로 제공해, LLM 앱을 조립하듯 만들 수 있게 해주는 프레임워크다.

## LangChain의 핵심 구성 요소

| 구성 요소 | 역할 |
|---|---|
| 프롬프트 템플릿 | 변수를 끼워 넣는 재사용 가능한 프롬프트 |
| 모델(LLM) | OpenAI·Anthropic 등 여러 모델을 같은 방식으로 호출 |
| 체인(Chain) | 여러 단계를 연결해 파이프라인 구성 |
| 리트리버(Retriever) | 벡터 DB에서 관련 문서 검색(RAG) |
| 메모리(Memory) | 대화 기록을 유지 |

## 코드 예제: 간단한 체인

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 1. 프롬프트 템플릿 (변수 {product}를 나중에 채움)
prompt = ChatPromptTemplate.from_template(
    "{product}를 홍보하는 짧은 카피 한 줄 작성해줘"
)

# 2. 모델
model = ChatOpenAI(model="gpt-4o")

# 3. 체인으로 연결 (프롬프트 -> 모델)
chain = prompt | model

# 4. 실행 (변수만 넣으면 됨)
result = chain.invoke({"product": "무선 이어폰"})
print(result.content)
```

`prompt | model`처럼 파이프(`|`) 기호로 단계를 연결하는 것이 LangChain의 특징이다. 각 단계를 부품처럼 갈아 끼우거나 추가할 수 있다.

## LangChain을 쓸까 말까

```text
쓰면 좋은 경우:
- RAG, 에이전트처럼 여러 부품을 조합하는 복잡한 앱
- 여러 LLM 제공자를 바꿔가며 쓸 가능성이 있을 때

굳이 안 써도 되는 경우:
- 단순히 프롬프트 하나 보내고 응답 받는 정도
- 추상화 레이어의 학습 비용이 이득보다 클 때
```

## 실무 포인트

- **LangChain은 추상화가 많아 학습 곡선이 있다.** 단순한 작업에는 오히려 API를 직접 호출하는 것이 더 이해하기 쉽고 디버깅도 편하다. 복잡도가 실제로 필요해질 때 도입하는 것이 좋다.
- **버전 간 변화가 잦은 편이다.** LangChain은 빠르게 발전하며 API가 바뀌는 경우가 있으므로, 튜토리얼을 따라 할 때 버전이 맞는지 확인해야 한다.
- **LangSmith 같은 관측 도구와 함께 쓰면 디버깅이 쉬워진다.** 여러 단계를 거치는 체인은 어디서 문제가 생겼는지 파악하기 어려운데, 각 단계의 입출력을 추적해주는 도구가 도움이 된다.

## 마무리 요약

- LangChain은 프롬프트 템플릿·체인·RAG·메모리 같은 LLM 앱 공통 패턴을 부품으로 제공하는 프레임워크다.
- 파이프(`|`) 기호로 단계를 연결해 파이프라인을 조립하듯 만드는 것이 특징이다.
- 복잡한 앱에는 유용하지만 단순한 작업에는 직접 API 호출이 더 나을 수 있어, 필요할 때 도입하는 것이 좋다.

## 참고 자료

- [LangChain 공식 문서](https://python.langchain.com/docs/introduction/)
- [LangChain GitHub](https://github.com/langchain-ai/langchain)
