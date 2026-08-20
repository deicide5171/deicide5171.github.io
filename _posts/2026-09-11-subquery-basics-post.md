---
layout: single
title: "서브쿼리가 뭔가요 — 쿼리 안에 들어가는 또 하나의 쿼리"
date: 2026-09-11 12:35:00 +0530
categories: database
tags: ["서브쿼리", "subquery", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "SQL 쿼리 안에 중첩되는 서브쿼리의 개념과 자주 쓰는 형태, 성능 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## "평균보다 비싼 상품"을 한 번에 구하려면

"평균 가격보다 비싼 상품"을 찾으려면, 먼저 평균 가격을 구하고 그 값으로 다시 조회해야 한다. 이 두 단계를 **하나의 쿼리 안에** 넣을 수 있다. **서브쿼리(subquery)**는 **다른 쿼리 안에 중첩된 SELECT 문**이다. 안쪽 쿼리 결과를 바깥 쿼리가 사용한다.

## 예시

```sql
-- 평균 가격보다 비싼 상품
SELECT name, price
FROM products
WHERE price > (SELECT AVG(price) FROM products);
```

괄호 안 `(SELECT AVG(price) ...)`가 서브쿼리다. 먼저 평균을 구하고, 바깥 쿼리가 그 값과 비교한다.

## 서브쿼리가 쓰이는 자리

| 위치 | 예 |
|---|---|
| WHERE 절 | `WHERE price > (SELECT ...)` |
| FROM 절 | `FROM (SELECT ...) AS t` (인라인 뷰) |
| SELECT 절 | `SELECT (SELECT COUNT(*) ...) AS cnt` |
| IN과 함께 | `WHERE id IN (SELECT ...)` |

## 실무 포인트

- **JOIN으로 바꾸는 게 빠를 때가 많다.** 특히 `IN (서브쿼리)`는 데이터가 크면 느릴 수 있다. 같은 결과를 JOIN으로 표현하면 옵티마이저가 더 잘 최적화하는 경우가 많으니, 느리면 JOIN 대안을 검토한다.
- **상관 서브쿼리를 조심하라.** 바깥 행마다 안쪽 쿼리가 반복 실행되는 형태(상관 서브쿼리)는 행 수만큼 실행되어 매우 느릴 수 있다. `EXPLAIN`으로 실행 계획을 확인한다.
- **가독성과 성능의 균형.** 서브쿼리는 로직을 직관적으로 표현하지만 중첩이 깊으면 읽기 어렵다. 복잡하면 CTE(`WITH`)로 단계를 나눠 이름을 붙이면 읽기 쉽다.

## 마무리 요약

- 서브쿼리는 다른 쿼리 안에 중첩된 SELECT로, 안쪽 결과를 바깥 쿼리가 사용한다.
- WHERE·FROM·SELECT·IN 등 여러 자리에 쓸 수 있다.
- 큰 데이터에선 JOIN이 빠를 수 있고, 상관 서브쿼리는 느릴 수 있으니 `EXPLAIN`으로 확인한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Subqueries](https://www.postgresql.org/docs/current/functions-subquery.html)
