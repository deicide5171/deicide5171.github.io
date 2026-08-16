---
layout: single
title: "전원이 꺼져도 커밋은 살아남는다 — WAL과 체크포인트로 보는 DB 장애 복구의 원리"
date: 2026-08-23 13:35:00 +0530
categories: database
tags: ["database", "wal", "checkpoint", "crash-recovery", "postgresql", "durability"]
toc: true
toc_sticky: true
excerpt: "커밋 직후 서버 전원이 나가도 데이터가 사라지지 않는 이유를 WAL(Write-Ahead Logging)과 체크포인트 메커니즘으로 풀어보고, 복구 시간과 I/O 부하 사이의 트레이드오프를 튜닝하는 법을 정리한다."
---

`COMMIT`이 성공으로 돌아온 직후 서버 전원이 나갔다고 하자. 재시작한 DB에서 그 데이터는 남아 있을까? ACID의 D(내구성)가 보장하는 답은 "남아 있다"이지만, 이 보장이 어떻게 구현되는지는 의외로 잘 알려져 있지 않다. 커밋할 때마다 수정된 데이터 페이지를 전부 디스크에 쓰면 되겠지만, 데이터 파일 곳곳에 흩어진 페이지를 트랜잭션마다 랜덤 쓰기로 반영하고 fsync까지 하는 방식으로는 쓸 만한 처리량이 나오지 않는다.

그래서 거의 모든 RDBMS는 반대로 접근한다. 데이터 페이지는 메모리(버퍼 풀)에서만 고치고 디스크 반영은 미루되, "무엇을 바꿨는지"를 적은 로그 레코드만 커밋 시점에 디스크에 확실히 남기는 것이다. 이것이 WAL(Write-Ahead Logging)이고, PostgreSQL의 WAL, MySQL InnoDB의 리두 로그(redo log), SQLite의 WAL 모드가 모두 같은 원리 위에 서 있다. 장애가 나면 재시작 시 이 로그를 다시 재생(replay)해서 잃어버린 페이지 변경을 복원한다.

이 글에서는 PostgreSQL을 기준으로 WAL이 내구성과 성능을 동시에 잡는 원리, 체크포인트가 복구 시간을 제어하는 방식, 그리고 체크포인트 간격을 둘러싼 트레이드오프를 정리한다.

## 핵심 개념 1: WAL — 데이터보다 로그를 먼저 쓴다

WAL의 규칙은 하나다. **어떤 데이터 페이지도, 그 페이지의 변경 내용을 담은 로그 레코드가 디스크에 안전하게 기록되기 전에는 디스크에 내려가지 않는다.** 커밋 시점에 디스크에 동기화(fsync)되는 것은 데이터 파일이 아니라 WAL 파일뿐이다. 이 순서만 지켜지면, 어떤 시점에 전원이 나가도 "커밋됐는데 로그에 없는 변경"은 존재할 수 없다.

성능 면에서도 이 구조는 유리하다. WAL은 파일 끝에 이어 붙이는 **순차 쓰기**라서 데이터 파일 곳곳을 갱신하는 랜덤 쓰기보다 훨씬 빠르고, 같은 시점에 커밋되는 여러 트랜잭션의 로그를 한 번의 fsync로 묶어 내리는 그룹 커밋도 가능하다. 각 로그 레코드에는 LSN(Log Sequence Number)이라는 단조 증가 위치 값이 붙고, 각 데이터 페이지에는 자신을 마지막으로 수정한 레코드의 LSN이 기록된다. 복구 시 "이 페이지에 이 로그를 다시 적용해야 하는가"를 판정하는 기준이 바로 이 값이다.

## 핵심 개념 2: 체크포인트 — 복구 시작점을 앞으로 당기는 장치

WAL만으로는 두 가지 문제가 남는다. 로그를 영원히 지울 수 없다는 것, 그리고 재시작 시 로그 전체를 재생해야 해서 복구 시간이 무한정 길어질 수 있다는 것이다. 이를 해결하는 장치가 **체크포인트(checkpoint)**다. 체크포인트는 그 시점까지 메모리에 쌓인 더티 페이지(수정됐지만 아직 디스크에 안 내려간 페이지)를 데이터 파일에 반영하고, "이 지점 이전의 변경은 모두 데이터 파일에 있다"는 표시를 남기는 작업이다.

체크포인트가 끝나면 그 이전 구간의 WAL은 복구에 필요 없어지므로 재활용하거나 지울 수 있고, 장애 후 복구는 항상 **마지막 체크포인트의 REDO 지점부터** 시작하면 된다. 즉 체크포인트 간격이 곧 최악의 경우 재생해야 할 WAL 양이고, 이는 복구 소요 시간의 상한을 결정한다. PostgreSQL은 `checkpoint_timeout`(시간 기준)과 `max_wal_size`(WAL 누적량 기준) 중 먼저 도달하는 쪽에서 체크포인트를 시작한다.

<img src="/assets/images/posts/2026-08-23-wal-checkpoint-crash-recovery-1.svg" alt="정상 운영 시 커밋은 WAL만 fsync하고 더티 페이지는 체크포인트 때 데이터 파일에 반영되는 구조, 장애 복구 시 마지막 체크포인트부터 WAL을 재생하는 타임라인" style="width:100%;">

## 핵심 개념 3: 복구 흐름과 토른 페이지 방어

