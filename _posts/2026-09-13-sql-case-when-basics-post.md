---
layout: single
title: "CASE WHEN이 뭔가요 — SQL 안에서 조건 분기하기"
date: 2026-09-13 12:35:00 +0530
categories: database
tags: ["casewhen", "sql", "조건문", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "SQL 조회 결과에 조건에 따라 다른 값을 넣는 CASE WHEN 표현식의 사용법과 활용을 처음 배우는 사람 기준으로 정리했다."
---

## 값에 따라 다른 표시를 하고 싶다면

점수를 조회하면서 "90 이상은 A, 80 이상은 B..."처럼 등급을 함께 보여주고 싶다. 애플리케이션에서 후처리할 수도 있지만, SQL 안에서 바로 할 수 있다. **CASE WHEN**은 **조건에 따라 다른 값을 반환하는 SQL의 조건문(if-else)**이다.

## 기본 문법

```sql
SELECT name, score,
  CASE
    WHEN score >= 90 THEN 'A'
    WHEN score >= 80 THEN 'B'
    WHEN score >= 70 THEN 'C'
    ELSE 'F'
  END AS grade
FROM students;
```

위에서부터 조건을 검사해, 처음 맞는 `THEN` 값을 쓴다. 아무것도 안 맞으면 `ELSE` 값이 된다.

## 활용 예

| 용도 | 예 |
|---|---|
| 등급/분류 | 점수 → A/B/C |
| 조건부 집계 | `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` |
| 값 치환 | 코드 → 사람이 읽는 이름 |

## 실무 포인트

- **조건부 집계에 강력하다.** `SUM(CASE WHEN status='완료' THEN 1 ELSE 0 END)`처럼 쓰면 "완료 건수"만 세는 등, 한 쿼리에서 여러 조건별 개수를 한 번에 구할 수 있다(피벗 효과).
- **순서가 중요하다.** WHEN은 위에서부터 검사하고 처음 맞는 것에서 멈춘다. `score >= 80`을 `score >= 90`보다 위에 두면 90점도 B가 되어버린다. 좁은 조건을 위에 둔다.
- **ELSE를 빼먹지 마라.** ELSE가 없고 어떤 조건도 안 맞으면 결과가 `NULL`이 된다. 의도한 것이 아니라면 ELSE로 기본값을 지정한다.

## 마무리 요약

- CASE WHEN은 조건에 따라 다른 값을 반환하는 SQL의 조건문(if-else)이다.
- 위에서부터 조건을 검사해 처음 맞는 값을 쓰고, 안 맞으면 ELSE 값이 된다.
- 등급 분류·조건부 집계에 유용하며, WHEN 순서와 ELSE 지정에 주의한다.

## 참고 자료

- [PostgreSQL 공식 문서 - CASE](https://www.postgresql.org/docs/current/functions-conditional.html)
