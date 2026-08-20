---
layout: single
title: "CHECK 제약이 뭔가요 — 잘못된 값을 DB가 거부하게 하기"
date: 2026-09-16 13:35:00 +0530
categories: database
tags: ["check", "제약조건", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "나이가 음수이거나 상태값이 이상한 데이터가 들어오지 못하게 DB에서 막는 CHECK 제약의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 애플리케이션 검증만으로 충분할까

나이에 음수, 가격에 마이너스, 상태에 없는 값이 들어오면 안 된다. 애플리케이션에서 검증하지만, 버그나 다른 경로로 잘못된 값이 DB에 저장될 수 있다. **CHECK 제약**은 **컬럼 값이 특정 조건을 만족해야만 저장을 허용**해, DB 차원에서 잘못된 값을 막는다.

## 사용법

```sql
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    price INT CHECK (price >= 0),        -- 음수 가격 거부
    status VARCHAR(10) CHECK (status IN ('active','sold','hidden'))
);
-- price에 -100을 넣으려 하면 오류로 거부됨
```

조건이 참(true)일 때만 저장되고, 거짓이면 오류로 막는다.

## 자주 쓰는 조건

| 조건 | 예 |
|---|---|
| 범위 | `age BETWEEN 0 AND 150` |
| 목록 | `status IN ('a','b','c')` |
| 관계 | `end_date >= start_date` |

## 실무 포인트

- **DB가 마지막 방어선.** 애플리케이션 검증(빠른 피드백)과 CHECK 제약(최종 보장)을 함께 쓴다. 여러 서비스·수동 SQL 등 어떤 경로로 들어와도 잘못된 값이 저장되지 않는다.
- **상태값엔 IN 목록.** "상태는 active/sold/hidden 중 하나"처럼 정해진 값만 허용할 때 유용하다. 오타나 없는 상태값을 원천 차단한다.
- **NULL은 통과할 수 있다.** CHECK 조건은 NULL에 대해 "위반 아님"으로 취급되는 경우가 많다. NULL을 막으려면 `NOT NULL`을 함께 걸어야 한다.

## 마무리 요약

- CHECK 제약은 컬럼 값이 조건을 만족할 때만 저장을 허용해 잘못된 데이터를 DB가 막는다.
- 범위(BETWEEN)·목록(IN)·컬럼 간 관계 등 다양한 조건을 걸 수 있다.
- 앱 검증과 함께 최종 방어선으로 쓰고, NULL은 별도로 `NOT NULL`로 막아야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Check Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS)
