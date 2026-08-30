---
layout: single
title: "MySQL InnoDB Gap Lock과 Next-Key Lock — Phantom Read를 막는 락 범위 확장의 내부 동작"
date: 2026-09-25 12:35:00 +0530
categories: database
tags: ["MySQL", "InnoDB", "GapLock", "NextKeyLock", "격리수준"]
toc: true
toc_sticky: true
excerpt: "REPEATABLE READ에서 분명 존재하지 않는 값의 범위를 조회했을 뿐인데 다른 트랜잭션의 INSERT가 락 대기에 걸려버리는 상황을, InnoDB가 실제 행이 아닌 '행 사이의 간격'까지 잠그는 Gap Lock과 Next-Key Lock의 내부 동작으로 정리했다."
---

## 왜 지금 Gap Lock을 다시 봐야 하는가

트랜잭션 격리수준을 공부할 때 REPEATABLE READ는 보통 "같은 트랜잭션 안에서 같은 행을 두 번 읽으면 항상 같은 값이 보인다"는 스냅샷 관점으로 설명된다. 그런데 실제 MySQL InnoDB에서 REPEATABLE READ로 동작하는 서비스를 운영하다 보면, 존재하지 않는 값의 범위를 조회(`SELECT ... WHERE id BETWEEN 10 AND 20 FOR UPDATE`)했을 뿐인데 다른 트랜잭션의 `INSERT id=15`가 락 대기에 걸려버리는, 표준 MVCC 스냅샷 격리 설명만으로는 이해되지 않는 현상을 마주치게 된다. 이는 InnoDB가 표준 REPEATABLE READ보다 한 단계 더 나아가, Phantom Read까지 막기 위해 실제 존재하는 행뿐 아니라 행과 행 "사이의 간격(gap)"까지 잠그는 독자적인 락 메커니즘을 갖고 있기 때문이다. 이 동작을 모르면 락 경합 원인을 다른 곳에서 찾느라 시간을 허비하게 된다.

## 핵심 개념 1 — Record Lock, Gap Lock, Next-Key Lock의 세 층위

InnoDB의 락은 세 종류로 나뉜다. Record Lock은 인덱스 레코드 자체(실제 존재하는 행)에 거는 전통적인 락이다. Gap Lock은 인덱스 레코드 사이의 "간격"에 거는 락으로, 그 간격 안에 새 행을 INSERT하는 것을 막는다. Gap Lock은 실제 행을 잠그지 않으므로 여러 트랜잭션이 서로 다른 Gap Lock을 동시에 가질 수 있다는 점이 특이하다. Next-Key Lock은 Record Lock과 그 레코드 바로 앞의 Gap을 합친 것으로, "이 값 이하이면서 이 간격에 새로 삽입되는 것도 막는다"는 의미를 갖는다. `id BETWEEN 10 AND 20`처럼 범위 조건에 락을 거는 쿼리는 실제로 10~20 사이에 존재하는 각 행에 Next-Key Lock을 걸고, 그 범위의 시작과 끝에도 Gap Lock을 추가로 걸어 범위 전체를 봉쇄한다.

## 핵심 개념 2 — 왜 이 락이 REPEATABLE READ에서만 문제가 되는가

Gap Lock과 Next-Key Lock의 존재 이유는 명확하다. MVCC 스냅샷만으로는 SELECT 결과의 일관성은 지킬 수 있지만, `SELECT ... FOR UPDATE`나 `UPDATE`처럼 잠금이 필요한 쓰기 의도가 섞인 쿼리에서는 같은 트랜잭션 안에서 동일 조건으로 다시 조회했을 때 "이전에 없던 행이 새로 나타나는" Phantom Read를 막을 방법이 스냅샷만으로는 없다. InnoDB는 REPEATABLE READ 격리수준에서 이 문제를 Gap Lock으로 해결하기로 선택했다(표준 SQL 명세가 요구하는 것보다 강한 잠금이다). 반면 READ COMMITTED로 낮추면 InnoDB는 Gap Lock을 사실상 비활성화한다 — Phantom Read를 허용하는 대신 락 범위를 실제 행으로만 좁혀 동시성을 높이는 트레이드오프다. 이 때문에 "REPEATABLE READ에서 이상하게 INSERT가 자주 막힌다"는 증상을 겪는 팀 중 일부는 격리수준을 READ COMMITTED로 낮춰 해결하기도 하는데, 이는 Phantom Read 허용이라는 트레이드오프를 감수하는 결정임을 분명히 인지하고 내려야 한다.

