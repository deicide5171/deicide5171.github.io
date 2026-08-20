---
layout: single
title: "WHERE에 함수 쓰면 인덱스가 안 탄다 — sargable 이해하기"
date: 2026-09-18 13:35:00 +0530
categories: database
tags: ["인덱스", "sargable", "sql", "성능", "입문"]
toc: true
toc_sticky: true
excerpt: "인덱스를 걸어도 WHERE에서 컬럼에 함수를 쓰면 왜 인덱스를 못 타는지, 어떻게 고치는지 처음 배우는 사람 기준으로 정리했다."
---

## 인덱스를 걸었는데 왜 느릴까

`created_at` 컬럼에 인덱스를 걸었는데도 조회가 느리다. 원인은 종종 **WHERE에서 인덱스 컬럼을 함수로 감싸기** 때문이다. 인덱스는 "컬럼의 원래 값" 순으로 정렬돼 있어, 컬럼을 가공하면 인덱스를 못 쓴다.

## 안 되는 경우 vs 되는 경우

```sql
-- 인덱스 못 탐: 컬럼을 함수로 감쌈
WHERE DATE(created_at) = '2026-09-18'
WHERE YEAR(created_at) = 2026
WHERE price * 2 > 1000

-- 인덱스 탈 수 있음: 컬럼은 그대로, 값을 가공
WHERE created_at >= '2026-09-18' AND created_at < '2026-09-19'
WHERE price > 500
```

## 왜 그런가 (sargable)

```text
인덱스는 컬럼의 원래 값으로 정렬돼 있다.
컬럼에 함수를 씌우면(DATE(col)) -> 원래 값 순서가 깨져
  모든 행을 함수 적용해봐야 함 -> 인덱스 무용
"인덱스를 탈 수 있는 조건"을 sargable하다고 한다.
```

## 실무 포인트

- **컬럼은 그대로, 값을 가공하라.** `DATE(created_at) = '오늘'` 대신 범위 조건(`>= 오늘 AND < 내일`)으로 바꾸면 인덱스를 탄다. 함수는 컬럼이 아니라 비교 대상 값 쪽에 적용한다.
- **함수 기반 인덱스도 있다.** 꼭 `LOWER(email)`처럼 함수를 써야 한다면, 그 함수 결과에 대한 **함수 기반 인덱스**를 만들 수 있다(PostgreSQL 등). 그러면 함수를 써도 인덱스를 탄다.
- **EXPLAIN으로 확인하라.** 인덱스를 타는지 아닌지는 `EXPLAIN`으로 실행 계획을 보면 안다. "Seq Scan/Full Table Scan"이 나오면 인덱스를 못 타는 것이니 조건을 sargable하게 고친다.

## 마무리 요약

- WHERE에서 인덱스 컬럼을 함수로 감싸면(`DATE(col)`) 인덱스를 못 타 느려진다.
- 컬럼은 그대로 두고 비교 값을 가공(범위 조건)하면 인덱스를 탄다(sargable).
- 함수가 꼭 필요하면 함수 기반 인덱스를 만들고, `EXPLAIN`으로 인덱스 사용을 확인한다.

## 참고 자료

- [Use The Index, Luke - Functions](https://use-the-index-luke.com/sql/where-clause/functions)
