---
layout: single
title: "RAG 정확도를 끌어올리는 하이브리드 검색과 재순위(Reranking)"
date: 2026-09-24 13:50:00 +0530
categories: ai
tags: ["RAG", "하이브리드검색", "reranking", "벡터검색", "정보검색"]
toc: true
toc_sticky: true
excerpt: "벡터 검색만으로 RAG를 구축했을 때 고유명사나 코드 스니펫 질의에서 정확도가 떨어지는 이유를 짚고, BM25와 벡터 검색을 결합하는 하이브리드 검색과 재순위 단계로 검색 품질을 높이는 구조를 정리했다."
---

## 왜 지금 하이브리드 검색을 다시 봐야 하는가

RAG 파이프라인을 처음 구축할 때는 대부분 임베딩 모델로 문서를 벡터화하고 코사인 유사도로 가장 가까운 청크를 찾는 순수 벡터 검색만으로 시작한다. 의미적으로 유사한 문서를 잘 찾아낸다는 점에서 초기 프로토타입 단계에서는 충분히 잘 작동한다. 문제는 실제 서비스에 투입한 뒤 나타난다 — 제품 코드명, 에러 코드, 특정 API 함수명처럼 정확한 문자열 일치가 중요한 질의에서 벡터 검색은 의미적으로 "비슷한" 다른 문서를 가져오고 정작 정확히 일치하는 문서는 놓치는 경우가 반복된다. 임베딩은 의미적 유사성을 포착하는 데는 강하지만, 희귀한 고유명사나 정확한 토큰 매칭에는 상대적으로 약하다는 구조적 한계가 있기 때문이다.

## 핵심 개념 1 — 벡터 검색과 키워드 검색은 서로 다른 실패 모드를 가진다

BM25 같은 전통적인 키워드 기반 검색(sparse retrieval)은 정확한 토큰 일치에 강하지만 동의어나 문맥적 의미 차이를 이해하지 못한다. 반대로 벡터 기반 검색(dense retrieval)은 의미적 유사성은 잘 잡아내지만 정확한 식별자나 드문 용어에서는 성능이 떨어진다. 하이브리드 검색은 이 두 방식을 병렬로 실행한 뒤 결과를 병합함으로써 각 방식의 실패 모드를 서로 보완한다.

| 검색 방식 | 강점 | 약점 |
|---|---|---|
| BM25 (Sparse) | 정확한 키워드·식별자 일치 | 동의어·문맥 이해 부족 |
| 벡터 검색 (Dense) | 의미적 유사성 파악 | 희귀 고유명사·정확 매칭 약함 |
| 하이브리드 | 두 방식의 결과를 결합 | 병합 로직·가중치 튜닝 필요 |

## 핵심 개념 2 — 결과 병합과 재순위(Reranking)의 역할

두 검색 결과를 단순히 합치는 것만으로는 충분하지 않다. BM25 점수와 코사인 유사도는 스케일 자체가 다르기 때문에, 이를 직접 비교하지 않고 순위(rank) 기반으로 결합하는 RRF(Reciprocal Rank Fusion) 같은 기법을 흔히 쓴다. 여기서 한 단계 더 나아가, 병합된 후보군(보통 상위 20~50개)을 대상으로 별도의 재순위 모델(cross-encoder)을 돌리는 것이 최근 RAG 파이프라인의 표준 구성이다. 재순위 모델은 질의와 문서를 함께 입력받아 관련도를 직접 예측하기 때문에, 임베딩 유사도만으로는 구분하기 어려운 미묘한 관련성 차이를 훨씬 정확하게 걸러낼 수 있다.

## 예제 — RRF로 두 검색 결과 병합하기

```python
def reciprocal_rank_fusion(result_lists, k=60):
    scores = {}
    for results in result_lists:
        for rank, doc_id in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

bm25_results = bm25_search(query, top_k=50)      # 문서 ID 리스트, 순위순
vector_results = vector_search(query, top_k=50)  # 문서 ID 리스트, 순위순

fused = reciprocal_rank_fusion([bm25_results, vector_results])
candidates = [doc_id for doc_id, _ in fused[:30]]

# 재순위 모델로 최종 정렬
reranked = cross_encoder_rerank(query, candidates, top_k=8)
```

RRF는 점수 스케일 차이를 신경 쓰지 않고 순위만으로 병합할 수 있어 구현이 단순하면서도 실무에서 꾸준히 좋은 성능을 보인다.

## 실무 포인트

- **재순위 모델은 후보군 규모를 작게 유지해야 한다.** cross-encoder는 질의-문서 쌍마다 별도로 추론해야 해서 벡터 검색보다 훨씬 느리므로, 1차 검색에서 상위 20~50개로 추려낸 뒤에만 적용해야 지연시간이 감당 가능한 수준을 유지한다.
- **도메인에 특화된 재순위 모델을 우선 검토하라.** 범용 재순위 모델보다 코드 검색, 법률 문서, 의료 문서처럼 도메인 특화 재순위 모델이 존재하는 경우 정확도 차이가 크게 난다.
- **하이브리드 검색 도입 전에 실패 사례를 먼저 수집하라.** 벡터 검색만으로 실패하는 질의 유형(정확한 코드, 고유명사, 숫자 등)을 로그에서 먼저 파악한 뒤 하이브리드 검색 도입 효과를 정량적으로 검증하는 것이 순서에 맞다.

## 마무리 요약

- 벡터 검색과 키워드 검색은 서로 다른 실패 모드를 가지므로, 하이브리드 검색으로 결합하면 각각의 약점을 보완할 수 있다.
- RRF 같은 순위 기반 병합 기법은 점수 스케일 차이 문제 없이 두 검색 결과를 안정적으로 합칠 수 있다.
- 재순위(cross-encoder) 단계를 병합된 후보군의 상위 일부에만 적용하면, 지연시간을 감당 가능한 수준으로 유지하면서도 최종 검색 정확도를 크게 끌어올릴 수 있다.

## 참고 자료

- [Elastic - Reciprocal rank fusion](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
- [Pinecone - Rerankers and Two-Stage Retrieval](https://www.pinecone.io/learn/series/rag/rerankers/)
