---
layout: single
title: "pg_dump로는 안 된다 — pgBackRest·WAL-G로 하는 PostgreSQL 물리 백업 실전"
date: 2026-08-24 12:35:00 +0530
categories: database
tags: ["postgresql", "pgbackrest", "wal-g", "backup", "disaster-recovery", "wal-archiving"]
toc: true
toc_sticky: true
excerpt: "수백 GB급 PostgreSQL 운영 환경에서 pg_dump가 감당하지 못하는 백업 부담을, pgBackRest와 WAL-G가 물리 백업·WAL 아카이빙으로 어떻게 해결하는지 비교 정리한다."
---

수십 GB짜리 개발 DB라면 `pg_dump` 한 줄로 충분하다. 그러나 수백 GB, 수 TB급 운영 DB에서 논리 백업은 백업 자체에 몇 시간이 걸리고, 복원은 그보다 더 오래 걸리며, 백업 도중 벌어진 트랜잭션의 일관성 보장도 까다로워진다. 이 규모에서는 데이터 파일을 통째로 복사하는 물리 백업(physical backup)과, 그 사이의 변경분을 놓치지 않는 WAL 아카이빙의 조합이 사실상 유일한 선택지다.

문제는 물리 백업을 직접 구현하려면 `pg_basebackup`만으로는 부족한 기능 — 증분/차등 백업, 병렬 처리, 원격 스토리지 업로드, 보관 주기 관리 — 이 많다는 것이다. 이 공백을 메우는 두 대표 도구가 pgBackRest와 WAL-G다.

이 글에서는 두 도구의 설계 철학 차이, 실제 설정, 그리고 백업 전략 수립 시 놓치기 쉬운 점을 정리한다.

## 핵심 개념 1: 논리 백업과 물리 백업은 다른 문제를 푼다

`pg_dump`는 SQL 문 또는 커스텀 포맷으로 데이터를 논리적으로 덤프한다. 스키마 변경(메이저 버전 업그레이드, 컬럼 타입 변경)에 유연하지만, 덤프·복원 모두 SQL을 다시 실행하는 과정이라 데이터 규모에 비례해 느려진다. 반면 물리 백업은 디스크의 데이터 파일 자체를 바이트 단위로 복사한다. 복원 시 SQL 재실행이 없으므로 훨씬 빠르지만, 같은 메이저 버전 간에만 호환된다.

운영 환경의 RTO(복구 목표 시간)를 짧게 가져가야 한다면 물리 백업이 기본 선택지가 되고, `pg_basebackup`이 그 표준 도구다. 하지만 `pg_basebackup`은 증분 백업이 없고(PostgreSQL 17부터 일부 지원 시작), 병렬 압축·업로드가 제한적이며, 보관 정책 관리 기능이 없다. pgBackRest와 WAL-G는 이 위에서 실무에 필요한 기능을 채운다.

## 핵심 개념 2: pgBackRest vs WAL-G

| 구분 | pgBackRest | WAL-G |
|---|---|---|
| 구현 언어 | C/Perl | Go |
| 백업 유형 | 풀/증분/차등 | 풀 + 델타(증분) |
| 병렬 처리 | 백업·복원 모두 병렬 지원 | 병렬 업로드/다운로드 지원 |
| 스토리지 백엔드 | S3, Azure, GCS, POSIX, SFTP | S3, GCS, Azure, 파일시스템 |
| 페이지 체크섬 검증 | 지원 | 제한적 |
| 설정 복잡도 | 상대적으로 높음(기능이 많은 만큼) | 상대적으로 단순 |
| 대표 채택 사례 | 대규모 온프레미스/하이브리드 | Postgres Operator(Zalando), Patroni 연동 |

pgBackRest는 기능이 풍부한 대신 설정 항목도 많아 학습 곡선이 있고, WAL-G는 Kubernetes 오퍼레이터 생태계(Zalando Postgres Operator, CloudNativePG 일부 구성)에서 가볍게 붙이기 좋은 선택으로 자주 쓰인다. 둘 다 핵심 원리는 같다 — 주기적인 베이스 백업 + 연속적인 WAL 아카이빙.

## 예제: pgBackRest 설정과 백업 명령

```ini
# /etc/pgbackrest/pgbackrest.conf
[global]
repo1-path=/var/lib/pgbackrest
repo1-retention-full=2
repo1-type=s3
repo1-s3-bucket=my-pg-backups
repo1-s3-region=ap-northeast-2
repo1-s3-endpoint=s3.ap-northeast-2.amazonaws.com
process-max=4
compress-type=zst

[main]
pg1-path=/var/lib/postgresql/16/main
```

```bash
# postgresql.conf 쪽 필수 설정
# archive_mode = on
# archive_command = 'pgbackrest --stanza=main archive-push %p'

# 최초 스탠자 생성 및 풀 백업
pgbackrest --stanza=main stanza-create
pgbackrest --stanza=main --type=full backup

# 이후 증분 백업 (변경분만)
pgbackrest --stanza=main --type=incr backup

# 특정 시점으로 복원 (PITR과 결합)
pgbackrest --stanza=main --type=time \
  --target="2026-08-24 09:00:00" restore
```

WAL-G는 환경 변수 기반 설정(`WALG_S3_PREFIX`, `PGHOST` 등)과 `wal-g backup-push`, `wal-g backup-fetch` 명령 조합으로 유사한 흐름을 구현한다.

## 실무 포인트

- **백업은 복원 테스트 전까지 백업이 아니다**: 별도 인스턴스에 정기적으로 복원해 실제로 서비스가 뜨는지 검증하는 절차 없이는, 장애 시점에 백업 파일이 손상돼 있었다는 사실을 그때서야 알게 된다. pgBackRest의 `check` 명령과 정기 복원 리허설을 함께 스케줄링해야 한다.
- **WAL 아카이빙 지연을 반드시 모니터링한다**: `archive_command`가 실패하거나 원격 스토리지 업로드가 밀리면 WAL이 로컬 디스크에 쌓여 디스크가 가득 차고 DB가 정지할 수 있다. 아카이빙 랙(lag)을 지표로 노출해 알람을 걸어야 한다.
- **증분 백업 체인이 길어질수록 복원 시간이 늘어난다**: 매번 증분만 쌓으면 백업 속도는 빨라지지만, 복원할 때 풀 백업부터 모든 증분을 순서대로 적용해야 하므로 체인이 길면 RTO가 나빠진다. 정기적으로 풀 백업을 다시 잡아 체인을 리셋하는 보관 정책이 필요하다.

## 3줄 요약

- 대용량 PostgreSQL 운영 환경에서는 `pg_dump` 논리 백업 대신 데이터 파일을 직접 복사하는 물리 백업과 WAL 아카이빙의 조합이 필요하다.
- pgBackRest는 기능이 풍부하고 검증이 강력한 대신 설정이 복잡하고, WAL-G는 가볍고 Kubernetes 오퍼레이터 생태계와 궁합이 좋다.
- 백업은 정기적인 복원 리허설과 WAL 아카이빙 랙 모니터링 없이는 신뢰할 수 없으며, 증분 체인 길이와 RTO의 트레이드오프도 함께 관리해야 한다.

## 참고 자료

- [pgBackRest 공식 문서](https://pgbackrest.org/user-guide.html)
- [WAL-G GitHub 저장소](https://github.com/wal-g/wal-g)
- [PostgreSQL 공식 문서: Continuous Archiving and Point-in-Time Recovery](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [PostgreSQL 공식 문서: pg_basebackup](https://www.postgresql.org/docs/current/app-pgbasebackup.html)
