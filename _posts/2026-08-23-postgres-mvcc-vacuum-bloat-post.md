---
layout: single
title: "지운 데이터가 디스크를 차지하는 이유 — PostgreSQL MVCC와 VACUUM, 테이블 블로트 관리"
date: 2026-08-23 12:35:00 +0530
categories: database
tags: ["postgresql", "mvcc", "vacuum", "autovacuum", "table-bloat"]
toc: true
toc_sticky: true
excerpt: "PostgreSQL에서 DELETE를 해도 디스크 사용량이 줄지 않는 이유를 MVCC의 튜플 버전 관리에서부터 추적하고, VACUUM이 실제로 하는 일과 못 하는 일, autovacuum 튜닝과 블로트 진단 방법을 정리한다."
---

수백만 건을 DELETE했는데 테이블 크기가 그대로인 경험은 PostgreSQL을 운영하는 사람이라면 한 번쯤 겪는다. UPDATE만 반복했을 뿐인데 테이블이 원본 데이터 크기의 몇 배로 부풀어 있고, 같은 쿼리가 예전보다 눈에 띄게 느려지기도 한다. 이 현상의 뿌리는 PostgreSQL이 동시성을 처리하는 방식, 즉 MVCC(Multi-Version Concurrency Control)에 있다.

PostgreSQL은 UPDATE나 DELETE를 할 때 기존 행을 그 자리에서 고치거나 지우지 않는다. 대신 행의 새 버전을 만들어 옆에 쓰고, 옛 버전에는 "이 트랜잭션 이후로는 안 보임"이라는 표시만 남긴다. 덕분에 읽는 트랜잭션은 락을 기다리지 않고 자신의 스냅숏에 맞는 버전을 읽을 수 있지만, 그 대가로 아무도 볼 수 없게 된 **죽은 튜플(dead tuple)**이 힙에 계속 쌓인다. 이것을 치우는 것이 VACUUM의 일이고, 치우지 못해 누적된 결과가 **테이블 블로트(bloat)**다.

이 글에서는 MVCC가 튜플 버전을 어떻게 관리하는지부터 시작해, VACUUM이 실제로 하는 일과 하지 못하는 일, autovacuum이 왜 큰 테이블에서 늦게 도는지, 그리고 블로트를 진단하고 관리하는 실무 방법을 정리한다.

## 죽은 튜플은 어떻게 생기나 — xmin, xmax와 가시성 판정

힙에 저장되는 모든 튜플에는 시스템 컬럼 `xmin`(이 버전을 만든 트랜잭션 ID)과 `xmax`(이 버전을 지우거나 갱신한 트랜잭션 ID)가 붙는다. INSERT는 `xmin`만 채워진 튜플을 만들고, DELETE는 기존 튜플의 `xmax`에 자기 트랜잭션 ID를 기록할 뿐이다. UPDATE는 둘의 조합이다 — 옛 버전에 `xmax`를 찍고, 새 버전을 `xmin`과 함께 새로 쓴다.

각 트랜잭션은 자신이 시작될 때의 스냅숏을 기준으로 "이 튜플 버전이 나에게 보이는가"를 `xmin`/`xmax`로 판정한다. 어떤 튜플 버전을 볼 수 있는 트랜잭션이 시스템에 하나도 남지 않게 되면 그 버전은 죽은 튜플이 된다. 중요한 것은 이 판정이 **현재 살아 있는 가장 오래된 트랜잭션(xmin horizon)** 기준이라는 점이다. 몇 시간째 열려 있는 트랜잭션이 하나라도 있으면, 그 트랜잭션이 볼 수도 있는 옛 버전들은 전부 "아직 죽지 않은" 것으로 취급되어 VACUUM이 치울 수 없다.

## VACUUM이 하는 일과 못 하는 일

VACUUM(그리고 이를 자동으로 돌리는 autovacuum)은 죽은 튜플이 차지하던 공간을 회수해 **같은 테이블 안에서 재사용 가능한 빈 공간**으로 만들고, 그 위치를 FSM(Free Space Map)에 등록한다. 인덱스에서 죽은 튜플을 가리키던 엔트리도 함께 정리하고, 트랜잭션 ID 랩어라운드를 막기 위한 튜플 동결(freeze)도 수행한다. 일반 VACUUM은 읽기·쓰기와 동시에 돌 수 있어 서비스 중에 실행해도 안전하다.

반면 일반 VACUUM이 **하지 못하는 일**은 파일 크기 축소다. 파일 끝부분이 통째로 비어 있는 특수한 경우가 아니면 데이터 파일을 OS에 반환하지 않는다. 파일을 실제로 줄이려면 `VACUUM FULL`이 필요한데, 이는 테이블 전체를 새 파일로 다시 쓰면서 **ACCESS EXCLUSIVE 락**을 잡는다. 즉 실행되는 동안 그 테이블에 대한 읽기조차 전부 막힌다.

| 구분 | VACUUM (일반) | VACUUM FULL |
|---|---|---|
| 락 | 읽기·쓰기와 동시 실행 가능 | ACCESS EXCLUSIVE (읽기도 차단) |
| 공간 처리 | 테이블 내부 재사용 공간으로 회수 | 새 파일로 재작성, OS에 반환 |
| 추가 디스크 | 거의 불필요 | 테이블 크기만큼 임시 공간 필요 |
| 용도 | 상시 유지보수 (autovacuum) | 블로트가 심각할 때의 최후 수단 |

