---
layout: single
title: "테이블을 잠그지 않고 바꾼다 — gh-ost와 pt-online-schema-change 내부 동작"
date: 2026-08-25 13:35:00 +0530
categories: database
tags: ["online-ddl", "gh-ost", "pt-online-schema-change", "mysql", "schema-migration"]
toc: true
toc_sticky: true
excerpt: "수억 건짜리 MySQL 테이블에 컬럼 하나 추가하려다 서비스가 멈추는 사고를 막는 gh-ost와 pt-online-schema-change의 그림자 테이블 복사·binlog 스트리밍·컷오버 메커니즘을 비교한다."
---

MySQL에서 수억 건짜리 테이블에 `ALTER TABLE`로 컬럼 하나를 추가하려는데, 이 명령이 몇 시간 동안 테이블을 잠그고 서비스 전체를 멈춰 세운 적이 있다면 이미 이 문제를 몸으로 겪은 것이다. InnoDB의 온라인 DDL(`ALGORITHM=INPLACE`)이 많은 변경을 무중단으로 처리할 수 있게 개선되긴 했지만, 여전히 특정 변경 유형이나 MySQL 버전, 복제 지연 요구 조건에 따라 온라인 DDL만으로는 부족한 경우가 많다.

이 틈을 메우는 것이 **gh-ost**(GitHub)와 **pt-online-schema-change**(Percona Toolkit, 이하 pt-osc)다. 둘 다 "원본 테이블을 잠그지 않고 스키마를 바꾼다"는 목표는 같지만, 그 목표를 달성하는 내부 메커니즘이 근본적으로 다르다. 이 글은 애플리케이션·배포 레벨의 무중단 마이그레이션 패턴(Expand-Contract 등)이 아니라, 이 두 도구가 MySQL 내부에서 실제로 데이터를 어떻게 옮기는지에 집중한다.

## 핵심 개념 1: 공통 전략 — 그림자 테이블 복사 후 스왑

두 도구 모두 기본 전략은 같다. 원본 테이블과 동일한 구조에 원하는 변경 사항을 적용한 **그림자 테이블(shadow/ghost table)**을 새로 만들고, 원본 데이터를 그 테이블로 조금씩 복사한다. 복사가 끝나면 원본 테이블과 그림자 테이블의 이름을 원자적으로 바꿔치기(rename swap)해서 전환을 완료한다. 문제는 이 복사가 진행되는 동안 원본 테이블에 계속 들어오는 변경(INSERT/UPDATE/DELETE)을 그림자 테이블에도 반영해야 한다는 점이고, 이 부분에서 두 도구의 접근이 갈린다.

## 핵심 개념 2: pt-osc의 트리거 방식 vs gh-ost의 binlog 스트리밍

**pt-online-schema-change**는 원본 테이블에 `INSERT`, `UPDATE`, `DELETE` 트리거를 걸어, 원본에 변경이 생길 때마다 그 트리거가 그림자 테이블에도 즉시 같은 변경을 반영한다. 구현이 상대적으로 단순하지만, 모든 쓰기 트랜잭션이 트리거 실행 비용을 추가로 부담하게 되므로 쓰기가 많은 테이블에서는 원본 테이블 자체의 쓰기 성능에 영향을 줄 수 있다.

**gh-ost**는 트리거를 전혀 쓰지 않는다. 대신 자신을 MySQL 복제 토폴로지의 레플리카처럼 등록해서 **binlog(바이너리 로그) 스트림을 직접 읽고**, 원본 테이블에 대한 변경 이벤트를 파싱해 그림자 테이블에 비동기로 반영한다. 트리거가 없으므로 원본 테이블의 쓰기 경로에 추가 부하를 주지 않고, 복제 지연이 심할 때는 스로틀링(throttling)으로 복사 속도를 늦춰 레플리카가 따라잡을 시간을 벌 수 있다. 대신 binlog 포맷이 ROW여야 하고, 복제 토폴로지에 개입하는 만큼 운영 복잡도는 더 높다.

| 구분 | pt-online-schema-change | gh-ost |
|---|---|---|
| 변경 반영 방식 | 트리거(INSERT/UPDATE/DELETE) | binlog 스트림 파싱 |
| 원본 테이블 쓰기 부하 | 트리거 실행 비용 추가 | 거의 없음 |
| 필요 조건 | 트리거 생성 권한 | ROW 포맷 binlog, 복제 권한 |
| 처리량 제어(throttle) | 복제 지연 기준 폴링 | binlog 스트림 기반 정교한 제어 |
| 실행 위치 | 어디서나 실행 가능 | 마스터 또는 레플리카 대상 |

