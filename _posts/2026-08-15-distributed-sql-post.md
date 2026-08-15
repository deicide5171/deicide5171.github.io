---
layout: single
title: "분산 SQL, 왜 지금 RDBMS와 NoSQL 사이의 답이 됐나"
date: 2026-08-15 12:40:00 +0530
categories: system-design
tags: ["distributed-systems", "database", "sql", "scalability", "consensus"]
toc: true
toc_sticky: true
excerpt: "관계형 DB의 익숙함과 NoSQL의 수평 확장성을 동시에 노리는 분산 SQL의 구조와, 도입 전에 반드시 이해해야 할 합의 알고리즘·트레이드오프를 정리한다."
---

## 왜 지금 분산 SQL인가

서비스가 커지면 늘 같은 갈림길에 선다. 관계형 DB(PostgreSQL, MySQL)는 트랜잭션과 스키마가 익숙하지만 단일 노드의 한계에 부딪히고, NoSQL은 수평 확장은 쉽지만 조인·트랜잭션을 포기해야 하는 경우가 많다. 그동안 많은 팀이 "일단 샤딩을 직접 구현"하거나 "일부 데이터만 NoSQL로 빼는" 식으로 이 갈림길을 우회해왔다.

최근 CockroachDB, Google AlloyDB, YugabyteDB 같은 **분산 SQL(Distributed SQL / NewSQL)** 데이터베이스가 성숙해지면서, 관계형 스키마와 트랜잭션 보장을 유지한 채로 NoSQL 수준의 수평 확장을 노리는 선택지가 실용적인 수준에 올라왔다. PostgreSQL 호환 계층을 앞세운 제품이 늘면서, 애플리케이션 코드를 크게 바꾸지 않고도 분산 아키텍처로 넘어갈 수 있다는 점이 특히 매력적이다.

동시에 오픈소스 DB 생태계 자체가 커지면서(특히 PostgreSQL 기반 확장이 활발해지면서), "직접 샤딩을 짤 것인가, 분산 SQL을 쓸 것인가"는 이제 시스템 설계 초기 단계에서 진지하게 검토해야 하는 질문이 됐다.

## 세 갈래 아키텍처 비교

| 항목 | 단일 노드 RDBMS | NoSQL(도큐먼트/KV) | 분산 SQL |
|---|---|---|---|
| 스키마 | 강한 스키마, 조인 지원 | 유연한 스키마, 조인 미지원 | 강한 스키마, 조인 지원 |
| 트랜잭션 | 강한 ACID | 대체로 약함(일부 문서 단위) | 분산 환경에서도 ACID 목표 |
| 확장 방식 | 수직 확장 위주 | 수평 확장 기본 | 수평 확장 + 관계형 유지 |
| 데이터 배치 | 단일 노드 | 파티션 키 기반 샤딩 | Raft 그룹 단위 자동 리밸런싱 |
| 대표 비용 | 확장 한계, 단일장애점 | 트랜잭션·조인 제약 | 지연 시간(합의 라운드트립) |

분산 SQL이 공짜로 확장성을 주는 것은 아니다. 여러 노드가 하나의 값에 합의해야 하므로, 그 합의 과정 자체가 새로운 지연 요소가 된다.

## 핵심 개념: Raft 합의와 리전 간 쓰기

분산 SQL 대부분은 데이터를 작은 범위(range)로 쪼개고, 각 range를 3개 이상의 노드에 복제한 뒤 **Raft** 같은 합의 알고리즘으로 리더를 뽑아 쓰기를 처리한다.

- **리더(Leader)**: 해당 range의 쓰기를 받아 로그를 복제하고, 과반수 노드가 승인하면 커밋을 확정한다.
- **팔로워(Follower)**: 리더의 로그를 복제해두고, 리더 장애 시 새 리더 선출에 참여한다.
- **쿼럼(Quorum)**: 노드 5개 중 3개가 응답하면 커밋 확정 — 과반수만 살아있으면 서비스가 계속된다.

멀티 리전 배포에서는 이 쿼럼 노드들이 지리적으로 떨어져 있을 수 있어, 쓰기 하나가 여러 리전을 오가는 라운드트립을 거치게 된다. 이것이 분산 SQL에서 가장 자주 나오는 지연 이슈의 원인이다.

## 예제: 분산 SQL에서의 리전 인지 테이블 설계

CockroachDB 스타일의 지역 지정 예시다.

```sql
CREATE TABLE orders (
    order_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region     STRING NOT NULL,
    customer   STRING NOT NULL,
    amount     DECIMAL NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
) LOCALITY REGIONAL BY ROW AS region;
```

`REGIONAL BY ROW`는 각 행의 리더 복제본을 `region` 컬럼 값에 해당하는 리전에 고정시킨다. 한국 사용자의 주문은 한국 리전 노드가 리더가 되어, 매 요청마다 해외 리전까지 왕복하지 않고 로컬에서 쓰기를 처리할 수 있다.

## 실무 포인트

- **핫스팟을 피하라**: range 하나에 쓰기가 몰리면 그 range의 리더 노드가 병목이 된다. 파티션 키 설계 단계에서 쓰기 분산을 반드시 검토한다.
- **읽기 일관성 수준을 명시적으로 고른다**: 강한 일관성이 필요 없는 조회(대시보드, 통계)는 팔로워 읽기(follower reads)로 지연을 줄일 수 있다.
- **마이그레이션은 점진적으로**: 전체 DB를 한 번에 옮기기보다, 새로 확장이 필요한 도메인부터 분산 SQL로 이전하며 운영 노하우를 쌓는 편이 안전하다.
- **모니터링 지표를 새로 정의한다**: 단일 노드 시절의 "쿼리 응답 시간"만으로는 부족하다. 리더 선출 빈도, 쿼럼 지연, 리밸런싱 이벤트를 함께 관찰해야 한다.

## 3줄 요약

- 분산 SQL은 관계형 스키마·트랜잭션을 유지하면서 NoSQL 수준의 수평 확장을 노리는 아키텍처다.
- 내부적으로는 range를 Raft로 복제하고 쿼럼 합의로 쓰기를 커밋하며, 이 합의 과정이 지연의 핵심 원인이 된다.
- 리전 인지 테이블 설계와 파티션 키 선정이 실제 성능을 좌우하므로, 도입 전 워크로드 패턴 분석이 필수다.

## 참고 자료

- [CockroachDB Docs — Architecture Overview](https://www.cockroachlabs.com/docs/stable/architecture/overview)
- [Raft Consensus Algorithm](https://raft.github.io/)
- [Google AlloyDB Documentation](https://cloud.google.com/alloydb/docs)
