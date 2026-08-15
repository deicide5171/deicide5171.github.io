---
layout: single
title: "리랭킹으로 RAG 정확도 끌어올리기 — 검색과 생성 사이의 빠진 고리"
date: 2026-08-21 12:50:00 +0530
categories: ai
tags: ["ai", "rag", "reranking", "retrieval", "embedding", "llm"]
toc: true
toc_sticky: true
excerpt: "벡터 유사도 검색만으로는 관련성 높은 문서를 놓치기 쉬운 RAG 파이프라인에, 2단계 리랭킹을 추가해 검색 정확도를 끌어올리는 방법을 정리한다."
---

RAG(Retrieval-Augmented Generation) 파이프라인을 처음 구성할 때는 대개 임베딩 벡터로 문서를 색인하고, 질의 벡터와의 코사인 유사도가 높은 순으로 top-k개를 뽑아 LLM 컨텍스트에 넣는 방식을 쓴다. 구현이 단순하고 벡터 DB(예: Pinecone, Weaviate, pgvector)만 있으면 바로 돌아가기 때문에 대부분의 RAG 튜토리얼이 이 구조로 끝난다.

문제는 이 1차 검색만으로는 "의미적으로 비슷한 문서"와 "질문에 실제로 답할 수 있는 문서"가 항상 일치하지 않는다는 점이다. 임베딩은 질의와 문서를 각각 독립적으로 벡터 공간에 투영한 뒤 거리만 비교하기 때문에, 표현은 비슷하지만 핵심 답이 빠진 문서가 상위에 오르고, 표현은 다르지만 정확한 답을 담은 문서가 순위 밖으로 밀리는 경우가 흔히 생긴다. top-k를 늘려 이 문제를 우회하려 하면 이번에는 관련 없는 문서가 컨텍스트를 채워 LLM이 엉뚱한 근거로 답을 생성하는 부작용이 나타난다.

이 글에서는 1차 검색 결과를 그대로 쓰지 않고, 그 위에 **리랭킹(reranking)** 단계를 하나 더 얹어 검색 정확도를 끌어올리는 방법을 정리한다. 리랭킹은 새로운 개념이라기보다, 정보 검색(IR) 분야에서 오래 쓰인 2단계 검색(retrieve-then-rerank) 구조를 임베딩 기반 RAG에 그대로 가져온 것에 가깝다.

## 핵심 개념 1: Bi-Encoder와 Cross-Encoder의 차이

1차 검색에 쓰이는 임베딩 모델은 보통 **Bi-Encoder** 구조다. 질의와 문서를 각각 독립적으로 인코딩해 고정 길이 벡터로 만들고, 이 벡터들 사이의 거리(코사인 유사도 등)만 비교한다. 문서 임베딩은 색인 시점에 미리 계산해 벡터 DB에 저장해두므로, 검색 시점에는 질의 하나만 인코딩하면 되고 나머지는 근사 최근접 이웃(ANN) 탐색으로 매우 빠르게 끝난다. 문서가 수백만 건이어도 밀리초 단위 응답이 가능한 이유가 여기에 있다.

리랭킹에 쓰이는 **Cross-Encoder**는 구조가 다르다. 질의와 문서를 따로 인코딩하지 않고, 둘을 하나의 입력으로 이어붙여(concatenate) 트랜스포머에 함께 넣는다. 이렇게 하면 어텐션 레이어가 질의의 각 토큰과 문서의 각 토큰 사이 상호작용을 직접 계산할 수 있어, 두 텍스트를 독립적으로 압축한 벡터의 거리만 보는 Bi-Encoder보다 훨씬 정밀한 관련성 점수를 낼 수 있다. 다만 질의-문서 쌍마다 매번 전체 순전파를 새로 돌려야 하므로, 후보 문서 전체에 대해 미리 계산해두는 것이 불가능하고 검색할 때마다 비용이 든다.

## 핵심 개념 2: 리랭킹이 정확도를 올리는 원리

두 방식을 하나의 파이프라인으로 합치는 이유는 각각의 장단점이 정확히 상호 보완적이기 때문이다. Bi-Encoder는 전체 문서 집합에서 빠르게 후보군을 좁히는 역할(recall 중심)을 맡고, Cross-Encoder는 그렇게 좁혀진 소수의 후보만을 대상으로 정밀하게 순위를 다시 매기는 역할(precision 중심)을 맡는다.

전체 문서에 Cross-Encoder를 직접 돌리면 정확도는 가장 높겠지만 문서 수에 비례해 연산량이 늘어나 실시간 서비스에 쓸 수 없다. 반대로 Bi-Encoder만 쓰면 빠르지만 앞서 말한 대로 의미적 유사성과 실제 관련성이 어긋나는 사례를 걸러내지 못한다. top-k개(예: 100개)까지만 Cross-Encoder로 재채점하면, 전체 대비 연산량은 크게 줄이면서도 최종적으로 LLM에 넘길 top-n개(예: 5개)의 품질은 1차 검색만 썼을 때보다 눈에 띄게 개선되는 것이 일반적으로 보고되는 패턴이다. 다만 개선 폭은 도메인과 질의 유형에 따라 달라지므로, 구체적인 수치는 자신의 데이터셋으로 직접 검증하는 편이 안전하다.

## 핵심 개념 3: 리랭킹 모델 선택 시 고려사항

