---
layout: single
title: "복합 인덱스 컬럼 순서의 함정 — 카디널리티와 쿼리 패턴으로 설계하는 법"
date: 2026-08-16 12:35:00 +0530
categories: database
tags: ["database", "index", "composite-index", "postgresql", "query-tuning"]
toc: true
toc_sticky: true
excerpt: "복합 인덱스를 걸었는데도 특정 쿼리만 느린 이유는 대부분 컬럼 순서에 있다. 리프트모스트 프리픽스 규칙과 동등·범위 조건 배치 원칙으로 컬럼 순서를 설계하는 방법을 정리한다."
---

## 인덱스는 있는데 왜 이 쿼리만 느릴까

운영 DB에 복합 인덱스를 걸어뒀는데도 특정 쿼리만 유독 느리게 나오는 경우가 있다. 인덱스가 없어서가 아니라, **컬럼 순서가 그 쿼리의 조건 패턴과 맞지 않아** 옵티마이저가 인덱스를 절반만 활용하거나 넓은 범위를 스캔하는 경우다. 단일 컬럼 인덱스는 순서 고민이 필요 없지만, 컬럼 두세 개를 묶는 순간부터 "어떤 컬럼을 앞에 둘 것인가"가 설계의 실질적인 난이도를 좌우한다.

문제는 이 판단에 하나로 고정된 정답이 없다는 점이다. 같은 테이블이라도 쿼리 패턴과 컬럼별 카디널리티(값의 다양성)에 따라 최적 순서가 달라진다. `(customer_id, created_at)`과 `(created_at, customer_id)`는 컬럼 구성이 같지만, 실제로는 서로 다른 쿼리를 위한 인덱스다.

이 글에서는 컬럼 순서를 결정하는 두 가지 핵심 기준 — **리프트모스트 프리픽스 규칙**과 **동등·범위 조건 배치 원칙** — 을 정리하고, 실행계획이 어떻게 달라지는지 확인한다.

## 핵심 개념 1: 리프트모스트 프리픽스(Leftmost Prefix) 규칙

B-Tree 복합 인덱스 `(a, b, c)`는 먼저 `a` 값으로 정렬되고, 같은 `a` 값 안에서 `b`로, 같은 `b` 값 안에서 `c`로 정렬된 구조다. 따라서 쿼리의 조건이 인덱스의 **왼쪽부터 연속된 접두사(prefix)** 를 포함할 때만 해당 인덱스를 효율적으로 탈 수 있다.

| WHERE 절 조건 | 인덱스 `(a, b, c)` 활용 여부 |
|---|---|
| `a = ?` | 사용 가능 — 접두사 1개 |
| `a = ? AND b = ?` | 사용 가능 — 접두사 2개 |
| `a = ? AND b = ? AND c = ?` | 사용 가능 — 전체 활용 |
| `b = ?` (a 없이 단독) | 사용 불가 — 접두사가 아님 |
| `a = ? AND c = ?` (b 건너뜀) | `a`까지만 인덱스로 탐색, `c`는 스캔 후 필터로 처리 |

이 규칙 덕분에 `(a, b, c)` 인덱스 하나가 있으면 `(a)`, `(a, b)` 조건 쿼리도 함께 커버된다. 반대로 `b`나 `c`만으로 조회하는 쿼리가 잦다면, 그 컬럼이 인덱스의 맨 앞에 오는 별도 인덱스가 필요하다.

## 핵심 개념 2: 동등 조건을 앞에, 범위 조건을 뒤에

컬럼 순서를 정할 때 자주 쓰이는 관례가 **동등 조건(`=`) 컬럼을 먼저, 범위 조건(`>`, `<`, `BETWEEN`) 컬럼을 나중에** 두는 것이다. 이유는 B-Tree 구조 자체에 있다. 앞쪽 컬럼 값이 같은 항목끼리 먼저 묶이고, 그 묶음 안에서 다음 컬럼 순으로 정렬되어 있기 때문에, 동등 조건이 앞에 있으면 옵티마이저가 해당 값 하나에 해당하는 좁은 구간만 정확히 짚어 들어갈 수 있다. 반면 범위 조건이 앞에 오면 그 범위에 해당하는 여러 값을 전부 넓게 훑어야 하고, 그 안에서는 뒤 컬럼이 정렬되어 있지 않으므로 별도 필터링이 추가로 필요하다.

정렬(`ORDER BY`)이 걸린 쿼리라면 한 단계 더 고려할 것이 있다. 인덱스 순서가 정렬 순서와 일치하면 별도의 정렬(Sort) 단계 없이 인덱스를 읽는 순서 그대로 결과를 반환할 수 있다. 그래서 실무에서는 "동등 조건 → 정렬 기준 컬럼 → 범위 조건 컬럼" 순으로 배치하는 방식이 자주 권장된다.

| 컬럼 순서 | 유리한 쿼리 패턴 |
|---|---|
| `(status, created_at)` | `status = 'PAID' AND created_at > ?` — 상태 그룹 안에서 날짜 범위 좁게 탐색 |
| `(created_at, status)` | `created_at > ?` 단독 조회, 또는 `ORDER BY created_at`이 주된 정렬 기준일 때 |
| `(customer_id, status, created_at)` | 고객별 최근 주문 목록처럼 조건 3개가 함께 자주 쓰일 때 |

