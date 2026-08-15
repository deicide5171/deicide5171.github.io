---
layout: single
title: "CDC로 데이터베이스 변경을 실시간으로 흘려보내기 — Debezium 실전"
date: 2026-08-20 12:35:00 +0530
categories: database
tags: ["database", "cdc", "debezium", "kafka", "replication", "data-pipeline"]
toc: true
toc_sticky: true
excerpt: "폴링 대신 트랜잭션 로그를 읽어 변경분만 실시간으로 전파하는 CDC의 원리와, Debezium으로 이를 구현할 때의 커넥터 설계·주의점을 정리한다."
---

주문 테이블이 바뀔 때마다 검색 인덱스, 캐시, 데이터 웨어하우스를 함께 갱신해야 하는 상황은 흔하다. 가장 손쉬운 접근은 `updated_at` 컬럼을 기준으로 주기적으로 폴링하며 변경분을 긁어오는 배치 동기화다. 문제는 폴링 주기가 짧아질수록 원본 DB에 걸리는 조회 부하가 커지고, 반대로 주기를 늘리면 다운스트림 시스템이 최신 상태를 반영하지 못하는 지연이 쌓인다는 점이다. 게다가 물리 삭제(hard delete)나 컬럼 값이 원래대로 되돌아가는 왕복 변경(update-then-revert)은 `updated_at` 비교만으로는 아예 놓치기 쉽다.

CDC(Change Data Capture)는 이 문제를 다른 방향에서 접근한다. 애플리케이션이 테이블을 직접 쿼리하는 대신, 데이터베이스가 이미 내구성 보장을 위해 기록하고 있는 트랜잭션 로그(WAL, binlog 등)를 읽어 커밋된 변경 이벤트를 그대로 스트림으로 흘려보낸다. 원본 테이블에는 추가 조회 부하를 거의 주지 않으면서도, insert/update/delete 각각을 놓치지 않고 커밋 순서 그대로 전파할 수 있다는 점이 폴링 방식과 근본적으로 다르다.

이번 글에서는 CDC의 로그 마이닝 원리와, 오픈소스 CDC 플랫폼 중 가장 널리 쓰이는 Debezium이 이를 Kafka Connect 위에서 어떻게 구현하는지, 그리고 이벤트 기반 아키텍처에서 자주 함께 언급되는 아웃박스 패턴과의 관계를 정리한다.

## 핵심 개념 1: 로그 기반 CDC의 원리

관계형 DB는 크래시 복구와 복제를 위해 커밋된 모든 변경을 트랜잭션 로그에 먼저 기록한다. PostgreSQL의 WAL(Write-Ahead Log), MySQL의 binlog가 대표적이다. CDC 도구는 이 로그를 마치 리플리케이션 슬레이브처럼 구독해, 로그 레코드를 파싱해서 "어떤 테이블의 어떤 행이 어떤 값에서 어떤 값으로 바뀌었는지"를 구조화된 이벤트로 재구성한다.

이 방식이 폴링과 다른 점은 세 가지다. 첫째, 원본 테이블에 SELECT를 던지지 않으므로 조회 부하가 사실상 없다. 둘째, 로그는 커밋 순서를 그대로 보존하므로 이벤트 순서가 보장된다. 셋째, 삭제나 트랜잭션 중간의 중간값 변경도 로그에는 모두 남기 때문에 폴링에서 놓치던 이벤트를 잡아낼 수 있다. 대신 로그 포맷은 DB 엔진마다 다르고 버전 호환성 이슈가 있어, 이를 안정적으로 파싱하는 커넥터 구현이 CDC 도구의 핵심 가치가 된다.

## 핵심 개념 2: Debezium 커넥터 아키텍처

Debezium은 자체 스트리밍 엔진을 새로 만드는 대신 Kafka Connect의 소스 커넥터(Source Connector)로 동작한다. 즉 Kafka Connect 클러스터에 커넥터 설정을 등록하면, Debezium이 해당 DB의 리플리케이션 프로토콜(PostgreSQL은 논리적 복제 슬롯, MySQL은 binlog 클라이언트 프로토콜)로 접속해 변경 이벤트를 읽고, 이를 Kafka 토픽에 그대로 발행하는 구조다.

<img src="/assets/images/posts/2026-08-20-cdc-debezium-change-data-capture-1.svg" alt="DB 트랜잭션 로그에서 Debezium 커넥터를 거쳐 Kafka 토픽으로 변경 이벤트가 흐르는 구조도" style="width:100%;">

토픽은 보통 테이블 단위로 자동 생성되며, 각 메시지는 변경 전(`before`)과 변경 후(`after`) 값, 그리고 변경 종류(create/update/delete)를 담은 봉투(envelope) 구조를 따른다. 최초 연결 시에는 스냅샷 단계를 거쳐 기존 데이터 전체를 한 번 읽어 초기 상태를 만들고, 이후부터는 로그 스트리밍으로 전환해 실시간 변경만 이어 붙인다. Kafka Connect 위에 얹혀 있기 때문에 컨슈머 쪽에서는 일반적인 Kafka 컨슈머 애플리케이션과 동일하게 다룰 수 있고, Kafka Connect 자체의 분산·재시작·오프셋 관리 기능을 그대로 재사용한다는 것이 이 아키텍처의 이점이다.

