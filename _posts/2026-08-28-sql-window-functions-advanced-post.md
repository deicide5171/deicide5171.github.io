---
layout: single
title: "서브쿼리 지옥에서 벗어나기 — SQL 윈도우 함수 고급 패턴"
date: 2026-08-28 12:35:00 +0530
categories: database
tags: ["database", "sql", "window-function", "query-optimization", "postgresql"]
toc: true
toc_sticky: true
excerpt: "순위, 이동평균, 전월 대비 증감처럼 상관 서브쿼리와 자기 조인으로 억지로 풀던 문제를 SQL 윈도우 함수의 프레임과 파티션 개념으로 단순하고 빠르게 다시 쓰는 방법을 정리한다."
---

"사용자별 최근 3개 주문의 평균 금액", "전월 대비 매출 증감률", "부서 내 급여 순위" 같은 요구사항을 GROUP BY만으로 풀려고 하면 곧바로 한계에 부딪힌다. GROUP BY는 여러 행을 하나로 뭉개기 때문에, 뭉개지기 전 개별 행의 값을 그대로 유지하면서 동시에 그룹 단위 계산도 함께 보고 싶다는 요구를 표현할 수 없다. 그래서 흔히 상관 서브쿼리(correlated subquery)나 같은 테이블을 여러 번 조인하는 자기 조인으로 우회하는데, 이 방식은 코드가 급격히 복잡해지고 각 행마다 서브쿼리가 재실행되어 성능도 떨어진다.

윈도우 함수(window function)는 이 문제를 정면으로 해결하기 위해 SQL 표준(SQL:2003)에 추가된 기능이다. `GROUP BY`처럼 행을 하나로 합치지 않으면서도, 지정한 행 집합(윈도우) 안에서 순위·누적합·이전 행 값 같은 계산을 각 행에 붙여서 반환한다. 이 글에서는 윈도우 함수의 핵심 구성 요소인 `PARTITION BY`·`ORDER BY`·프레임(frame)을 정리하고, 실무에서 자주 쓰는 고급 패턴 몇 가지를 코드로 살펴본다.

## 핵심 개념 1: PARTITION BY와 ORDER BY — GROUP BY와의 결정적 차이

윈도우 함수의 기본 문법은 `함수(...) OVER (PARTITION BY 그룹기준 ORDER BY 정렬기준)`다. `PARTITION BY`는 `GROUP BY`처럼 데이터를 그룹으로 나누지만, 그룹으로 나눈 뒤에도 **각 행을 그대로 유지한 채** 그 그룹 안에서의 계산 결과만 각 행에 덧붙인다는 점이 다르다. `ORDER BY`는 그 그룹 내부의 행 순서를 정하며, `RANK()`·`ROW_NUMBER()`처럼 순서에 의존하는 함수나 누적합처럼 순서대로 계산이 쌓이는 함수에 필수다.

| 구분 | GROUP BY | 윈도우 함수 (OVER) |
|---|---|---|
| 결과 행 수 | 그룹 수만큼으로 줄어듦 | 원본 행 수 그대로 유지 |
| 개별 행 값 접근 | 불가능(집계값만 남음) | 가능(그룹 계산값을 각 행에 덧붙임) |
| 같은 쿼리에서 원본 컬럼과 집계값 동시 사용 | 서브쿼리·조인 필요 | 바로 가능 |

## 핵심 개념 2: 순위 함수 3형제 — ROW_NUMBER, RANK, DENSE_RANK

동점 처리 방식만 다른 세 함수를 혼동하면 "1등이 두 명인데 다음 등수가 몇 번이어야 하는가"에서 의도와 다른 결과가 나온다. `ROW_NUMBER()`는 동점이어도 무조건 순차 번호(1,2,3,4...)를 매기고, `RANK()`는 동점에 같은 등수를 준 뒤 다음 등수를 건너뛰며(1,1,3,4...), `DENSE_RANK()`는 동점에 같은 등수를 주되 다음 등수를 건너뛰지 않는다(1,1,2,3...). "부서별 급여 상위 3명"처럼 정확히 N개 행만 필요하면 `ROW_NUMBER()`가 맞고, "동점자를 모두 포함한 상위 3위 그룹"이 필요하면 `RANK()`가 맞다.

## 핵심 개념 3: 프레임(frame) — 이동평균과 누적합의 핵심

