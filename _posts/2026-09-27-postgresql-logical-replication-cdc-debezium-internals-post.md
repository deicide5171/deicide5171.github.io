---
layout: single
title: "PostgreSQL 논리적 복제와 CDC 내부 동작 — WAL을 SQL 변경으로 디코딩하는 방법"
date: 2026-09-27 12:35:00 +0530
categories: database
tags: ["PostgreSQL", "논리적복제", "CDC", "Debezium", "WAL"]
toc: true
toc_sticky: true
excerpt: "Debezium 같은 CDC 도구가 마법처럼 실시간으로 DB 변경을 캡처하는 것처럼 보이지만, 실제로는 PostgreSQL의 WAL을 논리적 디코딩 플러그인이 해석하고 replication slot이 상태를 관리하는 구체적인 파이프라인이다. 그 내부 동작을 정리했다."
---

## 왜 CDC 내부 동작을 알아야 하는가

Debezium이나 AWS DMS 같은 CDC(Change Data Capture) 도구를 붙이면 신기하게도 INSERT/UPDATE/DELETE가 실시간으로 Kafka 토픽에 이벤트로 쌓인다. 많은 팀이 이를 "커넥터가 알아서 감지해준다"는 블랙박스로 다루지만, 실제로는 PostgreSQL이 제공하는 논리적 복제(logical replication) 인프라 위에서 동작하는 구체적인 메커니즘이다. 이 내부 구조를 모르면 replication slot이 쌓여 디스크가 가득 차거나, 스키마 변경 후 커넥터가 죽는 사고를 원인도 모른 채 겪게 된다.

## 핵심 개념 1 — WAL과 논리적 디코딩

PostgreSQL은 모든 데이터 변경을 커밋하기 전에 WAL(Write-Ahead Log)에 먼저 기록한다. 물리적 복제(streaming replication)는 이 WAL을 바이트 단위로 그대로 복제본에 적용하지만, 논리적 복제는 WAL 레코드를 사람이 읽을 수 있는 논리적 변경(어느 테이블의 어느 행이 어떻게 바뀌었는지)으로 **디코딩**한다. 이 디코딩을 수행하는 것이 출력 플러그인(output plugin)이며, `pgoutput`(PostgreSQL 내장, 논리 복제의 기본값)이나 `wal2json`, `decoderbufs` 같은 확장이 이 역할을 한다. Debezium은 내부적으로 `pgoutput`이나 `wal2json`을 통해 WAL을 읽고, 이를 Debezium 고유의 변경 이벤트 포맷(before/after 이미지 포함)으로 다시 변환해 Kafka Connect로 보낸다.

## 핵심 개념 2 — Replication Slot: 상태를 기억하는 책갈피

논리적 디코딩만으로는 "어디까지 읽었는지"를 알 수 없다. 이를 위해 PostgreSQL은 **replication slot**이라는 서버 측 객체를 제공한다. slot은 컨슈머(예: Debezium)가 마지막으로 확인한 WAL 위치(LSN, Log Sequence Number)를 서버에 영구히 기록해두고, 컨슈머가 재연결하면 그 지점부터 이어서 변경을 전달한다. 문제는 slot이 확인(confirm)되지 않은 WAL을 서버가 **절대 삭제하지 않는다**는 점이다. 컨슈머가 죽거나 네트워크가 끊겨 오랫동안 slot을 소비하지 않으면, WAL이 계속 누적되어 디스크 공간을 잠식하는 유명한 장애 패턴으로 이어진다.

| 구성 요소 | 역할 |
|---|---|
| WAL | 모든 변경의 원본 로그(물리적 바이트 스트림) |
| 출력 플러그인(pgoutput 등) | WAL을 논리적 변경(테이블·행·값)으로 디코딩 |
| Replication Slot | 컨슈머가 어디까지 읽었는지 서버에 기록, 미확인 WAL 보존 |
| Publication | 어떤 테이블을 논리 복제 대상으로 노출할지 정의 |

## 코드 예제 — Publication과 Replication Slot 생성

```sql
-- 1. 논리 복제 대상 테이블을 publication으로 노출
CREATE PUBLICATION debezium_pub FOR TABLE orders, order_items;

-- 2. 논리 복제 slot 생성 (pgoutput 플러그인 사용)
SELECT pg_create_logical_replication_slot('debezium_slot', 'pgoutput');

-- 3. slot이 얼마나 쌓였는지(=미확인 WAL 양) 확인
SELECT slot_name, active,
       pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes
FROM pg_replication_slots;
```

`lag_bytes`가 계속 증가한다면 컨슈머가 slot을 제대로 소비하지 못하고 있다는 신호이므로, 커넥터 헬스체크와 함께 이 값을 모니터링하는 것이 CDC 운영의 기본이다.

## 실무 포인트

- **쓰지 않는 slot은 즉시 제거하라.** 커넥터를 영구히 폐기했는데 slot을 지우지 않으면 WAL이 무한정 쌓인다. `SELECT pg_drop_replication_slot('slot_name')`로 정리해야 하며, 운영에서는 slot lag에 대한 알림을 반드시 설정해야 한다.
- **DDL(스키마 변경)은 논리 복제의 약점이다.** 컬럼 추가·삭제 같은 DDL은 기본적으로 논리 복제 스트림에 포함되지 않으므로, Debezium은 별도의 스키마 히스토리 메커니즘으로 이를 추적한다. 스키마 변경 배포 순서와 CDC 커넥터 재시작 타이밍을 맞추지 않으면 이벤트 파싱 오류가 난다.
- **초기 스냅샷 비용을 고려하라.** 커넥터를 처음 붙이면 기존 데이터 전체를 스냅샷으로 읽어오는 단계가 필요한데, 대용량 테이블에서는 이 초기 스냅샷이 상당한 I/O 부하를 유발한다. 저트래픽 시간대에 시작하거나 증분 스냅샷 기능을 활용하는 것이 안전하다.

## 마무리 요약

- 논리적 복제는 WAL을 출력 플러그인이 논리적 변경으로 디코딩하는 구조이며, Debezium 같은 CDC 도구는 이 위에서 동작한다.
- Replication slot은 컨슈머의 읽기 위치를 서버에 기록하지만, 미확인 WAL을 삭제하지 않으므로 컨슈머 장애 시 디스크 잠식 위험이 있다.
- Slot lag 모니터링, 미사용 slot 정리, DDL과 초기 스냅샷 처리 전략이 안정적인 CDC 운영의 핵심이다.

## 참고 자료

- [PostgreSQL 공식 문서 — 논리적 복제](https://www.postgresql.org/docs/current/logical-replication.html)
- [PostgreSQL 공식 문서 — Replication Slots](https://www.postgresql.org/docs/current/warm-standby.html#STREAMING-REPLICATION-SLOTS)
- [Debezium 공식 문서 — PostgreSQL 커넥터](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
