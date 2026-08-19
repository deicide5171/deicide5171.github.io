---
layout: single
title: "정확도와 속도, 어느 쪽을 먼저 포기할까 — pgvector HNSW/IVFFlat 인덱스 튜닝"
date: 2026-08-30 13:35:00 +0530
categories: database
tags: ["database", "pgvector", "hnsw", "ivfflat", "vector-search", "postgresql"]
toc: true
toc_sticky: true
excerpt: "pgvector에서 벡터 인덱스 없이 순차 스캔만 쓰면 데이터가 늘수록 검색이 선형으로 느려진다. HNSW와 IVFFlat의 서로 다른 근사 검색 원리와, 재현율·지연·구축 비용을 맞바꾸는 파라미터를 정리한다."
---

임베딩 벡터를 PostgreSQL에 그냥 컬럼으로 넣고 코사인 유사도로 정렬(`ORDER BY embedding <=> query_vector`)하면 정확한 결과가 나온다. 문제는 이 방식이 **전체 로우를 순회하는 순차 스캔(sequential scan)**이라는 점이다. 데이터가 수만 건일 때는 문제없지만 수백만 건으로 늘면 쿼리 하나에 수 초가 걸리는 상황이 온다. pgvector가 제공하는 HNSW와 IVFFlat 인덱스는 이 문제를 정확한 최근접 이웃(exact KNN) 대신 **근사 최근접 이웃(ANN, Approximate Nearest Neighbor)**으로 바꿔서 해결한다 — 100% 정확한 답 대신 대부분 정확한 답을 훨씬 빠르게 얻는 트레이드오프다.

이 글은 두 인덱스 방식의 동작 원리 차이와, 각각의 파라미터가 재현율(recall)·쿼리 지연·인덱스 구축 시간이라는 세 축을 어떻게 맞바꾸는지 정리한다. 어느 인덱스가 "더 좋다"가 아니라 워크로드 특성에 따라 다른 선택이 맞다는 것이 핵심이다.

## 핵심 개념 1: IVFFlat — 공간을 클러스터로 나눠 탐색 범위를 좁힌다

IVFFlat(Inverted File with Flat compression)은 전체 벡터 공간을 k-means 클러스터링으로 `lists`개의 클러스터로 미리 나눈다. 검색 시에는 쿼리 벡터가 어느 클러스터 중심에 가까운지 확인한 뒤, 그 중심에서 가장 가까운 `probes`개의 클러스터 안에 있는 벡터들만 정확하게 비교한다. 전체 데이터가 아니라 일부 클러스터만 훑으므로 빨라지지만, 쿼리 벡터가 클러스터 경계 근처에 있을 경우 진짜 최근접 이웃이 탐색하지 않은 이웃 클러스터에 있을 수 있어 재현율 손실이 생긴다.

`lists`가 너무 적으면 클러스터 하나가 너무 커져서 결국 순차 스캔과 큰 차이가 없어지고, 너무 많으면 클러스터가 지나치게 세분화돼 `probes`를 늘리지 않는 한 재현율이 떨어진다. pgvector 공식 가이드는 `lists = rows / 1000`(백만 건 미만) 또는 `sqrt(rows)`(그 이상)를 출발점으로 권장한다.

## 핵심 개념 2: HNSW — 계층적 그래프를 타고 내려가며 탐색한다

HNSW(Hierarchical Navigable Small World)는 접근 자체가 다르다. 벡터들을 그래프의 노드로 보고, 각 노드가 가까운 다른 노드들과 간선으로 연결된 다층 그래프를 만든다. 위쪽 레이어는 노드 수가 적고 간선이 성기며, 아래로 내려갈수록 노드가 조밀해진다. 검색은 가장 위 레이어에서 시작해 쿼리와 가까운 노드로 그리디하게 이동하다가, 한 레이어에서 더 가까운 노드를 못 찾으면 한 층 아래로 내려가는 과정을 반복해 최하위 레이어에서 최종 근접 이웃을 찾는다.

이 구조 덕분에 HNSW는 IVFFlat보다 일반적으로 더 높은 재현율과 더 빠른 쿼리 속도를 동시에 낸다는 평가를 받는다 — 클러스터 경계 문제 같은 근본적 약점이 없기 때문이다. 대신 그래프를 구축하는 비용(인덱스 생성 시간, 메모리 사용량)이 IVFFlat보다 훨씬 크고, 데이터가 계속 추가되는 워크로드에서는 그래프 갱신 비용도 고려해야 한다.

| 구분 | IVFFlat | HNSW |
|---|---|---|
| 탐색 구조 | k-means 클러스터 | 계층적 그래프 |
| 인덱스 구축 속도 | 빠름 | 느림(더 많은 메모리·CPU) |
| 쿼리 속도·재현율 | 준수하나 클러스터 경계에서 손실 | 대체로 더 우수 |
| 메모리 사용량 | 적음 | 많음(그래프 간선 저장) |
| 데이터 추가 시 | 재군집화 없이도 대체로 안정적 | 점진적 삽입 지원되나 비용 있음 |
| 적합한 상황 | 구축 시간·메모리가 빠듯한 대용량 | 쿼리 성능·재현율이 최우선 |

## 핵심 개념 3: 재현율-지연-구축 비용의 삼각형

