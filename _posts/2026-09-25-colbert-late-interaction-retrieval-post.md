---
layout: single
title: "ColBERT Late Interaction — 토큰 단위 매칭으로 RAG 검색 정확도 끌어올리기"
date: 2026-09-25 13:50:00 +0530
categories: ai
tags: ["ColBERT", "LateInteraction", "RAG", "검색정확도", "벡터검색"]
toc: true
toc_sticky: true
excerpt: "문서 전체를 벡터 하나로 뭉뚱그리는 일반 임베딩 검색이 특정 키워드가 핵심인 질문에서 관련 문서를 놓치는 문제를, 문서를 토큰 단위 벡터 여러 개로 남겨두고 질의 시점에 매칭하는 ColBERT의 Late Interaction 구조로 해결하는 방법을 정리했다."
---

## 왜 지금 Late Interaction을 다시 봐야 하는가

일반적인 밀집 벡터(dense embedding) 검색은 문서 전체를 하나의 고정 길이 벡터로 압축한 뒤, 질의 벡터와의 코사인 유사도로 순위를 매긴다. 이 방식은 문서의 "전반적인 주제"를 포착하는 데는 강하지만, "특정 모델명", "정확한 오류 코드", "법 조항 번호"처럼 세부적이고 국소적인 정보가 검색 결과를 좌우하는 질문에서는 약점을 드러낸다. 문서 전체를 하나의 벡터로 뭉개는 과정에서 이런 세부 신호가 다른 정보에 묻혀 희석되기 때문이다. 리랭킹(Cross-Encoder)으로 이 문제를 보완할 수도 있지만, Cross-Encoder는 질의-문서 쌍마다 매번 전체를 함께 인코딩해야 해서 후보 수가 많으면 속도가 급격히 느려진다. ColBERT(Contextualized Late Interaction over BERT)는 이 둘 사이의 절충점을 제시한 방식으로, RAG 파이프라인의 검색 품질을 개선하려는 팀들 사이에서 다시 주목받고 있다.

## 핵심 개념 1 — 문서를 하나의 벡터가 아니라 토큰마다 벡터로 남긴다

일반 밀집 검색(bi-encoder)은 문서를 인코딩한 뒤 마지막에 풀링(pooling)을 거쳐 벡터 하나로 압축한다. ColBERT는 이 풀링 단계를 생략한다. BERT 계열 인코더를 문서에 통과시킨 뒤, 나온 토큰별 임베딩 수십~수백 개를 그대로 인덱스에 저장한다. 질의도 마찬가지로 토큰별 벡터 여러 개로 인코딩한다. 결국 하나의 문서는 "이 문서를 대표하는 벡터 하나"가 아니라 "이 문서 안의 각 단어가 문맥상 어떤 의미인지를 담은 벡터 다발"로 표현된다. 이것이 이름의 "Late Interaction"이 의미하는 바다 — 질의와 문서의 상호작용(interaction)을 인코딩 이전이 아니라, 인코딩을 각자 끝낸 뒤(late) 검색 시점에 계산한다.

## 핵심 개념 2 — MaxSim으로 토큰끼리 가장 잘 맞는 짝을 찾는다

검색 시점에 ColBERT는 MaxSim이라는 연산으로 질의-문서 점수를 계산한다. 질의의 각 토큰 벡터에 대해, 문서에 있는 모든 토큰 벡터와의 유사도를 계산하고 그중 가장 높은 값(최댓값)만 취한다. 이 과정을 질의의 모든 토큰에 대해 반복한 뒤 그 최댓값들을 합산해 최종 점수를 만든다. 직관적으로 말하면 "질의에 있는 각 단어가, 문서 안에서 자신과 가장 비슷한 단어를 만났을 때 그 유사도만큼 점수를 준다"는 방식이다. 이 구조 덕분에 질의의 특정 핵심 단어 하나가 문서 안의 한 토큰과 매우 강하게 일치하면, 문서의 나머지 부분이 관련 없더라도 그 강한 일치가 점수에 그대로 반영된다 — 일반 밀집 벡터가 전체 평균으로 희석시키는 신호를, ColBERT는 토큰 단위로 보존한다.

