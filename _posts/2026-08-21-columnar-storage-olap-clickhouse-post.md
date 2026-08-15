---
layout: single
title: "OLAP을 위한 컬럼 스토어 — ClickHouse는 왜 이렇게 빠를까"
date: 2026-08-21 13:35:00 +0530
categories: database
tags: ["database", "clickhouse", "olap", "columnar-storage", "analytics"]
toc: true
toc_sticky: true
excerpt: "수십억 행을 스캔하는 집계 쿼리에서 행 지향 RDB가 한계를 보이는 이유와, 컬럼 지향 저장 방식으로 이를 극복하는 ClickHouse의 내부 구조를 정리한다."
---

로그나 이벤트 데이터를 몇 년치 쌓아두고 "특정 기간 동안 사용자별 평균 응답 시간을 구해줘" 같은 집계 쿼리를 돌려본 적이 있다면, 익숙한 RDB에서 이런 쿼리가 유독 느리다는 걸 느꼈을 것이다. 테이블에 컬럼이 수십 개 있어도 쿼리가 실제로 필요로 하는 건 그중 두세 개뿐인데, 행 지향(row-oriented) 저장 구조에서는 디스크에서 한 행을 읽을 때 그 행에 속한 모든 컬럼을 통째로 읽어야 한다. 필요 없는 컬럼까지 매번 디스크에서 끌어오는 셈이니, 스캔해야 할 행 수가 수십억 단위로 늘어나면 I/O 자체가 병목이 된다.

이런 문제는 OLTP(온라인 트랜잭션 처리)에 최적화된 RDB의 설계 철학과 맞닿아 있다. OLTP는 "특정 주문 하나를 찾아서 상태를 갱신"하는 것처럼 행 단위로 읽고 쓰는 작업에 강하도록 만들어졌다. 반면 OLAP(온라인 분석 처리)은 "전체 주문 중 카테고리별 합계"처럼 소수의 컬럼을 대량의 행에 걸쳐 집계하는 작업이 대부분이다. 같은 저장 구조로 두 워크로드를 모두 감당하려 하면 어느 한쪽은 반드시 비효율이 생긴다.

ClickHouse는 이 문제를 컬럼 지향 저장과 그에 맞춘 실행 엔진으로 정면 돌파한 OLAP 전용 데이터베이스다. 이 글에서는 행 지향과 컬럼 지향 저장 방식의 차이, 컬럼 스토어가 압축과 스캔 속도에서 유리한 원리, 그리고 ClickHouse의 핵심 저장 엔진인 MergeTree의 기본 개념을 정리한다.

## 핵심 개념 1: 행 지향 vs 컬럼 지향 저장 방식

행 지향 저장에서는 한 행의 모든 컬럼 값이 디스크에 연속으로 기록된다. `(id, name, amount, created_at)` 형태의 레코드가 있다면 `id1, name1, amount1, created_at1, id2, name2, amount2, created_at2, ...` 순서로 저장되는 식이다. 이 방식은 행 전체를 읽거나 쓰는 작업(레코드 삽입, 특정 ID로 단건 조회)에 유리하다.

<img src="/assets/images/posts/2026-08-21-columnar-storage-olap-clickhouse-1.svg" alt="행 지향 저장과 컬럼 지향 저장 구조 비교 다이어그램" style="width:100%;">

컬럼 지향 저장에서는 반대로 같은 컬럼의 값들이 모아서 연속으로 저장된다. `id1, id2, id3, ...`, `name1, name2, name3, ...` 처럼 컬럼별로 별도 블록에 나뉜다. 이 구조에서는 `amount` 컬럼의 합계만 구하는 쿼리라면 다른 컬럼은 아예 디스크에서 읽을 필요가 없다. 필요한 컬럼만 골라 읽는다는 점이 OLAP 쿼리 성능의 핵심 차이를 만든다.

## 핵심 개념 2: 컬럼 스토어가 압축과 스캔 속도에서 유리한 이유

컬럼 지향 저장이 빠른 이유는 단순히 "필요한 컬럼만 읽어서"만은 아니다. 같은 컬럼 안에서는 값의 타입과 분포가 유사한 경우가 많아 압축 효율이 크게 올라간다. 예를 들어 `status` 컬럼처럼 값의 종류가 몇 가지로 제한된 경우 딕셔너리 인코딩이나 런렝스 인코딩(RLE) 같은 기법으로 매우 높은 압축률을 기대할 수 있고, 시계열 값처럼 인접한 값들이 비슷한 컬럼에는 델타 인코딩이 효과적이다. 압축률이 높아지면 디스크에서 읽어야 할 바이트 수 자체가 줄어들어 I/O 비용이 낮아진다.

또한 같은 타입의 값이 연속으로 배치되어 있으면 CPU의 SIMD(벡터화) 연산을 활용하기 쉬워진다. 한 번의 명령으로 여러 값을 동시에 처리할 수 있어, 합계·평균 같은 집계 연산이 빠르게 처리된다. ClickHouse는 이런 벡터화 실행 엔진을 갖추고 있어, 컬럼 단위로 읽어온 데이터를 블록 단위로 처리하며 집계 성능을 끌어올린다.

