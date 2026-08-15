---
layout: single
title: "벡터 DB 4파전 — Pinecone, Weaviate, Qdrant, pgvector 실무 비교"
date: 2026-08-17 12:50:00 +0530
categories: ai
tags: ["vector-db", "pinecone", "weaviate", "qdrant", "pgvector", "rag"]
toc: true
toc_sticky: true
excerpt: "RAG·시맨틱 검색 도입 시 가장 먼저 부딪히는 선택지인 Pinecone, Weaviate, Qdrant, pgvector를 배포 형태·인덱스·필터링·운영 부담 기준으로 비교한다."
---

## 왜 지금 벡터 DB 선택이 고민거리인가

RAG나 시맨틱 검색을 붙이기로 결정하면 곧바로 다음 질문이 따라온다. "임베딩을 어디에 저장하고 어떻게 검색할 것인가." 예전에는 선택지가 많지 않았지만, 지금은 완전관리형 서비스부터 오픈소스 전용 엔진, 기존 RDB에 얹는 확장까지 성격이 전혀 다른 옵션들이 공존한다. 이 선택은 이후 인프라 구조와 운영 비용을 상당 기간 좌우한다.

이 글에서는 실무에서 자주 비교 대상에 오르는 네 가지 — **Pinecone, Weaviate, Qdrant, pgvector** — 를 배포 형태, 인덱스 구조, 필터링·하이브리드 검색 지원, 운영 부담이라는 네 축으로 나눠 정리한다. "어떤 게 제일 빠른가"보다 "우리 상황에서 어떤 게 덜 골치 아픈가"에 초점을 맞춘다.

<img src="/assets/images/posts/2026-08-17-vector-db-comparison-1.svg" alt="벡터 DB 선택 흐름도 - 기존 인프라, 하이브리드 검색 요구, 운영 인력 기준으로 Pinecone, Weaviate, Qdrant, pgvector를 분기하는 의사결정 트리" style="width:100%;">

## 핵심 개념 1: 네 가지 옵션의 성격 차이

네 가지는 같은 카테고리로 묶기 애매할 만큼 성격이 다르다. Pinecone은 처음부터 벡터 검색 전용으로 설계된 완전관리형 서비스라 인프라를 직접 운영할 필요가 없다. Weaviate와 Qdrant는 오픈소스 벡터 DB로, 자체 호스팅과 관리형 클라우드를 모두 선택할 수 있다. pgvector는 벡터 DB라기보다 **PostgreSQL에 벡터 타입과 인덱스를 추가하는 확장**에 가까워, 이미 Postgres를 쓰는 팀이라면 별도 인프라 없이 시작할 수 있다.

| 항목 | Pinecone | Weaviate | Qdrant | pgvector |
|---|---|---|---|---|
| 배포 형태 | 완전관리형 전용 | 오픈소스 + 관리형 | 오픈소스 + 관리형 | Postgres 확장 |
| 구현 언어 | 비공개 | Go | Rust | C (Postgres 내장) |
| 자체 호스팅 | 불가 | 가능 | 가능 | 가능(기존 Postgres) |
| API 형태 | REST/SDK | GraphQL/REST/gRPC | REST/gRPC | SQL |

## 핵심 개념 2: 인덱스와 필터링·하이브리드 검색

벡터 검색은 대부분 HNSW(그래프 기반) 계열 근사 최근접 이웃(ANN) 인덱스를 쓴다는 점에서 네 옵션이 크게 다르지 않다. 차이가 갈리는 지점은 **메타데이터 필터링과 벡터 검색을 얼마나 자연스럽게 결합하느냐**, 그리고 **키워드 검색(BM25)과의 하이브리드 지원 여부**다.

| 항목 | Pinecone | Weaviate | Qdrant | pgvector |
|---|---|---|---|---|
| 기본 인덱스 | 관리형(내부 최적화) | HNSW | HNSW | IVFFlat / HNSW |
| 메타데이터 필터링 | 지원(사전 필터) | 지원 | 지원(강점으로 언급됨) | SQL WHERE 그대로 활용 |
| 하이브리드 검색(BM25+벡터) | 제한적 | 네이티브 지원 | 지원 | 별도 조합 필요(FTS+벡터) |
| 트랜잭션·조인 | 없음 | 없음 | 없음 | Postgres 트랜잭션·조인 그대로 |

