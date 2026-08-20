---
layout: single
title: "RAG가 뭔가요 — 검색 증강 생성 개념을 처음부터 이해하기"
date: 2026-09-01 12:50:00 +0530
categories: ai
tags: ["rag", "llm", "ai기초", "입문", "검색증강생성"]
toc: true
toc_sticky: true
excerpt: "LLM 애플리케이션에서 가장 많이 언급되는 RAG(검색 증강 생성)가 정확히 무엇을 하는 기술인지, 왜 필요한지 개념부터 정리했다."
---

## 왜 LLM에게 그냥 물어보면 안 되는가

LLM은 학습 시점까지의 데이터로만 답을 만든다. 그래서 최신 정보나 회사 내부 문서처럼 학습 데이터에 없는 내용을 물으면 그럴듯하지만 틀린 답(환각, hallucination)을 만들어낸다. **RAG(Retrieval-Augmented Generation, 검색 증강 생성)**는 이 문제를 "모델을 다시 학습시키는 대신, 답할 때 필요한 문서를 찾아서 같이 보여주는" 방식으로 해결한다.

## RAG의 기본 흐름

| 단계 | 하는 일 |
|---|---|
| 1. 색인 | 문서를 잘게 나누고(청킹) 임베딩으로 변환해 벡터 DB에 저장 |
| 2. 검색 | 사용자 질문도 임베딩으로 변환해 벡터 DB에서 가장 관련 있는 문서를 찾음 |
| 3. 증강 | 찾은 문서를 프롬프트에 함께 넣어 LLM에게 전달 |
| 4. 생성 | LLM이 그 문서를 참고해 답을 생성 |

핵심은 LLM 자체는 그대로 두고, **질문에 맞는 근거 문서를 실시간으로 찾아 붙여준다**는 점이다.

## 코드 예제: 아주 단순한 RAG 흐름

```python
def answer_with_rag(question, vector_db, llm_client):
    # 1. 질문과 관련된 문서 검색
    relevant_docs = vector_db.search(question, top_k=3)

    # 2. 검색된 문서를 컨텍스트로 조립
    context = "\n\n".join(doc.text for doc in relevant_docs)

    # 3. 문서를 근거로 답하도록 프롬프트 구성
    prompt = f"""다음 문서를 참고해서 질문에 답해줘. 문서에 없는 내용은 모른다고 답해.

문서:
{context}

질문: {question}"""

    return llm_client.generate(prompt)
```

"문서에 없으면 모른다고 답해"라는 지시를 넣는 것이 실무에서 환각을 줄이는 가장 기본적이고 효과적인 방법이다.

## 실무 포인트

- **RAG는 파인튜닝의 대체재가 아니라 다른 문제를 푸는 도구다.** 최신 정보·사내 문서 검색에는 RAG가, 말투나 응답 스타일을 바꾸는 데는 파인튜닝이 더 적합하다.
- **검색 품질이 나쁘면 아무리 좋은 LLM을 붙여도 답이 부정확하다.** 문제가 생기면 먼저 "검색된 문서가 실제로 질문과 관련 있는가"부터 확인해야 한다.
- **문서를 어떻게 자르는지(청킹 전략)가 검색 정확도에 큰 영향을 준다.** 너무 잘게 자르면 문맥이 끊기고, 너무 크게 자르면 관련 없는 내용까지 섞여 들어간다.

## 마무리 요약

- RAG는 LLM을 재학습시키지 않고 질문에 맞는 문서를 찾아 함께 제공해 답변 정확도를 높이는 기법이다.
- 색인 → 검색 → 증강 → 생성의 4단계로 동작한다.
- 검색 품질이 전체 답변 품질을 좌우하므로, 문제가 생기면 검색 결과부터 점검해야 한다.

## 참고 자료

- [Pinecone - RAG 개념 정리](https://www.pinecone.io/learn/retrieval-augmented-generation/)
- [LangChain 공식 문서 - RAG](https://python.langchain.com/docs/tutorials/rag/)
