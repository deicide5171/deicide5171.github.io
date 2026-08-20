---
layout: single
title: "CTE(WITH)가 뭔가요 — 복잡한 쿼리를 읽기 쉽게 나누기"
date: 2026-09-15 12:35:00 +0530
categories: database
tags: ["cte", "with", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "중첩 서브쿼리로 복잡해진 SQL을 단계별로 이름 붙여 정리하는 CTE(WITH 절)의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 서브쿼리가 겹겹이 쌓여 읽기 힘들다

서브쿼리 안에 서브쿼리가 중첩되면 SQL이 괄호 지옥이 되어 읽기 어렵다. **CTE(Common Table Expression)**는 **`WITH` 절로 중간 결과에 이름을 붙여** 쿼리를 단계별로 정리하는 기능이다. 프로그래밍에서 긴 식을 변수로 나누는 것과 비슷하다.

## 서브쿼리 vs CTE

```sql
-- 서브쿼리(중첩): 읽기 어려움
SELECT * FROM (SELECT category, AVG(price) avg_p FROM products GROUP BY category) t
WHERE t.avg_p > 1000;

-- CTE: 단계로 나눠 읽기 쉬움
WITH cat_avg AS (
  SELECT category, AVG(price) AS avg_p
  FROM products GROUP BY category
)
SELECT * FROM cat_avg WHERE avg_p > 1000;
```

`WITH 이름 AS (쿼리)`로 정의하고, 아래에서 그 이름을 테이블처럼 쓴다.

## 장점

| 장점 | 설명 |
|---|---|
| 가독성 | 단계마다 이름을 붙여 흐름이 보임 |
| 재사용 | 한 CTE를 쿼리에서 여러 번 참조 |
| 재귀 | `WITH RECURSIVE`로 계층 조회 |

## 실무 포인트

- **복잡한 쿼리를 단계로 쪼개라.** 여러 집계·조인이 얽힌 쿼리를 CTE로 "1단계 집계 → 2단계 필터 → 3단계 조인"처럼 나누면 훨씬 읽기 쉽고 디버깅도 편하다.
- **재귀 CTE로 계층을 탄다.** `WITH RECURSIVE`는 "상사의 상사의..."처럼 계층을 반복해 타고 올라가는 조회를 가능하게 한다. 조직도·카테고리 트리·댓글 스레드에 유용하다.
- **성능은 상황에 따라.** CTE가 항상 빠른 건 아니다. DB에 따라 CTE를 최적화 경계로 취급해 느려질 수도 있으니, 성능이 중요하면 `EXPLAIN`으로 실행 계획을 확인한다.

## 마무리 요약

- CTE(WITH)는 중간 결과에 이름을 붙여 복잡한 쿼리를 단계별로 정리하는 기능이다.
- 중첩 서브쿼리보다 읽기 쉽고, 한 CTE를 여러 번 참조하거나 재귀 조회에 쓸 수 있다.
- 가독성·디버깅에 좋지만 성능은 상황에 따라 다르니 `EXPLAIN`으로 확인한다.

## 참고 자료

- [PostgreSQL 공식 문서 - WITH Queries](https://www.postgresql.org/docs/current/queries-with.html)
