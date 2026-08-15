---
layout: single
title: "MVCC 완전 정복 — PostgreSQL은 락 없이 어떻게 동시성을 처리할까"
date: 2026-08-20 13:35:00 +0530
categories: database
tags: ["database", "postgresql", "mvcc", "concurrency", "isolation-level", "transaction"]
toc: true
toc_sticky: true
excerpt: "읽기가 쓰기를 막지 않는 PostgreSQL의 동시성 처리 비결인 MVCC의 튜플 버전 관리 방식과, 그로 인해 발생하는 벌룬(bloat) 문제를 정리한다."
---

여러 트랜잭션이 같은 테이블에 동시에 접근할 때 가장 먼저 떠오르는 걱정은 "누가 읽는 동안 다른 누군가 쓰면 어떻게 되는가"다. 락 기반 동시성 제어를 쓰는 시스템이라면 답은 단순하다. 읽기 락과 쓰기 락이 서로를 막아서, 한쪽이 끝날 때까지 다른 쪽은 대기한다. 이 방식은 이해하기 쉽지만, 읽기와 쓰기가 빈번한 워크로드에서는 대기 행렬이 곧 성능 병목이 된다.

PostgreSQL을 포함한 대부분의 현대 관계형 DBMS는 이 문제를 다른 방식으로 푼다. 바로 MVCC(Multi-Version Concurrency Control, 다중 버전 동시성 제어)다. 핵심 아이디어는 간단하다. 데이터를 수정할 때 기존 값을 그 자리에서 덮어쓰는 대신, 새 버전을 별도로 만들어둔다. 그러면 읽는 트랜잭션은 쓰기 작업이 끝나기를 기다릴 필요 없이, 자신이 시작된 시점에 유효했던 버전을 그대로 읽으면 된다. "읽기가 쓰기를 막지 않고, 쓰기가 읽기를 막지 않는다"는 PostgreSQL의 오래된 설계 원칙은 바로 이 구조에서 나온다.

다만 공짜는 아니다. 옛 버전을 계속 만들어내는 만큼, 더는 어떤 트랜잭션도 볼 필요가 없어진 버전을 청소하는 작업이 별도로 필요하다. 이 글에서는 MVCC가 튜플 단위로 버전을 어떻게 관리하는지, 격리 수준에 따라 그 버전이 어떻게 다르게 보이는지, 그리고 그 대가로 따라오는 VACUUM과 블로트 문제까지 순서대로 정리한다.

## 핵심 개념 1: 튜플마다 xmin/xmax로 버전을 관리한다

PostgreSQL은 테이블의 각 행(튜플)에 사용자가 정의하지 않은 시스템 컬럼을 몇 개 더 붙여서 저장한다. 그중 MVCC의 핵심은 `xmin`과 `xmax`다.

- `xmin`: 이 튜플 버전을 만든(INSERT한) 트랜잭션의 ID
- `xmax`: 이 튜플 버전을 무효화한(DELETE하거나 UPDATE로 새 버전으로 대체한) 트랜잭션의 ID. 아직 유효하다면 비어 있다.

UPDATE는 실제로는 "기존 튜플의 `xmax`를 현재 트랜잭션 ID로 채우고, 변경된 내용을 담은 새 튜플을 `xmin`이 현재 트랜잭션 ID인 채로 새로 삽입"하는 동작이다. 물리적으로 값을 고쳐 쓰는 것이 아니라, 옛 버전은 그대로 두고 새 버전을 옆에 하나 더 만드는 셈이다. DELETE도 마찬가지로 튜플을 즉시 지우지 않고 `xmax`만 채워서 "이 시점부터는 무효"라고 표시한다.

이렇게 만들어진 여러 버전은 논리적으로 하나의 행이 시간 순서대로 이어진 체인을 이룬다. 각 트랜잭션은 스캔 시점에 자신의 트랜잭션 ID와 각 튜플의 `xmin`/`xmax`를 비교해서, 그 버전이 "나에게 보여야 하는 버전인지"를 판단한다.

