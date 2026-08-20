---
layout: single
title: "임베딩이 뭔가요 — 텍스트를 벡터로 바꾸는 임베딩 개념 입문"
date: 2026-08-31 14:50:00 +0530
categories: ai
tags: ["임베딩", "embedding", "벡터", "입문", "ai기초"]
toc: true
toc_sticky: true
excerpt: "RAG와 시맨틱 검색의 기반이 되는 텍스트 임베딩이 무엇이고 왜 필요한지, 처음 접하는 사람 기준으로 개념부터 정리했다."
---

## 왜 컴퓨터는 글자를 그대로 이해하지 못하는가

"강아지"와 "개"는 사람에게는 비슷한 의미지만, 컴퓨터 입장에서는 서로 다른 문자열일 뿐이다. 단순 문자열 비교로는 두 단어가 비슷한 의미라는 것을 알 방법이 없다. **임베딩(embedding)**은 이 문제를 해결하기 위해 단어나 문장을 의미가 비슷할수록 가까운 위치에 놓이는 숫자 벡터로 바꾸는 기술이다.

## 임베딩이 하는 일

| 입력 | 출력(단순화) | 의미 |
|---|---|---|
| "강아지" | [0.12, -0.05, 0.88, ...] | 수백~수천 차원의 실수 벡터 |
| "개" | [0.14, -0.03, 0.85, ...] | "강아지"와 벡터가 가깝다 |
| "자동차" | [-0.72, 0.41, 0.02, ...] | "강아지"와 벡터가 멀다 |

벡터 사이의 거리(코사인 유사도 등)를 계산하면 "이 두 텍스트가 의미적으로 얼마나 비슷한가"를 숫자로 구할 수 있다. 이것이 검색 엔진의 키워드 매칭과 임베딩 기반 검색(시맨틱 검색)의 가장 큰 차이다.

## 코드 예제: 임베딩 생성과 유사도 계산

```python
from openai import OpenAI
import numpy as np

client = OpenAI()

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return np.array(response.data[0].embedding)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

vec1 = get_embedding("강아지가 공원에서 뛰어논다")
vec2 = get_embedding("개 한 마리가 잔디밭을 뛰어다닌다")
vec3 = get_embedding("주식 시장이 오늘 급락했다")

print(cosine_similarity(vec1, vec2))  # 높은 값(의미가 비슷함)
print(cosine_similarity(vec1, vec3))  # 낮은 값(의미가 다름)
```

두 문장은 단어가 거의 겹치지 않지만 의미는 비슷하므로 유사도가 높게 나온다. 반면 세 번째 문장과는 유사도가 낮게 나온다.

## 임베딩은 어디에 쓰이는가

- **시맨틱 검색**: 키워드가 정확히 일치하지 않아도 의미가 비슷한 문서를 찾는다.
- **RAG(검색 증강 생성)**: 질문과 관련된 문서를 임베딩 유사도로 찾아 LLM에게 함께 전달한다.
- **추천 시스템**: 사용자가 좋아한 콘텐츠와 벡터가 가까운 다른 콘텐츠를 추천한다.
- **클러스터링·분류**: 비슷한 벡터끼리 자동으로 그룹을 짓는다.

## 실무 포인트

- **임베딩 벡터는 그 자체로 저장 공간을 많이 차지한다.** 문서가 많아지면 일반 DB 대신 전용 벡터 DB(Pinecone, Qdrant, pgvector 등)를 검토해야 한다.
- **임베딩 모델이 바뀌면 기존에 저장해둔 벡터와 호환되지 않는다.** 모델을 교체할 때는 전체 데이터를 재임베딩해야 한다는 점을 미리 고려해야 한다.
- **짧은 키워드보다 문맥이 있는 문장 단위로 임베딩할 때 검색 품질이 더 좋다.** 텍스트를 어떻게 잘라서 임베딩할지(청킹)도 결과에 큰 영향을 준다.

## 마무리 요약

- 임베딩은 텍스트를 의미 기반으로 비교할 수 있는 숫자 벡터로 바꾸는 기술이다.
- 벡터 사이의 코사인 유사도로 두 텍스트의 의미적 유사성을 계산할 수 있다.
- 시맨틱 검색, RAG, 추천 시스템 등 대부분의 최신 AI 응용의 기반 기술이다.

## 참고 자료

- [OpenAI 공식 문서 - Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Hugging Face - Sentence Transformers](https://www.sbert.net/)
