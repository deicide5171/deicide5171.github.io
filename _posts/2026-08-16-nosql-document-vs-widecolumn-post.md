---
layout: single
title: "도큐먼트 vs 와이드컬럼 — NoSQL 데이터 모델링, 언제 무엇을 써야 할까"
date: 2026-08-16 13:35:00 +0530
categories: database
tags: ["nosql", "mongodb", "cassandra", "데이터모델링", "database"]
toc: true
toc_sticky: true
excerpt: "MongoDB 같은 도큐먼트 모델과 Cassandra 같은 와이드컬럼 모델은 같은 'NoSQL'로 묶이지만 설계 철학이 정반대라, 데이터 구조·쿼리 방식·확장 전략 차이를 알아야 올바른 선택을 할 수 있다."
---

## 왜 지금 이 구분이 중요한가

서비스가 커지면서 "관계형은 너무 무겁다, NoSQL을 쓰자"는 결정을 내리는 팀이 많다. 그런데 정작 어떤 NoSQL을 쓸지는 대충 넘어가는 경우가 흔하다. 문제는 **NoSQL이 하나의 모델이 아니라는 점**이다. MongoDB로 대표되는 도큐먼트 모델과 Cassandra로 대표되는 와이드컬럼 모델은 둘 다 "스키마리스, 조인 없음"이라는 인상 때문에 비슷해 보이지만, 실제로는 데이터를 저장하고 조회하는 방식이 근본적으로 다르다.

도큐먼트 모델은 "관련 데이터를 하나의 문서로 묶어 유연하게 담는" 접근이고, 와이드컬럼 모델은 "쿼리 패턴을 먼저 정하고 그 쿼리가 빠르도록 물리적으로 데이터를 배치하는" 접근이다. 이 차이를 모르면 카산드라 테이블을 문서 DB처럼 설계했다가 조회 한 번에 전체 테이블을 스캔하거나, 몽고DB 컬렉션을 관계형처럼 정규화했다가 조인을 애플리케이션에서 재구현하는 상황이 벌어진다.

## 핵심 개념 1: 도큐먼트 모델(MongoDB)의 사고방식

도큐먼트 DB는 JSON과 비슷한 구조(BSON)로 하나의 "엔티티"를 하나의 문서에 담는다. 관계형이라면 여러 테이블에 나뉘어 있을 사용자와 그 사용자의 최근 주문 목록을, 문서 하나 안에 배열로 **임베딩(embedding)** 할 수 있다. 반대로 자주 독립적으로 조회되거나 크기가 계속 커지는 데이터는 별도 컬렉션으로 분리해 `_id`로 **참조(referencing)** 한다. 스키마가 컬렉션 단위로 강제되지 않아 문서마다 필드가 달라도 되고, 이 유연성 덕분에 요구사항이 자주 바뀌는 초기 서비스나 다형적인 데이터(상품 카탈로그처럼 카테고리별 속성이 제각각인 경우)에 잘 맞는다.

## 핵심 개념 2: 와이드컬럼 모델(Cassandra)의 사고방식

와이드컬럼 스토어는 반대로 접근한다. 먼저 "이 데이터를 어떤 쿼리로 조회할 것인가"를 정하고, 그 쿼리가 단일 노드에서 빠르게 끝나도록 **파티션 키(partition key)** 와 **클러스터링 키(clustering key)** 를 설계한다. 같은 파티션 키를 가진 행들은 물리적으로 같은 노드에 모여 저장되고, 그 안에서 클러스터링 키 순서로 정렬된다. "특정 사용자의 주문을 최신순으로 조회" 같은 정해진 접근 패턴은 매우 빠르지만, 설계 시 고려하지 않은 조건(예: 파티션 키 없이 금액 범위로 검색)은 비효율적이거나 아예 지원되지 않는다. 조인이 없고 마스터 없는 피어투피어 구조라 노드를 추가하면 쓰기 처리량이 거의 선형으로 늘어나, 로그·시계열·이벤트처럼 쓰기가 많고 조회 패턴이 고정된 워크로드에 강하다.

## 비교표

| 기준 | 도큐먼트(MongoDB) | 와이드컬럼(Cassandra) |
|---|---|---|
| 데이터 구조 | 중첩 가능한 JSON 유사 문서 | 파티션 키 + 클러스터링 키 기반 넓은 행 |
| 쿼리 유연성 | 임의 필드 조건·집계 파이프라인 지원 | 파티션 키 기반 조회가 기본, 임의 조건 검색은 취약 |
| 스키마 변경 | 문서 단위로 자유로움 | 테이블 설계 시 쿼리를 먼저 확정해야 함 |
| 확장 방식 | 샤딩(레인지/해시 기반) | 컨시스턴트 해싱 기반 파티셔닝, 쓰기 확장성 강점 |
| 일관성 모델 | 기본적으로 강한 일관성(단일 문서 단위) | 튜너블 컨시스턴시(ONE/QUORUM/ALL 선택) |
| 대표 워크로드 | 카탈로그, 사용자 프로필, CMS | 시계열, 센서 로그, 대규모 쓰기 이벤트 |

