---
layout: single
title: "Testcontainers로 진짜 통합 테스트 만들기 — Spring Boot 실전 가이드"
date: 2026-08-18 13:25:00 +0530
categories: backend
tags: ["testcontainers", "spring-boot", "integration-test", "junit5", "docker"]
toc: true
toc_sticky: true
excerpt: "H2 인메모리 DB나 Mock으로는 잡히지 않는 실운영 버그를 막기 위해, 실제 DB·메시지 브로커를 Docker 컨테이너로 띄워 검증하는 Testcontainers 활용법을 Spring Boot 예제로 정리한다."
---

## 왜 지금 Testcontainers인가

"로컬에서는 테스트가 다 통과했는데 운영에서 터졌다"는 문제의 상당수는 테스트 환경과 운영 환경이 다른 데이터베이스를 쓰기 때문에 생긴다. JPA 통합 테스트에서 흔히 쓰는 H2 인메모리 DB는 PostgreSQL의 `JSONB` 타입, 특정 락 동작, 네이티브 쿼리 문법을 완벽히 흉내 내지 못한다. 그 결과 "테스트는 통과하지만 실제 DB에서는 실패하는" 코드가 조용히 배포되곤 한다.

Testcontainers는 이 간극을 없앤다. JUnit 테스트 실행 시점에 Docker로 실제 PostgreSQL, Kafka, Redis 컨테이너를 띄우고, 테스트가 끝나면 자동으로 정리한다. Mock이나 대체 DB가 아니라 운영과 동일한 엔진으로 검증하기 때문에 "진짜 통합 테스트"라 부를 수 있다. Spring Boot 3.1부터는 `@ServiceConnection` 애노테이션이 도입되어 컨테이너의 접속 정보(URL, 계정 등)를 Spring 설정에 수동 연결할 필요 없이 자동으로 주입해주면서, 이전보다 도입 장벽이 크게 낮아졌다. 최근에는 Docker가 Testcontainers 프로젝트를 직접 지원하며 `spring-boot-devtools`와 연동해 코드 리로드 사이에도 컨테이너를 유지하는 실험적 기능까지 나오는 등, 로컬 개발 루프 자체를 빠르게 만드는 방향으로도 계속 발전하고 있다.

<img src="/assets/images/posts/2026-08-18-testcontainers-integration-test-1.svg" alt="Testcontainers 아키텍처 - JUnit 테스트에서 Docker 데몬을 통해 PostgreSQL·Kafka·Redis 컨테이너를 기동하고 Ryuk이 정리하는 흐름" style="width:100%;">

## 핵심 개념 1: 컨테이너 기반 테스트가 해결하는 문제

| 방식 | 실제 엔진과의 동일성 | 실행 속도 | 대표 한계 |
|---|---|---|---|
| H2/인메모리 DB | 낮음(방언·함수 차이) | 매우 빠름 | JSONB, 시퀀스, 락 동작 등 미세 차이로 거짓 양성 발생 |
| Mock/Stub 리포지토리 | 없음(로직만 검증) | 매우 빠름 | 쿼리 자체의 정합성은 검증 불가 |
| 공유 개발 DB | 높음 | 빠름 | 테스트 간 데이터 오염, 병렬 실행 불가 |
| Testcontainers | 매우 높음(실제 엔진) | 느림(컨테이너 기동 비용) | Docker 데몬 필요, CI 환경 구성 필요 |

Testcontainers는 속도를 다소 희생하는 대신 신뢰도를 확보하는 선택이다. 모든 테스트를 컨테이너로 돌릴 필요는 없고, 단위 테스트는 Mock으로 빠르게, 쿼리·트랜잭션 경계를 검증해야 하는 통합 테스트만 Testcontainers로 돌리는 것이 실무에서 흔한 조합이다.

## 핵심 개념 2: JUnit 5 생명주기와 싱글턴 컨테이너 패턴

`@Testcontainers` 확장과 `@Container` 애노테이션을 쓰면 테스트 클래스마다 컨테이너를 새로 만들 수 있지만, 이 경우 테스트 클래스가 늘어날수록 전체 실행 시간이 크게 늘어난다. 실무에서는 컨테이너를 `static` 필드로 선언해 테스트 클래스 전체(혹은 여러 클래스가 상속하는 베이스 클래스) 안에서 하나의 컨테이너를 재사용하는 **싱글턴 컨테이너 패턴**을 주로 쓴다. 컨테이너가 죽지 않고 떠 있어도, 종료 시 정리를 담당하는 Ryuk 사이드카 컨테이너가 테스트 JVM 종료를 감지해 정리하므로 리소스가 새지 않는다.

