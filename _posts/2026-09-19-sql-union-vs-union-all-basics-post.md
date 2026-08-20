---
layout: single
title: "UNION과 UNION ALL 차이가 뭔가요 — 결과 합칠 때 주의점"
date: 2026-09-19 13:35:00 +0530
categories: database
tags: ["sql", "union", "union-all", "중복제거", "입문"]
toc: true
toc_sticky: true
excerpt: "두 쿼리 결과를 세로로 합치는 UNION과 UNION ALL의 차이, 그리고 성능 함정을 처음 배우는 사람 기준으로 정리했다."
---

## "두 테이블 결과를 하나로 합치고 싶다"

올해 주문과 작년 주문처럼 구조가 같은 두 결과를 세로로 이어 붙이고 싶을 때 **UNION**을 쓴다. 그런데 `UNION`과 `UNION ALL`은 결과가 다를 수 있다. 차이는 **중복 제거 여부**다.

## 두 방식의 차이

```sql
-- UNION: 합친 뒤 중복 행을 제거
SELECT name FROM customer_2025
UNION
SELECT name FROM customer_2026;

-- UNION ALL: 중복 제거 없이 그대로 합침
SELECT name FROM customer_2025
UNION ALL
SELECT name FROM customer_2026;
```

| 구분 | 중복 처리 | 속도 |
|---|---|---|
| UNION | 중복 행 제거 | 느림(정렬·비교 필요) |
| UNION ALL | 그대로 다 합침 | 빠름 |

## 왜 UNION이 느린가

UNION은 중복을 없애기 위해 내부적으로 전체 결과를 정렬하거나 해시해서 비교한다. 데이터가 많으면 이 과정이 큰 비용이 된다. UNION ALL은 그냥 이어 붙이므로 그 비용이 없다.

## 실무 포인트

- **중복이 없다고 확신하면 UNION ALL.** 두 결과가 겹칠 일이 없거나, 중복이 있어도 괜찮다면 UNION ALL이 훨씬 빠르다.
- **습관적으로 UNION 쓰지 마라.** "그냥 합치기"인데 UNION을 쓰면 불필요한 중복 제거 비용을 매번 낸다. 기본을 UNION ALL로 두고 필요할 때만 UNION.
- **컬럼 개수·타입을 맞춰라.** 두 SELECT의 컬럼 수와 순서, 타입이 호환돼야 한다. 안 맞으면 에러가 난다.

## 마무리 요약

- UNION은 합친 뒤 중복을 제거하고, UNION ALL은 중복 제거 없이 그대로 합친다.
- 중복 제거 때문에 UNION이 더 느리다.
- 중복이 문제없다면 UNION ALL이 성능상 유리하며, 컬럼 수·타입은 맞춰야 한다.

## 참고 자료

- [PostgreSQL 문서 - UNION](https://www.postgresql.org/docs/current/queries-union.html)