두 인덱스 모두 결국 같은 트레이드오프 삼각형 위에 있다. 탐색 범위를 넓히면(IVFFlat의 `probes`를 늘리거나 HNSW의 `ef_search`를 늘리면) 재현율은 올라가지만 쿼리 지연도 함께 늘어난다. 인덱스 구축 시 더 정교한 구조를 만들면(HNSW의 `m`, `ef_construction`을 늘리면) 쿼리 시점의 재현율·속도는 좋아지지만 인덱스 생성 시간과 저장 공간이 커진다. "정확도, 속도, 구축 비용 중 어느 것도 공짜로 얻을 수 없다"는 것이 ANN 인덱스 튜닝의 근본 제약이다.

<img src="/assets/images/posts/2026-08-30-pgvector-hnsw-ivfflat-tuning-1.svg" alt="IVFFlat이 벡터 공간을 클러스터로 나눠 일부만 탐색하는 방식과 HNSW가 계층적 그래프를 위에서 아래로 타고 내려가며 탐색하는 방식을 비교하고, 재현율-지연-구축비용 삼각형 트레이드오프를 보여주는 다이어그램" style="width:100%;">

## 예제: 인덱스 생성과 검색 시 파라미터 조정

```sql
-- HNSW 인덱스 생성 — m(간선 수), ef_construction(구축 시 탐색 폭)
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 검색 시 재현율-지연 트레이드오프 조정 (세션 단위)
SET hnsw.ef_search = 100;  -- 기본값보다 넓게 탐색 → 재현율↑ 지연↑

SELECT id, content
FROM items
ORDER BY embedding <=> '[0.12, 0.87, ...]'::vector
LIMIT 10;

-- IVFFlat 인덱스 생성 — lists(클러스터 수)
CREATE INDEX ON items USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000);

-- 검색 시 탐색할 클러스터 수 조정
SET ivfflat.probes = 20;  -- 기본 1 → 더 많은 클러스터 확인, 재현율↑ 지연↑

SELECT id, content
FROM items
ORDER BY embedding <=> '[0.12, 0.87, ...]'::vector
LIMIT 10;
```

## 실무 포인트

- **재현율을 실측 없이 추정하지 마라.** 정확한 KNN 결과(인덱스 없이 순차 스캔한 결과)를 기준 삼아, 인덱스를 쓴 근사 검색 결과와 얼마나 겹치는지(recall@k)를 실제 데이터셋으로 측정해야 파라미터가 적절한지 판단할 수 있다. 문서의 권장값은 출발점일 뿐 데이터 분포에 따라 최적값이 달라진다.
- **HNSW의 `m`, `ef_construction`은 인덱스 생성 후 바꿀 수 없다.** 이 두 파라미터는 그래프 구조 자체를 결정하므로 변경하려면 인덱스를 재생성해야 한다. 반면 `ef_search`와 IVFFlat의 `probes`는 쿼리 시점(세션 단위) 파라미터라 재생성 없이 즉시 조정 가능하다 — 이 차이를 알아야 어떤 파라미터를 운영 중 실시간으로 튜닝할 수 있는지 헷갈리지 않는다.
- **대량 삽입 후에는 IVFFlat 인덱스를 재검토해야 한다.** IVFFlat의 클러스터 중심은 인덱스 생성 시점 데이터 분포로 고정되므로, 이후 데이터 분포가 크게 바뀌면(예: 새로운 카테고리 대량 유입) 기존 클러스터링이 최적이 아니게 되어 재현율이 서서히 떨어질 수 있다. HNSW는 점진적 삽입을 더 자연스럽게 지원하지만, 대량 삽입 시에는 인덱스를 끄고 벌크 삽입 후 재생성하는 편이 전체 처리 시간 면에서 유리한 경우가 많다.

## 3줄 요약

- pgvector의 HNSW와 IVFFlat은 모두 순차 스캔을 근사 최근접 이웃 탐색으로 바꿔 검색 속도를 높이지만, IVFFlat은 클러스터 기반, HNSW는 계층적 그래프 기반으로 탐색 원리가 근본적으로 다르다.
- HNSW는 대체로 더 높은 재현율과 빠른 쿼리 속도를 내지만 인덱스 구축 비용과 메모리 사용량이 크고, IVFFlat은 구축이 빠르고 가볍지만 클러스터 경계에서 재현율 손실이 생길 수 있다.
- 재현율·지연·구축 비용은 서로 맞바꿔야 하는 삼각형 관계이며, 실제 데이터셋으로 recall@k를 측정해 파라미터를 정하고 HNSW의 구조 파라미터와 쿼리 시점 파라미터를 구분해 운영해야 한다.

## 참고 자료

- [pgvector 공식 GitHub: README (인덱스 옵션 전체)](https://github.com/pgvector/pgvector)
- [pgvector 공식 문서: HNSW 인덱싱 가이드](https://github.com/pgvector/pgvector#hnsw)
- [pgvector 공식 문서: IVFFlat 인덱싱 가이드](https://github.com/pgvector/pgvector#ivfflat)
- [Malkov & Yashunin: Efficient and robust approximate nearest neighbor search using HNSW graphs (원 논문)](https://arxiv.org/abs/1603.09320)
