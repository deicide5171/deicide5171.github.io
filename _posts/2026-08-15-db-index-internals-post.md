---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — DB 인덱스 내부 구조"
date: 2026-08-15 12:10:00 +0530
categories: dev-insight
tags: ["database", "index", "b-tree", "postgresql", "학습로드맵"]
toc: true
toc_sticky: true
excerpt: "Flutter 앱, 네이버 클라우드 지도 API, PostGIS 공간 DB, AI 에이전트까지 다뤄온 이 블로그의 다음 학습 주제로 DB 인덱스 내부 구조를 추천하는 이유를 정리한다."
---

## 왜 지금 인덱스 내부 구조인가

이 블로그의 글들을 쭉 훑어보면 흐름이 보인다. Flutter로 앱을 만들고, 네이버 클라우드 지도 API를 붙이고, 최근에는 PostGIS 기반 공간 DB와 분산 SQL, AI 에이전트까지 다루기 시작했다. 즉 "기능을 붙이는 단계"에서 "데이터를 저장하고 조회하는 방식 자체를 설계하는 단계"로 관심사가 옮겨가고 있다는 뜻이다.

그런데 지금까지의 글에는 공통된 빈틈이 하나 있다. **인덱스를 "쓰는" 이야기는 많은데(공간 인덱스 GiST, 분산 SQL의 range 등), 인덱스가 내부적으로 왜 그렇게 동작하는지는 아직 다루지 않았다.** `WHERE` 절에 인덱스를 걸었는데도 느린 경우, `EXPLAIN` 결과를 봐도 왜 인덱스를 안 타는지 판단이 안 서는 경우는 결국 내부 구조를 모르면 답이 안 나오는 문제들이다.

특히 오늘 다룬 분산 SQL 글에서 range와 리더 복제를 설명했고, GIS 글에서 GiST 공간 인덱스를 언급했는데, 이 둘 다 결국 "인덱스 자료구조가 어떻게 생겼는가"라는 같은 뿌리에서 나온 응용이다. 그 뿌리를 한 번 파두면 두 글을 훨씬 깊이 있게 이해할 수 있다.

## 왜 하필 인덱스 내부인가 — 다른 후보와 비교

추천 후보는 여럿 있었지만, 이 블로그의 궤적을 기준으로 우선순위를 매겨봤다.

| 후보 주제 | 지금 필요한 이유 | 시급도 |
|---|---|---|
| **DB 인덱스 내부 구조** | 지도·분산 DB 글에서 반복 등장한 인덱스 개념의 뿌리 | 높음 |
| 테스팅 전략 | Flutter 앱 글이 여러 편인데 테스트 관련 글이 없음 | 중간 |
| Docker/CI 파이프라인 | 배포 자동화 경험이 아직 블로그에 없음 | 중간 |
| 네트워크 심화 | API 연동 글은 많지만 TCP/TLS 레벨 이해는 별도 | 낮음(급하지 않음) |

테스팅과 CI도 분명 필요하지만, 지금 막 분산 SQL·공간 인덱스를 다룬 직후이니 "그 인덱스가 왜 그렇게 동작하는가"를 먼저 메우는 것이 학습 곡선상 자연스럽다.

## 핵심 개념: B-Tree vs LSM-Tree vs GiST

인덱스는 하나의 정답 구조가 아니라, 워크로드에 따라 다른 트레이드오프를 가진 자료구조 여러 개다.

- **B-Tree**: PostgreSQL, MySQL의 기본 인덱스. 정렬된 키를 균형 트리로 유지해 `=`, `<`, `>`, `BETWEEN` 조회에 강하다. 읽기 위주 워크로드에 적합하다.
- **LSM-Tree(Log-Structured Merge-Tree)**: RocksDB, Cassandra 등이 채택. 쓰기를 메모리에 먼저 모았다가 순차적으로 디스크에 병합(compaction)한다. 쓰기가 매우 많은 워크로드에 유리하지만, 오래된 데이터를 지우는 compaction 비용이 따로 든다.
- **GiST(Generalized Search Tree)**: PostGIS의 공간 인덱스가 이걸 기반으로 한다. 값이 아니라 "겹치는 범위(bounding box)"를 기준으로 트리를 구성해, 좌표·범위 데이터를 인덱싱할 수 있게 일반화한 구조다.

셋 다 "탐색 범위를 좁혀서 전체 스캔을 피한다"는 목적은 같지만, 무엇을 빠르게 하고 무엇을 희생하는지가 다르다.

## 예제: EXPLAIN으로 인덱스 동작 확인하기

이론만으로는 감이 안 오니, 실제 쿼리 플랜으로 확인하는 습관을 들이는 게 중요하다.

```sql
-- 인덱스가 있는지, 실제로 타는지 확인
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders
WHERE customer_id = 42
  AND created_at > now() - interval '7 days';
```

```
Index Scan using idx_orders_customer_created on orders
  Index Cond: (customer_id = 42 AND created_at > ...)
  Buffers: shared hit=12
```

`Index Scan`이 아니라 `Seq Scan`이 나온다면, 인덱스가 없거나 옵티마이저가 "인덱스보다 전체 스캔이 더 싸다"고 판단한 것이다. 이 판단 기준(선택도, 통계 정보)을 이해하는 것 자체가 인덱스 내부 구조 학습의 핵심 목표다.

## 학습 순서 제안

1. **B-Tree 기본기**: 노드 분할, 균형 유지 원리부터 이해한다. 알고리즘 교재 수준의 자료구조 지식이면 충분하다.
2. **복합 인덱스와 컬럼 순서**: `(customer_id, created_at)`과 `(created_at, customer_id)`가 왜 다른 쿼리에 유리한지 직접 실험해본다.
3. **EXPLAIN 읽는 습관**: 자신이 만든 쿼리마다 플랜을 확인하는 루틴을 들인다.
4. **LSM-Tree, GiST로 확장**: 오늘 다룬 분산 SQL(Raft + range)과 PostGIS(GiST) 글을 다시 읽으며 연결 짓는다.

## 실무 포인트

- 인덱스는 "걸어두면 무조건 빠르다"가 아니다. 쓰기 비용이 늘고, 잘못된 컬럼 순서는 오히려 옵티마이저에게 무시당한다.
- 카디널리티(값의 다양성)가 낮은 컬럼에 단독 인덱스를 걸어봐야 옵티마이저가 잘 안 쓴다 — 이 판단 로직을 아는 것이 인덱스 설계의 실전 감각이다.
- 오늘 만든 분산 SQL·GIS 글을 나중에 다시 읽을 때, "이 인덱스가 왜 이런 트레이드오프를 갖는가"를 스스로 설명할 수 있는지 확인해보면 좋은 복습이 된다.

## 3줄 요약

- 이 블로그는 지도·분산 DB 글에서 인덱스를 반복적으로 언급해왔지만, 정작 인덱스 내부 구조는 다룬 적이 없다.
- B-Tree, LSM-Tree, GiST는 모두 "전체 스캔을 피한다"는 목적은 같지만 워크로드별 트레이드오프가 다르다.
- EXPLAIN으로 실제 쿼리 플랜을 확인하는 습관이, 이론 학습을 실전 감각으로 연결하는 가장 빠른 길이다.

## 참고 자료

- [PostgreSQL 공식 문서 — Indexes](https://www.postgresql.org/docs/current/indexes.html)
- [PostgreSQL — GiST 인덱스](https://www.postgresql.org/docs/current/gist.html)
- [RocksDB — LSM-Tree 개요](https://github.com/facebook/rocksdb/wiki/Overview)
