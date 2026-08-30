---
layout: single
title: "R2DBC 내부 동작 — JDBC를 리액티브로 감싸는 게 안 되는 이유"
date: 2026-09-27 12:25:00 +0530
categories: backend
tags: ["R2DBC", "Spring WebFlux", "리액티브프로그래밍", "논블로킹IO", "JDBC"]
toc: true
toc_sticky: true
excerpt: "Spring WebFlux로 전체 스택을 논블로킹으로 구성했는데 DB 호출 지점에서 스레드가 블로킹되는 문제를 겪어본 적 있다면, JDBC 자체가 리액티브와 근본적으로 양립할 수 없는 이유와 R2DBC가 이를 다른 프로토콜 계층에서 해결하는 방식을 알아야 한다."
---

## 왜 JDBC를 그냥 감싸면 안 되는가

Spring WebFlux로 애플리케이션을 논블로킹으로 구성했다면, 이상적으로는 요청을 처리하는 소수의 이벤트 루프 스레드가 절대 블로킹되지 않아야 한다. 그런데 데이터베이스 접근에 JDBC를 그대로 쓰면 이 원칙이 첫 관문에서 무너진다. JDBC의 `Connection`, `Statement`, `ResultSet` API는 애초에 **동기 블로킹 호출**을 전제로 설계됐다. `resultSet.next()`를 호출하면 그 스레드는 DB가 다음 행을 보내줄 때까지 물리적으로 멈춰 있어야 한다. 이걸 `Mono.fromCallable(() -> jdbcCall())`로 감싸 별도 스레드 풀에서 실행하는 것도 가능은 하지만, 그 순간 리액티브 스택의 핵심 이점인 "적은 스레드로 많은 동시 연결 처리"가 사라진다. 결국 블로킹 I/O를 논블로킹으로 만드는 방법은 스레드를 숨기는 게 아니라, 애초에 블로킹이 발생하지 않는 프로토콜 계층에서 다시 구현하는 것뿐이다. R2DBC(Reactive Relational Database Connectivity)가 그 답이다.

## 핵심 개념 1 — SPI 자체가 리액티브 스트림 기반이다

R2DBC는 JDBC 위에 리액티브 어댑터를 씌운 것이 아니라, 데이터베이스와 통신하는 SPI(Service Provider Interface) 자체를 Reactive Streams `Publisher`(`Mono`/`Flux`)로 정의했다. 쿼리를 실행하면 즉시 결과가 아니라 구독(subscribe)해야 데이터가 흐르기 시작하는 `Result` 객체가 반환된다. 드라이버 구현체(PostgreSQL용 `r2dbc-postgresql` 등)는 DB와의 통신을 처음부터 Netty 같은 논블로킹 네트워크 라이브러리 위에 직접 구현한다. 즉 소켓 레벨에서부터 이벤트 기반으로 동작하며, 데이터를 기다리는 동안 스레드를 점유하지 않고 이벤트 루프에 제어권을 돌려준다.

## 핵심 개념 2 — 커넥션 풀과 트랜잭션도 리액티브하게

전통적인 커넥션 풀(HikariCP 등)은 블로킹 `getConnection()` 호출로 풀에서 커넥션을 빌려오는 구조라 그대로 쓸 수 없다. R2DBC 생태계는 `r2dbc-pool`이라는 자체 풀 구현을 제공하며, 커넥션 획득 자체도 `Mono<Connection>`으로 표현된다. 트랜잭션 경계 역시 `TransactionalOperator`나 Spring의 `@Transactional`이 리액티브 컨텍스트(`Context`)를 통해 전파되는데, 이는 스레드 로컬을 쓰는 JDBC 트랜잭션 전파와 근본적으로 다른 메커니즘이다. 리액티브 체인은 여러 스레드를 오갈 수 있으므로, 트랜잭션 상태를 스레드가 아니라 구독 컨텍스트에 묶어야 하기 때문이다.

| 항목 | JDBC | R2DBC |
|---|---|---|
| API 모델 | 동기 블로킹 호출 | Reactive Streams(Publisher) |
| 네트워크 I/O | 블로킹 소켓 | 논블로킹(Netty 기반) |
| 커넥션 풀 | HikariCP 등(블로킹 획득) | r2dbc-pool(리액티브 획득) |
| 트랜잭션 전파 | ThreadLocal | Reactive Context |
| 생태계 성숙도 | 매우 높음(전 벤더 지원) | 제한적(주요 RDB 위주) |

## 코드 예제 — Spring Data R2DBC 리포지토리

```java
public interface OrderRepository extends ReactiveCrudRepository<Order, Long> {

    // 블로킹 호출 없이 Flux로 스트리밍 조회
    Flux<Order> findByStatus(String status);
}

@Service
public class OrderService {

    private final OrderRepository repository;
    private final TransactionalOperator txOperator;

    public Mono<Order> createOrder(Order order) {
        return repository.save(order)
                .flatMap(saved -> updateInventory(saved))
                .as(txOperator::transactional);  // 리액티브 트랜잭션 경계
    }
}
```

## 실무 포인트

- **JPA/Hibernate와의 조합은 아직 성숙하지 않다.** Hibernate Reactive 같은 프로젝트가 있지만 JDBC 기반 JPA만큼 기능이 완비되지 않았다. 복잡한 연관관계 매핑이 많은 도메인이라면 R2DBC + Spring Data R2DBC의 단순한 매핑 모델이 오히려 한계로 작용할 수 있다.
- **드라이버 지원 범위를 먼저 확인하라.** PostgreSQL, MySQL, MariaDB, SQL Server, H2는 공식/커뮤니티 드라이버가 있지만 오래된 상용 DB나 특수 벤더는 R2DBC 드라이버 자체가 없을 수 있다.
- **블로킹 라이브러리를 실수로 섞지 마라.** R2DBC로 전환해도 같은 요청 처리 경로에서 블로킹 HTTP 클라이언트나 JDBC 기반 캐시 라이브러리를 호출하면 이벤트 루프 스레드가 그 지점에서 멈춘다. 스택 전체가 논블로킹이어야 이점이 살아난다.

## 마무리 요약

- JDBC는 API 자체가 블로킹을 전제하므로, 별도 스레드 풀로 감싸도 리액티브 스택의 스레드 효율 이점을 살릴 수 없다.
- R2DBC는 SPI 자체를 Reactive Streams로 정의하고 소켓 레벨부터 논블로킹으로 구현해, 이 문제를 프로토콜 계층에서 근본적으로 해결한다.
- 커넥션 풀과 트랜잭션 전파도 리액티브 컨텍스트 기반으로 재설계됐지만, JPA 대비 생태계 성숙도가 낮으므로 도메인 복잡도를 감안해 도입을 판단해야 한다.

## 참고 자료

- [R2DBC 공식 사이트](https://r2dbc.io/)
- [Spring Data R2DBC 공식 문서](https://docs.spring.io/spring-data/r2dbc/reference/)
- [Reactive Streams 스펙](https://www.reactive-streams.org/)
