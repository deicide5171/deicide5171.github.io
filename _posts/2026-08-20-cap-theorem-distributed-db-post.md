---
layout: single
title: "CAP 정리로 분산 DB 제대로 고르기 — Cassandra·MongoDB·CockroachDB는 어디에 서 있나"
date: 2026-08-20 13:35:00 +0530
categories: database
tags: ["cap-theorem", "distributed-database", "cassandra", "mongodb", "cockroachdb", "consistency"]
toc: true
toc_sticky: true
excerpt: "CAP 정리를 '3개 중 2개 선택'이라는 슬로건으로만 기억하면 실제 DB 선택에 도움이 안 된다. Cassandra, MongoDB, CockroachDB가 CAP 삼각형의 어디에 위치하는지 설정값 수준까지 짚어본다."
---

## 왜 지금 CAP 정리를 다시 봐야 하나

분산 DB 후보가 넘쳐나는 요즘, "우리 서비스는 가용성이 중요하니 AP로 가자" 같은 말이 회의에서 쉽게 나온다. 문제는 이 말이 CAP 정리를 잘못 요약한 채로 쓰인다는 점이다. CAP은 "3개 중 2개만 고르라"는 정리가 아니라, **네트워크 파티션이 실제로 발생한 순간**에 한해 일관성과 가용성 중 하나를 포기해야 한다는 좁고 구체적인 주장이다.

이 차이를 모르면 마케팅 문구만 보고 "이 DB는 CP니까 안전하다"고 단정하거나, 같은 DB라도 설정값에 따라 삼각형 위 위치가 움직인다는 사실을 놓치기 쉽다. Cassandra, MongoDB, CockroachDB는 세 개 모두 분산 DB지만 기본 동작과 튜닝 가능 범위가 전혀 다르다. 이번 글에서는 CAP 정리를 정확히 정리하고, 이 세 DB가 실제로 어디에 서 있는지를 설정값 수준에서 짚어본다.

## 핵심 개념 1: CAP 정리, 정확히 무엇을 말하는가

| 항목 | 의미 | 흔한 오해 |
|---|---|---|
| Consistency(일관성) | 모든 노드가 항상 최신의 동일한 값을 반환 | "절대 틀리지 않는다"가 아니라 "읽기 시점 최신값 일치" |
| Availability(가용성) | 살아있는 노드는 항상(에러 없이) 응답 | "빠르다"가 아니라 "응답 자체는 반드시 온다" |
| Partition Tolerance(파티션 허용) | 노드 간 네트워크가 끊겨도 시스템은 계속 동작 | "선택 사항"이 아니라 분산 시스템의 전제조건 |

네트워크가 멀쩡할 때는 C와 A를 동시에 만족하기 어렵지 않다. CAP의 트레이드오프는 **파티션이 발생한 순간에만** 작동한다: 분리된 쪽 노드가 응답을 거부(C 선택)하거나, 오래된 값이라도 응답(A 선택)하는 두 갈래뿐이다. 분산 시스템에서 파티션은 발생 여부가 아니라 언제 발생하느냐의 문제이므로, 실질적으로 모든 분산 DB는 CP 아니면 AP로 분류된다. CA는 파티션이 없는 단일 노드에서만 성립한다.

## 핵심 개념 2: 실전 DB는 삼각형 어디에 있나

<img src="/assets/images/posts/2026-08-20-cap-theorem-distributed-db-1.svg" alt="CAP 삼각형 개념도와 Cassandra, MongoDB, CockroachDB의 위치" style="width:100%;">

| DB | 기본 성향 | 근거 | 튜닝 가능 범위 |
|---|---|---|---|
| Cassandra | AP | 마스터 없는 구조, 기본 컨시스턴시 레벨이 낮아 일부 노드만 응답해도 성공 처리 | 쿼럼 레벨을 높이면 CP 쪽에 가깝게 이동 가능 |
| MongoDB | CP에 가까움 | 단일 프라이머리 구조, `w: majority` 쓰기가 기본값에 가까워 과반수 미확보 시 쓰기 실패 | 세컨더리 읽기·낮은 write concern으로 AP 쪽으로 이동 가능 |
| CockroachDB | CP | Raft 기반 쿼럼 커밋, 소수 쪽 파티션은 쓰기·강한 읽기 모두 거부 | 팔로워 읽기(약한 일관성 허용) 정도만 부분 완화 |