## 예제: PostgreSQL 컨테이너로 Repository 통합 테스트 (Java/JUnit 5)

```java
@SpringBootTest
@Testcontainers
class OrderRepositoryIntegrationTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres =
            new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private OrderRepository orderRepository;

    @Test
    void 상태별_주문_조회는_실제_인덱스_조건을_그대로_탄다() {
        // given
        orderRepository.save(new Order("ORD-1001", OrderStatus.PAID));
        orderRepository.save(new Order("ORD-1002", OrderStatus.PENDING));

        // when
        List<Order> paidOrders = orderRepository.findByStatus(OrderStatus.PAID);

        // then
        assertThat(paidOrders).hasSize(1);
        assertThat(paidOrders.get(0).getOrderNumber()).isEqualTo("ORD-1001");
    }
}
```

`@ServiceConnection`을 붙이면 Spring Boot가 컨테이너 타입(여기서는 PostgreSQL)을 인식해 `spring.datasource.url`, 계정 정보를 자동으로 테스트 컨텍스트에 주입한다. `@DynamicPropertySource`로 URL을 일일이 꺼내 등록하던 이전 방식보다 코드가 짧아지고, 컨테이너 종류를 바꿔도 설정 코드를 거의 손댈 필요가 없다.

여러 테스트 클래스에서 컨테이너를 공유하려면 아래처럼 베이스 클래스로 뽑아 상속하는 방식이 흔히 쓰인다.

```java
@Testcontainers
abstract class AbstractIntegrationTest {

    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine")
                    .withReuse(true); // ~/.testcontainers.properties 에 reuse.enable=true 필요

    static {
        POSTGRES.start();
    }

    @DynamicPropertySource
    static void registerProps(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }
}
```

`withReuse(true)`와 로컬 설정 파일의 reuse 옵션을 함께 켜면, 로컬 개발 중 반복 실행하는 테스트에서 컨테이너를 매번 새로 기동하지 않고 재사용해 실행 시간을 줄일 수 있다. 단, CI 환경에서는 잡 종료 시 컨테이너도 함께 정리되는 것이 보통이라 reuse 효과가 로컬만큼 크지 않다는 점은 감안해야 한다.

## 실무 포인트

- **CI 러너에 Docker-in-Docker(또는 소켓 마운트) 구성이 필요하다.** GitHub Actions 기본 러너는 Docker 데몬을 이미 포함하지만, 사내 자체 호스팅 러너나 컨테이너 기반 CI에서는 Docker 소켓 접근 권한을 별도로 확인해야 한다.
- **이미지 태그를 고정한다.** `postgres:latest`처럼 태그를 고정하지 않으면 어느 날 갑자기 메이저 버전이 올라가면서 테스트가 이유 없이 깨질 수 있다. 운영 DB와 같은 메이저 버전으로 명시적으로 고정하는 것이 안전하다.
- **모든 테스트를 컨테이너화하지 않는다.** 순수 도메인 로직이나 서비스 계층 단위 테스트까지 컨테이너로 돌리면 빌드 시간이 급격히 늘어난다. Repository·쿼리 검증처럼 실제 DB 동작이 필요한 지점에만 선택적으로 적용한다.
- **병렬 실행 시 포트 충돌에 주의한다.** Testcontainers는 기본적으로 호스트 포트를 임의로 매핑해 이 문제를 자동 회피하지만, 고정 포트를 강제로 지정하는 설정을 쓰면 병렬 테스트 간 충돌이 재발할 수 있다.

## 3줄 요약

- Testcontainers는 H2·Mock으로는 잡히지 않는 "실제 DB에서만 드러나는 버그"를 잡기 위해 진짜 DB 엔진을 Docker 컨테이너로 띄워 테스트한다.
- Spring Boot의 `@ServiceConnection`을 쓰면 접속 정보 수동 연결 없이 컨테이너를 Spring 컨텍스트에 바로 연결할 수 있고, 싱글턴 컨테이너 패턴으로 여러 테스트 클래스가 하나의 컨테이너를 재사용해 실행 시간을 줄일 수 있다.
- 모든 테스트를 컨테이너화할 필요는 없으며, 이미지 태그 고정과 CI의 Docker 접근 권한 확인을 함께 챙겨야 안정적으로 도입할 수 있다.

## 참고 자료

- [Testcontainers 공식 문서](https://testcontainers.com/)
- [Spring Boot Reference — Testcontainers](https://docs.spring.io/spring-boot/reference/testing/testcontainers.html)
- [Baeldung — Built-in Testcontainers Support in Spring Boot](https://www.baeldung.com/spring-boot-built-in-testcontainers)
