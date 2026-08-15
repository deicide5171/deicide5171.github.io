---
layout: single
title: "트랜잭션 격리수준, PostgreSQL과 MySQL은 왜 다르게 동작하는가"
date: 2026-08-15 11:35:00 +0530
categories: database
tags: ["database", "transaction", "isolation-level", "postgresql", "mysql", "mvcc"]
toc: true
toc_sticky: true
excerpt: "같은 REPEATABLE READ인데 왜 PostgreSQL과 MySQL의 동시성 동작이 다를까. MVCC 스냅샷 아이솔레이션 원리와 네 가지 격리수준, 실무에서 자주 만나는 write skew 문제를 정리한다."
---

## 왜 지금 이 주제인가

트래픽이 적을 때는 잘 돌던 잔액 차감 로직이 동시 요청 몇 개가 겹치자 잔액이 음수로 떨어지는 버그를 만들어낸 경험이 있을 것이다. 원인은 대부분 코드가 아니라 **트랜잭션 격리수준을 정확히 이해하지 못한 것**에 있다. ANSI SQL 표준이 정의한 네 가지 격리수준은 이름은 같아도 DBMS마다 구현 방식이 다르고, 그 차이가 실제 동시성 버그로 이어진다.

특히 PostgreSQL과 MySQL(InnoDB)은 둘 다 "REPEATABLE READ"라는 이름을 쓰지만, 내부적으로는 서로 다른 방식으로 동시성을 제어한다. 이 차이를 모르고 한쪽 DB에서 검증한 로직을 다른 DB로 그대로 옮기면 예상치 못한 동시성 버그를 만나기 쉽다.

## 핵심 개념 1: 네 가지 격리수준과 이상 현상

ANSI SQL은 격리수준이 낮을수록 허용되는 "이상 현상(anomaly)"이 늘어난다고 정의한다.

| 격리수준 | Dirty Read | Non-repeatable Read | Phantom Read | 비고 |
|---|---|---|---|---|
| Read Uncommitted | 발생 가능 | 발생 가능 | 발생 가능 | 실무에서 거의 안 씀 |
| Read Committed | 방지 | 발생 가능 | 발생 가능 | PostgreSQL 기본값 |
| Repeatable Read | 방지 | 방지 | 표준상 발생 가능 | MySQL(InnoDB) 기본값 |
| Serializable | 방지 | 방지 | 방지 | 성능 비용 가장 큼 |

- **Dirty Read**: 커밋되지 않은 다른 트랜잭션의 변경을 읽어버리는 것
- **Non-repeatable Read**: 같은 행을 두 번 읽었는데 그 사이 다른 트랜잭션이 커밋해서 값이 달라지는 것
- **Phantom Read**: 같은 조건으로 두 번 조회했는데 그 사이 새로 삽입된 행이 나타나는 것

표에서 눈여겨볼 지점은 Repeatable Read다. 표준은 phantom read를 허용하지만, **실제 구현은 표준보다 강한 보장을 주기도 한다.** 여기서부터 DB마다 이야기가 갈린다.

## 핵심 개념 2: MVCC 스냅샷 아이솔레이션과 DB별 차이

PostgreSQL과 MySQL 모두 락 대신 **MVCC(Multi-Version Concurrency Control)** 로 Repeatable Read를 구현한다. 트랜잭션이 시작되는 시점(또는 첫 쿼리 시점)의 데이터 스냅샷을 확보하고, 트랜잭션이 끝날 때까지 그 스냅샷만 본다는 점은 동일하다.

<img src="/assets/images/posts/2026-08-15-transaction-isolation-levels-1.svg" alt="MVCC 스냅샷 아이솔레이션에서 두 트랜잭션이 같은 행을 동시에 수정할 때 write-write 충돌이 감지되는 타임라인" style="width:100%;">

차이는 **쓰기 충돌을 어떻게 처리하느냐**에서 갈린다.

