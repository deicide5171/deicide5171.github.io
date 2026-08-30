---
layout: single
title: "Matryoshka 임베딩 — 벡터 차원을 유연하게 잘라 쓰는 법"
date: 2026-09-24 13:50:00 +0530
categories: ai
tags: ["MatryoshkaEmbedding", "벡터검색", "임베딩", "차원축소", "RAG"]
toc: true
toc_sticky: true
excerpt: "임베딩 차원이 클수록 검색 정확도는 높지만 벡터 DB 저장 비용과 검색 속도가 함께 나빠지는 트레이드오프를, 하나의 모델로 여러 차원을 동시에 지원하는 Matryoshka Representation Learning으로 완화하는 방법을 정리했다."
---

## 왜 지금 Matryoshka 임베딩을 다시 봐야 하는가

RAG 파이프라인에서 임베딩 차원을 정할 때는 딜레마가 있다. 차원이 클수록(예: 3072차원) 의미를 더 정밀하게 표현해 검색 정확도가 높아지지만, 벡터 하나당 저장 공간이 커지고 코사인 유사도 계산 비용도 늘어 대규모 벡터 DB에서는 비용과 지연시간이 함께 나빠진다. 전통적인 해법은 차원이 다른 임베딩 모델을 별도로 학습시키거나, PCA 같은 사후 차원 축소 기법을 적용하는 것이었지만, 전자는 모델을 여러 개 유지해야 하는 부담이 있고 후자는 임베딩 품질이 눈에 띄게 떨어지는 경우가 많았다. Matryoshka Representation Learning(MRL)은 이 문제를 "학습 단계에서부터 차원을 잘라도 의미가 보존되도록 만든다"는 방식으로 접근한 기법으로, 최근 여러 임베딩 모델이 이 방식을 채택하고 있다.

## 핵심 개념 1 — 러시아 인형처럼 중첩된 표현을 학습한다

이름의 유래가 된 마트료시카 인형처럼, MRL은 벡터의 앞쪽 부분집합(prefix)만 잘라내도 그 자체로 유의미한 임베딩이 되도록 학습한다. 예를 들어 1536차원으로 학습된 모델이 있다면, 전체 1536차원뿐 아니라 앞쪽 768차원, 앞쪽 256차원, 앞쪽 64차원만 잘라내도 각각이 독립적으로 쓸만한 임베딩이 되도록 손실 함수 자체가 이 여러 차원의 부분집합에 대해 동시에 계산된다. 일반적인 임베딩 모델은 벡터의 모든 차원이 서로 얽혀 있어 일부만 잘라내면 의미가 심하게 훼손되는 반면, MRL로 학습된 벡터는 앞쪽 차원에 더 중요하고 거친 의미 정보가, 뒤쪽 차원에 갈수록 세부적인 보정 정보가 위계적으로 배치된다.

## 핵심 개념 2 — 정확도와 비용 사이에서 차원을 동적으로 선택할 수 있다

이 특성 덕분에 하나의 모델로 여러 활용 시나리오에 대응할 수 있다. 1차 후보군을 빠르게 걸러내는 단계에서는 64~128차원으로 잘라낸 벡터를 써서 저장 공간과 계산량을 최소화하고, 최종 재순위(rerank) 단계에서만 전체 차원을 불러와 정밀하게 비교하는 2단계 검색 구조를 만들 수 있다. 이는 재순위 모델을 별도로 두는 것과는 다른 접근이다 — 같은 임베딩을 다른 정밀도로 재사용하는 것이므로 별도의 재순위 모델을 학습하거나 서빙할 필요가 없다.

| 차원 | 저장 공간 | 검색 속도 | 정확도 | 적합한 용도 |
|---|---|---|---|---|
| 전체(예: 1536) | 큼 | 느림 | 가장 높음 | 최종 재순위, 고정밀 검색 |
| 중간(예: 256) | 중간 | 중간 | 준수함 | 일반적인 벡터 검색 |
| 작음(예: 64) | 매우 작음 | 매우 빠름 | 낮지만 후보 추리기엔 충분 | 대규모 1차 필터링 |

## 예제 — 차원을 잘라 2단계 검색 구현하기

```python
import numpy as np

def truncate_and_normalize(embedding, dim):
    truncated = embedding[:dim]
    # MRL 임베딩은 자르고 난 뒤 재정규화가 필요한 경우가 많음
    return truncated / np.linalg.norm(truncated)

# 1단계: 저차원으로 대규모 후보군에서 빠르게 상위 K개 추리기
query_embedding_full = embed_model.encode(query)  # 예: 1536차원
query_small = truncate_and_normalize(query_embedding_full, 128)

candidates = vector_db.search(query_small, dim=128, top_k=200)

# 2단계: 전체 차원으로 상위 후보만 정밀 재정렬
query_full = truncate_and_normalize(query_embedding_full, 1536)
reranked = []
for doc in candidates:
    doc_full_vec = fetch_full_embedding(doc.id)  # 전체 차원 벡터는 후보만 조회
    score = cosine_similarity(query_full, doc_full_vec)
    reranked.append((doc, score))

final_results = sorted(reranked, key=lambda x: -x[1])[:20]
```

전체 차원 벡터는 상위 200개 후보에 대해서만 조회하면 되므로, 전체 데이터셋에 대해 고차원 유사도를 계산하는 비용을 피하면서도 최종 정확도는 유지할 수 있다.

## 실무 포인트

- **사용 중인 임베딩 모델이 실제로 MRL로 학습됐는지 먼저 확인하라.** 일반 임베딩 모델의 벡터를 임의로 잘라 쓰면 MRL 모델과 달리 의미가 크게 훼손되므로, 모델 카드나 문서에서 Matryoshka 지원 여부를 명시적으로 확인해야 한다.
- **잘라낸 차원으로도 재정규화(정규화 후 코사인 유사도 계산)를 잊지 마라.** 벡터를 자르기만 하고 정규화하지 않으면 유사도 계산 결과가 왜곡될 수 있다.
- **차원별 정확도 손실을 실제 도메인 데이터로 벤치마크하라.** MRL 논문의 벤치마크 결과가 모든 도메인에 그대로 적용되지는 않으므로, 1차 필터링에 쓸 차원을 얼마나 줄여도 recall이 허용 범위 안에 있는지 자체 검증이 필요하다.

## 마무리 요약

- Matryoshka Representation Learning은 벡터의 앞쪽 부분집합만 잘라도 유의미한 임베딩이 되도록 학습 단계에서부터 위계적 구조를 부여한다.
- 이 덕분에 하나의 모델로 저차원 1차 필터링과 고차원 정밀 재정렬을 조합하는 2단계 검색을 별도의 재순위 모델 없이 구현할 수 있다.
- 실제 도입 전에는 사용 모델의 MRL 지원 여부, 재정규화 필요성, 도메인별 차원-정확도 트레이드오프를 반드시 검증해야 한다.

## 참고 자료

- [Kusupati et al. - Matryoshka Representation Learning (arXiv)](https://arxiv.org/abs/2205.13147)
- [OpenAI - Embeddings with reduced dimensions](https://platform.openai.com/docs/guides/embeddings#reducing-embedding-dimensions)
