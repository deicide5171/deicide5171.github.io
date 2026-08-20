---
layout: single
title: "UPSERT가 뭔가요 — 있으면 수정, 없으면 삽입 한 번에"
date: 2026-09-10 13:35:00 +0530
categories: database
tags: ["upsert", "sql", "onconflict", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "데이터가 있으면 UPDATE, 없으면 INSERT를 한 문장으로 처리하는 UPSERT의 개념과 DB별 문법을 처음 배우는 사람 기준으로 정리했다."
---

## "있으면 수정, 없으면 삽입"을 어떻게 하나

조회수 카운트를 저장한다고 하자. 해당 글의 행이 있으면 +1(UPDATE), 없으면 새로 만들어야(INSERT) 한다. 이걸 "먼저 조회 → 있으면 UPDATE, 없으면 INSERT"로 나눠 하면 코드도 길고, 그 사이에 동시 요청이 끼면 충돌한다. **UPSERT**는 이 **"있으면 수정, 없으면 삽입"을 한 문장으로** 처리한다(UPDATE + INSERT).

## DB별 문법

| DB | 문법 |
|---|---|
| PostgreSQL | `INSERT ... ON CONFLICT ... DO UPDATE` |
| MySQL | `INSERT ... ON DUPLICATE KEY UPDATE` |
| 표준 SQL | `MERGE` |

## 예시 (PostgreSQL)

```sql
INSERT INTO page_views (page_id, views)
VALUES (10, 1)
ON CONFLICT (page_id)
DO UPDATE SET views = page_views.views + 1;
```

`page_id=10`이 없으면 새로 넣고(views=1), 이미 있으면 기존 views에 +1 한다. 한 문장으로 끝난다.

## 실무 포인트

- **고유 제약(UNIQUE)이 있어야 동작한다.** "충돌"을 판단할 기준 키(기본키나 UNIQUE 인덱스)가 있어야 한다. 이 제약이 없으면 UPSERT는 "충돌"을 감지하지 못해 항상 INSERT만 한다.
- **경쟁 조건에 안전하다.** "조회 후 분기" 방식은 조회와 저장 사이에 다른 요청이 끼면 중복 삽입 오류가 난다. UPSERT는 DB가 원자적으로 처리하므로 동시 요청에도 안전하다.
- **DB마다 문법·동작이 다르다.** PostgreSQL의 `ON CONFLICT`, MySQL의 `ON DUPLICATE KEY`는 세부 동작이 다르다. 트리거·리턴값·잠금 방식 차이가 있으니 쓰는 DB의 문서를 확인한다.

## 마무리 요약

- UPSERT는 "있으면 UPDATE, 없으면 INSERT"를 한 문장으로 처리한다.
- PostgreSQL은 `ON CONFLICT DO UPDATE`, MySQL은 `ON DUPLICATE KEY UPDATE`를 쓴다.
- 충돌 기준이 될 UNIQUE 제약이 필요하며, 조회-분기 방식보다 동시 요청에 안전하다.

## 참고 자료

- [PostgreSQL 공식 문서 - INSERT ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