카디널리티도 함께 봐야 한다. 값의 종류가 몇 개 안 되는 컬럼(예: 상태값 3~4종)에 단독 인덱스를 걸면 옵티마이저가 "차라리 전체 스캔이 낫다"고 판단해 인덱스를 무시하는 경우가 흔하다. 이런 저카디널리티 컬럼은 단독보다는, 카디널리티가 높은 컬럼과 묶은 복합 인덱스의 앞자리에 두어 "그룹을 나누는 용도"로 쓰는 편이 효과적이다.

## 예제: 컬럼 순서를 바꿨을 때 실행계획이 어떻게 달라지는가

아래 두 인덱스는 같은 컬럼으로 구성되지만 순서만 다르다.

```sql
-- 인덱스 A: 동등 조건(customer_id)을 앞에
CREATE INDEX idx_orders_a ON orders (customer_id, created_at);

-- 인덱스 B: 범위 조건(created_at)을 앞에
CREATE INDEX idx_orders_b ON orders (created_at, customer_id);

-- 조회 쿼리: 특정 고객의 최근 7일 주문
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders
WHERE customer_id = 42
  AND created_at > now() - interval '7 days'
ORDER BY created_at DESC;
```

인덱스 A를 쓰면 옵티마이저는 `customer_id = 42`에 해당하는 좁은 구간을 먼저 짚고, 그 안에서 `created_at` 조건과 정렬을 동시에 만족하는 순서로 읽는다. 개념적으로는 다음과 같은 계획이 나온다.

```
Index Scan using idx_orders_a on orders
  Index Cond: (customer_id = 42 AND created_at > ...)
```

인덱스 B를 쓰면 `created_at > ...` 조건에 해당하는 훨씬 넓은 구간(전체 고객의 최근 7일 데이터)을 먼저 훑은 뒤, 그 안에서 `customer_id = 42`인 행만 걸러내야 한다.

```
Index Scan using idx_orders_b on orders
  Index Cond: (created_at > ...)
  Filter: (customer_id = 42)
```

전체 고객 수가 많고 한 고객의 주문 비중이 작을수록 인덱스 A와 B의 스캔 범위 차이는 크게 벌어진다. 자주 조회되는 조건 조합에 맞춰 컬럼 순서를 고르는 것이 결과 행 수 자체를 바꾸지는 않아도, 그 결과에 도달하기까지 훑어야 하는 인덱스 구간의 크기를 좌우한다.

<img src="/assets/images/posts/2026-08-16-composite-index-column-order-1.svg" alt="복합 인덱스 컬럼 순서에 따른 탐색 범위 비교 - 동등 조건을 앞에 둔 인덱스 A와 범위 조건을 앞에 둔 인덱스 B의 스캔 범위 차이" style="width:100%;">

## 실무 포인트

- **쿼리 패턴을 먼저 수집한다.** 가장 자주 실행되는 WHERE·ORDER BY 조합을 확인한 뒤 컬럼 순서를 정한다. 이론상 맞는 순서라도 실제 서비스에서 그 쿼리가 드물게 쓰인다면 최적화 우선순위가 낮다.
- **리프트모스트 프리픽스를 활용해 인덱스 개수를 줄인다.** `(a, b, c)` 인덱스가 있으면 `(a)`, `(a, b)` 조건 쿼리도 커버되므로, 하위 조합을 위한 인덱스를 따로 만들 필요가 없는 경우가 많다.
- **인덱스가 늘어날수록 쓰기 비용도 늘어난다.** INSERT·UPDATE·DELETE마다 관련된 모든 인덱스가 함께 갱신되므로, 컬럼 순서만 다른 인덱스를 여러 개 만들어두는 것은 신중히 판단해야 한다.
- **결정 전후로 반드시 `EXPLAIN (ANALYZE, BUFFERS)`로 확인한다.** 이론상 맞는 순서라도 통계 정보가 오래됐거나 데이터 분포가 특이하면 옵티마이저가 다르게 판단할 수 있다.
- **커버링 인덱스도 함께 고려한다.** 자주 조회하는 컬럼을 인덱스에 포함시켜(예: PostgreSQL의 `INCLUDE` 절) 테이블 접근 자체를 줄이는 방법도 함께 검토할 가치가 있다.

## 3줄 요약

- 복합 인덱스는 리프트모스트 프리픽스 규칙 때문에, 인덱스 왼쪽부터 연속된 조건을 가진 쿼리만 온전히 활용할 수 있다.
- 동등 조건 컬럼을 앞에, 범위 조건 컬럼을 뒤에 두는 배치와 각 컬럼의 카디널리티, 실제 쿼리 패턴을 함께 고려해야 최적의 순서가 나온다.
- 설계 후에는 반드시 `EXPLAIN`으로 실제 실행계획을 확인해 이론과 실제 데이터 분포가 맞는지 검증해야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 — Multicolumn Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- [Use The Index, Luke! — The Equality, Sort, Range Rule](https://use-the-index-luke.com/sql/where-clause/the-equals-operator/concatenated-keys)
- [MySQL 8.0 Reference Manual — Multiple-Column Indexes](https://dev.mysql.com/doc/refman/8.0/en/multiple-column-indexes.html)