<img src="/assets/images/posts/2026-08-23-postgres-mvcc-vacuum-bloat-1.svg" alt="UPDATE가 죽은 튜플을 만들고 VACUUM이 그 공간을 재사용 가능하게 회수하는 과정을 보여주는 다이어그램" style="width:100%;">

## autovacuum은 왜 큰 테이블에서 늦게 도는가

autovacuum이 특정 테이블을 청소하는 시점은 대략 `autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor × 행 수`만큼 죽은 튜플이 쌓였을 때다. scale_factor의 기본값은 0.2, 즉 전체 행의 20%다. 1억 행 테이블이라면 죽은 튜플이 2천만 개가 될 때까지 autovacuum이 시작조차 하지 않는다는 뜻이다. 게다가 autovacuum은 I/O 부하를 제한하는 비용 기반 지연(cost-based delay)을 받으며 돌기 때문에, 시작한 뒤에도 큰 테이블 한 번 도는 데 오랜 시간이 걸릴 수 있다.

그래서 갱신이 잦은 대형 테이블에는 전역 설정 대신 **테이블 단위로 scale_factor를 낮추는** 것이 정석이다. 자주, 조금씩 도는 VACUUM이 가끔 크게 도는 VACUUM보다 언제나 낫다.

## 예제 — 블로트 진단과 테이블 단위 튜닝

```sql
-- 1) 죽은 튜플 비율과 마지막 vacuum 시각 확인
SELECT relname,
       n_live_tup,
       n_dead_tup,
       round(n_dead_tup * 100.0 / nullif(n_live_tup + n_dead_tup, 0), 1)
           AS dead_ratio_pct,
       last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;

-- 2) pgstattuple 확장으로 실제 블로트 측정 (정확하지만 테이블 전체를 읽음)
CREATE EXTENSION IF NOT EXISTS pgstattuple;
SELECT table_len, dead_tuple_percent, free_percent
FROM pgstattuple('orders');

-- 3) 갱신이 잦은 대형 테이블: 행 수의 1%만 쌓여도 vacuum이 돌도록 조정
ALTER TABLE orders SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold    = 1000
);

-- 4) VACUUM을 막고 있는 장기 트랜잭션 찾기
SELECT pid, state, xact_start, query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'active')
  AND xact_start < now() - interval '30 minutes'
ORDER BY xact_start;
```

## 실무 포인트와 흔한 함정

**함정 1 — 블로트가 쌓이면 반사적으로 VACUUM FULL을 돌리는 것.** VACUUM FULL은 읽기까지 차단하는 락을 잡으므로 운영 중 테이블에 돌리면 그대로 장애가 된다. 진짜 문제는 대개 "autovacuum이 왜 못 따라갔는가"이고, 답은 scale_factor 조정이나 장기 트랜잭션 정리인 경우가 많다. 이미 부풀어버린 공간을 정말 반환해야 한다면 락을 최소화하면서 온라인으로 재작성하는 `pg_repack` 같은 확장을 검토하는 편이 안전하다.

**함정 2 — idle in transaction 커넥션 방치.** 애플리케이션이 트랜잭션을 열어놓고 커밋을 잊으면, 그 세션 하나가 클러스터 전체의 xmin horizon을 붙잡아 **모든 테이블**의 VACUUM을 무력화한다. "VACUUM을 계속 돌리는데 죽은 튜플이 줄지 않는다"면 십중팔구 이 경우다. `idle_in_transaction_session_timeout`을 설정해 방치된 트랜잭션을 강제 종료하는 안전망을 두는 것이 좋다. 같은 이유로 오래 걸리는 배치 조회, 방치된 복제 슬롯, `hot_standby_feedback`이 켜진 스탠바이의 장기 쿼리도 점검 대상이다.

덧붙여, 갱신이 잦은 테이블이라면 `fillfactor`를 100 미만(예: 90)으로 낮춰 페이지에 여유 공간을 남겨두는 것도 유효하다. 인덱스 컬럼을 건드리지 않는 UPDATE가 같은 페이지 안에서 처리되는 **HOT(Heap-Only Tuple) 업데이트**의 비율이 올라가고, 인덱스 갱신과 블로트 양쪽이 줄어든다.

## 마무리 요약

- PostgreSQL의 UPDATE/DELETE는 행을 지우지 않고 버전 표시만 남기므로, 죽은 튜플을 회수하는 VACUUM이 따라가지 못하면 테이블 블로트가 쌓인다.
- 일반 VACUUM은 공간을 테이블 내부 재사용분으로만 돌려놓으며, 파일 축소가 필요할 때 VACUUM FULL은 읽기까지 차단하므로 운영 중에는 pg_repack 등의 대안을 검토한다.
- 대형 테이블은 autovacuum scale_factor를 테이블 단위로 낮추고, 장기 트랜잭션(idle in transaction)이 xmin horizon을 붙잡고 있지 않은지 상시 감시한다.

## 참고 자료

- [PostgreSQL 공식 문서 — Routine Vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
- [PostgreSQL 공식 문서 — MVCC 소개](https://www.postgresql.org/docs/current/mvcc-intro.html)
- [PostgreSQL 공식 문서 — VACUUM 명령](https://www.postgresql.org/docs/current/sql-vacuum.html)
- [PostgreSQL 공식 문서 — pgstattuple 확장](https://www.postgresql.org/docs/current/pgstattuple.html)
- [PostgreSQL 공식 문서 — Heap-Only Tuples (HOT)](https://www.postgresql.org/docs/current/storage-hot.html)