## 핵심 개념 3: 아웃박스 패턴과의 관계

마이크로서비스가 자기 DB를 갱신하면서 동시에 다른 서비스에 이벤트도 안정적으로 발행해야 할 때, 트랜잭션과 메시지 발행을 하나로 묶기 어렵다는 이중 쓰기(dual write) 문제가 생긴다. 아웃박스 패턴은 이를 "비즈니스 테이블 갱신과 아웃박스 테이블에 이벤트 로우 삽입을 같은 로컬 트랜잭션으로 묶는다"는 방식으로 우회한다. 이렇게 하면 이벤트 발행 자체가 원자적 DB 트랜잭션의 일부가 되어, 메시지 브로커 발행 실패로 인한 불일치를 걱정할 필요가 없어진다.

여기서 CDC가 필요한 이유가 생긴다. 아웃박스 테이블에 쌓인 로우를 다시 별도 프로세스가 폴링해서 Kafka로 보내면 결국 처음의 폴링 문제로 되돌아간다. Debezium은 아웃박스 테이블 전용 이벤트 라우터(Outbox Event Router) 변환기를 제공해서, 아웃박스 테이블에 삽입되는 로우를 CDC로 그대로 캡처한 뒤, 로우의 컬럼 값(대상 토픽, 이벤트 타입, 페이로드)에 맞춰 적절한 Kafka 토픽으로 라우팅해준다. 즉 아웃박스 패턴이 "무엇을 안전하게 남길지"를 정하고, CDC/Debezium이 "그것을 어떻게 실시간으로 옮길지"를 담당하는 상호 보완 관계다.

## 예제

PostgreSQL 테이블을 캡처하는 Debezium 커넥터 설정 예시다.

```json
{
  "name": "orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres-primary",
    "database.port": "5432",
    "database.user": "debezium_replicator",
    "database.password": "${file:/secrets/db.properties:password}",
    "database.dbname": "shopdb",
    "topic.prefix": "shop",
    "schema.include.list": "public",
    "table.include.list": "public.orders,public.outbox_event",
    "plugin.name": "pgoutput",
    "slot.name": "shop_orders_slot",
    "publication.autocreate.mode": "filtered",
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.table.field.event.id": "id",
    "transforms.outbox.table.field.event.key": "aggregate_id",
    "transforms.outbox.route.by.field": "aggregate_type"
  }
}
```

`plugin.name`을 `pgoutput`으로 지정한 것은 PostgreSQL 10 이상에서 기본 제공하는 논리적 디코딩 플러그인을 그대로 쓰겠다는 의미이며, `slot.name`으로 지정한 복제 슬롯이 이 커넥터 전용으로 WAL 위치를 추적한다. `transforms.outbox`는 위에서 설명한 이벤트 라우터로, `outbox_event` 테이블에 새 로우가 들어올 때마다 `aggregate_type` 값에 맞는 토픽으로 페이로드를 재배치한다.

## 실무 포인트

- **복제 슬롯은 방치되면 쌓인다**: 논리적 복제 슬롯은 컨슈머(Debezium)가 오프셋을 가져가지 않는 한 WAL을 계속 보존하므로, 커넥터가 오래 멈추면 원본 DB의 디스크 사용량이 늘어날 수 있다. 커넥터 중단 상태를 별도로 모니터링해야 한다.
- **스냅샷 단계의 부하를 미리 가늠한다**: 최초 연결 시 대상 테이블 전체를 훑는 스냅샷은 테이블 크기에 비례해 시간이 걸리고 원본 DB에 읽기 부하를 준다. 트래픽이 적은 시간대에 초기 배포하는 편이 안전하다.
- **스키마 변경(DDL)에 대한 대응을 미리 정한다**: 컬럼 추가·삭제 같은 스키마 변경이 있으면 캡처되는 메시지 스키마도 함께 바뀐다. Debezium은 스키마 히스토리 토픽으로 이를 추적하지만, 컨슈머 쪽 스키마 호환성 정책(예: Avro/Schema Registry의 호환 모드)을 함께 설계해야 한다.
- **정확히 한 번(exactly-once)이 기본은 아니다**: 커넥터 재시작이나 장애 복구 시 일부 이벤트가 중복 발행될 수 있으므로, 컨슈머 쪽에서 이벤트 키 기반 멱등 처리를 전제로 설계하는 편이 안전하다.

## 3줄 요약

- CDC는 폴링 대신 DB의 트랜잭션 로그(WAL/binlog)를 직접 읽어, 원본 조회 부하 없이 커밋 순서 그대로 변경 이벤트를 스트리밍한다.
- Debezium은 Kafka Connect의 소스 커넥터로 동작하며, 스냅샷 후 로그 스트리밍으로 전환해 테이블별 Kafka 토픽에 변경 이벤트를 발행한다.
- 아웃박스 패턴과 결합하면 이중 쓰기 문제 없이 이벤트를 안전하게 발행할 수 있지만, 복제 슬롯 관리·스키마 변경·중복 이벤트 처리는 운영 단계에서 별도로 챙겨야 한다.

## 참고 자료

- [Debezium 공식 문서](https://debezium.io/documentation/reference/stable/index.html)
- [Debezium PostgreSQL 커넥터 문서](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Debezium Outbox Event Router 문서](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Kafka Connect 공식 문서](https://kafka.apache.org/documentation/#connect)
