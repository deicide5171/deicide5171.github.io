---
layout: single
title: "SQL에서 NULL이 뭔가요 — '값 없음'이 만드는 함정"
date: 2026-09-10 12:35:00 +0530
categories: database
tags: ["null", "sql", "데이터베이스기초", "isnull", "입문"]
toc: true
toc_sticky: true
excerpt: "SQL에서 NULL이 왜 '= NULL'로 비교되지 않고 어떤 함정을 만드는지, 올바른 처리법을 처음 배우는 사람 기준으로 정리했다."
---

## NULL은 0도 빈 문자열도 아니다

SQL에서 **NULL**은 "값이 없음(모름)"을 뜻한다. 숫자 0이나 빈 문자열 `''`과는 다르다. "아직 입력 안 함", "해당 없음" 같은 상태다. 문제는 이 NULL이 비교·계산에서 **예상 밖으로 동작**한다는 점이다.

## NULL의 함정

| 시도 | 결과 |
|---|---|
| `WHERE col = NULL` | 아무것도 안 나옴 (틀린 문법) |
| `WHERE col IS NULL` | 올바른 방법 |
| `NULL = NULL` | 참이 아니라 "불명(unknown)" |
| `1 + NULL` | 결과가 NULL |

NULL은 "모름"이라서 `= NULL`로 비교할 수 없다. "모르는 값이 모르는 값과 같은가?"는 답할 수 없으니 참이 아니다.

## 올바른 처리

```sql
-- NULL 여부는 IS NULL / IS NOT NULL 로
SELECT * FROM users WHERE phone IS NULL;

-- NULL을 기본값으로 대체: COALESCE
SELECT name, COALESCE(phone, '미등록') AS phone
FROM users;

-- 집계 시 COUNT(col)은 NULL을 안 센다
SELECT COUNT(*), COUNT(phone) FROM users; -- 두 값이 다를 수 있음
```

## 실무 포인트

- **비교는 반드시 `IS NULL`/`IS NOT NULL`로.** `= NULL`, `!= NULL`은 항상 아무것도 매칭하지 않는다. NULL 여부를 거를 땐 전용 문법을 써야 한다.
- **`COALESCE`로 기본값을 정하라.** 화면에 NULL을 그대로 보여주면 어색하다. `COALESCE(값, 기본값)`으로 "미등록" 같은 대체값을 지정하면 깔끔하다.
- **집계·조인에서 NULL을 조심하라.** `COUNT(컬럼)`은 NULL을 세지 않고, NULL이 있는 컬럼으로 조인하면 매칭이 빠진다. 합계·평균도 NULL은 무시되니 의도와 맞는지 확인한다.

## 마무리 요약

- NULL은 "값 없음(모름)"으로 0·빈 문자열과 다르며, `= NULL`로는 비교되지 않는다.
- NULL 여부는 `IS NULL`/`IS NOT NULL`로 거르고, `COALESCE`로 기본값을 대체한다.
- 집계·조인에서 NULL은 빠지거나 무시되므로 결과가 의도와 맞는지 확인해야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Comparison Functions](https://www.postgresql.org/docs/current/functions-comparison.html)