pgvector의 가장 큰 차별점은 벡터 검색이 **관계형 데이터와 같은 트랜잭션 경계 안에** 들어온다는 것이다. 주문·권한 같은 데이터와 임베딩을 조인해 한 번에 쿼리할 수 있다. 반대로 Weaviate와 Qdrant는 검색 기능(하이브리드, 필터 성능) 자체에 더 특화되어 있고, Pinecone은 운영 부담 최소화를 우선한 형태다.

## 예제 1: pgvector — 기존 Postgres에 벡터 검색 추가하기

```sql
-- 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    department TEXT,
    embedding VECTOR(1536)
);

-- HNSW 인덱스 생성
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);

-- 필터 + 벡터 검색을 한 쿼리로
SELECT id, content
FROM documents
WHERE department = 'legal'
ORDER BY embedding <=> '[0.012, -0.034, ...]'
LIMIT 5;
```

기존 스키마에 컬럼과 인덱스 하나만 추가하면 되므로, 별도 벡터 DB 없이도 검색 프로토타입을 빠르게 붙여볼 수 있다.

## 예제 2: Qdrant — 필터 조건을 포함한 벡터 검색

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url="http://localhost:6333")

results = client.search(
    collection_name="documents",
    query_vector=embedding_vector,
    query_filter=Filter(
        must=[FieldCondition(key="department", match=MatchValue(value="legal"))]
    ),
    limit=5,
)
```

Qdrant와 Weaviate는 이런 payload 필터를 벡터 검색과 결합하는 API가 처음부터 1급 기능으로 설계되어, 필터 조건이 복잡해질수록 전용 벡터 DB 쪽이 다루기 편해지는 경향이 있다.

## 실무 포인트

- **Postgres를 이미 쓰고 데이터 규모가 크지 않다면 pgvector부터 검토한다.** 별도 인프라 없이 시작할 수 있고, 관계형 데이터와의 조인이 필요한 서비스에 특히 유리하다.
- **하이브리드 검색이 핵심 요구사항이면 Weaviate·Qdrant가 더 자연스럽다.** BM25와 벡터 결합을 애플리케이션 레벨에서 직접 구현하지 않아도 되는 경우가 많다.
- **운영 인력을 최소화하려면 완전관리형(Pinecone, 또는 나머지의 관리형 클라우드)을 우선 고려한다.** 다만 벤더 종속과 데이터 리전 제약은 계약 전에 확인해야 한다.
- **비용·성능 수치는 이 글에서 단정하지 않는다.** 과금 체계와 인스턴스 비용은 시점·사용량에 따라 달라지므로, 각 서비스의 최신 공식 문서로 직접 확인하는 것이 안전하다.
- **임베딩 모델 교체 시 재인덱싱 비용을 초기 설계에 포함한다.**

## 3줄 요약

- Pinecone·Weaviate·Qdrant·pgvector는 "더 빠른 벡터 DB"가 아니라 배포 형태와 운영 철학이 서로 다른 선택지다.
- 관계형 데이터와의 조인이 중요하면 pgvector, 하이브리드 검색과 필터 성능이 중요하면 Weaviate/Qdrant, 운영 부담 최소화가 우선이면 완전관리형이 출발점으로 적합하다.
- 비용·성능 수치는 서비스별 최신 문서로 직접 확인하고, 임베딩 모델 교체 시 재인덱싱 비용까지 초기 설계에 포함해야 한다.

## 참고 자료

- [Pinecone 공식 문서](https://docs.pinecone.io/)
- [Weaviate 공식 문서](https://weaviate.io/developers/weaviate)
- [Qdrant 공식 문서](https://qdrant.tech/documentation/)
- [pgvector GitHub 저장소](https://github.com/pgvector/pgvector)
