---
layout: single
title: "EXPLAIN ANALYZE 해부하기 — 쿼리 플래너가 남기는 단서 읽는 법"
date: 2026-08-17 12:35:00 +0530
categories: database
tags: ["postgresql", "explain-analyze", "query-planner", "query-tuning", "sql"]
toc: true
toc_sticky: true
excerpt: "cost, rows, actual time, loops — EXPLAIN ANALYZE 출력의 각 숫자가 실제로 무엇을 의미하는지, 어디를 먼저 봐야 하는지를 실행 계획 예제로 정리한다."
---

## 왜 지금 EXPLAIN ANALYZE인가

인덱스를 걸었는데도 쿼리가 느리거나, 반대로 인덱스가 왜 안 타는지 궁금할 때 결국 마주치는 것이 `EXPLAIN` 출력이다. 문제는 이 출력이 처음 보면 숫자와 노드 이름이 뒤섞인 트리일 뿐이라, "이 쿼리는 Seq Scan을 한다"까지는 읽어도 그게 왜 문제인지, 어느 줄을 먼저 고쳐야 하는지는 별개의 문제라는 점이다.

이전에 다룬 인덱스 내부 구조나 복합 인덱스 컬럼 순서 이야기가 "인덱스를 어떻게 설계할까"였다면, 이번 글은 그 설계가 실제로 쿼리 플래너에게 어떻게 받아들여지는지를 **읽는 법**에 집중한다. 인덱스를 아무리 잘 설계해도, 플래너가 그 인덱스를 실제로 쓰는지 확인하는 도구가 EXPLAIN ANALYZE이기 때문이다.

## 핵심 개념 1: EXPLAIN과 EXPLAIN ANALYZE는 다른 도구다

`EXPLAIN`은 플래너가 **세운 계획**만 보여준다. 실제로 쿼리를 실행하지 않고, 통계 정보를 바탕으로 각 단계의 예상 비용과 예상 행 수만 추정한다. 반면 `EXPLAIN ANALYZE`는 쿼리를 **실제로 실행**하면서 각 단계가 걸린 실제 시간과 실제로 처리한 행 수까지 함께 보여준다.

| 구분 | EXPLAIN | EXPLAIN ANALYZE |
|---|---|---|
| 쿼리 실행 여부 | 실행하지 않음(계획만 수립) | 실제로 실행함 |
| 보여주는 값 | 예상 cost, 예상 rows | 예상값 + 실측 actual time, actual rows, loops |
| INSERT/UPDATE/DELETE 사용 시 | 안전(부작용 없음) | **실제로 데이터가 바뀐다** — 주의 필요 |
| 용도 | 계획만 빠르게 확인 | 예상과 실측의 괴리(추정 오차)까지 확인 |

**DML 문에 EXPLAIN ANALYZE를 쓰면 실제로 커밋될 수 있다는 점이 가장 흔한 실수다.** 운영 DB에서 확인이 필요하면 트랜잭션을 열고 `ROLLBACK`으로 마무리하거나, `EXPLAIN (ANALYZE, BUFFERS)`를 SELECT 쿼리에만 우선 적용하는 것이 안전하다.

## 핵심 개념 2: 실행 계획은 트리이고, 안쪽부터 실행된다

실행 계획은 들여쓰기로 표현된 트리 구조다. 가장 안쪽(리프 노드)이 먼저 실행되어 그 결과가 바깥쪽 노드로 전달되는 방식이므로, 읽는 순서는 출력 순서가 아니라 **안에서 바깥으로**다.

<img src="/assets/images/posts/2026-08-17-explain-analyze-query-planner-1.svg" alt="쿼리 실행 계획 트리 구조 - Hash Join 노드 아래 Seq Scan과 Index Scan 리프 노드, cost와 actual time 비교" style="width:100%;">

자주 보는 노드 유형은 다음과 같다.

| 노드 유형 | 의미 | 흔한 발생 상황 |
|---|---|---|
| Seq Scan | 테이블 전체를 순차적으로 읽음 | 조건에 맞는 인덱스가 없거나, 조건을 만족하는 행 비율이 높아 인덱스보다 전체 스캔이 유리하다고 판단됨 |
| Index Scan | 인덱스로 위치를 찾은 뒤 힙(실제 행)까지 접근 | 조건을 만족하는 행이 적을 때 |
| Index Only Scan | 인덱스만으로 결과를 반환(힙 접근 없음) | SELECT 절 컬럼이 인덱스에 모두 포함된 커버링 인덱스 상황 |
| Nested Loop | 바깥 결과의 각 행마다 안쪽을 반복 탐색 | 한쪽 결과 집합이 작고, 다른 쪽에 조인 조건 인덱스가 있을 때 |
| Hash Join | 한쪽을 해시테이블로 만들고 다른 쪽과 매칭 | 양쪽 다 크고 동등 조인일 때 |

## 핵심 개념 3: cost, rows, actual time — 각 숫자가 말하는 것

한 줄에 나오는 숫자들을 분해하면 다음과 같다.

