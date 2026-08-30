---
layout: single
title: "커버링 인덱스와 Index-Only Scan으로 쿼리 성능 극대화하기"
date: 2026-09-24 13:35:00 +0530
categories: database
tags: ["커버링인덱스", "IndexOnlyScan", "쿼리튜닝", "인덱스설계", "PostgreSQL"]
toc: true
toc_sticky: true
excerpt: "조건절에 맞는 인덱스를 추가했는데도 쿼리가 여전히 느린 이유가 인덱스에서 조건만 찾고 나머지 컬럼은 결국 테이블 본체를 다시 읽으러 가기 때문이라는 점을 짚고, 이 추가 조회를 없애는 커버링 인덱스와 Index-Only Scan의 동작 원리를 정리했다."
---

## 왜 지금 커버링 인덱스를 다시 봐야 하는가

WHERE 절 조건에 맞춰 인덱스를 추가했는데도 기대만큼 쿼리가 빨라지지 않는 경우가 있다. 원인을 찾아보면 인덱스를 이용해 조건에 맞는 행의 위치는 빠르게 찾아냈지만, SELECT 절에 나열된 나머지 컬럼 값을 가져오기 위해 결과로 나온 각 행마다 다시 테이블 본체(heap)에 접근하는 추가 I/O가 발생하고 있는 경우가 많다. 이 추가 접근을 실행계획에서는 흔히 "Heap Fetch" 또는 "테이블 접근"으로 표현하며, 인덱스에서 찾은 행 수가 많을수록 이 부분이 전체 쿼리 시간의 상당 부분을 차지하게 된다. 커버링 인덱스는 이 문제를 "쿼리가 필요로 하는 모든 컬럼을 아예 인덱스 자체에 포함시켜, 테이블 본체를 다시 찾아갈 필요 자체를 없앤다"는 방식으로 해결한다.

## 핵심 개념 1 — 일반 인덱스와 커버링 인덱스의 차이

일반적인 B-tree 인덱스는 인덱스로 지정한 컬럼(들)과, 실제 행의 위치를 가리키는 포인터(PostgreSQL은 CTID, MySQL InnoDB는 클러스터형 인덱스의 특성상 프라이머리 키)만 담고 있다. 조건절에 쓰이는 컬럼과 SELECT 절에서 실제로 읽어야 하는 컬럼이 다르면, 인덱스에서 조건에 맞는 위치를 찾은 뒤 그 포인터를 따라 테이블 본체로 다시 이동해 나머지 컬럼 값을 읽어야 한다. 커버링 인덱스는 조건절 컬럼뿐 아니라 SELECT 절에 필요한 컬럼까지 인덱스 안에 함께 저장해서(PostgreSQL의 `INCLUDE` 절, MySQL의 복합 인덱스 마지막 컬럼 추가 방식), 쿼리가 인덱스만 읽고도 완결되도록 만든다.

## 핵심 개념 2 — Index-Only Scan이 성립하기 위한 추가 조건

인덱스에 필요한 컬럼을 모두 담아뒀다고 해서 항상 Index-Only Scan이 되는 것은 아니다. PostgreSQL에서는 MVCC 구조상 인덱스 항목만으로는 그 행이 현재 트랜잭션에서 보이는(visible) 버전인지 판단할 수 없어, 원칙적으로는 여전히 heap을 확인해야 한다. 이 문제를 해결하는 것이 Visibility Map이다 — 해당 페이지의 모든 행이 모든 트랜잭션에 보인다는 것이 보장되면 그 페이지는 Visibility Map에 표시되고, 이 경우에만 heap 접근 없이 인덱스만으로 쿼리를 완결할 수 있다. 즉 VACUUM이 자주 돌지 않아 Visibility Map이 최신 상태가 아니면, 컬럼을 다 포함한 커버링 인덱스를 만들어도 실제로는 Index-Only Scan이 아니라 여전히 heap fetch가 섞인 계획이 나올 수 있다.

| 항목 | 일반 인덱스 + 테이블 접근 | 커버링 인덱스 + Index-Only Scan |
|---|---|---|
| 조건 컬럼 매칭 | 인덱스에서 찾음 | 인덱스에서 찾음 |
| SELECT 컬럼 조회 | 테이블 본체(heap) 재접근 | 인덱스 자체에서 바로 획득 |
| PostgreSQL 추가 요건 | 해당 없음 | Visibility Map 최신 상태 필요 |
| 효과가 큰 상황 | - | 조회 행 수가 많고 SELECT 컬럼이 적을 때 |

## 예제 — PostgreSQL INCLUDE 절로 커버링 인덱스 만들기

```sql
-- 조건절: status, 조회 컬럼: order_id, total, created_at
CREATE INDEX idx_orders_status_covering
ON orders (status)
INCLUDE (order_id, total, created_at);

EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, total, created_at
FROM orders
WHERE status = 'SHIPPED';

-- 실행계획 예시
-- Index Only Scan using idx_orders_status_covering on orders
--   Index Cond: (status = 'SHIPPED')
--   Heap Fetches: 0   <- 이 값이 0이면 완전한 Index-Only Scan
```

`INCLUDE` 절에 넣은 컬럼은 인덱스 정렬 순서에는 관여하지 않고 단순히 함께 저장만 되므로, 조건절에 쓰이지 않는 컬럼을 인덱스 키에 억지로 포함시켜 정렬 비용을 늘리는 것보다 효율적이다.

## 실무 포인트

- **`Heap Fetches` 값을 반드시 확인하라.** `EXPLAIN ANALYZE`에서 Index Only Scan이라고 나와도 `Heap Fetches`가 0이 아니면 여전히 상당수의 heap 접근이 발생하고 있다는 뜻이므로, `autovacuum` 설정을 점검해야 한다.
- **모든 조회 컬럼을 무작정 인덱스에 포함시키지 마라.** 커버링 인덱스는 쓰기(INSERT/UPDATE) 시 유지보수해야 할 인덱스 크기와 개수를 늘리므로, 실제로 빈번하고 성능이 중요한 쿼리 패턴에 한해 선택적으로 적용해야 한다.
- **넓은 테이블(컬럼 수가 많거나 TEXT/JSON 컬럼이 큰 경우)에서는 커버링 인덱스 자체가 비대해질 수 있다.** 이 경우 인덱스 크기와 쿼리 개선 효과를 함께 저울질해야 한다.

## 마무리 요약

- 조건절에 맞는 인덱스가 있어도 SELECT 컬럼을 위해 테이블 본체에 재접근하는 heap fetch가 성능 병목이 되는 경우가 흔하다.
- 커버링 인덱스는 필요한 컬럼을 인덱스 자체에 포함시켜 이 재접근을 없애지만, PostgreSQL에서는 Visibility Map이 최신이어야 실제 Index-Only Scan이 성립한다.
- `EXPLAIN ANALYZE`의 `Heap Fetches` 값을 확인해야 커버링 인덱스가 실제로 의도한 효과를 내고 있는지 검증할 수 있다.

## 참고 자료

- [PostgreSQL - Index-Only Scans and Covering Indexes](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
- [PostgreSQL - CREATE INDEX (INCLUDE clause)](https://www.postgresql.org/docs/current/sql-createindex.html)