- **PostgreSQL**: Repeatable Read 이상에서 같은 행을 두 트랜잭션이 동시에 수정하려 하면, 먼저 커밋한 트랜잭션만 성공하고 나머지는 `could not serialize access due to concurrent update` 오류로 **abort**시킨다. 애플리케이션이 재시도 로직을 갖추고 있어야 한다.
- **MySQL(InnoDB)**: Repeatable Read에서 **넥스트 키 락(next-key lock)** 을 함께 사용해 phantom read를 상당 부분 실무적으로 방지한다. 표준상으로는 Repeatable Read가 phantom read를 허용하지만, InnoDB의 넥스트 키 락 덕분에 범위 조회에 대한 삽입까지 막히는 경우가 많다.

즉 "REPEATABLE READ면 다 똑같겠지"라고 가정하고 한쪽 DB에서 검증한 동시성 로직을 다른 DB에 그대로 옮기면, 락 대기 시간이나 실패 처리 방식이 달라져 문제가 생길 수 있다.

## 예제: Write Skew — Serializable 이하에서만 생기는 함정

Repeatable Read까지 올려도 막히지 않는 대표적인 이상 현상이 **write skew**다. 서로 다른 행을 각자 수정하지만 그 조합이 비즈니스 규칙을 깨는 경우다.

```sql
-- 온콜 당직자가 최소 1명은 있어야 한다는 규칙
-- T1, T2가 동시에 실행되면 둘 다 "다른 한 명이 있으니 나는 빠져도 된다"고 판단

-- T1
BEGIN;
SELECT count(*) FROM oncall WHERE active = true; -- 2명 확인
UPDATE oncall SET active = false WHERE user_id = 'alice';
COMMIT;

-- T2 (T1과 거의 동시에 실행)
BEGIN;
SELECT count(*) FROM oncall WHERE active = true; -- 역시 2명 확인 (같은 스냅샷)
UPDATE oncall SET active = false WHERE user_id = 'bob';
COMMIT;

-- 결과: 두 트랜잭션 모두 성공 → 당직자 0명 (규칙 위반)
```

두 트랜잭션이 서로 다른 행(`alice`, `bob`)을 수정하기 때문에 MVCC의 write-write 충돌 감지에 걸리지 않는다. 이 문제를 막으려면 `SERIALIZABLE` 격리수준을 쓰거나, `SELECT ... FOR UPDATE`로 읽은 행에 명시적 락을 걸어야 한다.

## 실무 포인트

- **기본값부터 확인한다**: PostgreSQL은 Read Committed, MySQL(InnoDB)은 Repeatable Read가 기본값이다. ORM 설정이나 커넥션 풀 설정에서 이 기본값을 암묵적으로 바꾸는 경우가 있으니 실제 적용된 값을 반드시 확인한다.
- **재시도 로직은 선택이 아니라 필수다**: Repeatable Read 이상에서 직렬화 실패(serialization failure)가 발생할 수 있다는 전제로, 애플리케이션 계층에 짧은 backoff 재시도를 넣어야 한다.
- **Serializable은 공짜가 아니다**: PostgreSQL의 SSI(Serializable Snapshot Isolation)는 술어 락(predicate lock) 추적 비용이 있어 처리량이 떨어질 수 있다. 정말 write skew가 걱정되는 임계 구간에만 좁혀 적용하는 것이 현실적이다.
- **`SELECT ... FOR UPDATE`를 락 대체 수단으로 적극 활용한다**: 격리수준을 통째로 올리는 대신, 충돌 위험이 있는 특정 조회에만 명시적 락을 거는 편이 성능 영향을 최소화한다.

## 3줄 요약

- 격리수준이 낮을수록 dirty read·non-repeatable read·phantom read 같은 이상 현상이 더 많이 허용된다.
- PostgreSQL과 MySQL은 같은 이름의 Repeatable Read라도 MVCC 충돌 처리 방식(abort vs 넥스트 키 락)이 달라 동작이 다르다.
- write skew처럼 Repeatable Read로도 막히지 않는 함정이 있으므로, Serializable 격리수준이나 `SELECT ... FOR UPDATE`를 상황에 맞게 선택해야 한다.

## 참고 자료

- [PostgreSQL Documentation — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [MySQL 8.0 Reference Manual — InnoDB Locking and Transaction Model](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html)
- [PostgreSQL Wiki — Serializable Snapshot Isolation (SSI)](https://wiki.postgresql.org/wiki/SSI)