리랭킹 모델은 크게 두 갈래로 나뉜다. 하나는 Cohere Rerank, Jina Reranker처럼 API 형태로 제공되는 관리형 모델이고, 다른 하나는 sentence-transformers의 CrossEncoder 클래스로 로드해 직접 호스팅하는 오픈소스 모델(예: `ms-marco-MiniLM` 계열, `bge-reranker` 계열)이다. 관리형 API는 도입이 빠르고 모델 튜닝을 신경 쓸 필요가 없는 대신, 문서마다 외부 호출 비용과 네트워크 지연이 붙는다. 자체 호스팅은 지연시간을 직접 통제할 수 있고 데이터가 외부로 나가지 않는다는 장점이 있지만, GPU 인프라와 모델 서빙을 직접 관리해야 한다.

모델을 고를 때는 (1) 대상 언어를 실제로 학습했는지(다국어 지원 여부), (2) 한 번에 처리 가능한 후보 문서 수와 배치 처리 지원 여부, (3) 검색 도메인(법률, 의료, 코드 등 전문 영역)과 학습 데이터의 유사성을 함께 살펴야 한다. 범용 벤치마크(MTEB의 reranking 트랙 등) 순위가 자신의 실제 데이터에서도 그대로 재현된다는 보장은 없으므로, 후보 모델 2~3개를 실제 질의 샘플로 오프라인 평가(nDCG, MRR 등)한 뒤 선택하는 과정을 거치는 편이 안전하다.

<img src="/assets/images/posts/2026-08-21-rag-reranking-retrieval-quality-1.svg" alt="1차 검색(Bi-Encoder)에서 후보군을 추출하고, 리랭킹(Cross-Encoder)으로 정밀하게 재정렬한 뒤, 상위 문서만 LLM 생성 단계로 넘기는 RAG 파이프라인 구조도" style="width:100%;">

## 예제

아래는 1차 검색 후 리랭킹을 적용하는 전형적인 파이프라인을 의사코드로 정리한 것이다(Python).

```python
# 1) 1차 검색: Bi-Encoder + 벡터 DB
query_embedding = bi_encoder.encode(query)
candidates = vector_db.search(
    query_embedding,
    top_k=100,  # 넉넉히 뽑아 recall을 확보
)

# 2) 리랭킹: Cross-Encoder로 (query, document) 쌍을 함께 채점
pairs = [(query, doc.text) for doc in candidates]
scores = cross_encoder.predict(pairs)  # 각 쌍마다 관련성 점수

reranked = sorted(
    zip(candidates, scores),
    key=lambda x: x[1],
    reverse=True,
)

# 3) 상위 n개만 골라 LLM 컨텍스트로 전달
top_n_docs = [doc for doc, score in reranked[:5]]
context = "\n\n".join(doc.text for doc in top_n_docs)

answer = llm.generate(prompt=build_prompt(query, context))
```

관리형 리랭킹 API를 쓰는 경우에도 큰 흐름은 동일하다. 자체 Cross-Encoder를 호출하는 부분만 API 클라이언트 호출로 바뀔 뿐, "넉넉한 후보군 확보 → 정밀 재채점 → 상위 n개만 사용"이라는 3단계 구조 자체는 그대로 유지된다.

## 실무 포인트

- **지연시간 트레이드오프**: 리랭킹은 검색 파이프라인에 추가 연산 단계를 하나 더 얹는 것이므로, 후보 문서 수(k)와 리랭킹 모델의 크기에 비례해 응답 지연시간이 늘어난다. 실시간 챗봇처럼 응답 속도가 중요한 서비스라면 리랭킹을 배치나 캐싱이 가능한 구간에 배치하거나, 더 가벼운 리랭킹 모델을 선택하는 절충이 필요하다.
- **top-k / top-n 크기 튜닝**: 1차 검색의 top-k를 너무 작게 잡으면 애초에 정답 문서가 후보군에 들어오지 못해 리랭킹이 아무리 정교해도 소용이 없다(recall 상한 문제). 반대로 k를 지나치게 키우면 리랭킹 연산량이 늘어 지연시간이 커진다. 보통 k는 리랭킹 모델이 감당 가능한 배치 크기와 목표 응답시간을 함께 고려해 실험적으로 정하고, 최종 LLM에 넘기는 n은 컨텍스트 길이 제한과 프롬프트 예산에 맞춰 별도로 정하는 것이 합리적이다.
- **평가 지표를 함께 추적한다**: 리랭킹 도입 전후의 체감 품질만으로 판단하지 말고, 보유한 질의-정답 문서 쌍이 있다면 nDCG나 MRR 같은 지표로 실제 개선 여부를 정량적으로 확인하는 편이 좋다.

## 3줄 요약

- 벡터 유사도 기반 1차 검색(Bi-Encoder)만으로는 의미적 유사성과 실제 관련성이 어긋나는 문서가 상위에 오르는 경우가 흔하다.
- 좁혀진 후보군에 한해 질의-문서 쌍을 함께 인코딩하는 Cross-Encoder로 리랭킹을 적용하면, 전체 연산량을 감당 가능한 수준으로 유지하면서 최종 검색 정확도를 끌어올릴 수 있다.
- 리랭킹은 지연시간을 늘리는 추가 단계이므로, top-k/top-n 크기와 모델 선택을 실제 데이터로 검증하며 지연시간과 정확도 사이 균형점을 찾아야 한다.

## 참고 자료

- [Sentence-Transformers: Cross-Encoders 문서](https://www.sbert.net/examples/applications/cross-encoder/README.html)
- [Passage Re-ranking with BERT (arXiv:1901.04085)](https://arxiv.org/abs/1901.04085)
- [Cohere Rerank 공식 문서](https://docs.cohere.com/docs/rerank-overview)
- [Pinecone: Rerankers in RAG](https://www.pinecone.io/learn/series/rag/rerankers/)
