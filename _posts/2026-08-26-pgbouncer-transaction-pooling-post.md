---
layout: single
title: "커넥션 풀 위에 커넥션 풀을 얹었더니 — PgBouncer 트랜잭션 풀링과 앱 풀의 상호작용"
date: 2026-08-26 13:35:00 +0530
categories: database
tags: ["database", "pgbouncer", "postgresql", "connection-pooling", "hikaricp"]
toc: true
toc_sticky: true
excerpt: "애플리케이션의 HikariCP 풀과 DB 앞단의 PgBouncer 풀을 함께 쓸 때, 트랜잭션 풀링 모드가 세션 상태(prepared statement, advisory lock)를 어떻게 깨뜨리는지 정리한다."
---

PostgreSQL 커넥션은 하나당 프로세스 하나를 포크하는 구조라 생성 비용이 크고, 동시 연결 수에도 실질적인 상한이 있다(기본 `max_connections=100`). 서비스 인스턴스가 여러 대이고 인스턴스마다 HikariCP 같은 애플리케이션 커넥션 풀을 유지하면, 인스턴스 수 × 풀 크기만큼 DB에 실제 연결이 열려 이 상한을 쉽게 넘는다. PgBouncer는 이 문제를 애플리케이션과 DB 사이에 경량 프록시를 두어, 수백 개의 클라이언트 연결을 훨씬 적은 수의 실제 DB 연결로 다중화하는 방식으로 해결한다.

문제는 PgBouncer가 제공하는 세 가지 풀링 모드 중 가장 효율적인 **트랜잭션 풀링(transaction pooling)**을 쓰는 순간, 애플리케이션이 당연하게 여기던 "커넥션은 세션 하나에 고정된다"는 가정이 깨진다는 것이다. 이 가정이 깨지면 prepared statement, 세션 레벨 설정(`SET`), advisory lock처럼 세션에 상태를 남기는 기능들이 예측 불가능하게 오작동한다. 이 글에서는 트랜잭션 풀링이 실제로 무엇을 바꾸는지, 애플리케이션 풀과 어떻게 상호작용하는지 정리한다.

## 핵심 개념 1: 세 가지 풀링 모드의 차이

| 모드 | 커넥션 반환 시점 | 세션 상태 유지 |
|---|---|---|
| Session pooling | 클라이언트가 연결을 끊을 때 | 완전히 유지됨(가장 안전, 효율 낮음) |
| Transaction pooling | 트랜잭션이 끝날 때(COMMIT/ROLLBACK) | 트랜잭션 안에서만 유지 |
| Statement pooling | 쿼리 하나가 끝날 때 | 유지 안 됨(가장 제약이 많음) |

Session pooling은 가장 안전하지만 다중화 효율이 낮다(클라이언트 연결 수만큼 실제 연결이 필요할 수 있음). Transaction pooling은 트랜잭션이 끝나는 즉시 그 물리 연결을 다른 클라이언트가 재사용할 수 있어 다중화 효율이 가장 높고, 실무에서 가장 많이 쓰인다. 문제는 "트랜잭션과 트랜잭션 사이"에 같은 물리 연결이 유지된다는 보장이 없다는 것이다.

## 핵심 개념 2: 트랜잭션 풀링이 깨뜨리는 것들

트랜잭션 풀링에서는 매 트랜잭션마다 다른 물리 연결에 배정될 수 있으므로, 세션 범위(연결 전체에 걸쳐 유지돼야 하는) 상태에 의존하는 기능이 깨진다.

- **Prepared statement**: JDBC 드라이버가 자동으로 만드는 서버 사이드 prepared statement는 그 statement를 준비한 물리 연결에만 존재한다. 트랜잭션이 끝나고 다음 트랜잭션이 다른 물리 연결을 받으면 "prepared statement가 존재하지 않는다"는 오류가 난다.
- **세션 레벨 `SET` 문**: `SET search_path`나 `SET statement_timeout`처럼 세션 전체에 적용하려던 설정이 다음 트랜잭션에서는 사라져 있을 수 있다.
- **Advisory lock**: `pg_advisory_lock`으로 세션 단위 락을 걸었는데, 트랜잭션이 끝나고 커넥션이 반환되면 그 락이 남아있는 물리 연결이 다른 요청에 재사용되면서 의도치 않은 락 유지·해제가 일어난다.
- **`LISTEN`/`NOTIFY`**: 세션이 구독을 유지해야 하는 이 기능은 트랜잭션 풀링 모드와 근본적으로 맞지 않는다.

