---
layout: single
title: "쿼리는 멀쩡한데 왜 느릴까 — 락 경합 진단과 데드락 해결하기"
date: 2026-08-17 13:35:00 +0530
categories: database
tags: ["database", "lock", "deadlock", "mysql", "postgresql", "innodb"]
toc: true
toc_sticky: true
excerpt: "실행 계획도 인덱스도 멀쩡한데 응답이 느려지거나 갑자기 트랜잭션이 롤백된다면 범인은 락 경합과 데드락이다. 락 대기를 진단하는 SQL과 데드락 발생 원리, 실무 회피 전략을 정리한다."
---

## 왜 지금 이 주제인가

쿼리 튜닝을 아무리 해도 응답 시간이 들쭉날쭉하고, 어떤 요청은 멀쩡히 끝나는데 어떤 요청은 갑자기 `Deadlock found when trying to get lock` 에러로 롤백된다면, 문제는 실행 계획이 아니라 **락(lock) 경합**일 가능성이 높다. `EXPLAIN`으로는 보이지 않는 영역이라 원인 파악에 시간이 오래 걸리는 대표적인 장애 유형이다.

특히 트래픽이 몰리는 시간대에만 간헐적으로 발생하는 지연·롤백은 재현이 어려워 "가끔 그런다"로 방치되기 쉽다. 하지만 락 경합은 원인이 명확한 구조적 문제이고, DB가 제공하는 시스템 뷰로 어떤 트랜잭션이 무엇을 기다리는지 정확히 특정할 수 있다. 이 글에서는 락 경합 진단 방법과 데드락 발생·해결 원리, 실무 회피 전략을 다룬다.

## 핵심 개념 1: 락 경합이란 무엇인가

락 경합은 하나의 트랜잭션이 이미 잠근 리소스(행·페이지·테이블)를 다른 트랜잭션이 필요로 해서 대기 상태에 빠지는 현상이다. 대기 자체는 정상적인 동시성 제어지만, 대기 시간이 길어지거나 대기 트랜잭션이 쌓이면 전체 처리량이 급격히 떨어진다.

| 락 종류 | 설명 | 충돌 대상 |
|---|---|---|
| 공유 락(Shared, S) | 읽기용, 여러 트랜잭션이 동시 보유 가능 | 배타 락과만 충돌 |
| 배타 락(Exclusive, X) | 쓰기용, 단 하나의 트랜잭션만 보유 | 공유·배타 락 모두와 충돌 |
| 행 락(Row Lock) | 특정 레코드 단위 | 같은 행을 잠근 다른 트랜잭션 |
| 갭 락(Gap Lock, InnoDB) | 인덱스 레코드 사이 범위 | 범위 안 INSERT를 막아 phantom read 방지 |

행 단위 락이 세밀할수록 동시성은 좋아지지만, 인덱스가 없어 풀 스캔이 걸리면 의도치 않게 넓은 범위(심하면 테이블 전체)에 락이 걸려 경합이 커진다. **락 경합의 상당수는 사실 인덱스 문제다.**

## 핵심 개념 2: 데드락은 왜, 어떻게 감지되는가

데드락은 두 개 이상의 트랜잭션이 서로 상대방이 쥔 락을 기다리며 순환 대기(circular wait)에 빠지는 상태다. T1이 행 A를 잠그고 행 B를 기다리는데, T2는 행 B를 잠그고 행 A를 기다리면 둘 다 영원히 끝날 수 없다.

<img src="/assets/images/posts/2026-08-17-lock-contention-deadlock-1.svg" alt="두 트랜잭션이 서로 다른 행을 잠그고 상대 행을 기다려 순환 대기가 발생하는 데드락 wait-for 그래프" style="width:100%;">

MySQL(InnoDB)과 PostgreSQL 모두 내부적으로 **wait-for 그래프**를 유지하다가 순환이 감지되면 롤백 비용이 더 적은 쪽을 **victim**으로 골라 즉시 롤백시켜 순환을 끊는다. 즉 데드락은 DB가 방치하는 장애가 아니라 감지 즉시 자동 해소되는 상황이다. 문제는 롤백당한 트랜잭션을 애플리케이션이 재시도하도록 만들어 두지 않으면 그 요청이 그대로 실패로 끝난다는 점이다.

