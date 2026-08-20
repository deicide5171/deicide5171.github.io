---
layout: single
title: "SELECT FOR UPDATE가 뭔가요 — 조회하면서 행을 잠그기"
date: 2026-09-18 12:35:00 +0530
categories: database
tags: ["forupdate", "sql", "행잠금", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "조회한 행을 다른 트랜잭션이 못 바꾸게 잠그는 SELECT ... FOR UPDATE의 개념과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 조회한 뒤 바꾸는 사이에 끼어들면

재고를 조회해 값을 확인하고, 계산해서 다시 저장하는 동안 다른 트랜잭션이 같은 재고를 건드리면 값이 꼬인다. **SELECT ... FOR UPDATE**는 **조회하면서 그 행을 잠가**, 내 트랜잭션이 끝날 때까지 다른 트랜잭션이 그 행을 못 바꾸게 한다(비관적 락).

## 사용법

```sql
BEGIN;
-- 재고 행을 잠그고 조회
SELECT stock FROM products WHERE id = 1 FOR UPDATE;
-- 이 사이 다른 트랜잭션은 이 행을 못 건드리고 기다림
UPDATE products SET stock = stock - 1 WHERE id = 1;
COMMIT; -- 커밋하면 잠금 해제
```

`FOR UPDATE`를 붙이면 조회한 행에 쓰기 잠금이 걸린다. 다른 트랜잭션은 이 잠금이 풀릴 때까지 대기한다.

## 실무 포인트

- **재고 차감 같은 동시성에 쓴다.** "조회 → 판단 → 갱신"을 원자적으로 해야 하는 재고 차감, 좌석 예약 등에서 FOR UPDATE로 행을 잠가 이중 차감을 막는다.
- **잠금 범위·시간을 최소화.** 잠금을 오래 쥐면 다른 트랜잭션이 줄줄이 대기해 성능이 떨어진다. 필요한 행만 잠그고, 트랜잭션을 짧게 유지해 빨리 커밋한다.
- **데드락을 조심.** 여러 행을 여러 트랜잭션이 서로 다른 순서로 잠그면 교착 상태(데드락)에 빠진다. 잠그는 순서를 통일한다. 충돌이 드물면 낙관적 락이 대안일 수 있다.

## 마무리 요약

- SELECT FOR UPDATE는 조회한 행을 잠가 내 트랜잭션이 끝날 때까지 다른 트랜잭션이 못 바꾸게 한다.
- 재고 차감·좌석 예약처럼 "조회 후 갱신"을 원자적으로 해야 할 때 쓰는 비관적 락이다.
- 잠금 범위·시간을 최소화하고 데드락을 조심하며, 충돌이 드물면 낙관적 락도 고려한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Row-Level Locks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