## 예제: PgBouncer 설정과 JDBC 드라이버 대응

```ini
; pgbouncer.ini
[databases]
mydb = host=127.0.0.1 port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
; 트랜잭션 풀링과 충돌하는 서버 사이드 prepared statement 캐시 비활성화 유도
server_reset_query = DISCARD ALL
```

```java
// HikariCP + PgBouncer(transaction mode) 조합 시 JDBC URL 설정
// prepareThreshold=0 으로 서버 사이드 prepared statement 자체를 비활성화
String url = "jdbc:postgresql://pgbouncer-host:6432/mydb"
    + "?prepareThreshold=0"
    + "&preferQueryMode=simple"; // 확장 프로토콜 대신 단순 쿼리 프로토콜 사용
```

`server_reset_query = DISCARD ALL`은 커넥션이 반환될 때마다 세션 상태(임시 테이블, 설정, 준비된 문장 등)를 강제로 초기화해, 다음 클라이언트가 이전 클라이언트의 잔여 상태를 물려받지 않게 한다. 애플리케이션 쪽에서는 JDBC 드라이버가 서버 사이드 prepared statement를 자동 생성하지 않도록 `prepareThreshold=0`을 설정하는 것이 트랜잭션 풀링 모드에서 가장 흔한 대응이다.

## 실무 포인트

- **애플리케이션 풀 크기와 PgBouncer 풀 크기를 같이 설계한다**: HikariCP 풀이 인스턴스마다 20개씩 열려 있어도, PgBouncer의 `default_pool_size`가 25로 낮게 잡혀 있으면 결국 PgBouncer 앞단에서 대기가 생긴다. 두 계층의 풀 크기는 독립적으로 정하는 게 아니라, 실제 DB `max_connections`를 기준으로 역산해야 한다.
- **세션 상태에 의존하는 코드를 찾아 제거한다**: 마이그레이션 전에 코드베이스에서 `SET search_path`, advisory lock, temp table 사용처를 검색해 트랜잭션 풀링과 충돌할 부분을 미리 파악해야 한다. 이런 기능이 꼭 필요하다면 그 커넥션만 별도로 session pooling 모드의 다른 PgBouncer 인스턴스로 분리하는 것도 방법이다.
- **트랜잭션 밖에서 실행되는 쿼리를 주의한다**: 애플리케이션이 트랜잭션을 열지 않고 개별 쿼리(autocommit)를 여러 개 날리면, 트랜잭션 풀링 모드에서는 각 쿼리가 매번 다른 물리 연결에 배정될 수 있어 "직전 쿼리에서 설정한 세션 값"에 의존하는 로직이 원인 불명의 버그로 이어진다.

## 3줄 요약

- PgBouncer는 애플리케이션 연결 수를 적은 수의 실제 DB 연결로 다중화하지만, 가장 효율적인 트랜잭션 풀링 모드는 "연결이 세션에 고정된다"는 가정을 깨뜨린다.
- prepared statement, 세션 `SET`, advisory lock, LISTEN/NOTIFY는 세션 범위 상태에 의존하므로 트랜잭션 풀링과 충돌하기 쉽다.
- JDBC 드라이버의 prepareThreshold 비활성화와 PgBouncer의 DISCARD ALL 설정으로 상태 잔존 문제를 방어하고, 세션 의존 로직은 사전에 코드베이스에서 찾아 제거해야 한다.

## 참고 자료

- [PgBouncer 공식 문서: pool_mode](https://www.pgbouncer.org/config.html#pool_mode)
- [PgBouncer 공식 FAQ: Transaction pooling caveats](https://www.pgbouncer.org/faq.html)
- [PostgreSQL JDBC 공식 문서: Server Prepared Statements](https://jdbc.postgresql.org/documentation/query/)