| 방식 | 문서 표현 | 질의-문서 상호작용 시점 | 검색 속도 | 세부 키워드 민감도 |
|---|---|---|---|---|
| Bi-Encoder(일반 밀집 검색) | 벡터 1개(풀링) | 인코딩 이전(각자 독립) | 빠름(ANN 인덱스) | 낮음(평균으로 희석) |
| Cross-Encoder(리랭커) | 질의+문서 함께 인코딩 | 인코딩과 동시(early) | 느림(쌍마다 재인코딩) | 높음 |
| ColBERT(Late Interaction) | 토큰별 벡터 다발 | 인코딩 후 검색 시점(late) | 중간(토큰 인덱스 필요) | 높음 |

## 코드 예제 — RAGatouille로 ColBERT 인덱싱과 검색

```python
from ragatouille import RAGPretrainedModel

# 사전학습된 ColBERTv2 체크포인트 로드
model = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

# 문서 인덱싱 — 내부적으로 토큰별 벡터 다발을 저장
model.index(
    collection=[doc1_text, doc2_text, doc3_text],
    index_name="my_docs_colbert",
)

# 검색 — MaxSim 기반으로 토큰 단위 매칭 점수 계산
results = model.search(query="PostgreSQL BRIN 인덱스 pages_per_range 기본값", k=5)
for r in results:
    print(r["score"], r["content"][:80])
```

## 실무 포인트

- **인덱스 저장 공간이 일반 밀집 검색보다 훨씬 크다.** 문서 하나당 벡터 하나가 아니라 토큰 수만큼 벡터를 저장하므로, 대규모 코퍼스에서는 스토리지와 메모리 비용을 반드시 사전에 가늠해야 한다. PLAID 같은 압축 기법이 이 문제를 완화하지만 완전히 없애지는 못한다.
- **전체 코퍼스에 처음부터 ColBERT만 쓰기보다, 1단계 필터링 후 재랭킹에 결합하는 하이브리드 구조가 실용적이다.** 값싼 BM25나 일반 벡터 검색으로 후보를 수백 개로 좁힌 뒤, 그 후보에만 ColBERT의 정밀한 MaxSim 매칭을 적용하면 정확도와 비용의 균형을 잡기 쉽다.
- **고유명사, 제품 코드, 정확한 수치처럼 "정확히 일치하는 토큰"이 중요한 도메인에서 일반 밀집 검색 대비 개선폭이 가장 크다.** 반대로 문서 전체의 주제 유사도만 판단하면 되는 작업에서는 개선폭이 크지 않을 수 있으므로, 도입 전에 실제 실패 사례가 어떤 유형인지 먼저 분석하는 것이 좋다.

## 마무리 요약

- ColBERT는 문서를 벡터 하나로 압축하지 않고 토큰별 벡터 다발로 유지해, 질의와의 상호작용을 검색 시점에 계산하는 Late Interaction 구조를 취한다.
- MaxSim 연산이 질의 토큰마다 문서 내 가장 유사한 토큰을 찾아 점수를 합산하므로, 일반 밀집 벡터가 평균으로 희석시키는 세부 키워드 신호를 보존한다.
- 인덱스 크기가 커지는 트레이드오프가 있으므로, 1단계 검색으로 후보를 좁힌 뒤 ColBERT를 재랭킹에 결합하는 하이브리드 구조가 실무에서 균형점이 된다.

## 참고 자료

- [ColBERTv2 논문 (Effective and Efficient Retrieval via Lightweight Late Interaction)](https://arxiv.org/abs/2112.01488)
- [RAGatouille GitHub](https://github.com/AnswerDotAI/RAGatouille)