## 예제 1: MongoDB — 임베딩 문서 조회

```javascript
// 사용자 문서 안에 최근 주문을 임베딩
db.users.insertOne({
  _id: "user_123",
  name: "김민준",
  orders: [
    { orderId: "o1", amount: 32000, date: "2026-08-10" },
    { orderId: "o2", amount: 15000, date: "2026-08-14" }
  ]
});

// 조회 한 번으로 사용자와 최근 주문을 함께 가져온다(조인 없음)
db.users.findOne({ _id: "user_123" }, { name: 1, orders: 1 });

// 임의 조건 필터링도 자유롭다
db.users.find({ "orders.amount": { $gte: 20000 } });
```

## 예제 2: Cassandra — 파티션·클러스터링 키 기반 테이블

```sql
-- user_id로 파티셔닝하고, order_date 내림차순으로 클러스터링
CREATE TABLE orders_by_user (
  user_id text,
  order_date timestamp,
  order_id text,
  amount decimal,
  PRIMARY KEY (user_id, order_date)
) WITH CLUSTERING ORDER BY (order_date DESC);

-- 파티션 키를 반드시 지정해야 효율적으로 조회된다
SELECT order_id, amount FROM orders_by_user
WHERE user_id = 'user_123' LIMIT 10;

-- 파티션 키 없이 검색하려면 ALLOW FILTERING이 필요한데
-- 클러스터 전체를 스캔할 수 있어 운영 환경에서는 지양한다
```

<img src="/assets/images/posts/2026-08-16-nosql-document-vs-widecolumn-1.svg" alt="도큐먼트 모델과 와이드컬럼 모델의 데이터 구조 비교 다이어그램" style="width:100%;">

## 실무 포인트

- **도큐먼트 임베딩은 크기 제한과 무한 성장을 조심한다.** MongoDB 문서는 크기 상한이 있고, 배열이 계속 커지는 데이터(예: 활동 로그 전체)를 한 문서에 계속 임베딩하면 성능이 나빠진다. 자주 커지는 하위 데이터는 별도 컬렉션으로 분리하는 것이 안전하다.
- **Cassandra는 테이블을 쿼리 단위로 여러 개 만드는 것이 정상이다.** 관계형처럼 정규화된 테이블 하나로 여러 쿼리를 처리하려 하지 말고, 조회 패턴마다 비정규화된 테이블(query table)을 따로 두는 것이 표준 설계 방식이다.
- **세컨더리 인덱스와 ALLOW FILTERING은 예외적 상황에만 쓴다.** 두 기능 모두 파티션 키 없는 조회를 가능하게 하지만 대규모 데이터에서는 전체 스캔에 가까워질 수 있어, 조회 패턴이 바뀌면 인덱스보다 테이블을 새로 설계하는 편이 낫다.
- **강한 ACID 트랜잭션이 필요하면 두 모델 모두 한계가 있다.** MongoDB는 단일 문서 단위로는 원자적이지만 다중 문서 트랜잭션은 상대적으로 무겁고, Cassandra는 애초에 다중 행 트랜잭션을 지원하지 않는다. 정산처럼 강한 정합성이 필수인 도메인은 관계형 DB와 병행하는 구조를 검토한다.

## 3줄 요약

- 도큐먼트 모델(MongoDB)은 관련 데이터를 하나의 문서로 임베딩해 유연한 스키마와 풍부한 쿼리를 지원한다.
- 와이드컬럼 모델(Cassandra)은 쿼리 패턴을 먼저 정하고 파티션 키·클러스터링 키로 물리적 저장 위치를 설계하는 query-first 모델링이 핵심이다.
- 조회 패턴이 다양하고 유연성이 중요하면 도큐먼트, 쓰기량이 압도적이고 접근 패턴이 고정돼 있으면 와이드컬럼이 유리하다.

## 참고 자료

- [MongoDB Manual — Data Modeling Introduction](https://www.mongodb.com/docs/manual/core/data-modeling-introduction/)
- [Apache Cassandra Documentation — Data Modeling](https://cassandra.apache.org/doc/stable/cassandra/data_modeling/index.html)
- [DataStax — Basic Rules of Cassandra Data Modeling](https://www.datastax.com/blog/basic-rules-cassandra-data-modeling)
