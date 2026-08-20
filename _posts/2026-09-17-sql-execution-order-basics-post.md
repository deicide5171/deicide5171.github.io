---
layout: single
title: "SQL 실행 순서가 뭔가요 — WHERE에서 별칭이 안 되는 이유"
date: 2026-09-17 12:35:00 +0530
categories: database
tags: ["실행순서", "sql", "쿼리", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "SELECT가 실제로 실행되는 순서를 이해하면 WHERE에서 별칭을 못 쓰는 이유 등 헷갈리는 규칙이 풀린다는 것을 처음 배우는 사람 기준으로 정리했다."
---

## SQL은 적힌 순서대로 실행되지 않는다

SQL은 `SELECT ... FROM ... WHERE ...` 순으로 적지만, DB는 이 순서대로 실행하지 않는다. 실제 실행 순서를 알면 "WHERE에서 SELECT 별칭이 왜 안 되는지" 같은 헷갈리는 규칙이 이해된다.

## 실제 실행 순서

```text
1. FROM      : 테이블을 정한다
2. WHERE     : 행을 거른다
3. GROUP BY  : 그룹으로 묶는다
4. HAVING    : 그룹을 거른다
5. SELECT    : 컬럼을 고른다(별칭도 여기서 생김)
6. ORDER BY  : 정렬한다
7. LIMIT     : 개수를 자른다
```

## 이걸 알면 풀리는 것

| 궁금증 | 이유 |
|---|---|
| WHERE에서 SELECT 별칭 못 씀 | WHERE(2)가 SELECT(5)보다 먼저 |
| ORDER BY에선 별칭 됨 | ORDER BY(6)가 SELECT(5) 뒤 |
| WHERE엔 집계 조건 못 씀 | 집계는 GROUP BY(3) 이후, WHERE는 그 전 |

## 실무 포인트

- **WHERE엔 별칭 대신 원래 식.** `SELECT price*0.9 AS sale`을 `WHERE sale > 100`으로 못 쓴다. WHERE가 먼저 실행돼 아직 `sale`이 없기 때문이다. `WHERE price*0.9 > 100`처럼 원래 식을 쓰거나 서브쿼리/CTE로 감싼다.
- **집계 조건은 HAVING.** `WHERE COUNT(*) > 5`는 안 된다. 집계는 GROUP BY 이후에 생기므로, 그룹 조건은 `HAVING COUNT(*) > 5`로 쓴다.
- **LIMIT은 정렬 후.** `ORDER BY`로 정렬한 뒤 `LIMIT`으로 자르므로 "상위 10개"가 제대로 나온다. 정렬 없이 LIMIT만 쓰면 어떤 10개가 나올지 보장이 안 된다.

## 마무리 요약

- SQL은 적힌 순서가 아니라 FROM→WHERE→GROUP BY→HAVING→SELECT→ORDER BY→LIMIT 순으로 실행된다.
- 이 순서 때문에 WHERE에선 SELECT 별칭·집계 조건을 못 쓴다.
- WHERE엔 원래 식을, 집계 조건은 HAVING을 쓰고, LIMIT은 ORDER BY 뒤에 적용된다.

## 참고 자료

- [PostgreSQL 공식 문서 - SELECT](https://www.postgresql.org/docs/current/sql-select.html)
