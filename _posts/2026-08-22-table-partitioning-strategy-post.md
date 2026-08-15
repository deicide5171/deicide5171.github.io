---
layout: single
title: "테이블 파티셔닝 전략 — 언제 나누고 어떻게 쿼리를 지켜야 할까"
date: 2026-08-22 12:35:00 +0530
categories: database
tags: ["database", "partitioning", "postgresql", "scalability", "query-performance"]
toc: true
toc_sticky: true
excerpt: "행 수가 수억 건을 넘어가는 테이블에서 인덱스만으로 버티기 어려워질 때, 파티셔닝으로 테이블을 나누는 기준과 파티션 프루닝이 쿼리 성능을 지키는 원리를 정리한다."
---

서비스가 성장하면서 특정 테이블의 행 수가 수억 건을 넘어가기 시작하면, 인덱스를 아무리 잘 설계해도 이전과 같은 응답 속도를 유지하기 어려워지는 시점이 온다. B-tree 인덱스는 행 수가 늘어날수록 트리 깊이가 함께 늘어나고, VACUUM과 autovacuum이 처리해야 할 dead tuple 양도 비례해서 커진다. 인덱스 재구성(REINDEX)이나 통계 갱신(ANALYZE) 한 번에 걸리는 시간이 서비스 운영 시간대와 겹치기 시작하면, 문제는 더 이상 쿼리 하나의 성능이 아니라 테이블 유지보수 자체가 되어버린다.

이럴 때 검토하는 대안 중 하나가 파티셔닝(partitioning)이다. 하나의 논리적 테이블을 여러 개의 물리적 파티션으로 나누어, 애플리케이션이나 쿼리 작성자 입장에서는 여전히 단일 테이블처럼 다루면서도 실제 데이터는 기준에 따라 여러 개의 작은 테이블에 분산 저장하는 방식이다. 각 파티션은 자신만의 인덱스와 통계를 가지므로, VACUUM이나 인덱스 재구성도 파티션 단위로 나눠 돌릴 수 있고, 쿼리가 특정 파티션만 필요로 한다면 나머지 파티션은 아예 건드리지 않고 넘어갈 수도 있다.

이 글에서는 PostgreSQL의 선언적 파티셔닝(declarative partitioning)을 기준으로, 어떤 기준으로 테이블을 나눌지, 파티션을 나눈다고 해서 자동으로 쿼리가 빨라지는 것은 아니라는 점, 그리고 파티션 키를 고를 때 실무에서 주의해야 할 부분을 정리한다.

## 핵심 개념 1: 레인지/리스트/해시 파티셔닝 전략 비교

PostgreSQL이 지원하는 선언적 파티셔닝 방식은 크게 세 가지다. **레인지(RANGE) 파티셔닝**은 파티션 키 값의 연속된 구간을 기준으로 나누는 방식으로, 생성일시나 주문일자처럼 시간 흐름에 따라 계속 쌓이는 시계열 데이터에 가장 널리 쓰인다. 월별·분기별로 파티션을 만들어두면 오래된 구간을 통째로 아카이빙하거나 DROP하기도 쉽다.

**리스트(LIST) 파티셔닝**은 특정 값의 집합을 기준으로 나눈다. 국가 코드나 지점 코드처럼 값의 종류가 제한적이고 그 값 자체로 데이터를 구분하는 것이 자연스러울 때 적합하다. **해시(HASH) 파티셔닝**은 파티션 키에 해시 함수를 적용해 여러 파티션에 고르게 분산시키는 방식으로, 값의 범위나 카테고리로 나눌 기준이 마땅치 않지만 대신 데이터를 균등하게 흩어 각 파티션의 크기를 비슷하게 유지하고 싶을 때 사용한다. 다만 해시 파티셔닝은 특정 값 하나를 조회하는 쿼리에서는 유리해도, 범위 조회에는 레인지 파티셔닝만큼 도움이 되지 않는다는 차이가 있다.

## 핵심 개념 2: 파티션 프루닝으로 쿼리가 관련 파티션만 스캔하는 원리

파티셔닝이 실질적인 성능 이득으로 이어지는 핵심 메커니즘은 **파티션 프루닝(partition pruning)**이다. 쿼리 플래너는 WHERE 절에 파티션 키에 대한 조건이 있으면, 그 조건을 만족할 수 없는 파티션은 실행 계획 단계에서 아예 스캔 대상에서 제외한다. 예를 들어 `created_at`을 기준으로 월별 레인지 파티셔닝을 해둔 테이블에서 `WHERE created_at >= '2026-08-01'` 조건으로 조회하면, 플래너는 8월 이전 데이터를 담은 파티션들은 애초에 열어보지도 않는다.

이 덕분에 논리적으로는 테이블 전체를 대상으로 쿼리를 작성해도, 실제 스캔 범위는 조건에 해당하는 소수의 파티션으로 줄어든다. 파티션 프루닝이 실제로 적용되었는지는 `EXPLAIN` 실행 계획에서 스캔 대상 파티션 수를 확인하면 알 수 있고, 플래닝 시점에 값이 확정되지 않는 조건(바인드 파라미터 등)에 대해서도 실행 시점 프루닝이 동작하도록 설정(`enable_partition_pruning`)이 마련되어 있다.

