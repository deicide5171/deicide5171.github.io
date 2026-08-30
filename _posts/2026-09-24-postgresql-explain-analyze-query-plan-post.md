---
layout: single
title: "PostgreSQL EXPLAIN ANALYZE 실행계획 제대로 읽는 법"
date: 2026-09-24 13:35:00 +0530
categories: database
tags: ["PostgreSQL", "EXPLAIN", "쿼리튜닝", "실행계획", "인덱스"]
toc: true
toc_sticky: true
excerpt: "EXPLAIN ANALYZE 결과를 그냥 훑어보고 '느린 것 같다'로 끝내지 않기 위해, cost와 실제 실행시간의 관계, rows 추정치와 실제값의 괴리가 왜 통계 왜곡의 신호인지 실행계획 읽는 법을 체계적으로 정리했다."
---

## 왜 지금 실행계획 읽는 법을 제대로 배워야 하는가

느린 쿼리를 만나면 대부분 `EXPLAIN ANALYZE`를 실행해보긴 하지만, 결과를 보고 "Seq Scan이 있으니 인덱스가 없나 보다" 정도로만 판단하고 끝내는 경우가 많다. 문제는 실행계획에는 훨씬 많은 정보가 담겨 있고, 그 정보를 제대로 해석하지 못하면 엉뚱한 인덱스를 추가하거나 실제 병목이 아닌 곳을 최적화하느라 시간을 낭비하게 된다는 것이다. 특히 PostgreSQL의 쿼리 플래너는 통계 정보를 기반으로 실행 계획을 세우기 때문에, 이 통계가 실제 데이터 분포와 어긋나는 순간 계획 자체가 잘못된 방향으로 왜곡될 수 있다. 실행계획을 제대로 읽으려면 이 통계 왜곡을 감지하는 눈이 반드시 필요하다.

## 핵심 개념 1 — cost와 실제 실행시간(actual time)은 다른 것을 말한다

`EXPLAIN`만 실행하면 플래너가 예측한 비용(cost)만 보이고, `EXPLAIN ANALYZE`를 실행하면 실제로 쿼리를 수행한 뒤 각 노드의 실제 실행시간(actual time)과 실제 처리된 행 수(actual rows)까지 함께 보여준다. cost는 어디까지나 플래너가 통계를 바탕으로 "추정"한 상대적 비용이지 실제 밀리초 단위 시간이 아니다. 반면 actual time은 실제 측정값이다. 두 값의 절대 크기를 직접 비교하는 것은 의미가 없으며, 중요한 것은 여러 노드의 actual time을 비교해 어느 단계가 전체 실행시간의 대부분을 차지하는지 찾아내는 것이다.

## 핵심 개념 2 — rows 추정치와 actual rows의 괴리는 통계 왜곡의 신호다

각 노드에는 플래너가 예측한 행 수(`rows=N`)와 실제 처리된 행 수(`actual rows=N`)가 함께 표시된다. 이 둘의 차이가 크다면(예: 예측은 100건인데 실제는 10만 건), 해당 테이블의 통계 정보가 오래됐거나 조건절의 선택도(selectivity)를 플래너가 잘못 추정하고 있다는 뜻이다. 이 괴리는 플래너가 그 이후 단계에서도 잘못된 조인 순서나 조인 알고리즘(Nested Loop vs Hash Join)을 선택하게 만드는 연쇄 효과를 일으킨다. 즉 표면적으로는 마지막 단계가 느려 보여도, 진짜 원인은 훨씬 앞선 단계의 잘못된 추정치인 경우가 많다.

| 신호 | 의미 | 대응 |
|---|---|---|
| `rows` vs `actual rows` 큰 괴리 | 통계 정보 오래됨 또는 선택도 오추정 | `ANALYZE` 재실행, 확장 통계 고려 |
| `Seq Scan` + 큰 `actual rows` 필터링 | 인덱스 부재 또는 선택도가 낮은 조건 | 조건절에 맞는 인덱스 검토 |
| `Nested Loop`의 반복 횟수(loops) 과다 | 내부 테이블 접근이 너무 자주 반복됨 | 조인 순서·조인 알고리즘 재검토 |
| `Sort` 노드의 높은 memory/disk 사용 | `work_mem` 부족으로 디스크 정렬 발생 | `work_mem` 조정 또는 정렬 최소화 |

## 예제 — 실행계획에서 병목 찾기

```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT o.id, o.total, c.name
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.created_at > '2026-01-01'
ORDER BY o.total DESC
LIMIT 20;
```

```text
Limit (cost=15234.10..15234.15 rows=20) (actual time=812.3..812.4 rows=20 loops=1)
  ->  Sort (cost=15234.10..15734.20 rows=200040) (actual time=812.2..812.3 rows=20 loops=1)
        Sort Method: top-N heapsort  Memory: 28kB
        ->  Hash Join (cost=520.00..12100.30 rows=200040) (actual time=5.1..790.4 rows=198512 loops=1)
              Hash Cond: (o.customer_id = c.id)
              ->  Seq Scan on orders o (cost=0.00..9800.00 rows=200040)
                    (actual time=0.02..410.5 rows=198512 loops=1)
                    Filter: (created_at > '2026-01-01')
                    Rows Removed by Filter: 1801488
              ->  Hash (cost=350.00..350.00 rows=13600)
                    (actual time=5.0..5.0 rows=13600 loops=1)
```

이 계획에서 `Seq Scan on orders`가 필터 조건으로 180만 행을 걸러내고 있다는 점(`Rows Removed by Filter`)이 핵심 단서다. `created_at`에 인덱스가 없어 테이블 전체를 스캔한 뒤 필터링하고 있으므로, `created_at` 컬럼에 인덱스를 추가하면 이 단계의 시간을 크게 줄일 수 있다.

## 실무 포인트

- **`BUFFERS` 옵션을 항상 함께 사용하라.** `EXPLAIN (ANALYZE, BUFFERS)`로 실행하면 각 노드가 캐시에서 읽었는지(shared hit) 디스크에서 읽었는지(shared read)까지 알 수 있어, 콜드 캐시 상태에서의 느림인지 근본적인 계획 문제인지 구분할 수 있다.
- **운영 DB에서 `EXPLAIN ANALYZE`는 실제로 쿼리를 실행한다는 점을 잊지 마라.** `INSERT`, `UPDATE`, `DELETE` 쿼리에 `ANALYZE`를 붙이면 실제로 데이터가 변경되므로, 반드시 트랜잭션으로 감싸고 롤백하거나 읽기 전용 쿼리에만 사용해야 한다.
- **통계 오래됨이 의심되면 `ANALYZE 테이블명`을 먼저 실행해 보라.** autovacuum이 통계를 자동 갱신하지만, 대량 데이터 변경 직후에는 수동으로 `ANALYZE`를 실행해 즉시 통계를 최신화하는 것이 진단 정확도를 높인다.

## 마무리 요약

- cost는 플래너의 추정치이고 actual time은 실제 측정값이므로, 노드 간 actual time을 비교해 진짜 병목을 찾아야 한다.
- rows 추정치와 actual rows의 큰 괴리는 통계 왜곡의 신호이며, 이는 이후 단계의 조인 순서·알고리즘 선택까지 연쇄적으로 왜곡시킨다.
- `EXPLAIN (ANALYZE, BUFFERS)`로 캐시 히트 여부까지 함께 확인하면 콜드 캐시 문제와 근본적인 계획 문제를 구분할 수 있다.

## 참고 자료

- [PostgreSQL - Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
- [PostgreSQL - Planner Statistics](https://www.postgresql.org/docs/current/planner-stats.html)
