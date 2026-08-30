---
layout: single
title: "PostgreSQL 선언적 파티셔닝 — Range/List/Hash 전략과 파티션 프루닝의 조건"
date: 2026-09-27 13:35:00 +0530
categories: database
tags: ["PostgreSQL", "파티셔닝", "파티션프루닝", "쿼리최적화", "테이블설계"]
toc: true
toc_sticky: true
excerpt: "테이블이 수억 행을 넘어가면 인덱스만으로는 한계가 온다. PostgreSQL 선언적 파티셔닝의 Range/List/Hash 전략별 적합한 상황과, 쿼리가 실제로 필요한 파티션만 스캔하게 만드는 파티션 프루닝의 정확한 조건을 정리했다."
---

## 왜 파티셔닝이 필요해지는가

인덱스를 아무리 잘 설계해도 테이블 자체가 수억 행을 넘어가면 문제가 생긴다. VACUUM이 한 번 도는 데 걸리는 시간이 길어지고, 인덱스 크기가 커져 B-tree 탐색 깊이가 늘어나며, 오래된 데이터를 대량 삭제할 때 `DELETE`가 WAL을 폭발적으로 생성하고 테이블에 데드 튜플을 남긴다. PostgreSQL의 선언적 파티셔닝(declarative partitioning)은 논리적으로 하나의 테이블처럼 보이지만 물리적으로는 여러 개의 작은 테이블(파티션)로 나뉜 구조를 제공해, 이런 대용량 테이블 운영 문제를 근본적으로 다른 각도에서 해결한다. 핵심은 파티션을 나누는 기준(파티션 키)을 잘 고르는 것과, 쿼리가 실제로 그 이점을 누리게 만드는 파티션 프루닝 조건을 이해하는 것이다.

## 핵심 개념 1 — Range, List, Hash 전략 선택

**Range 파티셔닝**은 날짜나 순차 ID처럼 연속된 값 범위로 나누는 방식으로, 로그·이벤트·주문 이력처럼 시계열 데이터에 가장 흔히 쓰인다. 오래된 파티션을 통째로 `DETACH`해서 아카이빙하거나 삭제하는 것이 단순한 `DELETE`보다 훨씬 빠르고 WAL 부담도 적다. **List 파티셔닝**은 국가 코드, 테넌트 ID처럼 이산적인 값 집합으로 나누는데, 멀티테넌트 SaaS에서 테넌트별로 물리적 격리를 주고 싶을 때 적합하다. **Hash 파티셔닝**은 파티션 키의 해시값으로 균등하게 분산시키는 방식으로, 자연스러운 범위나 카테고리 기준이 없지만 그냥 하나의 거대한 테이블을 여러 물리 파티션으로 쪼개 관리 부담(VACUUM, 인덱스 크기)만 줄이고 싶을 때 선택한다.

| 전략 | 적합한 파티션 키 예시 | 장점 | 주의점 |
|---|---|---|---|
| Range | 생성일자, 시퀀스 ID | 오래된 데이터 DETACH가 빠름 | 경계값 설계가 중요 |
| List | 국가 코드, 테넌트 ID | 논리적 그룹 물리 분리 | 값 목록이 계속 늘면 관리 부담 |
| Hash | 균등 분산이 필요한 임의 키 | 핫스팟 없이 균등 분산 | 특정 파티션만 골라 스캔 불가 |

## 핵심 개념 2 — 파티션 프루닝이 실제로 동작하는 조건

파티셔닝의 성능 이점은 쿼리 플래너가 **필요 없는 파티션을 아예 스캔 계획에서 제외**하는 파티션 프루닝에서 나온다. 문제는 이게 항상 동작하지 않는다는 점이다. `WHERE created_at >= '2026-09-01'`처럼 파티션 키에 대한 조건이 리터럴 값이면 플래너가 계획 수립 시점(planning time)에 프루닝을 결정할 수 있다. 하지만 `WHERE created_at >= now() - interval '7 days'`처럼 파티션 키가 함수 결과에 걸려 있거나, 준비된 문장(prepared statement)의 바인드 파라미터로 들어오면 계획 시점에는 정확한 값을 알 수 없다. 이 경우 PostgreSQL은 실행 시점(execution time) 프루닝으로 넘어가는데, 최신 버전은 이를 잘 지원하지만 파티션 키를 다른 컬럼과 함수로 조합한 조건(`WHERE date_trunc('month', created_at) = ...`)에서는 프루닝이 아예 무력화되어 모든 파티션을 스캔하는 최악의 경우로 떨어질 수 있다.

## 코드 예제 — Range 파티션 테이블 생성과 프루닝 확인

```sql
CREATE TABLE orders (
    id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC NOT NULL
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2026_08 PARTITION OF orders
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE orders_2026_09 PARTITION OF orders
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

-- EXPLAIN으로 실제 프루닝 여부를 반드시 확인한다
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders WHERE created_at >= '2026-09-01' AND created_at < '2026-09-15';
-- 계획에 orders_2026_08이 아예 등장하지 않아야 프루닝이 성공한 것이다
```

## 실무 포인트

- **파티션 키는 반드시 조건절에 직접 등장해야 한다.** 애플리케이션 쿼리가 파티션 키를 감싸는 함수나 조인 조건으로만 걸러낸다면 프루닝이 무력화되므로, 쿼리 패턴을 먼저 분석하고 그에 맞는 파티션 키를 골라야 한다.
- **파티션 수가 너무 많아지면 오히려 계획 수립 비용이 커진다.** 파티션이 수천 개를 넘으면 플래너가 각 파티션을 검토하는 오버헤드 자체가 문제가 될 수 있으므로, 시계열이라면 월 단위/주 단위처럼 적절한 입도로 관리하고 오래된 파티션은 정기적으로 통합하거나 아카이빙해야 한다.
- **유니크 제약과 외래키는 파티션 키를 포함해야 한다.** PostgreSQL의 파티션 테이블에서 기본키나 유니크 제약을 걸려면 그 제약이 파티션 키를 포함해야 하는 제한이 있으므로, 스키마 설계 초기에 이 제약을 감안해야 한다.

## 마무리 요약

- Range/List/Hash 파티셔닝은 각각 시계열 데이터 아카이빙, 테넌트 물리 격리, 균등 분산이라는 서로 다른 목적에 맞춰 선택해야 한다.
- 파티션 프루닝은 파티션 키가 조건절에 직접 리터럴이나 프리페어드 바인드값으로 노출될 때만 확실히 동작하며, 함수로 감싼 조건에서는 무력화될 수 있다.
- 도입 전 반드시 `EXPLAIN (ANALYZE, BUFFERS)`로 실제 프루닝 여부를 확인하고, 파티션 수와 유니크 제약 설계를 함께 고려해야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 — Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [PostgreSQL 공식 문서 — Partition Pruning](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITION-PRUNING)