재시작한 PostgreSQL은 제어 파일에서 마지막 체크포인트 위치를 읽고, 거기서부터 WAL을 순서대로 재생한다(REDO). 페이지의 LSN이 로그 레코드의 LSN보다 이미 크면 그 변경은 반영된 것이므로 건너뛴다. 커밋 로그가 없는 트랜잭션의 변경은 PostgreSQL에서는 MVCC 특성상 "커밋 안 된 버전"으로 남아 자연히 무시되고, InnoDB처럼 언두(undo) 로그를 쓰는 엔진은 REDO 후 미완료 트랜잭션을 되돌리는 롤백 단계를 거친다.

한 가지 함정이 더 있다. DB 페이지(보통 8KB)는 디스크 섹터보다 커서, 쓰는 도중 전원이 나가면 페이지의 앞부분만 갱신된 **토른 페이지(torn page)**가 생길 수 있다. 이런 페이지에는 로그 재생 자체가 불가능하므로, PostgreSQL은 체크포인트 후 각 페이지가 처음 수정될 때 페이지 전체 이미지를 WAL에 넣는 `full_page_writes`로 방어하고, InnoDB는 더블라이트 버퍼(doublewrite buffer)로 같은 문제를 푼다.

| 구분 | PostgreSQL | MySQL InnoDB |
|---|---|---|
| 로그 이름 | WAL | 리두 로그(redo log) |
| 미완료 트랜잭션 처리 | MVCC로 자연 무시 | 언두 로그로 롤백 |
| 토른 페이지 방어 | full_page_writes | 더블라이트 버퍼 |
| 커밋 내구성 설정 | synchronous_commit | innodb_flush_log_at_trx_commit |

## 예제: PostgreSQL WAL·체크포인트 설정

```conf
# postgresql.conf — WAL·체크포인트 관련 핵심 설정

# 커밋 시 WAL을 디스크까지 동기화할지. on이면 커밋 유실 없음(기본값)
synchronous_commit = on

# 체크포인트 사이 최대 시간 간격 (기본 5min, 늘리면 복구 시간도 늘어남)
checkpoint_timeout = 15min

# WAL이 이 크기에 근접하면 시간과 무관하게 체크포인트를 시작 (기본 1GB)
max_wal_size = 4GB

# 체크포인트 쓰기를 간격의 90%에 걸쳐 분산해 I/O 스파이크 완화
checkpoint_completion_target = 0.9

# 체크포인트 발생 시각과 원인을 로그에 남김 (최근 버전 기본 on)
log_checkpoints = on

# 체크포인트 후 첫 수정 페이지의 전체 이미지를 WAL에 기록 (끄지 말 것)
full_page_writes = on
```

설정 후에는 서버 로그에서 체크포인트가 `time`(시간 도달) 때문에 도는지 `wal`(누적량 도달) 때문에 도는지 확인한다. `wal` 사유가 반복된다면 `max_wal_size`가 실제 쓰기량 대비 너무 작다는 신호다.

## 실무 포인트

- **`fsync = off`와 `synchronous_commit = off`를 혼동하지 말 것**: 흔한 안티패턴이 "쓰기 성능이 안 나온다"며 `fsync = off`를 켜는 것이다. 이 설정은 장애 시 복구 불가능한 데이터 파일 손상을 일으킬 수 있어 운영 환경에서는 금물이다. 반면 `synchronous_commit = off`는 최근 커밋 몇 개가 유실될 수 있을 뿐 DB 일관성 자체는 깨지지 않으므로, 유실을 감내할 수 있는 로그성 데이터라면 트랜잭션 단위로 선택적으로 쓸 수 있는 정당한 옵션이다.
- **체크포인트 간격은 복구 시간과 I/O 부하의 트레이드오프다**: 간격을 늘리면 full_page_writes로 인한 WAL 증폭과 반복 쓰기가 줄어 평상시 성능은 좋아지지만, 장애 시 재생할 WAL이 늘어 재시작이 느려진다. 복구 시간 목표(RTO)가 빡빡한 서비스라면 간격을 무작정 늘리면 안 된다.
- **체크포인트가 너무 잦으면 그 자체가 부하다**: `max_wal_size`가 작아 체크포인트가 수 분마다 강제로 돌면, 매번 페이지 전체 이미지를 다시 WAL에 쓰는 비용까지 겹쳐 쓰기 부하가 증폭된다. 로그의 체크포인트 사유를 보고 대부분 `time` 사유로 돌도록 여유를 주는 것이 일반적인 튜닝 방향이다.

## 3줄 요약

- 커밋 시 디스크에 동기화되는 것은 데이터 파일이 아니라 WAL이며, "로그를 데이터보다 먼저 쓴다"는 규칙 하나로 내구성과 순차 쓰기 성능을 동시에 얻는다.
- 체크포인트는 더티 페이지를 데이터 파일에 반영해 복구 시작점을 앞으로 당기는 장치로, 그 간격이 장애 시 재생할 WAL 양(=복구 시간)의 상한을 결정한다.
- 체크포인트 간격 튜닝은 평상시 I/O 부하와 복구 시간의 트레이드오프이며, `fsync = off` 같은 내구성 자체를 깨는 설정과 커밋 지연만 감수하는 `synchronous_commit = off`는 전혀 다른 선택지다.

## 참고 자료

- [PostgreSQL 공식 문서: Reliability and the Write-Ahead Log](https://www.postgresql.org/docs/current/wal-intro.html)
- [PostgreSQL 공식 문서: WAL Configuration](https://www.postgresql.org/docs/current/wal-configuration.html)
- [PostgreSQL 공식 문서: Write Ahead Log 설정 파라미터](https://www.postgresql.org/docs/current/runtime-config-wal.html)
- [MySQL 공식 문서: InnoDB Redo Log](https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html)
- [MySQL 공식 문서: InnoDB Doublewrite Buffer](https://dev.mysql.com/doc/refman/8.4/en/innodb-doublewrite-buffer.html)
