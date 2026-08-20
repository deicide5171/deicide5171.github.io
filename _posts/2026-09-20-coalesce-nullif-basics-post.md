---
layout: single
title: "SQL COALESCE와 NULLIF가 뭔가요 — NULL 다루는 두 함수"
date: 2026-09-20 13:35:00 +0530
categories: database
tags: ["sql", "coalesce", "nullif", "null", "입문"]
toc: true
toc_sticky: true
excerpt: "NULL을 기본값으로 바꾸는 COALESCE와 특정 값을 NULL로 바꾸는 NULLIF의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "NULL 때문에 결과가 이상하게 나온다"

NULL은 계산·표시에서 자주 문제를 일으킨다. NULL을 원하는 값으로 대체하거나, 반대로 특정 값을 NULL로 바꾸고 싶을 때 쓰는 함수가 **COALESCE**와 **NULLIF**다.

## COALESCE — 첫 번째 non-NULL

```sql
-- 인자를 앞에서부터 보고 처음 만나는 NULL이 아닌 값을 반환
COALESCE(nickname, name, '이름없음')
-- nickname 있으면 그것, 없으면 name, 그것도 없으면 '이름없음'

-- NULL을 0으로 바꿔 합계 계산
SELECT SUM(COALESCE(amount, 0)) FROM orders;
```

## NULLIF — 두 값이 같으면 NULL

```sql
-- 두 인자가 같으면 NULL, 다르면 첫 번째 값 반환
NULLIF(value, 0)      -- value가 0이면 NULL

-- 0으로 나누기 에러 방지
SELECT total / NULLIF(count, 0) FROM stats;
-- count가 0이면 NULLIF가 NULL → 나눗셈 결과도 NULL(에러 대신)
```

## 언제 무엇인가

| 함수 | 동작 |
|---|---|
| COALESCE | 여러 값 중 첫 번째 non-NULL 반환(NULL → 대체값) |
| NULLIF | 두 값이 같으면 NULL 반환(특정 값 → NULL) |

## 실무 포인트

- **집계 전 NULL을 0으로.** `SUM`·`AVG`은 NULL을 무시하지만, 표시나 나눗셈에선 `COALESCE`로 미리 채우면 안전하다.
- **0으로 나누기 방지에 NULLIF.** 분모를 `NULLIF(x, 0)`으로 감싸면 0일 때 에러 대신 NULL이 나온다.
- **표준 함수를 쓰라.** `COALESCE`는 SQL 표준이라 DB를 옮겨도 동작한다. `ISNULL`·`IFNULL`은 특정 DB 전용이다.

## 마무리 요약

- COALESCE는 여러 값 중 첫 non-NULL을 반환해 NULL을 기본값으로 대체한다.
- NULLIF는 두 값이 같으면 NULL을 반환하며, 0으로 나누기 방지에 유용하다.
- 이식성을 위해 표준 함수 COALESCE를 우선 쓴다.

## 참고 자료

- [PostgreSQL 문서 - COALESCE, NULLIF](https://www.postgresql.org/docs/current/functions-conditional.html)
