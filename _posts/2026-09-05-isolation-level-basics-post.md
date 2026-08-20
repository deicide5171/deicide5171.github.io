---
layout: single
title: "트랜잭션 격리수준이 뭔가요 — 동시성 문제를 그림으로 이해하기"
date: 2026-09-05 12:35:00 +0530
categories: database
tags: ["격리수준", "트랜잭션", "동시성", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "여러 트랜잭션이 동시에 실행될 때 생기는 문제와, 그것을 얼마나 막을지 정하는 격리수준의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 동시에 같은 데이터를 건드리면 무슨 일이 생기나

혼자 쓰는 DB라면 문제가 없지만, 여러 사용자가 동시에 같은 데이터를 읽고 쓰면 예상치 못한 결과가 나올 수 있다. **격리수준(Isolation Level)**은 "동시에 실행되는 트랜잭션들이 서로를 얼마나 볼 수 있게 할지"를 정하는 설정이다. 격리를 강하게 하면 안전하지만 느려지고, 약하게 하면 빠르지만 이상 현상이 생길 수 있다.

## 동시성이 만드는 세 가지 문제

| 문제 | 상황 |
|---|---|
| Dirty Read | 아직 커밋 안 된(취소될 수도 있는) 데이터를 읽음 |
| Non-Repeatable Read | 같은 데이터를 두 번 읽었는데 값이 달라짐(그 사이 누가 수정) |
| Phantom Read | 같은 조건으로 조회했는데 행 개수가 달라짐(그 사이 누가 삽입) |

## 격리수준 4단계

```text
READ UNCOMMITTED  - 커밋 안 된 것도 읽음 (Dirty Read 발생) — 가장 약함
READ COMMITTED    - 커밋된 것만 읽음 (Dirty Read 방지)
REPEATABLE READ   - 같은 데이터 재조회 시 값 고정 (Non-Repeatable Read 방지)
SERIALIZABLE      - 완전히 순차 실행한 것처럼 (모든 이상 방지) — 가장 강함, 가장 느림
```

아래로 갈수록 격리가 강해져 더 많은 이상 현상을 막지만, 그만큼 동시 처리 성능은 떨어진다.

## DB마다 기본값이 다르다

```text
MySQL(InnoDB) 기본값: REPEATABLE READ
PostgreSQL 기본값:   READ COMMITTED

-> 같은 코드라도 DB를 바꾸면 동시성 동작이 달라질 수 있다!
   MySQL에서 잘 되던 것이 PostgreSQL로 옮기니 이상하게 동작한다면
   기본 격리수준 차이를 먼저 의심해야 한다.
```

## 실무 포인트

- **격리수준을 무조건 SERIALIZABLE로 올리면 안전하지만 성능이 크게 떨어진다.** 대부분의 서비스는 READ COMMITTED나 REPEATABLE READ로 충분하며, 정말 엄격한 정합성이 필요한 특정 트랜잭션에만 선택적으로 높이는 것이 실무적이다.
- **격리수준을 높인다고 모든 동시성 문제가 사라지는 것은 아니다.** 예를 들어 "재고를 읽고 → 판단하고 → 차감"하는 로직은 격리수준만으로는 동시 판매를 막지 못할 수 있어, 별도의 락(비관적 락)이나 버전 검증(낙관적 락)이 필요하다.
- **기본값을 그대로 쓰기 전에 우리 서비스가 어떤 이상 현상을 허용할 수 없는지부터 정의하라.** 그 이상 현상을 막는 최소한의 격리수준을 고르는 것이 성능과 안전의 균형점이다.

## 마무리 요약

- 격리수준은 동시 실행 트랜잭션이 서로를 얼마나 볼 수 있게 할지 정하는 설정이다.
- Dirty Read·Non-Repeatable Read·Phantom Read를 어디까지 막을지에 따라 4단계로 나뉜다.
- MySQL과 PostgreSQL의 기본값이 다르므로 DB 이전 시 동시성 동작 변화를 반드시 확인해야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 - 트랜잭션 격리](https://www.postgresql.org/docs/current/transaction-iso.html)
- [MySQL 공식 문서 - 격리수준](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html)