| 락 종류 | 잠그는 대상 | 막는 것 | READ COMMITTED에서 |
|---|---|---|---|
| Record Lock | 실제 존재하는 행 | 해당 행의 동시 수정 | 그대로 동작 |
| Gap Lock | 행과 행 사이의 간격 | 그 간격으로의 새 INSERT | 사실상 비활성화 |
| Next-Key Lock | Record Lock + 앞쪽 Gap | 행 수정 + 그 앞 간격 INSERT | Record Lock만 남음 |

## 예제 — Gap Lock으로 인한 INSERT 대기 재현

```sql
-- 세션 A (REPEATABLE READ, 기본값)
BEGIN;
SELECT * FROM orders WHERE amount BETWEEN 100 AND 200 FOR UPDATE;
-- amount=100~200 사이 존재 행 + 앞뒤 간격에 Next-Key Lock 획득

-- 세션 B (다른 세션에서 동시 실행)
BEGIN;
INSERT INTO orders (amount) VALUES (150); -- 대기 걸림! 존재하지 않던 값인데도 막힘
-- 세션 A가 COMMIT/ROLLBACK 할 때까지 세션 B는 블로킹된다
```

```sql
-- 잠금 대기 현황 확인 (MySQL 8.0+)
SELECT * FROM performance_schema.data_lock_waits;
SELECT * FROM performance_schema.data_locks WHERE lock_type = 'RECORD';
```

## 실무 포인트

- **인덱스가 없는 컬럼에 조건을 걸면 Gap Lock 범위가 예상보다 훨씬 넓어질 수 있다.** InnoDB는 인덱스를 스캔하며 락을 거는데, 조건 컬럼에 인덱스가 없으면 풀스캔에 가까운 범위 전체에 Next-Key Lock이 걸려 동시성이 급격히 나빠진다. 락 경합이 심한 쿼리는 먼저 인덱스 존재 여부부터 확인해야 한다.
- **AUTO-INCREMENT 컬럼에 대량 INSERT가 몰리는 테이블은 Gap Lock으로 인한 데드락 위험이 커진다.** 여러 트랜잭션이 서로 다른 순서로 인접한 간격을 잠그려 하면 락 순환 대기가 발생하기 쉬우므로, 배치 크기를 줄이거나 INSERT 순서를 통일하는 것이 도움이 된다.
- **READ COMMITTED로 낮추는 것이 만능 해법은 아니다.** Gap Lock 경합은 사라지지만 Phantom Read를 허용하게 되므로, 애플리케이션 로직이 같은 트랜잭션 내 반복 조회의 일관성에 의존하고 있지 않은지 먼저 점검해야 한다.

## 마무리 요약

- InnoDB는 REPEATABLE READ에서 Phantom Read를 막기 위해 실제 행(Record Lock)뿐 아니라 행 사이의 간격(Gap Lock)까지 잠그며, 이 둘을 합친 것이 Next-Key Lock이다.
- 존재하지 않는 값 범위를 조회했을 뿐인데 다른 트랜잭션의 INSERT가 막히는 현상은 이 Gap Lock 때문이며, 이는 표준 SQL이 요구하는 것보다 강한 InnoDB 고유의 구현이다.
- READ COMMITTED에서는 Gap Lock이 사실상 비활성화되어 동시성은 높아지지만 Phantom Read를 허용하게 되므로, 격리수준 변경은 트레이드오프를 이해한 뒤 결정해야 한다.

## 참고 자료

- [MySQL 8.0 Reference Manual - InnoDB Locking (Record, Gap, Next-Key Locks)](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html)
- [MySQL 8.0 Reference Manual - Locks Set by Different SQL Statements in InnoDB](https://dev.mysql.com/doc/refman/8.0/en/innodb-locks-set.html)