## 예제: 락 대기와 데드락 이력 확인하기

어떤 트랜잭션이 무엇을 기다리는지는 각 DB가 제공하는 시스템 뷰로 직접 확인할 수 있다.

```sql
-- MySQL 8.0: 현재 락 대기 관계 확인
SELECT
  r.trx_id AS waiting_trx,
  r.trx_mysql_thread_id AS waiting_thread,
  b.trx_id AS blocking_trx,
  b.trx_mysql_thread_id AS blocking_thread,
  r.trx_query AS waiting_query
FROM performance_schema.data_lock_waits w
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_engine_transaction_id
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_engine_transaction_id;
```

```sql
-- PostgreSQL: 대기 중인 락과 그 원인이 되는 세션 확인
SELECT
  blocked.pid AS blocked_pid,
  blocked.query AS blocked_query,
  blocking.pid AS blocking_pid,
  blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks kl ON kl.locktype = bl.locktype
  AND kl.database IS NOT DISTINCT FROM bl.database
  AND kl.relation IS NOT DISTINCT FROM bl.relation
  AND kl.page IS NOT DISTINCT FROM bl.page
  AND kl.tuple IS NOT DISTINCT FROM bl.tuple
  AND kl.granted
JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
WHERE blocked.pid != blocking.pid;
```

두 쿼리 모두 "누가 무엇을 기다리는지"를 즉시 보여준다. `blocking_query`가 특정 배치 작업이나 장시간 트랜잭션으로 반복해서 나온다면, 그 작업의 트랜잭션 범위나 실행 시간을 줄이는 것이 우선순위다.

이미 발생한 데드락은 MySQL이라면 `SHOW ENGINE INNODB STATUS`의 `LATEST DETECTED DEADLOCK` 섹션에서, PostgreSQL이라면 `log_lock_waits = on` 설정 시 서버 로그의 `deadlock detected` 항목에서 관여한 두 트랜잭션의 쿼리를 그대로 확인할 수 있다.

## 실무 포인트

- **트랜잭션 범위를 최소화한다.** 트랜잭션 안에 외부 API 호출이나 긴 계산 로직을 넣지 않는다. 락을 쥔 채 대기하는 시간이 길어질수록 다른 트랜잭션의 대기 시간도 함께 늘어난다.
- **락 획득 순서를 통일한다.** 여러 행을 잠가야 하는 로직이라면, 모든 트랜잭션이 항상 같은 순서(예: ID 오름차순)로 잠그도록 맞추면 순환 대기 자체가 생기지 않는다.
- **인덱스로 락 범위를 좁힌다.** `WHERE` 조건에 맞는 인덱스가 없으면 불필요하게 넓은 범위가 잠기거나 갭 락이 과도하게 걸릴 수 있다. 락 경합의 상당수는 인덱스 튜닝만으로도 줄어든다.
- **재시도 로직과 타임아웃을 함께 둔다.** 데드락은 자동 해소되는 정상 동작이므로 victim 트랜잭션을 짧은 backoff 후 재시도하는 코드가 필요하고, `innodb_lock_wait_timeout`·`lock_timeout` 같은 무한 대기 방지 설정도 점검한다.

## 3줄 요약

- 락 경합은 `EXPLAIN`에 나오지 않는 동시성 문제이며, 원인의 상당수는 인덱스 부재로 인한 과도한 락 범위에 있다.
- 데드락은 wait-for 그래프의 순환 대기를 DB가 자동 감지해 victim 트랜잭션을 롤백시키는, 감지·해소가 즉시 이뤄지는 정상 동작이다.
- 락 대기와 데드락 이력은 각 DB의 시스템 뷰·로그로 직접 확인 가능하며, 락 획득 순서 통일과 애플리케이션 재시도 로직이 실무 대응의 핵심이다.

## 참고 자료

- [MySQL 8.0 Reference Manual — InnoDB Locking](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html)
- [MySQL 8.0 Reference Manual — Deadlocks in InnoDB](https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks.html)
- [PostgreSQL Documentation — Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
