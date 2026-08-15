---
layout: single
title: "시계열 데이터베이스 선택 가이드 — TimescaleDB vs InfluxDB, 언제 무엇을 써야 할까"
date: 2026-08-18 13:35:00 +0530
categories: database
tags: ["timescaledb", "influxdb", "time-series", "database", "postgresql"]
toc: true
toc_sticky: true
excerpt: "IoT 센서, 서버 메트릭, 금융 시세처럼 시간이 축이 되는 데이터가 늘어나는 만큼 일반 RDB로 버티기 힘든 지점도 함께 늘어난다. PostgreSQL 확장인 TimescaleDB와 전용 엔진인 InfluxDB를 데이터 모델·쿼리·운영 관점에서 비교해 선택 기준을 정리한다."
---

## 왜 지금 시계열 데이터베이스인가

서버 메트릭, IoT 센서값, 주가 틱, 애플리케이션 로그처럼 "시간 + 값"의 형태로 끊임없이 쌓이는 데이터가 늘고 있다. 이런 데이터는 쓰기가 압도적으로 많고(주로 append), 조회는 대부분 최근 구간이나 특정 시간 범위에 집중되며, 오래된 데이터는 요약해서 남기거나 아예 삭제하는 보존 정책이 필요하다는 공통점이 있다. 일반 RDB에 그대로 쌓다 보면 테이블이 비대해지고, 인덱스가 비대해지고, 오래된 데이터 삭제가 락 경합을 일으키는 문제가 반복된다.

이 문제를 겨냥한 시계열 데이터베이스 중 실무에서 가장 자주 비교되는 두 축이 **TimescaleDB**(PostgreSQL 확장)와 **InfluxDB**(전용 시계열 엔진)다. 접근 방식이 근본적으로 다르기 때문에 "무엇이 더 빠른가"보다 "우리 팀의 기존 스택과 쿼리 패턴에 어느 쪽이 맞는가"가 더 중요한 질문이다.

## 핵심 개념 1: 시계열 데이터의 저장 구조가 다른 이유

두 제품은 같은 문제(시간 축 대량 쓰기 + 범위 조회)를 서로 다른 기반 위에서 푼다. TimescaleDB는 PostgreSQL 테이블을 시간 구간별 **청크(chunk)**로 쪼개 하나의 논리적 테이블(하이퍼테이블)처럼 보이게 만든다. InfluxDB는 처음부터 시계열 전용으로 설계된 **TSM(Time-Structured Merge Tree)** 엔진에 쓰기를 순차 기록한 뒤 백그라운드로 압축·병합한다.

<img src="/assets/images/posts/2026-08-18-timeseries-db-selection-1.svg" alt="TimescaleDB 하이퍼테이블 청크 구조와 InfluxDB TSM 엔진 구조 비교" style="width:100%;">

## 핵심 개념 2: 데이터 모델과 쿼리 언어

| 항목 | TimescaleDB | InfluxDB |
|---|---|---|
| 데이터 모델 | 일반 테이블(컬럼 스키마) + 시간 컬럼 | 측정값(measurement) + 태그(tag) + 필드(field) |
| 쿼리 언어 | 표준 SQL 그대로 | InfluxQL 또는 Flux(버전별 상이) |
| JOIN | PostgreSQL의 JOIN을 그대로 사용 | 제한적, 별도 처리 필요한 경우가 많음 |
| 스키마 | 사전 정의(마이그레이션 관리) | 스키마리스에 가까움(태그 자유 추가) |
| 카디널리티 민감도 | 상대적으로 낮음 | 태그 카디널리티가 커지면 성능 저하 위험 |

TimescaleDB는 결국 PostgreSQL이므로 기존에 쓰던 ORM, 트랜잭션, 외래 키, 다른 테이블과의 JOIN을 그대로 쓸 수 있다는 점이 가장 큰 실무 장점이다. InfluxDB는 태그 기반 조회에 최적화돼 있어 "특정 호스트의 최근 CPU 사용률" 같은 조회는 빠르지만, 태그 조합이 지나치게 다양해지면(예: 사용자 ID를 태그로 사용) 카디널리티 폭발로 메모리 사용량이 급증할 수 있다.

## 핵심 개념 3: 압축과 다운샘플링

두 제품 모두 오래된 데이터를 압축하거나 요약하는 기능을 제공하지만 구현 방식이 다르다. TimescaleDB는 청크 단위로 컬럼 지향 압축을 적용할 수 있고, `continuous aggregate`로 시간대별 집계 결과를 별도 뷰처럼 유지·갱신한다. InfluxDB는 보존 정책(retention policy)과 연속 쿼리(continuous query, 버전에 따라 태스크 형태)로 오래된 원본 데이터를 지우면서 다운샘플링된 요약만 남기는 방식을 쓴다.

## 쿼리 예제

**TimescaleDB — 하이퍼테이블 생성과 시간대별 집계(SQL)**

```sql
-- 센서 데이터용 하이퍼테이블 생성
CREATE TABLE sensor_data (
  time        TIMESTAMPTZ NOT NULL,
  sensor_id   INT NOT NULL,
  temperature DOUBLE PRECISION
);
SELECT create_hypertable('sensor_data', 'time');

-- 1시간 단위 평균 온도 집계(연속 집계 뷰)
CREATE MATERIALIZED VIEW hourly_avg_temp
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       sensor_id,
       avg(temperature) AS avg_temp
FROM sensor_data
GROUP BY bucket, sensor_id;
```

**InfluxDB — 최근 24시간 평균값 조회(Flux)**

```flux
from(bucket: "sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
```

## 실무 포인트

- **기존 스택이 PostgreSQL이면 TimescaleDB가 도입 장벽이 낮다.** 별도 쿼리 언어 학습 없이 SQL과 기존 운영 도구(백업, 모니터링, 마이그레이션 툴)를 그대로 재사용할 수 있다.
- **태그로 쓸 값의 카디널리티를 미리 가늠한다.** InfluxDB에서 사용자 ID, 요청 ID처럼 값의 종류가 무한히 늘어나는 컬럼을 태그로 두면 메모리·성능 문제로 이어지기 쉽다. 이런 값은 필드로 옮기는 것이 안전하다.
- **보존 정책은 처음부터 설계에 포함한다.** 어느 쪽이든 원본 데이터를 무한히 쌓아두는 전제로 시작하면 나중에 압축·삭제 정책을 소급 적용하기 번거롭다.
- **버전별 쿼리 언어 변화를 확인한다.** InfluxDB는 버전에 따라 InfluxQL과 Flux 지원 범위가 다르므로, 도입 전 사용 버전의 공식 문서를 반드시 확인해야 한다(정확한 로드맵은 공식 문서 기준으로 판단할 것).

## 3줄 요약

- 시계열 데이터는 쓰기 위주·시간 범위 조회·보존 정책이라는 공통 요구사항 때문에 일반 RDB만으로는 한계가 생긴다.
- TimescaleDB는 PostgreSQL 확장으로 SQL·JOIN·기존 운영 도구를 그대로 쓸 수 있고, InfluxDB는 태그 기반 조회에 최적화된 전용 엔진이지만 카디널리티 관리가 필요하다.
- 선택 기준은 성능 벤치마크보다 팀의 기존 스택, 쿼리 패턴, 태그(라벨) 다양성에 두는 것이 현실적이다.

## 참고 자료

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [InfluxDB Documentation](https://docs.influxdata.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
