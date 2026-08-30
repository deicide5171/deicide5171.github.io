---
layout: single
title: "대량 데이터 벌크 INSERT가 느릴 때 — 흔한 실수와 튜닝 방법"
date: 2026-09-21 13:35:00 +0530
categories: database
tags: ["벌크인서트", "배치insert", "성능튜닝", "jdbc", "데이터마이그레이션"]
toc: true
toc_sticky: true
excerpt: "수십만 건의 데이터를 한 번에 넣어야 할 때 반복문으로 INSERT를 하나씩 실행하면 왜 느린지, 배치 처리와 DB 설정으로 실제 속도를 끌어올리는 방법을 정리했다."
---

## 왜 지금 이 문제를 짚어야 하나

초기 데이터 이관, 외부 시스템 동기화, 로그 적재처럼 수십만~수백만 건의 데이터를 한 번에 DB에 넣어야 하는 작업은 언젠가 반드시 마주친다. 처음 짜는 코드는 대개 이런 모습이다.

```java
for (Order order : orders) {
    jdbcTemplate.update("INSERT INTO orders (id, amount) VALUES (?, ?)",
        order.getId(), order.getAmount());
}
```

10건, 100건일 때는 문제없이 돌아간다. 그런데 데이터가 50만 건으로 늘어나면 이 코드는 몇 시간이 걸리기도 한다. 원인은 각 INSERT문마다 별도의 네트워크 왕복(round trip)이 발생하기 때문이다. 쿼리 자체는 수 밀리초면 끝나도, 애플리케이션과 DB 사이를 50만 번 왕복하는 네트워크 지연이 누적되면 전체 시간이 기하급수적으로 늘어난다.

## 잘못된 접근과 그 결과

가장 흔한 실수는 "느리니까 그냥 커넥션 풀 크기를 늘리자"는 식으로 근본 원인과 무관한 파라미터를 건드리는 것이다. 커넥션 풀은 동시 요청을 처리하기 위한 것이지, 순차적으로 실행되는 반복문 자체를 빠르게 만들어주지 않는다. 또 다른 실수는 각 INSERT를 개별 트랜잭션으로 커밋하는 것이다. 매 건마다 커밋하면 DB가 매번 디스크에 로그를 플러시(fsync)해야 해서, 트랜잭션 오버헤드가 네트워크 왕복 지연 위에 추가로 쌓인다.

## 올바른 접근: 배치와 트랜잭션 묶기

**1) JDBC 배치(batch)로 여러 INSERT를 한 번에 전송한다.**

```java
jdbcTemplate.batchUpdate(
    "INSERT INTO orders (id, amount) VALUES (?, ?)",
    orders,
    500,  // 배치 크기
    (ps, order) -> {
        ps.setLong(1, order.getId());
        ps.setBigDecimal(2, order.getAmount());
    }
);
```

이렇게 하면 500건씩 묶어 한 번의 네트워크 왕복으로 전송한다. 다만 JDBC 드라이버 설정에서 배치를 실제로 서버에 묶어 보내도록 옵션을 켜야 하는 경우가 있다. 예를 들어 MySQL은 URL에 `rewriteBatchedStatements=true`를 명시하지 않으면 `batchUpdate`를 써도 내부적으로 INSERT문을 하나씩 보내는 경우가 있어, 실제로 배치가 적용됐는지 반드시 확인해야 한다.

**2) 트랜잭션 범위를 적절히 묶는다.** 전체 50만 건을 하나의 트랜잭션으로 묶으면 롤백 세그먼트가 비대해지고 실패 시 전부 되돌리는 비용이 커진다. 보통 수천~수만 건 단위로 커밋 지점을 나누는 것이 안전하다.

**3) 대량 이관이라면 DB 전용 벌크 로드 도구를 검토한다.** PostgreSQL의 `COPY` 명령, MySQL의 `LOAD DATA INFILE`은 일반 INSERT문 파싱·플래닝 과정을 건너뛰고 데이터를 직접 적재하도록 최적화되어 있어, JDBC 배치보다도 훨씬 빠르다.

```sql
-- PostgreSQL 예시
COPY orders (id, amount) FROM '/path/to/orders.csv' WITH (FORMAT csv);
```

## 인덱스와 제약조건도 병목이다

인덱스가 많은 테이블에 대량 INSERT를 하면, 행이 삽입될 때마다 모든 인덱스가 함께 갱신되므로 인덱스 개수에 비례해 느려진다. 대규모 초기 적재 작업이라면 인덱스를 일시적으로 제거하고 데이터를 넣은 뒤 다시 생성하는 것이 전체적으로 더 빠를 수 있다. 다만 이 방식은 적재 도중 다른 쿼리가 그 인덱스에 의존한다면 서비스에 영향을 주므로, 운영 중인 테이블이 아니라 초기 이관이나 배치 작업에 한정해서 쓰는 것이 안전하다.

## 실무 포인트

- **오토커밋을 반드시 끄고 명시적 트랜잭션으로 묶어라.** 오토커밋 상태로 배치를 실행하면 JDBC 드라이버가 내부적으로 각 문장을 별도 트랜잭션처럼 처리해 배치 효과가 사라지는 경우가 있다.
- **외래키·유니크 제약 검증 비용도 고려하라.** 참조 무결성 검사가 걸린 테이블은 매 행마다 참조 대상 존재 여부를 확인하므로, 대량 적재 시점만 제약을 지연 검증(deferred constraint)으로 바꾸는 방법도 있다(PostgreSQL 지원).
- **적재 후 통계 정보를 갱신하라.** 대량 INSERT 직후 옵티마이저 통계(`ANALYZE`)가 갱신되지 않으면, 이후 쿼리 실행 계획이 예전 행 수 기준으로 잘못 세워질 수 있다.
- **배치 크기를 무작정 키우지 마라.** 배치 크기가 너무 크면 한 번에 전송하는 패킷 크기가 DB의 최대 패킷 크기 설정(`max_allowed_packet` 등)을 초과해 오류가 날 수 있다. 수백~수천 건 단위로 시작해 실측하며 조정한다.

## 마무리 요약

- 반복문으로 INSERT를 하나씩 실행하면 네트워크 왕복과 트랜잭션 오버헤드가 누적되어 대량 데이터에서 급격히 느려진다.
- JDBC 배치와 적절한 트랜잭션 커밋 단위로 묶는 것이 기본 해법이며, 초대량 이관은 `COPY`, `LOAD DATA INFILE` 같은 DB 전용 도구가 더 빠르다.
- 인덱스·제약조건 검증 비용, 배치 크기 상한, 적재 후 통계 갱신까지 함께 고려해야 실제 운영에서 안정적인 성능을 낼 수 있다.

## 참고 자료

- [PostgreSQL 공식 문서 - Populating a Database](https://www.postgresql.org/docs/current/populate.html)
- [MySQL 공식 문서 - Optimizing INSERT Statements](https://dev.mysql.com/doc/refman/8.4/en/insert-optimization.html)
