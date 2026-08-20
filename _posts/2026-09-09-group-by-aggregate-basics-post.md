---
layout: single
title: "GROUP BY와 집계 함수가 뭔가요 — 데이터를 묶어서 세기"
date: 2026-09-09 12:35:00 +0530
categories: database
tags: ["groupby", "집계함수", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "SQL에서 데이터를 그룹으로 묶어 개수·합계·평균을 구하는 GROUP BY와 집계 함수의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "카테고리별 주문 수"를 어떻게 구하나

전체 주문을 하나하나 세지 않고 "카테고리별로 몇 건인지"를 한 번에 구하고 싶다면 **GROUP BY**를 쓴다. GROUP BY는 **같은 값끼리 행을 묶고**, `COUNT`·`SUM`·`AVG` 같은 **집계 함수(aggregate function)**로 각 그룹의 통계를 계산한다.

## 자주 쓰는 집계 함수

| 함수 | 의미 |
|---|---|
| `COUNT(*)` | 행 개수 |
| `SUM(컬럼)` | 합계 |
| `AVG(컬럼)` | 평균 |
| `MAX` / `MIN` | 최댓값 / 최솟값 |

## 예제

```sql
-- 카테고리별 주문 건수와 평균 금액
SELECT category,
       COUNT(*)      AS 주문수,
       AVG(amount)   AS 평균금액
FROM orders
GROUP BY category;
```

`GROUP BY category`로 같은 카테고리끼리 묶고, 각 그룹에서 행 수(`COUNT`)와 평균(`AVG`)을 계산한다. 결과는 카테고리마다 한 줄씩 나온다.

## WHERE와 HAVING의 차이

```text
WHERE  : 그룹으로 묶기 "전"에 개별 행을 거른다.
HAVING : 그룹으로 묶은 "후"에 그룹을 거른다.

예) 주문 10건 이상인 카테고리만:
GROUP BY category HAVING COUNT(*) >= 10
```

## 실무 포인트

- **SELECT에는 GROUP BY 컬럼과 집계 함수만 넣어라.** 그룹으로 묶지 않은 일반 컬럼을 SELECT에 넣으면 "어느 행의 값을 보여줄지" 모호해 오류가 나거나 예상 밖 결과가 나온다.
- **조건 위치를 헷갈리지 마라.** 개별 행을 거를 땐 `WHERE`, 그룹 결과를 거를 땐 `HAVING`이다. `COUNT(*) >= 10` 같은 집계 조건은 `WHERE`에 못 쓰고 `HAVING`에 써야 한다.
- **GROUP BY 컬럼에 인덱스가 있으면 빠르다.** 대량 데이터를 그룹핑할 때 해당 컬럼에 인덱스가 있으면 정렬·그룹 비용이 줄어든다. 느리면 `EXPLAIN`으로 확인한다.

## 마무리 요약

- GROUP BY는 같은 값끼리 행을 묶고, 집계 함수로 각 그룹의 개수·합계·평균 등을 구한다.
- WHERE는 묶기 전 개별 행을, HAVING은 묶은 후 그룹을 거른다.
- SELECT에는 그룹 컬럼과 집계 함수만 넣어야 하며, 그룹 컬럼 인덱스가 성능에 도움 된다.

## 참고 자료

- [PostgreSQL 공식 문서 - GROUP BY](https://www.postgresql.org/docs/current/tutorial-agg.html)