중요한 건 "이 DB는 원래 AP다/CP다"라는 딱지가 아니라, **컨시스턴시 레벨 설정값 하나로 같은 DB가 삼각형 위에서 움직인다**는 사실이다. DB 선택은 이름이 아니라 워크로드에 어떤 레벨로 설정해서 쓸 것인가의 문제다.

## 예제 1: Cassandra 컨시스턴시 레벨 설정 (CQL)

```sql
-- 가용성 우선: 노드 하나만 응답해도 성공 처리
CONSISTENCY ONE;
SELECT * FROM users WHERE user_id = 123;

-- 일관성 우선: 복제본 과반수가 응답해야 성공 (읽기+쓰기 모두 QUORUM이면
-- 두 쿼럼 집합이 항상 겹쳐 최신값을 보장 = CP에 가깝게 동작)
CONSISTENCY QUORUM;
SELECT * FROM users WHERE user_id = 123;
```

`ONE`은 아무 노드나 응답하면 되므로 가용성이 높지만 아직 복제 안 된 오래된 값을 돌려줄 수 있다. 읽기·쓰기 모두 `QUORUM`이면 두 쿼럼 집합이 항상 겹쳐 최신값을 보장하지만, 과반수를 확보하지 못한 쪽은 요청 자체가 실패한다.

## 예제 2: MongoDB Write/Read Concern 설정 (mongosh)

```javascript
// 일관성 우선: 과반수 노드에 복제된 뒤에만 성공 응답
db.orders.insertOne(
  { orderId: "A1001", amount: 42000 },
  { writeConcern: { w: "majority" } }
);

// 같은 강도로 읽기: majority로 커밋된 값만 조회
db.orders.find({ orderId: "A1001" }).readConcern("majority");
```

`w: "majority"`는 과반수 세컨더리 복제를 기다린 뒤 응답하므로, 프라이머리가 파티션으로 고립되면 쓰기가 실패한다(CP 방향). `w: 1`로 낮추면 프라이머리 혼자만 반영해도 즉시 응답이 오지만, 복제 전 데이터 유실 위험이 커진다.

## 실무 포인트

- **"CP/AP다"로 끝내지 말고 컨시스턴시 레벨까지 확인한다.** 같은 Cassandra 클러스터도 애플리케이션마다 다른 레벨을 쓸 수 있다.
- **파티션 시나리오를 직접 시뮬레이션한다.** 네트워크를 끊어보고 어느 쪽이 실패하는지, 재시도·큐잉으로 버틸 수 있는지 미리 확인한다.
- **읽기·쓰기 레벨을 따로 결정한다.** 쓰기는 강하게, 조회는 약하게(또는 그 반대) 섞어 쓰는 것이 실무에선 자연스럽다.
- **CAP은 평상시 성능은 설명하지 않는다.** 파티션이 없을 때도 지연·일관성 트레이드오프는 존재하며, 이를 다루는 확장 개념이 PACELC라는 점도 알아두면 좋다.

## 3줄 요약

- CAP은 항상 2개를 고르라는 뜻이 아니라, 파티션이 실제로 발생한 순간에만 일관성·가용성 중 하나를 포기해야 한다는 좁은 주장이다.
- Cassandra는 기본 AP, MongoDB·CockroachDB는 CP에 가깝지만, 컨시스턴시 레벨·write concern 설정으로 위치가 움직인다.
- DB 선택은 이름표가 아니라 워크로드별 읽기·쓰기 레벨 설정의 문제이며, 파티션 시나리오를 직접 시험해보는 것이 가장 확실하다.

## 참고 자료

- [Gilbert & Lynch — Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services](https://users.ece.cmu.edu/~adrian/731-sp04/readings/GL-cap.pdf)
- [Apache Cassandra Docs — Consistency](https://cassandra.apache.org/doc/stable/cassandra/architecture/dynamo.html)
- [MongoDB Docs — Read Concern / Write Concern](https://www.mongodb.com/docs/manual/reference/write-concern/)
- [CockroachDB Docs — Consistency Model](https://www.cockroachlabs.com/docs/stable/architecture/overview)