## 핵심 개념 3: 컷오버(cut-over) — 가장 위험한 순간

복사가 끝난 뒤 원본과 그림자 테이블을 바꿔치기하는 컷오버 순간이 두 도구 모두에서 가장 조심스러운 구간이다. rename 자체는 원자적이지만, 그 직전까지 밀려 있던 변경분(트리거 큐 또는 binlog 큐)을 마저 반영하고 나서 rename해야 데이터 누락이 없다. pt-osc는 컷오버 시점에 짧은 테이블 잠금을 걸어 이 마지막 동기화와 rename을 원자적으로 처리하고, gh-ost는 `cut-over` 단계에서 원자적 rename을 위해 아주 짧은 순간 두 테이블을 동시에 잠그는 방식을 쓴다. 두 방식 모두 이 구간은 수백 밀리초 수준으로 짧지만, 트래픽이 매우 많은 서비스라면 이 짧은 순간에도 타임아웃이 발생할 수 있어 컷오버 시점을 트래픽이 낮은 시간대로 잡는 것이 안전하다.

## 예제: gh-ost 실행 명령

```bash
gh-ost \
  --host=db-primary.internal \
  --user=migration_user \
  --password="$MIGRATION_PW" \
  --database=shop \
  --table=orders \
  --alter="ADD COLUMN shipped_at DATETIME NULL" \
  --max-load=Threads_running=25 \
  --critical-load=Threads_running=50 \
  --chunk-size=1000 \
  --exact-rowcount \
  --switch-to-rbr \
  --allow-on-master \
  --execute
# --execute 없이 실행하면 dry-run으로 예상 동작만 검증
```

`--max-load`와 `--critical-load`는 복제 지연이나 스레드 부하가 임계값을 넘으면 자동으로 복사 속도를 늦추거나(throttle) 아예 중단하는 안전장치다. 운영 환경에서는 이 값을 반드시 서비스 특성에 맞게 조정하고, 대형 테이블은 실제 컷오버 전에 `--execute` 없는 dry-run으로 먼저 검증하는 것이 안전하다.

## 실무 포인트

- **외래 키가 걸린 테이블은 별도 검토가 필요하다**: 그림자 테이블은 이름이 다른 새 테이블이므로, 원본을 참조하는 외래 키가 있으면 두 도구 모두 처리 방식(외래 키 재생성, 삭제 후 재생성)을 옵션으로 제공한다. 대상 테이블에 걸린 FK 관계를 사전에 전부 파악해야 컷오버 후 참조 무결성이 깨지지 않는다.
- **복사 도중 부하 모니터링은 필수다**: 두 도구 모두 스로틀링 옵션을 제공하지만 기본값을 그대로 쓰면 트래픽 패턴에 안 맞을 수 있다. 복제 지연, 커넥션 수, 디스크 IO를 실시간으로 보면서 진행 상황을 조정해야 한다.
- **롤백 계획을 미리 세운다**: 컷오버 이후 문제가 발견되면 원본 테이블(gh-ost/pt-osc는 기본적으로 원본을 즉시 삭제하지 않고 `_원본명_del` 형태로 남겨둔다)로 되돌릴 수 있는 시간을 확보해 두고, 이 백업 테이블을 언제 정리할지도 별도로 계획해야 한다.

## 3줄 요약

- gh-ost와 pt-osc 모두 그림자 테이블에 데이터를 복사한 뒤 원자적 rename으로 전환하는 전략은 같지만, 변경 반영 방식이 트리거(pt-osc)냐 binlog 스트리밍(gh-ost)이냐로 갈린다.
- gh-ost는 트리거 부하가 없고 정교한 스로틀링이 가능한 대신 ROW binlog와 복제 권한이 필요해 운영 복잡도가 더 높다.
- 컷오버 순간이 가장 위험한 구간이므로 트래픽이 낮은 시간대로 잡고, 대형 테이블은 dry-run 검증과 부하 모니터링을 반드시 병행해야 한다.

## 참고 자료

- [gh-ost 공식 문서](https://github.com/github/gh-ost)
- [Percona Toolkit 공식 문서: pt-online-schema-change](https://docs.percona.com/percona-toolkit/pt-online-schema-change.html)
- [MySQL 공식 문서: Online DDL for InnoDB Table](https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl.html)
