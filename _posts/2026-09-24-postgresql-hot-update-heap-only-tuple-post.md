---
layout: single
title: "PostgreSQL HOT Update — 인덱스 재작성 없이 행을 갱신하는 최적화"
date: 2026-09-24 13:35:00 +0530
categories: database
tags: ["HOTUpdate", "PostgreSQL", "MVCC", "인덱스", "성능튜닝"]
toc: true
toc_sticky: true
excerpt: "PostgreSQL에서 UPDATE 한 번이 사실은 새 튜플 추가와 모든 인덱스 갱신을 함께 유발한다는 사실이 왜 인덱스가 많은 테이블의 쓰기 성능을 갉아먹는지 짚고, 이 비용을 조건부로 없애주는 HOT(Heap-Only Tuple) 업데이트의 동작 조건을 정리했다."
---

## 왜 지금 HOT Update를 다시 봐야 하는가

PostgreSQL은 MVCC를 구현하기 위해 UPDATE를 "기존 행을 그 자리에서 고친다"가 아니라 "새로운 버전의 튜플을 추가하고 옛 버전은 나중에 VACUUM이 정리한다"는 방식으로 처리한다. 문제는 이 방식이 순진하게 구현되면, 행 하나를 갱신할 때마다 그 테이블에 걸린 모든 인덱스에도 새 튜플을 가리키는 엔트리를 추가해야 한다는 점이다. 인덱스가 5개 걸린 테이블이라면 UPDATE 한 번이 5개 인덱스 모두에 쓰기를 유발하는 셈이다. 인덱스가 많고 쓰기가 빈번한 테이블에서는 이 비용이 눈에 띄는 병목이 된다. HOT(Heap-Only Tuple) Update는 특정 조건을 만족하면 인덱스를 전혀 건드리지 않고도 새 튜플 버전을 만들어내는 최적화로, 이 조건이 언제 성립하고 언제 깨지는지 이해하면 스키마 설계와 인덱스 전략에 실질적인 영향을 준다.

## 핵심 개념 1 — HOT이 성립하는 유일한 조건: 인덱싱된 컬럼이 바뀌지 않아야 한다

HOT 업데이트가 적용되려면 딱 한 가지 조건이 필요하다. UPDATE로 바뀌는 컬럼 중 어느 것도 그 테이블의 어떤 인덱스에도 포함되지 않아야 한다. 예를 들어 `email`에 인덱스가 있는 테이블에서 `last_login_at` 컬럼만 갱신한다면, `email` 값은 그대로이므로 기존 인덱스 엔트리가 여전히 유효한 튜플을 가리키게 만들 수 있다. 이때 PostgreSQL은 새 튜플을 같은 페이지 안에(공간이 있다면) 만들고, 옛 튜플이 새 튜플을 직접 가리키는 체인을 연결한다. 인덱스는 옛 튜플의 위치만 알고 있어도, 그 체인을 따라가면 최신 버전을 찾을 수 있으므로 인덱스를 갱신할 필요가 없다.

## 핵심 개념 2 — 같은 페이지 안에 여유 공간이 있어야 한다는 두 번째 조건

인덱싱되지 않은 컬럼만 바꾼다고 해서 항상 HOT이 적용되는 것은 아니다. 새 튜플 버전은 원래 튜플과 같은 힙 페이지 안에 만들어져야 하므로, 그 페이지에 새 튜플이 들어갈 만한 여유 공간이 남아있어야 한다. 이 여유 공간은 테이블의 `fillfactor` 설정으로 확보한다 — 기본값(100)으로 두면 페이지를 가득 채워 저장하므로 이후 업데이트가 들어올 여유 공간이 없어 HOT이 거의 발동하지 못한다. `fillfactor`를 90 정도로 낮추면 각 페이지에 10%의 여유 공간을 의도적으로 남겨, 이후 업데이트들이 그 공간을 활용해 HOT 체인을 만들 수 있게 된다.

| 조건 | 충족 시 | 미충족 시 |
|---|---|---|
| 인덱싱된 컬럼 변경 여부 | 변경 없음 → HOT 가능 | 하나라도 변경 → 일반 업데이트(모든 인덱스 갱신) |
| 같은 페이지 내 여유 공간 | 있음 → HOT 적용 | 없음 → 다른 페이지에 튜플 생성, 인덱스 갱신 필요 |
| fillfactor 설정 | 90 이하로 여유 공간 확보 | 100(기본값)이면 여유 공간 빠르게 소진 |

## 예제 — HOT 업데이트 발생 여부 확인하기

```sql
-- fillfactor를 낮춰 업데이트를 위한 여유 공간 확보
CREATE TABLE sessions (
    id BIGINT PRIMARY KEY,
    email TEXT,
    last_login_at TIMESTAMPTZ
) WITH (fillfactor = 90);

CREATE INDEX idx_sessions_email ON sessions (email);

-- HOT 통계 확인 (n_tup_hot_upd가 HOT으로 처리된 업데이트 수)
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / NULLIF(n_tup_upd, 0), 1) AS hot_ratio
FROM pg_stat_user_tables
WHERE relname = 'sessions';

-- email이 아닌 last_login_at만 갱신 -> HOT 후보
UPDATE sessions SET last_login_at = now() WHERE id = 42;
```

`hot_ratio`가 낮다면, 실제로는 인덱싱된 컬럼도 함께 갱신되고 있거나 `fillfactor`로 인한 여유 공간이 부족하다는 신호이므로 둘 중 무엇이 원인인지 점검해야 한다.

## 실무 포인트

- **자주 갱신되는 컬럼과 자주 조회 조건으로 쓰이는 컬럼을 분리해서 설계하라.** `last_login_at`처럼 자주 바뀌는 값에 실수로 인덱스를 걸어두면, 그 순간부터 관련된 모든 업데이트가 HOT의 혜택을 받지 못하게 된다.
- **쓰기가 빈번한 테이블은 `fillfactor`를 낮추는 것을 적극 고려하라.** 기본값을 그대로 두면 페이지가 가득 차 있어 HOT이 발동할 여지 자체가 줄어들며, 이는 곧 더 잦은 인덱스 블로트(bloat)로 이어진다.
- **`n_tup_hot_upd` 비율을 모니터링 대시보드에 포함하라.** 이 비율이 시간이 지나며 떨어진다면 페이지 여유 공간이 소진되고 있다는 신호이므로, `fillfactor` 재조정이나 더 잦은 VACUUM 스케줄을 검토해야 한다.

## 마무리 요약

- HOT 업데이트는 갱신되는 컬럼이 어떤 인덱스에도 포함되지 않고, 같은 페이지 안에 여유 공간이 있을 때만 성립해 인덱스 갱신 비용을 완전히 없앤다.
- `fillfactor`를 의도적으로 낮춰 페이지에 여유 공간을 남겨두는 것이 HOT을 활성화하는 핵심 설정이다.
- `pg_stat_user_tables`의 `n_tup_hot_upd` 비율을 모니터링하면 실제로 HOT이 얼마나 활용되고 있는지, 스키마나 설정을 조정해야 할 시점인지 판단할 수 있다.

## 참고 자료

- [PostgreSQL - Heap-Only Tuples (HOT) Source Code README](https://github.com/postgres/postgres/blob/master/src/backend/access/heap/README.HOT)
- [PostgreSQL - pg_stat_user_tables](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ALL-TABLES-VIEW)
