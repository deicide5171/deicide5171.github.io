---
layout: single
title: "그 순간으로 되돌리기 — PITR(Point-In-Time Recovery) 실전"
date: 2026-08-24 13:35:00 +0530
categories: database
tags: ["postgresql", "pitr", "point-in-time-recovery", "wal", "disaster-recovery", "timeline"]
toc: true
toc_sticky: true
excerpt: "실수로 DROP TABLE을 실행한 순간 필요한 것은 최신 상태 복구가 아니라 '그 사고 직전'으로의 복구다. PITR이 이를 가능하게 하는 원리와 recovery_target 설정, 타임라인 개념을 정리한다."
---

장애 복구(crash recovery)는 자동으로 일어난다. DB가 재시작되면 마지막 커밋 상태까지 스스로 복구한다. 그런데 문제가 "장애"가 아니라 "사람의 실수"라면 얘기가 다르다. 운영자가 `WHERE` 절 없는 `DELETE`를 실행하거나 배포 스크립트가 잘못된 테이블을 `DROP`했다면, DB는 멀쩡히 살아있고 그 실수도 커밋으로 완벽히 반영된다. 이럴 때 필요한 것은 "최신 상태로의 자동 복구"가 아니라 "그 사고 발생 몇 초 전"이라는 임의의 과거 시점으로 되돌리는 것이다.

이것이 PITR(Point-In-Time Recovery)이다. 베이스 백업과 연속적인 WAL 아카이브가 준비돼 있다면, 원하는 시각·트랜잭션·명명된 지점까지만 WAL을 재생해 그 순간의 DB 상태를 복원할 수 있다. 이 글에서는 PITR의 동작 원리, 복구 목표 지정 방법, 그리고 실무에서 자주 실수하는 지점을 정리한다.

## 핵심 개념 1: PITR은 크래시 복구와 다른 문제를 푼다

크래시 복구는 "가장 최근의 일관된 상태"로 자동 복원하는 것이 목표이며, 재시작 시 강제로 실행되고 대상 시점을 선택할 여지가 없다. PITR은 반대로 "임의로 지정한 과거 시점"으로 의도적으로 되돌리는 작업이며, 운영자가 명시적으로 트리거해야 한다.

| 구분 | 크래시 복구 | PITR |
|---|---|---|
| 트리거 | 재시작 시 자동 | 운영자가 수동으로 실행 |
| 목표 지점 | 항상 최신 일관 상태 | 임의로 지정한 과거 시점 |
| 전제 조건 | WAL만 있으면 됨 | 베이스 백업 + 연속 WAL 아카이브 필요 |
| 대표 시나리오 | 정전, 프로세스 강제 종료 | 실수로 인한 데이터 삭제, 랜섬웨어 |

PITR을 쓰려면 사전에 `archive_mode`가 켜져 있고 `archive_command`(또는 pgBackRest/WAL-G 같은 도구)로 WAL이 끊김 없이 별도 저장소에 쌓이고 있어야 한다. 이 연속성이 끊긴 구간이 있으면, 그 구간을 건너뛴 복구는 불가능하다.

## 핵심 개념 2: 복구 목표(recovery_target) 종류

PostgreSQL은 네 가지 방식으로 복구 목표 지점을 지정할 수 있다.

- **`recovery_target_time`**: 특정 시각까지 복구. 가장 직관적이지만, "사고가 정확히 몇 시 몇 분에 일어났는지" 확신이 없으면 여러 번 시행착오가 필요하다.
- **`recovery_target_xid`**: 특정 트랜잭션 ID 직전/직후까지 복구. 사고를 일으킨 트랜잭션 ID를 로그에서 특정할 수 있을 때 가장 정확하다.
- **`recovery_target_lsn`**: 특정 WAL LSN까지 복구. 로그 분석 도구로 정확한 LSN을 파악했을 때 사용.
- **`recovery_target_name`**: 사전에 `pg_create_restore_point()`로 만들어 둔 명명된 지점까지 복구. 위험한 배포 직전에 미리 찍어두면 가장 안전하고 빠르다.

