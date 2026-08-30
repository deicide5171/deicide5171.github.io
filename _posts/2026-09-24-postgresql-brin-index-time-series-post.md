---
layout: single
title: "PostgreSQL BRIN 인덱스로 대용량 시계열 테이블 인덱스 크기 줄이기"
date: 2026-09-24 12:35:00 +0530
categories: database
tags: ["BRIN", "PostgreSQL", "시계열", "인덱스설계", "쿼리최적화"]
toc: true
toc_sticky: true
excerpt: "센서 로그처럼 수억 건씩 쌓이는 시계열 테이블에서 B-tree 인덱스 크기가 테이블 크기에 육박해 디스크와 캐시를 모두 압박할 때, 물리적 저장 순서를 활용해 인덱스를 수백 분의 1로 줄이는 BRIN 인덱스의 동작 원리를 정리했다."
---

## 왜 지금 BRIN 인덱스를 다시 봐야 하는가

IoT 센서 로그, 애플리케이션 이벤트 로그처럼 시간 순서로 계속 쌓이기만 하는 테이블에 `created_at` 컬럼용 B-tree 인덱스를 만드는 것은 자연스러운 선택이다. 문제는 이런 테이블이 수억 건 규모로 커지면 B-tree 인덱스 자체의 크기가 테이블 크기의 상당 부분을 차지하게 된다는 점이다. 인덱스가 커지면 메모리(shared_buffers)에 다 올라가지 못해 인덱스 스캔조차 디스크 I/O를 유발하고, INSERT마다 인덱스 갱신 비용도 함께 커진다. BRIN(Block Range Index)은 "시계열 데이터는 물리적으로 저장된 순서와 값의 순서가 거의 일치한다"는 특성을 이용해, B-tree보다 수백 배 작은 크기로 비슷한 효과를 내도록 설계된 인덱스다.

## 핵심 개념 1 — B-tree와 근본적으로 다른 저장 단위

B-tree 인덱스는 개별 행(row)마다 인덱스 엔트리를 만든다. 반면 BRIN은 개별 행이 아니라, 테이블을 물리적으로 연속된 블록 범위(block range, 기본적으로 128개 페이지 단위)로 나누고, 그 범위 안에 있는 값의 최솟값과 최댓값 같은 요약 정보(summary)만 저장한다. 즉 BRIN 인덱스 하나의 엔트리는 "이 블록 범위 안의 `created_at` 값은 2026-01-01부터 2026-01-03 사이"라는 요약 하나로, 그 범위 안에 수천 개의 행이 있어도 인덱스 엔트리는 단 하나다. 이 차이 때문에 BRIN 인덱스의 크기는 보통 B-tree의 몇백 분의 1 수준에 불과하다.

## 핵심 개념 2 — "물리적 순서와 값의 상관관계"가 성립해야 효과가 있다

BRIN이 빠른 이유는 쿼리 시점에 "이 블록 범위는 요약값만 봐도 조건을 만족할 수 없다"는 것을 확인해 그 범위 전체를 건너뛸 수 있기 때문이다. 이게 성립하려면 값이 물리적 저장 순서와 상관관계(correlation)를 가져야 한다 — 즉 테이블에 새 행이 추가되는 순서와 인덱싱하려는 컬럼 값의 순서가 대체로 일치해야 한다. `created_at`처럼 항상 증가하며 append되는 컬럼은 이 상관관계가 매우 높아 BRIN에 이상적이다. 반대로 `user_id`처럼 여러 사용자의 이벤트가 뒤섞여 삽입되는 컬럼은 물리적 순서와 값의 순서가 무작위에 가까워, BRIN을 만들어도 거의 모든 블록 범위가 스캔 대상에서 제외되지 않아 사실상 풀스캔과 다를 바 없어진다.

| 항목 | B-tree | BRIN |
|---|---|---|
| 인덱스 단위 | 개별 행 | 블록 범위(기본 128페이지)의 요약값 |
| 인덱스 크기 | 테이블 크기에 비례해 상당히 큼 | 테이블 크기 대비 매우 작음(수백 분의 1) |
| 전제 조건 | 없음(모든 데이터 분포에 적용 가능) | 물리적 저장 순서와 값의 상관관계 필요 |
| 적합한 컬럼 | 범용 | 시계열 `created_at`, 자동 증가 ID 등 |
| INSERT 비용 | 인덱스 갱신 비용 있음 | 요약값만 갱신, 훨씬 저렴 |

## 예제 — BRIN 인덱스 생성과 크기 비교

```sql
-- 기존 B-tree 인덱스 크기 확인
CREATE INDEX idx_events_created_at_btree ON events (created_at);
SELECT pg_size_pretty(pg_relation_size('idx_events_created_at_btree'));
-- 예: 2.1 GB (1억 건 기준)

-- BRIN 인덱스로 교체
DROP INDEX idx_events_created_at_btree;
CREATE INDEX idx_events_created_at_brin ON events USING BRIN (created_at)
    WITH (pages_per_range = 32); -- 요약 단위를 더 세밀하게 (기본값 128보다 작게)

SELECT pg_size_pretty(pg_relation_size('idx_events_created_at_brin'));
-- 예: 4.8 MB — B-tree 대비 수백 분의 1

EXPLAIN ANALYZE
SELECT * FROM events WHERE created_at BETWEEN '2026-03-01' AND '2026-03-02';
-- Bitmap Heap Scan + Bitmap Index Scan on idx_events_created_at_brin
```

`pages_per_range`를 기본값보다 작게 설정하면 요약 단위가 세밀해져 불필요한 블록을 덜 읽지만, 그만큼 인덱스 크기도 커지므로 데이터 분포와 쿼리 패턴에 맞춰 조정해야 한다.

## 실무 포인트

- **테이블을 도입 전에 실제 물리적 상관관계를 확인하라.** `SELECT correlation FROM pg_stats WHERE tablename = 'events' AND attname = 'created_at'`로 상관계수를 확인해 1에 가까울수록 BRIN이 효과적이다. 0에 가깝다면 BRIN을 걸어도 효과가 거의 없다.
- **대량 UPDATE나 VACUUM FULL 이후에는 상관관계가 깨질 수 있다.** 행을 물리적으로 재배치하는 작업 이후에는 애초에 BRIN이 전제하던 순서 상관관계가 흐트러질 수 있으므로, 이런 작업 이후 성능을 재검증해야 한다.
- **BRIN과 B-tree를 함께 쓰는 것도 선택지다.** 자주 조회하는 최근 데이터 범위에는 B-tree를, 오래된 대용량 이력 데이터에는 BRIN을 적용하는 방식으로 파티셔닝과 결합해 쓰는 경우도 흔하다.

## 마무리 요약

- BRIN은 개별 행이 아니라 블록 범위 단위로 요약값만 저장해, B-tree 대비 수백 분의 1 크기로 시계열 데이터를 인덱싱할 수 있다.
- BRIN의 효과는 물리적 저장 순서와 컬럼 값의 상관관계에 전적으로 의존하므로, 상관계수를 확인하지 않고 도입하면 기대한 성능 이득을 얻지 못할 수 있다.
- 대량 데이터 재배치 작업 이후에는 상관관계가 깨질 수 있으니 BRIN 성능을 주기적으로 재검증해야 한다.

## 참고 자료

- [PostgreSQL - BRIN Indexes](https://www.postgresql.org/docs/current/brin-intro.html)
- [PostgreSQL - pg_stats view](https://www.postgresql.org/docs/current/view-pg-stats.html)
