---
layout: single
title: "쿼리 플래너는 어떻게 행 수를 추측할까 — 통계정보와 히스토그램으로 보는 카디널리티 추정"
date: 2026-08-25 12:35:00 +0530
categories: database
tags: ["query-planner", "statistics", "histogram", "cardinality-estimation", "postgresql", "analyze"]
toc: true
toc_sticky: true
excerpt: "EXPLAIN 결과에 찍힌 rows 추정치가 실제 값과 크게 어긋날 때, 그 추정이 어디서 나오는지를 ANALYZE 통계·히스토그램·MCV 리스트를 통해 파악하고 통계 갱신 전략을 정리한다."
---

`EXPLAIN`으로 실행 계획을 읽다 보면 `rows=1200` 같은 추정치를 종종 만난다. 그런데 실제로 실행해 보면(`EXPLAIN ANALYZE`) 진짜 행 수는 12만 건이었던 경우가 있다. 이런 추정-실제 간 괴리는 단순히 "플래너가 틀렸다"로 끝날 문제가 아니다. 이 추정치를 근거로 플래너가 인덱스 스캔 대신 시퀀셜 스캔을, 해시 조인 대신 네스티드 루프 조인을 선택했을 수 있고, 그 선택 하나가 쿼리 성능을 수십 배 차이 나게 만든다.

`EXPLAIN ANALYZE`를 읽는 법을 다룬 글들은 보통 "계획이 실제와 왜 다른지"를 결과 관점에서 진단하는 데 집중한다. 이 글은 한 단계 더 앞으로 가서, **그 추정치가 애초에 어디서 어떻게 계산되는지**를 다룬다. 즉 플래너가 참고하는 통계정보(statistics)와 히스토그램이 무엇이고, 이 통계가 부실하거나 오래되면 왜 추정이 어긋나는지를 정리한다.

## 핵심 개념 1: ANALYZE가 수집하는 통계의 정체

PostgreSQL에서 `ANALYZE` 명령(또는 오토바큠의 자동 실행)은 테이블 전체를 읽는 대신 **샘플링**을 통해 컬럼별 통계를 `pg_statistic` 카탈로그(사용자에게는 `pg_stats` 뷰로 노출)에 저장한다. 여기에는 크게 세 가지 정보가 담긴다.

- **n_distinct**: 해당 컬럼의 고유 값 개수 추정치. 이 값으로 등치 조건(`= 값`)의 선택도를 계산한다.
- **most_common_vals (MCV)**: 가장 자주 등장하는 값들과 그 빈도. 데이터가 균등 분포하지 않을 때 특정 값에 대한 조건의 정확도를 크게 높여준다.
- **histogram_bounds**: MCV에 포함되지 않은 나머지 값들을 등빈도(equi-depth) 구간으로 나눈 경계값 목록. 범위 조건(`BETWEEN`, `>`, `<`)의 선택도를 추정하는 데 쓰인다.

플래너는 쿼리의 `WHERE` 조건마다 이 통계를 조회해 "전체 행 중 몇 %가 이 조건을 만족할 것인가(선택도, selectivity)"를 계산하고, 여기에 테이블 전체 행 수를 곱해 `rows` 추정치를 만든다.

## 핵심 개념 2: 히스토그램이 선택도를 계산하는 방식

히스토그램은 값의 범위를 동일한 개수의 행이 들어가도록 나눈 구간(bucket) 경계값 배열이다. 예를 들어 `created_at` 컬럼에 히스토그램 경계값이 `[1월1일, 3월1일, 6월1일, 9월1일, 12월31일]`로 5개 구간이라면, 각 구간에는 전체 행의 약 25%씩 들어 있다는 뜻이다. `WHERE created_at > '5월1일'` 같은 조건이 들어오면, 플래너는 이 조건이 3월1일~6월1일 구간의 절반과 그 뒤 구간 전체에 걸쳐 있다고 보고 그 비율만큼 선택도를 계산한다.

이 방식의 약점은 **컬럼 간 상관관계를 가정하지 않는다**는 점이다. `WHERE country = 'KR' AND city = 'Seoul'` 같은 조건에서는 두 컬럼의 선택도를 각각 계산해 곱하는데, 실제로는 `city='Seoul'`인 행은 `country='KR'`일 확률이 매우 높으므로(상관관계가 강하므로) 독립 가정으로 계산한 선택도는 실제보다 훨씬 낮게(=결합 조건을 만족하는 행이 실제보다 적다고) 추정된다. PostgreSQL은 이 문제를 완화하기 위해 `CREATE STATISTICS`로 여러 컬럼 간의 확장 통계(extended statistics)를 별도로 만들 수 있게 지원한다.

