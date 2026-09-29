---
layout: single
title: "PostGIS와 pgvector, 한 DB에 모을 때의 트레이드오프 — 공간 검색과 의미 검색을 합치는 법"
date: 2026-09-29 12:45:00 +0530
categories: gis
tags: ["postgis", "pgvector", "벡터검색", "공간데이터베이스", "하이브리드검색"]
toc: true
toc_sticky: true
excerpt: "\"근처에서 '아이랑 가기 좋은 카페' 찾아주세요\"라는 요구사항은 공간 필터와 의미 검색을 동시에 만족해야 한다. PostGIS와 pgvector를 한 Postgres에 모을지, 벡터 전용 DB와 분리할지 판단하는 기준과 쿼리 설계를 정리했다."
---

## "근처에서 '아이랑 가기 좋은 카페' 찾아주세요"

지도 서비스에 이런 요구사항이 들어오면 곧바로 두 종류의 필터가 동시에 걸린다. 하나는 **공간 필터**("근처에서" — 현재 좌표 반경 2km 이내), 다른 하나는 **의미 필터**("아이랑 가기 좋은" — 키워드 매칭이 아니라 설명 텍스트의 의미로 판단). 기존에는 이 둘을 담당하는 시스템이 완전히 갈라져 있었다. 공간 검색은 PostGIS, 의미 검색은 Pinecone·Weaviate 같은 벡터 전용 DB. 그런데 2026년 들어 pgvector가 HNSW 인덱스와 필터 결합 성능을 계속 개선하면서, "굳이 DB를 두 개로 나눠야 하나"라는 질문이 실무 선택지로 올라왔다.

이 글은 새 기술 소개가 아니라 **아키텍처 결정**에 관한 것이다. 같은 Postgres 안에 PostGIS와 pgvector를 함께 두는 통합형과, 벡터 전용 DB를 따로 쓰는 분리형 중 무엇을 고를지, 그리고 통합형을 골랐을 때 실제 쿼리를 어떻게 짜야 두 인덱스가 서로를 방해하지 않는지를 정리한다.

## 전체 구조에서의 위치

매장 데이터가 들어오는 순간부터 생각해보면, 파이프라인은 이렇게 흐른다. 매장 등록 API → 설명 텍스트를 임베딩 모델에 보내 벡터 생성 → 위경도를 geometry로 변환 → 두 값을 어디에 저장할지 결정 → 검색 시점에 공간 필터와 벡터 유사도를 함께 적용해 순위를 매긴다.

<img src="/assets/images/posts/2026-09-29-postgis-pgvector-unified-search-tradeoff-1.svg" alt="통합형 아키텍처는 하나의 Postgres 테이블에 geometry와 vector 컬럼을 함께 두고 한 번의 SQL로 반경 필터와 벡터 유사도를 함께 처리하는 반면, 분리형 아키텍처는 벡터 전용 DB와 PostGIS를 나눠 애플리케이션 레이어에서 후보를 조인하며 top-K 후보에 반경 안 매장이 빠질 위험을 안게 되는 구조를 비교한 다이어그램" style="width:100%;">

여기서 핵심 함정은 **분리형에서 "후보 부족" 문제**다. 벡터 DB에서 유사도 top-100을 먼저 받아온 뒤 그중 반경 안에 있는 것만 걸러내면, 반경 안에 진짜 좋은 매장이 있어도 벡터 유사도 순위에서 100등 밖으로 밀려 있으면 애초에 후보에 들어오지 못한다. 반대로 반경 필터를 먼저 걸고 그 안에서만 벡터 유사도를 계산하려면, 벡터 DB가 "이 ID 집합 안에서만 검색"이라는 사전 필터링을 지원해야 하는데 모든 벡터 DB가 이를 효율적으로 지원하지는 않는다.

## 통합형 vs 분리형 — 무엇을 기준으로 고를까

| 기준 | 통합형 (PostGIS + pgvector) | 분리형 (벡터 DB + PostGIS) |
|---|---|---|
| 정합성 | 트랜잭션 하나로 보장 | 두 시스템 간 동기화 필요 |
| 사전 필터링 정확도 | SQL 하나로 공간+벡터 동시 적용 가능 | top-K 후보 부족 문제 발생 가능 |
| 운영 부담 | 낮음 (DB 한 대) | 높음 (동기화 파이프라인 별도 관리) |
| 대규모 벡터 성능 | 수천만 건 이상에서 전용 DB 대비 열세 | 전용 인덱스·샤딩으로 수억 건도 처리 |
| 적합한 규모 | 매장 수 수십만~수백만 건 | 매장 수 수억 건, 검색 QPS가 매우 높을 때 |