## 핵심 개념 3: 파티션 키 선택 시 고려사항

파티션 키는 한 번 정하면 이후에 바꾸기가 쉽지 않으므로, 설계 단계에서 실제 쿼리 패턴을 먼저 살펴보는 것이 중요하다. 가장 우선적으로 고려할 기준은 **자주 실행되는 쿼리의 WHERE 절에 실제로 등장하는 컬럼인가**이다. 파티션 키가 조회 조건과 무관하다면 프루닝 자체가 일어나지 않아 파티셔닝의 이점이 사라진다.

두 번째로는 데이터 분포의 균등성이다. 특정 구간에만 데이터가 몰리면 그 파티션만 비정상적으로 커져 파티셔닝의 목적이 무색해진다. 세 번째로는 조인이 잦은 테이블이라면 조인 키와 파티션 키를 일치시켜 파티션와이즈 조인(partitionwise join)을 활용할 수 있는지도 함께 검토할 만하다.

<img src="/assets/images/posts/2026-08-22-table-partitioning-strategy-1.svg" alt="created_at 기준 월별 레인지 파티셔닝 구조도. 쿼리 조건에 해당하는 파티션만 실제로 스캔되고 나머지 파티션은 프루닝으로 건너뛴다" style="width:100%;">

## 예제

아래는 주문 테이블을 생성일 기준 월별 레인지 파티셔닝으로 구성하는 예시다.

```sql
-- 부모 테이블: 파티션 키로 RANGE 파티셔닝을 선언
CREATE TABLE orders (
    id          bigint GENERATED ALWAYS AS IDENTITY,
    customer_id bigint NOT NULL,
    created_at  timestamptz NOT NULL,
    status      text NOT NULL,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 월별 파티션 생성
CREATE TABLE orders_2026_07 PARTITION OF orders
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE orders_2026_08 PARTITION OF orders
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

-- 파티션마다 별도 인덱스가 필요하므로, 부모에 인덱스를 걸어두면
-- 이후 생성되는 파티션에도 자동으로 전파된다
CREATE INDEX idx_orders_customer ON orders (customer_id);
```

`FOR VALUES FROM ... TO ...`의 상한은 미포함(exclusive)이므로 구간 경계를 겹치지 않게 설계해야 하며, 범위를 벗어나는 값이 들어오는 것을 막으려면 `DEFAULT` 파티션 없이 필요한 구간만 미리 만들어두거나, 별도의 배치 작업으로 다음 달 파티션을 미리 생성해두는 운영 절차가 필요하다.

## 실무 포인트

- **파티션 키가 쿼리 조건에 안 걸리면 프루닝은 무효화된다**: WHERE 절에 파티션 키 대신 다른 컬럼만 조건으로 들어가거나, 파티션 키에 함수를 씌운 형태(`WHERE date_trunc('day', created_at) = ...`)로 조회하면 플래너가 관련 파티션을 좁히지 못하고 전체 파티션을 순회할 수 있다. 파티션 키는 원래 컬럼 형태 그대로 조건에 노출시키는 것이 안전하다.
- **파티션 수가 너무 많으면 오히려 오버헤드가 된다**: 파티션 하나하나가 카탈로그 엔트리, 락, 플래닝 비용을 갖는 별도의 테이블이므로, 세밀하게 쪼갠다고 무조건 유리하지는 않다. 파티션 수가 지나치게 많아지면 플래닝 시간 자체가 늘어나거나 운영 도구(백업, 모니터링)가 다뤄야 할 객체 수가 급증하는 부작용이 생길 수 있으므로, 조회 패턴과 데이터 증가 속도를 함께 고려해 파티션 단위(일/주/월/분기)를 정하는 편이 안전하다.

## 3줄 요약

- 테이블 행 수가 매우 커지면 인덱스 유지보수와 쿼리 성능이 함께 나빠지며, 파티셔닝은 테이블을 물리적으로 나눠 이 부담을 파티션 단위로 분산시키는 방법이다.
- 레인지/리스트/해시 중 어떤 방식을 쓰든, 실제 성능 이득은 쿼리 플래너가 관련 없는 파티션을 스캔에서 제외하는 파티션 프루닝에서 나온다.
- 파티션 키는 실제 쿼리 조건에 그대로 등장해야 프루닝이 동작하며, 파티션을 지나치게 잘게 쪼개면 관리 오버헤드가 이점을 상쇄할 수 있다.

## 참고 자료

- [PostgreSQL 공식 문서: Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [PostgreSQL 공식 문서: Partition Pruning](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITION-PRUNING)
- [PostgreSQL 공식 문서: Runtime Configuration — enable_partition_pruning](https://www.postgresql.org/docs/current/runtime-config-query.html#GUC-ENABLE-PARTITION-PRUNING)
- [PostgreSQL 공식 문서: CREATE TABLE ... PARTITION OF](https://www.postgresql.org/docs/current/sql-createtable.html)