<img src="/assets/images/posts/2026-08-20-mvcc-postgresql-multiversion-concurrency-1.svg" alt="튜플 버전 체인 구조도 - xmin/xmax로 이어지는 버전 1, 2, 3과 스냅샷별 가시성 판단" style="width:100%;">

## 핵심 개념 2: 스냅샷 격리와 격리 수준별 차이

트랜잭션이 시작되면 PostgreSQL은 그 시점의 "스냅샷"을 하나 확보한다. 스냅샷은 대략 "이 시점에 이미 커밋된 트랜잭션들의 변경 결과만 보이고, 아직 진행 중이거나 이후에 시작된 트랜잭션의 변경은 보이지 않는다"는 가시성 규칙의 집합이다. 이 스냅샷을 언제 새로 갱신하느냐가 격리 수준의 차이를 만든다.

- **Read Committed**(PostgreSQL 기본값): 트랜잭션 내에서 각 SQL 문(statement)마다 새 스냅샷을 얻는다. 그래서 같은 트랜잭션 안에서도 문장 사이에 다른 트랜잭션이 커밋한 변경 사항이 다음 문장부터 보일 수 있다.
- **Repeatable Read**: 트랜잭션이 시작될 때(정확히는 트랜잭션 내 첫 쿼리 시점) 스냅샷 하나를 고정하고, 그 트랜잭션이 끝날 때까지 계속 그 스냅샷만 사용한다. 트랜잭션 도중 다른 트랜잭션이 커밋해도, 이미 고정된 스냅샷에는 반영되지 않는다.

두 격리 수준 모두 "쓰기가 읽기를 블로킹하지 않는다"는 MVCC의 기본 성질은 동일하게 누린다. 차이는 같은 트랜잭션 내에서 스냅샷이 몇 번 갱신되느냐, 그리고 그로 인해 반복 조회 시 결과가 달라질 수 있는지 여부에 있다. Repeatable Read는 이름 그대로 같은 쿼리를 반복해도 같은 결과를 보장하지만, 그 대가로 동시에 같은 행을 수정하려는 트랜잭션 간에는 직렬화 오류(serialization failure)가 발생할 수 있어 재시도 로직이 필요해진다.

## 핵심 개념 3: VACUUM이 필요한 이유와 테이블 블로트

UPDATE와 DELETE가 튜플을 그 자리에서 지우지 않고 새 버전을 계속 추가하는 방식이라면, 자연스러운 질문이 따라온다. 옛 버전은 언제 없어지는가. 답은 "아무도 그 버전을 볼 필요가 없어졌을 때"다. 더는 어떤 활성 트랜잭션의 스냅샷도 참조하지 않는 튜플 버전을 PostgreSQL은 "죽은 튜플(dead tuple)"이라고 부르고, 이를 정리하는 작업이 바로 VACUUM이다.

VACUUM은 죽은 튜플이 차지하던 공간을 회수해서 이후 INSERT/UPDATE가 재사용할 수 있게 표시한다. 이 작업이 제때 일어나지 않으면 테이블 파일 크기가 실제 살아있는 데이터양보다 훨씬 커지는 현상이 나타나는데, 이를 흔히 **테이블 블로트(bloat)**라고 부른다. 블로트가 심해지면 같은 데이터를 스캔하는 데도 더 많은 디스크 I/O가 필요해지고, 인덱스에도 죽은 엔트리가 쌓여 조회 성능이 점진적으로 나빠진다. PostgreSQL은 이 청소를 자동으로 수행하는 autovacuum 프로세스를 기본으로 제공하지만, 테이블 크기나 트랜잭션 트래픽 특성에 따라 기본 설정만으로는 청소 속도가 쌓이는 속도를 못 따라가는 경우가 있다.

## 예제

아래는 두 개의 psql 세션을 열어 Read Committed와 Repeatable Read의 가시성 차이를 직접 확인하는 예시다.