실무적으로는 **매장·POI 규모가 수백만 건 이하라면 통합형으로 시작하는 편이 합리적**이다. 정합성을 챙기기 쉽고 운영 포인트가 하나로 줄어든다. 트래픽과 데이터 규모가 벡터 전용 DB의 샤딩·분산 검색이 필요한 지점까지 커지면 그때 분리를 고려해도 늦지 않다 — 처음부터 분리형으로 시작해 동기화 파이프라인의 복잡도를 미리 짊어질 필요는 없다.

## 통합형 쿼리 설계 — 인덱스 순서가 성능을 가른다

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE places (
  id bigserial PRIMARY KEY,
  name text,
  description text,
  geom geometry(Point, 4326),
  embedding vector(768)
);

CREATE INDEX idx_places_geom ON places USING GIST (geom);
CREATE INDEX idx_places_embedding ON places USING HNSW (embedding vector_cosine_ops);

-- 반경 2km 안에서, 설명이 질의와 가장 유사한 순으로 20건
SELECT id, name,
       ST_Distance(geom::geography, ST_MakePoint(:lng, :lat)::geography) AS dist_m,
       embedding <=> :query_embedding AS cos_dist
FROM places
WHERE ST_DWithin(geom::geography, ST_MakePoint(:lng, :lat)::geography, 2000)
ORDER BY embedding <=> :query_embedding
LIMIT 20;
```

여기서 **공간 필터를 WHERE 절에, 벡터 정렬을 ORDER BY에 두는 순서**가 중요하다. 옵티마이저가 GiST 인덱스로 후보군을 좁힌 뒤 그 안에서만 HNSW 정렬을 시도하도록 유도해야, 전체 테이블에 대해 벡터 거리를 계산하는 최악의 경우를 피할 수 있다. 실행 계획을 `EXPLAIN ANALYZE`로 반드시 확인해, 반경 필터가 먼저 걸리고 있는지 검증한다.

## 실무 포인트

**코사인 거리와 미터 단위는 스케일이 다르다.** 두 값을 단순히 더해 하나의 점수로 합치면 안 된다. 최종 순위를 매길 때는 공간 거리를 반경 대비 비율로, 벡터 거리를 0~1 정규화값으로 각각 바꾼 뒤 가중합을 적용하는 편이 안전하다.

**임베딩 재계산 시점을 정해둔다.** 매장 설명이 수정될 때마다 임베딩을 동기적으로 다시 계산하면 쓰기 지연이 늘어난다. 설명 변경은 큐에 넣고 비동기로 임베딩을 갱신하되, 갱신 전까지는 이전 임베딩으로 검색되는 짧은 지연을 감수하는 것이 현실적인 절충이다.

**HNSW 인덱스는 메모리를 많이 먹는다.** GiST와 HNSW 두 인덱스가 같은 Postgres 인스턴스의 shared_buffers를 나눠 쓰므로, 벡터 차원 수와 매장 건수가 늘어날수록 메모리 압박이 먼저 온다. 통합형을 쓰기로 했다면 이 인덱스들의 메모리 사용량부터 먼저 측정해 인스턴스 크기를 정한다.

## 정리

- 공간 필터와 의미 검색을 동시에 요구하는 기능은 아키텍처 선택부터 시작한다. 매장 규모가 수백만 건 이하라면 PostGIS+pgvector 통합형으로 시작하는 편이 정합성과 운영 부담 모두에서 유리하다.
- 분리형을 쓸 때는 top-K 후보 부족 문제를 반드시 검증해야 한다. 벡터 유사도만으로 후보를 뽑으면 반경 안의 좋은 결과를 놓칠 수 있다.
- 통합형 쿼리는 WHERE의 공간 필터가 먼저 후보를 좁히도록 실행 계획을 확인하고, 코사인 거리와 미터 거리를 하나의 점수로 합칠 때는 반드시 정규화한다.

## 참고 자료

- [pgvector — GitHub](https://github.com/pgvector/pgvector)
- [Pedro Alonso — Advanced Search Techniques with pgvector and Geospatial Search](https://www.pedroalonso.net/blog/pgvector-postgres-search/)
- [PostGIS — ST_DWithin 문서](https://postgis.net/docs/ST_DWithin.html)