## 핵심 개념 3: 통계가 낡거나 부실할 때 생기는 증상

| 증상 | 원인 후보 |
|---|---|
| 대량 삽입 직후 계획이 갑자기 나빠짐 | ANALYZE 미실행으로 통계가 삽입 이전 상태에 머묾 |
| 특정 값 조건만 계획이 이상함 | 해당 값이 MCV에 없거나 `default_statistics_target`이 낮아 샘플 부족 |
| AND로 묶인 조건에서 추정 행 수가 실제보다 훨씬 적음 | 컬럼 간 상관관계 미반영, 확장 통계 부재 |
| JSONB·배열 컬럼 조건에서 추정이 부정확 | 해당 데이터 타입에 특화된 통계 부족 |

`default_statistics_target`은 컬럼당 수집할 히스토그램 구간·MCV 개수를 결정하는 설정으로, 기본값(100)이 데이터 분포가 매우 치우친 컬럼에는 부족할 수 있다. 컬럼 단위로 `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS n`으로 개별 조정할 수 있다.

## 예제: 통계 확인과 확장 통계 생성

```sql
-- 특정 컬럼의 통계 요약 확인
SELECT attname, n_distinct, most_common_vals, most_common_freqs, histogram_bounds
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';

-- 대량 변경 후 통계 갱신
ANALYZE orders;

-- 특정 컬럼의 샘플링 정밀도 상향 (기본 100 -> 500)
ALTER TABLE orders ALTER COLUMN customer_id SET STATISTICS 500;
ANALYZE orders;

-- country, city처럼 상관관계가 강한 컬럼 조합에 확장 통계 생성
CREATE STATISTICS orders_country_city_stat (dependencies)
ON country, city FROM orders;
ANALYZE orders;
```

확장 통계를 만든 뒤에는 `EXPLAIN`에서 해당 조건의 `rows` 추정치가 실제 값에 가까워졌는지 반드시 재확인해야 한다. 통계를 추가한다고 항상 개선되는 것은 아니며, 통계 유지 자체에도 오버헤드가 있으므로 실제로 계획이 나빠지는 조건에 한해 선택적으로 적용하는 것이 바람직하다.

## 실무 포인트

- **오토바큠 설정을 통계 갱신 주기로도 생각한다**: `autovacuum_analyze_scale_factor`가 크면 대량 변경 후에도 오토 ANALYZE가 늦게 돈다. 배치 삽입 직후 성능 저하가 반복된다면 배치 직후 수동 `ANALYZE`를 파이프라인에 넣는 것이 안전하다.
- **MCV에 없는데 자주 조회되는 값이 있는지 확인한다**: 신규 상태값처럼 최근에 늘기 시작한 값은 통계 갱신 시점에 따라 MCV에 아직 반영되지 않았을 수 있다. 이 경우 조건의 실제 빈도와 추정 빈도가 크게 어긋난다.
- **확장 통계는 만병통치약이 아니다**: `CREATE STATISTICS`는 지정한 컬럼 조합에만 효과가 있고, 유지 비용도 있다. `EXPLAIN`에서 특정 AND 조건의 추정 행 수가 실제보다 체계적으로 어긋나는 것을 확인한 뒤에만 추가한다.

## 3줄 요약

- 쿼리 플래너의 `rows` 추정치는 `ANALYZE`가 수집한 n_distinct, MCV, 히스토그램 통계에서 계산된 선택도와 테이블 행 수의 곱이다.
- 히스토그램은 컬럼 간 상관관계를 가정하지 않기 때문에 여러 조건이 AND로 묶이면 추정이 실제보다 크게 어긋나기 쉽고, 이를 보완하는 것이 확장 통계(`CREATE STATISTICS`)다.
- 대량 변경 직후 계획이 나빠지는 문제는 대부분 통계가 오래됐기 때문이며, `default_statistics_target` 조정과 배치 후 수동 `ANALYZE`로 상당 부분 해결된다.

## 참고 자료

- [PostgreSQL 공식 문서: Row Estimation Examples](https://www.postgresql.org/docs/current/row-estimation-examples.html)
- [PostgreSQL 공식 문서: Planner Statistics](https://www.postgresql.org/docs/current/planner-stats.html)
- [PostgreSQL 공식 문서: Extended Statistics](https://www.postgresql.org/docs/current/sql-createstatistics.html)