```sql
-- 세션 A: 기본 격리 수준(Read Committed)으로 트랜잭션 시작
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- 예: 1000

-- (이 시점에 세션 B가 별도로 실행됨)
-- 세션 B: UPDATE accounts SET balance = 2000 WHERE id = 1; COMMIT;

-- 세션 A에서 같은 트랜잭션 안에서 다시 조회
SELECT balance FROM accounts WHERE id = 1;  -- Read Committed: 2000 (변경분이 보임)
COMMIT;
```

```sql
-- 세션 A: Repeatable Read로 트랜잭션 시작
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;  -- 예: 1000

-- (이 시점에 세션 B가 별도로 실행됨)
-- 세션 B: UPDATE accounts SET balance = 2000 WHERE id = 1; COMMIT;

-- 세션 A에서 같은 트랜잭션 안에서 다시 조회
SELECT balance FROM accounts WHERE id = 1;  -- Repeatable Read: 여전히 1000 (스냅샷 고정)
COMMIT;

-- COMMIT 이후 새 트랜잭션에서 조회하면 그때는 2000이 보인다
```

두 예제 모두 세션 B의 UPDATE가 세션 A의 SELECT를 블로킹하지 않는다는 점, 즉 MVCC 덕분에 읽기와 쓰기가 서로를 기다리지 않는다는 점은 동일하다. 다만 세션 A 내부에서 같은 쿼리를 반복했을 때 그 결과가 격리 수준에 따라 달라진다.

## 실무 포인트

장시간 실행되는 트랜잭션은 MVCC의 가장 큰 실무적 위험 요소다. 트랜잭션이 오래 열려 있으면 그 트랜잭션이 시작된 시점 이후에 만들어진 죽은 튜플들을 VACUUM이 회수하지 못한다. 아직 살아있는 그 트랜잭션의 스냅샷이 이론적으로는 그 옛 버전을 참조할 수 있기 때문이다. 배치 작업이나 실수로 커밋/롤백하지 않고 방치된 연결이 며칠씩 열려 있으면, 그동안 발생한 모든 UPDATE/DELETE의 옛 버전이 청소되지 못하고 계속 쌓여 테이블이 눈에 띄게 부풀어 오를 수 있다.

autovacuum을 튜닝할 때 흔히 살펴보는 지점은 다음과 같다.

- `autovacuum_vacuum_scale_factor` / `autovacuum_vacuum_threshold`: 테이블에서 변경된(죽은) 튜플 비율이 이 값을 넘으면 autovacuum이 트리거된다. 갱신이 잦은 큰 테이블은 기본 비율(퍼센트 기준)로는 너무 늦게 트리거될 수 있어, 테이블 단위로 더 낮은 값을 개별 설정하는 경우가 많다.
- `pg_stat_activity`에서 `state`가 `idle in transaction`으로 오래 머무는 세션이 있는지 주기적으로 확인한다. 애플리케이션 커넥션 풀이나 트랜잭션 타임아웃 설정으로 이런 세션이 방치되지 않도록 막는 것이 근본적인 예방책이다.
- `pg_stat_user_tables`의 `n_dead_tup`으로 테이블별 죽은 튜플 수를 확인하면, 어느 테이블이 블로트 위험이 큰지 파악하는 데 도움이 된다.

## 3줄 요약

- PostgreSQL은 UPDATE/DELETE 시 튜플을 덮어쓰지 않고 `xmin`/`xmax`로 버전을 관리하는 MVCC 방식을 써서, 읽기와 쓰기가 서로를 블로킹하지 않는다.
- Read Committed는 문장마다, Repeatable Read는 트랜잭션 시작 시점에 스냅샷을 고정하며, 이 차이가 같은 트랜잭션 내 반복 조회 결과에 영향을 준다.
- 옛 버전(죽은 튜플)은 VACUUM이 정리해야 하며, 장시간 트랜잭션이 이를 막으면 테이블 블로트로 이어지므로 autovacuum 설정과 방치된 트랜잭션 감시가 실무에서 중요하다.

## 참고 자료

- [PostgreSQL 공식 문서 — Concurrency Control (MVCC)](https://www.postgresql.org/docs/current/mvcc-intro.html)
- [PostgreSQL 공식 문서 — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL 공식 문서 — Routine Vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