`recovery_target_inclusive` 옵션으로 지정한 지점을 포함할지(사고 트랜잭션까지 포함) 제외할지(그 직전까지만) 결정한다.

## 예제: 특정 시각으로 PITR 수행 (PostgreSQL 16 이상)

```bash
# 1. 베이스 백업을 새 데이터 디렉터리로 복원
pg_basebackup -D /var/lib/postgresql/16/restore \
  --checkpoint=fast

# 2. 복구 신호 파일 생성 (12 이전은 recovery.conf, 이후는 이 방식)
touch /var/lib/postgresql/16/restore/recovery.signal
```

```conf
# postgresql.conf (restore 디렉터리)
restore_command = 'cp /mnt/wal_archive/%f %p'
recovery_target_time = '2026-08-24 09:14:00+09'
recovery_target_action = 'pause'   # 목표 지점에서 일시정지, 검증 후 promote
```

```sql
-- 복구가 목표 지점에서 일시정지되면, 별도 연결로 데이터를 확인한다
SELECT count(*) FROM orders WHERE created_at > '2026-08-24 09:00:00';

-- 원하는 상태가 맞으면 승격(더 이상 WAL을 받지 않고 쓰기 가능한 상태로 전환)
SELECT pg_promote();
```

`recovery_target_action = 'pause'`로 두면 목표 지점에서 자동으로 승격하지 않고 멈춰서, 실제로 원하는 상태인지 검증한 뒤 `pg_promote()`로 확정할 수 있다. 이 확인 단계 없이 바로 `promote`로 진행하면 목표 시점을 잘못 잡았을 때 되돌릴 방법이 없다.

## 실무 포인트

- **PITR은 원본 인스턴스가 아니라 별도 인스턴스에서 수행한다**: 운영 중인 DB에 직접 복구를 시도하면 원본 데이터까지 잃을 위험이 있다. 별도 서버(또는 별도 데이터 디렉터리)에 복원해 검증한 뒤, 애플리케이션 전환이나 특정 테이블만 골라 원본에 반영하는 방식이 안전하다.
- **타임라인(timeline) 개념을 이해해야 한다**: PITR로 과거 시점에서 새 쓰기가 시작되면 PostgreSQL은 새로운 타임라인 ID를 부여한다. 같은 베이스 백업에서 다시 다른 시점으로 복구를 시도할 때, 타임라인이 갈라진 이후의 WAL은 서로 호환되지 않으므로 `recovery_target_timeline` 설정을 명확히 해야 헷갈리지 않는다.
- **RPO는 WAL 아카이빙 주기에 의해 결정된다**: PITR로 복구 가능한 가장 최근 시점은 아카이빙된 WAL의 최신 지점까지다. `archive_command` 실패나 아카이빙 지연이 누적되면, 사고 직전까지 복구하고 싶어도 그 구간의 WAL이 없어 불가능할 수 있다. 아카이빙 상태를 감시하는 것이 PITR 신뢰성의 전제 조건이다.

## 3줄 요약

- PITR은 재시작 시 자동으로 일어나는 크래시 복구와 달리, 사람의 실수로 인한 사고 등에서 임의의 과거 시점으로 의도적으로 되돌리는 수동 복구 절차다.
- `recovery_target_time/xid/lsn/name` 중 상황에 맞는 방식으로 목표 지점을 지정하고, `recovery_target_action = pause`로 검증 후 승격하는 것이 안전하다.
- 별도 인스턴스에서 복구를 수행하고, 타임라인 개념과 WAL 아카이빙 연속성(RPO 결정 요인)을 이해하는 것이 실무 적용의 핵심이다.

## 참고 자료

- [PostgreSQL 공식 문서: Recovery Target Settings](https://www.postgresql.org/docs/current/runtime-config-wal.html#RUNTIME-CONFIG-WAL-RECOVERY-TARGET)
- [PostgreSQL 공식 문서: Continuous Archiving and Point-in-Time Recovery (PITR)](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [PostgreSQL 공식 문서: pg_create_restore_point](https://www.postgresql.org/docs/current/functions-admin.html)
- [PostgreSQL 공식 문서: Timelines](https://www.postgresql.org/docs/current/continuous-archiving.html#BACKUP-TIMELINES)
