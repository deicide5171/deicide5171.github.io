---
layout: single
title: "MySQL vs PostgreSQL, 새 프로젝트엔 뭘 써야 할까 — 실무 선택 기준"
date: 2026-08-31 12:35:00 +0530
categories: database
tags: ["mysql", "postgresql", "비교", "입문", "데이터베이스선택"]
toc: true
toc_sticky: true
excerpt: "신규 프로젝트에서 MySQL과 PostgreSQL 중 무엇을 선택해야 할지, 기능·생태계·운영 관점에서 실무 기준으로 비교한다."
---

## 왜 아직도 이 질문이 반복되는가

새 프로젝트를 시작할 때마다 "MySQL이냐 PostgreSQL이냐"는 질문이 다시 등장한다. 둘 다 오픈소스 RDBMS로 무료이고, 웬만한 CRUD 서비스에는 어느 쪽을 써도 큰 문제가 없기 때문에 오히려 결정이 더 어렵게 느껴진다. 이 글은 "정답은 없다"는 뻔한 결론 대신, 어떤 기준으로 판단하면 되는지를 구체적으로 정리했다.

## 핵심 차이 비교

| 항목 | MySQL | PostgreSQL |
|---|---|---|
| 기본 철학 | 단순함, 빠른 읽기 성능 중심 | 표준 SQL 준수, 기능 풍부함 |
| 데이터 타입 | 기본 타입 위주 | JSONB, 배열, 사용자 정의 타입 등 풍부 |
| 인덱스 | B-Tree, Full-text 중심 | B-Tree·GiST·GIN·BRIN 등 다양 |
| 복제·확장 생태계 | 성숙(그룹 복제, ProxySQL) | 성숙(논리적 복제, Citus, PgBouncer) |
| 클라우드 매니지드 | RDS, Aurora MySQL 등 폭넓음 | RDS, Aurora PostgreSQL, Supabase 등 폭넓음 |
| 대표 채택 사례 | 전통적 웹 서비스, WordPress 계열 | 복잡한 쿼리·분석 워크로드, GIS(PostGIS) |

## 판단 흐름

```text
1. 팀에 이미 익숙한 DB가 있는가?
   → 있으면 특별한 이유가 없는 한 그대로 간다 (러닝커브가 가장 큰 비용이다)

2. JSON 필드를 관계형 데이터처럼 쿼리해야 하는가?
   → PostgreSQL의 JSONB + GIN 인덱스가 훨씬 강력하다

3. 공간 데이터(GIS)를 다루는가?
   → PostGIS 확장이 있는 PostgreSQL이 사실상 표준이다

4. 매우 단순한 CRUD + 읽기 위주 워크로드인가?
   → MySQL도 충분하고 관리형 서비스 선택지가 더 다양할 수 있다
```

## 코드로 보는 차이 한 가지: UPSERT 문법

```sql
-- MySQL
INSERT INTO users (id, name) VALUES (1, 'Kim')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- PostgreSQL
INSERT INTO users (id, name) VALUES (1, 'Kim')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
```

문법 하나만 봐도 마이그레이션이 생각보다 손이 많이 간다는 걸 알 수 있다. 이런 사소한 차이가 나중에 DB를 바꾸기 어렵게 만드는 락인 요소가 된다.

## 실무 포인트

- **트랜잭션 격리수준의 기본값이 다르다.** MySQL(InnoDB)은 기본이 REPEATABLE READ, PostgreSQL은 READ COMMITTED다. 동시성 버그를 옮길 때 반드시 확인해야 한다.
- **PostgreSQL은 확장(extension) 생태계가 강점이다.** pgvector로 벡터 검색, PostGIS로 공간 쿼리, TimescaleDB로 시계열까지 하나의 DB로 확장할 수 있다.
- **MySQL은 복제와 운영 도구가 오래되고 검증된 편이라 대규모 트래픽 서비스에서 축적된 노하우가 많다.**

## 마무리 요약

- 팀의 기존 경험이 가장 큰 결정 요인이며, 특별한 이유 없이는 익숙한 쪽을 택하는 것이 합리적이다.
- 반정형 데이터·복잡한 쿼리·GIS가 필요하면 PostgreSQL이 유리하다.
- 단순 CRUD 위주라면 MySQL도 충분하며 관리형 서비스 선택지가 넓다.

## 참고 자료

- [PostgreSQL 공식 문서](https://www.postgresql.org/docs/)
- [MySQL 공식 문서](https://dev.mysql.com/doc/)