## 핵심 개념 3: ClickHouse의 MergeTree 엔진

MergeTree는 ClickHouse에서 가장 널리 쓰이는 저장 엔진 계열이다. 데이터를 삽입할 때마다 즉시 정렬된 상태로 유지하는 대신, 삽입된 데이터를 우선 정렬된 작은 조각(파트, part)으로 디스크에 기록하고, 백그라운드에서 이 파트들을 주기적으로 병합(merge)해 더 큰 정렬된 파트로 합쳐나간다. 이 병합 과정 덕분에 쓰기 성능을 유지하면서도 읽기 시점에는 정렬된 데이터에서 효율적인 스캔이 가능해진다.

테이블을 정의할 때 지정하는 `ORDER BY` 키(정렬 키)는 각 파트 내부에서 데이터가 어떤 순서로 저장될지를 결정한다. 이 정렬 키와 일치하거나 접두사가 되는 조건으로 쿼리를 필터링하면, 스파스 인덱스(sparse index)를 통해 관련 없는 데이터 블록 전체를 건너뛸 수 있어 스캔 범위가 크게 줄어든다. 반대로 정렬 키와 무관한 컬럼으로 필터링하면 이런 이점을 얻기 어렵다. 이 때문에 MergeTree 테이블을 설계할 때는 실제 쿼리 패턴을 고려해 정렬 키를 신중하게 선택하는 것이 중요하다.

## 예제

다음은 이벤트 로그를 저장하는 MergeTree 테이블을 생성하고 집계 쿼리를 실행하는 예시다.

```sql
CREATE TABLE events
(
    event_date Date,
    event_time DateTime,
    user_id UInt64,
    event_type String,
    duration_ms UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_type, event_date, user_id);
```

```sql
SELECT
    event_type,
    count() AS total_events,
    avg(duration_ms) AS avg_duration
FROM events
WHERE event_date >= '2026-01-01'
  AND event_date < '2026-02-01'
GROUP BY event_type
ORDER BY total_events DESC;
```

`PARTITION BY toYYYYMM(event_date)`는 월 단위로 데이터를 물리적으로 분리해, 오래된 파티션 전체를 통째로 건너뛰거나 삭제하기 쉽게 만든다. `ORDER BY (event_type, event_date, user_id)`는 정렬 키로, `event_type` 조건이 붙은 쿼리에서 스캔 범위를 효과적으로 줄여준다.

## 실무 포인트

OLTP와 OLAP을 같은 데이터베이스, 같은 테이블 구조로 처리하려 하면 어느 한쪽이 손해를 본다. OLTP는 트랜잭션 단위의 정합성과 빠른 단건 조회·갱신이 핵심이고, OLAP은 대량의 행을 스캔해 소수 컬럼을 집계하는 것이 핵심이다. 이 둘의 접근 패턴이 근본적으로 다르기 때문에, 실무에서는 원본 트랜잭션 데이터는 RDB(PostgreSQL, MySQL 등)에 두고 분석용으로 별도 파이프라인을 통해 ClickHouse 같은 컬럼 스토어에 적재하는 구조를 많이 쓴다.

다만 ClickHouse가 모든 워크로드에 적합한 것은 아니다. 개별 레코드를 자주 갱신(UPDATE)하거나 삭제해야 하는 트랜잭션성 워크로드에는 맞지 않는다. MergeTree는 삽입과 백그라운드 병합 위주로 설계되어 있어, 행 단위의 잦은 업데이트·삭제는 별도의 뮤테이션 연산으로 처리되며 비용이 크다. 또한 외래 키 제약이나 다중 테이블 조인 트랜잭션처럼 강한 정합성 보장이 필요한 경우에도 RDB가 더 적합하다. ClickHouse는 "쓰고 나서 대부분 읽기만 하는" 추가(append) 위주의 대량 데이터 분석에 강점을 가진 도구로 이해하는 것이 정확하다.

## 3줄 요약

- 행 지향 저장은 행 전체를 함께 읽어 OLTP에 유리하고, 컬럼 지향 저장은 필요한 컬럼만 읽어 OLAP 집계 쿼리에 유리하다.
- 컬럼 스토어는 유사한 값이 모여 압축률이 높아지고, 벡터화 연산과 결합해 대량 스캔 성능을 끌어올린다.
- ClickHouse의 MergeTree는 정렬된 파트를 백그라운드 병합으로 유지하며, 정렬 키 설계가 쿼리 성능을 좌우한다.

## 참고 자료

- [ClickHouse 공식 문서 - MergeTree 개요](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree)
- [ClickHouse 공식 문서 - 컬럼 지향 데이터베이스란](https://clickhouse.com/docs/concepts/why-clickhouse-is-so-fast)
- [ClickHouse 공식 문서 - 데이터 압축](https://clickhouse.com/docs/data-compression/compression-in-clickhouse)