- **cost=시작비용..종료비용**: 추정 비용이며 단위는 시간(ms)이 아니라 플래너 내부 상대값이다. 시작비용은 "첫 행을 내놓기까지"의 비용, 종료비용은 "전체를 다 내놓기까지"의 비용이다.
- **rows**: 플래너가 통계 정보(히스토그램, distinct 값 개수 등)로 추정한 행 수다.
- **actual time=시작..종료** (EXPLAIN ANALYZE에서만): 실제로 걸린 시간(ms)이며, 마찬가지로 첫 행/전체 행 기준이다.
- **loops**: 이 노드가 몇 번 반복 실행됐는지. Nested Loop의 안쪽 노드처럼 바깥 루프마다 반복되는 노드는 loops가 1보다 크고, 이때 actual time은 **1회 실행 평균**이므로 총 소요 시간은 `actual time × loops`로 다시 계산해야 한다.

가장 중요한 습관은 **rows(예상)와 actual rows(실측)를 비교하는 것**이다. 둘의 차이가 크면(예: 예상 180행인데 실측 4만 행) 통계가 최신 데이터 분포를 반영하지 못해 플래너가 잘못된 조인 방식이나 스캔 방식을 골랐을 가능성이 크다. 이 경우 `ANALYZE 테이블명`으로 통계를 갱신하는 것이 인덱스를 새로 만드는 것보다 먼저 시도할 조치다.

## 예제: 실행 계획 읽어보기

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.id, o.total_amount, c.name
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.grade = 'VIP';
```

```text
Hash Join  (cost=54.00..1120.30 rows=820 width=48)
           (actual time=0.6..14.2 rows=795 loops=1)
  Hash Cond: (o.customer_id = c.id)
  ->  Seq Scan on orders o  (cost=0.00..820.00 rows=40000 width=24)
                            (actual time=0.02..8.1 rows=40000 loops=1)
  ->  Hash  (cost=42.50..42.50 rows=180 width=28)
            (actual time=0.5..0.5 rows=175 loops=1)
        ->  Index Scan using idx_customers_grade on customers c
              (cost=0.29..42.10 rows=180 width=28)
              (actual time=0.01..0.4 rows=175 loops=1)
              Index Cond: (grade = 'VIP')
Planning Time: 0.31 ms
Execution Time: 14.6 ms
```

이 계획에서 확인할 점은 두 가지다. 첫째, `orders`에는 인덱스 없이 Seq Scan이 걸리지만 예상(40000)과 실측(40000) rows가 일치해 **통계는 정확**하다. 둘째, `customers`는 `idx_customers_grade` 인덱스를 타는 Index Scan이고 예상(180)과 실측(175)도 거의 일치한다. 즉 이 쿼리에서 시간을 대부분 잡아먹는 건 `orders` 전체를 훑는 Seq Scan이며, `orders`가 앞으로 더 커질 걸 감안하면 조인 조건이나 자주 쓰는 WHERE 조건에 맞는 인덱스 추가를 검토할 지점이라는 것을 이 한 줄만으로 판단할 수 있다.

## 실무 포인트

- **BUFFERS 옵션을 항상 같이 켠다**: `EXPLAIN (ANALYZE, BUFFERS)`는 shared hit(캐시 적중)와 read(디스크 읽기) 횟수를 함께 보여준다. actual time이 짧아도 read가 많으면 캐시가 워밍업되지 않은 상태에서 잰 것일 수 있어, 콜드 상태 재현이 필요한지 판단하는 데 쓴다.
- **loops가 1보다 큰 노드는 곱해서 봐야 한다**: 표면적인 actual time만 보고 "이 노드는 빠르다"고 오판하기 쉬운 지점이다.
- **Planning Time도 무시하지 않는다**: 파티션이 많거나 통계 수집 대상이 큰 테이블에서는 계획을 세우는 시간 자체가 실행 시간과 맞먹을 수 있다.
- **환경별 실측치는 그대로 비교하지 않는다**: 캐시 상태, 동시 부하, 하드웨어가 다르면 같은 쿼리도 actual time이 크게 달라진다. 절대 수치보다 예상/실측 rows의 괴리, 어떤 노드 유형이 선택됐는지에 먼저 주목한다.

## 3줄 요약

- EXPLAIN은 계획만, EXPLAIN ANALYZE는 실제 실행까지 하므로 DML에 함부로 쓰지 않는다.
- 실행 계획은 트리이며 리프 노드부터 실행되고, cost는 추정치·actual time은 실측치·loops는 반복 횟수라는 점을 구분해서 읽는다.
- rows(예상)와 actual rows(실측)의 차이가 크면 통계 갱신(ANALYZE)부터 의심하는 것이 인덱스 재설계보다 먼저다.

## 참고 자료

- [PostgreSQL 공식 문서 — Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
- [PostgreSQL 공식 문서 — EXPLAIN 명령어 레퍼런스](https://www.postgresql.org/docs/current/sql-explain.html)
- [Depesz — EXPLAIN 분석 도구](https://explain.depesz.com/)
