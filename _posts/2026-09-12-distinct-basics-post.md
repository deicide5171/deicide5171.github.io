---
layout: single
title: "DISTINCT가 뭔가요 — 중복 없이 값 뽑아내기"
date: 2026-09-12 13:35:00 +0530
categories: database
tags: ["distinct", "sql", "중복제거", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "조회 결과에서 중복 행을 제거하는 SQL DISTINCT의 사용법과 성능 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## "우리 회원이 사는 도시 목록"을 뽑으려면

회원 테이블에서 도시를 조회하면 같은 도시가 수백 번 반복해 나온다. "어떤 도시들이 있는지"만 알고 싶다면 중복을 없애야 한다. **DISTINCT**는 **조회 결과에서 중복 행을 제거**해 고유한 값만 남긴다.

## 사용법

```sql
-- 중복 도시 제거
SELECT DISTINCT city FROM users;

-- 여러 컬럼 조합의 고유값
SELECT DISTINCT city, age FROM users;
-- (city, age) 조합이 같은 것만 하나로 묶음
```

`DISTINCT`는 SELECT 바로 뒤에 한 번 쓰며, 나열한 컬럼들의 **조합**을 기준으로 중복을 판단한다.

## DISTINCT vs GROUP BY

| 구분 | DISTINCT | GROUP BY |
|---|---|---|
| 목적 | 고유값만 | 그룹별 집계 |
| 집계 함수 | 못 씀 | COUNT·SUM 등 가능 |
| 예 | 도시 목록 | 도시별 회원 수 |

단순히 중복만 제거하면 DISTINCT, 그룹별로 개수·합계를 구하면 GROUP BY다.

## 실무 포인트

- **DISTINCT는 정렬·비교 비용이 있다.** 중복을 없애려면 DB가 값을 정렬하거나 해시로 비교해야 해서, 데이터가 크면 느릴 수 있다. 정말 중복 제거가 필요한지 먼저 생각한다.
- **`COUNT(DISTINCT ...)`로 고유 개수.** "몇 개의 서로 다른 도시가 있나"는 `SELECT COUNT(DISTINCT city)`로 구한다. 자주 쓰는 유용한 형태다.
- **JOIN 후 중복을 DISTINCT로 덮지 마라.** JOIN 결과에 원치 않는 중복이 생겨 DISTINCT로 가리는 경우가 있는데, 이는 JOIN 조건이 잘못됐다는 신호일 수 있다. 근본 원인을 먼저 확인한다.

## 마무리 요약

- DISTINCT는 조회 결과에서 중복 행을 제거해 고유한 값만 남긴다.
- 나열한 컬럼들의 조합을 기준으로 중복을 판단하며, 고유 개수는 `COUNT(DISTINCT ...)`로 구한다.
- 정렬·비교 비용이 있어 큰 데이터에선 느릴 수 있고, JOIN 중복을 DISTINCT로 덮기 전에 원인을 확인한다.

## 참고 자료

- [PostgreSQL 공식 문서 - SELECT DISTINCT](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)