프레임은 `ORDER BY`로 정해진 순서 안에서 "현재 행 기준으로 어디부터 어디까지를 계산에 포함할지"를 지정하는 절이다. 기본값은 `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`로, 첫 행부터 현재 행까지의 누적 계산이다. 이동평균처럼 "최근 N개 행"이 필요하면 `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`처럼 물리적 행 개수 기준 프레임을 명시해야 한다. `RANGE`와 `ROWS`의 차이도 중요한데, `RANGE`는 `ORDER BY` 값이 같은 행들을 하나로 묶어 처리하고 `ROWS`는 값 동일 여부와 무관하게 물리적 행 순서로만 센다 — 동점 값이 있는 데이터에서 둘의 결과가 달라질 수 있다.

<img src="/assets/images/posts/2026-08-28-sql-window-functions-advanced-1.svg" alt="ORDER BY로 정렬된 행 위에서 현재 행을 기준으로 프레임 범위가 이동하며 이동평균을 계산하는 구조" style="width:100%;">

## 예제: 상관 서브쿼리를 윈도우 함수로 바꾸기

```sql
-- Before: 사용자별 최근 3개 주문 평균을 상관 서브쿼리로 (행마다 서브쿼리 재실행)
SELECT o.order_id, o.user_id, o.amount, o.ordered_at,
  (SELECT avg(o2.amount)
   FROM orders o2
   WHERE o2.user_id = o.user_id
     AND o2.ordered_at <= o.ordered_at
   ORDER BY o2.ordered_at DESC
   LIMIT 3) AS recent_avg
FROM orders o;

-- After: 윈도우 함수로 한 번의 스캔 + 정렬로 계산
SELECT
  order_id, user_id, amount, ordered_at,
  avg(amount) OVER (
    PARTITION BY user_id
    ORDER BY ordered_at
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
  ) AS recent_avg,
  amount - lag(amount) OVER (PARTITION BY user_id ORDER BY ordered_at) AS diff_from_prev,
  rank() OVER (PARTITION BY user_id ORDER BY amount DESC) AS amount_rank
FROM orders;
```

`lag()`는 파티션 내에서 현재 행 기준 이전 N번째 행의 값을 가져오는 함수로, 전월 대비 증감처럼 "이전 시점과 비교" 패턴에 정확히 맞는다. 반대 방향은 `lead()`다. 상관 서브쿼리 버전은 행마다 서브쿼리 플래너가 별도로 계산을 반복하지만, 윈도우 함수 버전은 대부분 한 번의 정렬된 스캔으로 처리되어 실행 계획이 훨씬 단순해진다.

## 실무 포인트

- **프레임을 생략하면 기본값 함정에 빠질 수 있다**: `ORDER BY`만 쓰고 프레임을 명시하지 않으면 기본 프레임이 적용되는데, 이는 함수마다 다르게 동작할 수 있어(`sum()`은 누적합이 기본이지만 원하는 게 전체 합계라면 프레임을 명시적으로 지워야 한다) 의도와 다른 결과가 나오기 쉽다. 누적 계산이 아니라면 `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`을 명시하는 습관을 들인다.
- **윈도우 함수는 WHERE 절에서 바로 못 쓴다**: 윈도우 함수는 `SELECT`·`ORDER BY` 단계에서 평가되므로 `WHERE rank() = 1`처럼 바로 필터링할 수 없다. 서브쿼리나 `WITH` 절로 감싼 뒤 바깥 쿼리에서 필터링해야 한다.
- **`EXPLAIN`으로 Sort 비용을 확인할 것**: `PARTITION BY`·`ORDER BY`가 많아지면 내부적으로 여러 번의 정렬이 필요할 수 있다. 여러 윈도우 함수가 같은 `PARTITION BY`/`ORDER BY`를 공유하도록 통일하면 옵티마이저가 정렬을 재사용할 여지가 커진다.

## 3줄 요약

- 윈도우 함수는 GROUP BY와 달리 행을 뭉개지 않고 각 행에 그룹 단위 계산 결과를 덧붙여, 원본 컬럼과 집계값을 한 쿼리에서 동시에 다룰 수 있게 한다.
- `ROW_NUMBER`·`RANK`·`DENSE_RANK`는 동점 처리 방식이 다르므로 요구사항에 맞는 함수를 골라야 하고, 이동평균·누적합에는 프레임(ROWS/RANGE)을 명시적으로 지정해야 한다.
- 상관 서브쿼리나 자기 조인으로 짜던 순위·누적·전 행 비교 로직은 대부분 윈도우 함수로 더 짧고 빠르게 다시 쓸 수 있다.

## 참고 자료

- [PostgreSQL 공식 문서: Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html)
- [PostgreSQL 공식 문서: Window Function Calls](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS)
- [MySQL 공식 문서: Window Function Concepts and Syntax](https://dev.mysql.com/doc/refman/8.4/en/window-function-concepts.html)
