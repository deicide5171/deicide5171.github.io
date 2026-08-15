---
layout: single
title: "벌크헤드 패턴 — 한 서비스 장애가 전체를 침몰시키지 않는 격리 설계"
date: 2026-08-19 13:45:00 +0530
categories: system-design
tags: ["bulkhead", "resilience4j", "microservices", "fault-isolation", "thread-pool"]
toc: true
toc_sticky: true
excerpt: "의존성 하나가 느려질 때 서비스 전체가 멈추지 않도록, 스레드풀·커넥션풀을 격벽처럼 나누는 벌크헤드 패턴의 개념과 구현을 정리한다."
---

## 왜 지금 벌크헤드(Bulkhead)인가

MSA 환경에서 서비스 하나는 보통 여러 다운스트림 의존성(다른 API, DB, 외부 서비스)을 호출한다. 문제는 이 호출들이 종종 **같은 스레드풀, 같은 커넥션풀을 공유**한다는 데 있다. 의존성 중 하나가 느려지면 그 요청을 처리하던 스레드와 커넥션이 반환되지 못하고 계속 쌓이고, 결국 풀 전체가 고갈되어 그 의존성과 아무 상관없는 요청까지 처리하지 못하는 상황이 벌어진다. 장애가 서비스 하나에서 시작해 시스템 전체로 번지는 전형적인 경로다.

**벌크헤드**는 배의 격벽(隔壁)에서 이름을 따온 패턴이다. 배 밑바닥에 구멍이 나도 격벽으로 나뉜 구획 하나만 침수되고 배는 가라앉지 않는다. 소프트웨어에서도 마찬가지로, 의존성별로 스레드풀·커넥션풀 같은 리소스를 물리적으로 분리해두면 한 의존성의 장애가 그 구획 안에서만 소진되고 다른 요청 처리 능력은 그대로 남는다. 서킷 브레이커가 "장애가 난 대상으로의 호출을 끊는" 역할이라면, 벌크헤드는 그 이전 단계에서 "애초에 장애의 영향 범위를 물리적으로 제한"하는 역할을 한다. 둘은 경쟁 관계가 아니라 함께 쌓아야 하는 방어선이다.

## 핵심 개념 1: 격리 전략 — 스레드풀 격리 vs 세마포어 격리

벌크헤드를 구현하는 방식은 크게 두 가지다. Resilience4j 기준으로 정리하면 다음과 같다.

| 구분 | 스레드풀 격리(ThreadPoolBulkhead) | 세마포어 격리(SemaphoreBulkhead) |
|---|---|---|
| 동작 방식 | 의존성 호출마다 별도 스레드풀에서 실행, 별도 큐로 대기 | 호출 스레드(보통 요청 스레드) 그대로 사용, 동시 실행 수만 카운터로 제한 |
| 타임아웃 | 호출 스레드와 분리되어 있어 타임아웃 시 즉시 반환 가능 | 실행 중인 호출을 강제로 끊기 어려움 |
| 오버헤드 | 스레드 전환·컨텍스트 스위칭 비용 발생 | 상대적으로 가볍다 |
| 적합한 상황 | 응답 지연이 길거나 예측 어려운 외부 호출 | 내부 호출, 지연 시간이 짧고 예측 가능한 경우 |

정답은 없고, 신뢰하기 어려운 외부 의존성일수록 스레드풀 격리 쪽으로, 통제 가능한 내부 서비스일수록 세마포어 격리로 기우는 경향이 일반적이다.

## 핵심 개념 2: 어느 레벨에서 격리할 것인가

"격리"라는 말은 여러 층위에 적용할 수 있다. 실제로는 아래 표의 레벨들을 함께 조합해서 쓰는 경우가 많다.

| 레벨 | 예시 | 장점 | 한계 |
|---|---|---|---|
| 스레드풀 | 의존성 X 전용 스레드풀, Y 전용 스레드풀 | 애플리케이션 코드 레벨에서 세밀하게 제어 | 풀 개수가 늘면 관리·튜닝 부담 증가 |
| 커넥션풀 | HikariCP를 데이터소스별·용도별로 분리 | DB 커넥션 고갈이 다른 쿼리 경로로 전파되지 않음 | 커넥션 총량 관리가 더 복잡해짐 |
| 프로세스/컨테이너 | 배치 작업과 API 서버를 별도 인스턴스로 분리 | OS 레벨 리소스(CPU, 메모리)까지 격리 | 배포·운영 단위가 늘어남 |
| 서비스(MSA 경계) | 조회 전용 서비스와 쓰기 서비스를 별도 배포 | 장애 반경이 서비스 단위로 원천 차단 | 설계·조직 차원의 투자 필요 |

작게는 스레드풀 하나를 나누는 것부터 시작해서, 조직이 감당할 수 있는 만큼 상위 레벨로 확장하는 것이 현실적인 접근이다.

## 예제 1: Resilience4j로 스레드풀 벌크헤드 적용하기 (Java/Spring Boot)

```java
@Configuration
public class BulkheadConfig {

    @Bean
    public ThreadPoolBulkheadRegistry threadPoolBulkheadRegistry() {
        ThreadPoolBulkheadConfig configForServiceY = ThreadPoolBulkheadConfig.custom()
                .maxThreadPoolSize(10)
                .coreThreadPoolSize(5)
                .queueCapacity(20)
                .build();

        return ThreadPoolBulkheadRegistry.of(Map.of("serviceY", configForServiceY));
    }
}

@Service
public class ServiceYClient {

    private final ThreadPoolBulkhead bulkhead;
    private final RestClient restClient;

    public ServiceYClient(ThreadPoolBulkheadRegistry registry, RestClient restClient) {
        this.bulkhead = registry.bulkhead("serviceY");
        this.restClient = restClient;
    }

    public CompletableFuture<Response> call(Request request) {
        return bulkhead.executeSupplier(() -> restClient.post(request));
    }
}
```

핵심은 `serviceY` 전용 스레드풀을 별도로 정의해 그 의존성 호출만 이 풀에서 실행되게 하는 것이다. 다른 의존성 호출은 각자의 풀에서 실행되므로 `serviceY`가 응답을 지연시켜도 대기·거부는 이 풀 안에서만 발생한다.

## 예제 2: 커넥션풀도 의존성별로 나누기

```yaml
# application.yml
spring:
  datasource:
    order-db:
      hikari:
        pool-name: order-db-pool
        maximum-pool-size: 15
        connection-timeout: 3000
    reporting-db:
      hikari:
        pool-name: reporting-db-pool
        maximum-pool-size: 5
        connection-timeout: 3000
```

`order-db`(주문 처리)와 `reporting-db`(무거운 집계 쿼리)를 같은 풀로 묶으면 리포트 쿼리가 오래 걸릴 때 주문 처리까지 커넥션을 못 받을 수 있다. 풀을 분리하면 리포트 쪽이 전부 소진돼도 주문 처리 풀은 영향받지 않는다.

## 실무 포인트

- **풀 크기는 추정치에서 시작해 부하 테스트로 조정한다.** 코드 예제의 수치는 설명을 위한 예시일 뿐이며, 실제 값은 트래픽 패턴과 다운스트림 응답 시간 분포를 보면서 맞춰야 한다.
- **풀 사용률·큐 대기 시간·거부(rejected) 횟수를 모니터링 지표로 반드시 노출한다.** 벌크헤드가 조용히 요청을 거부하기 시작해도 관측되지 않으면 장애 원인 파악이 늦어진다.
- **가장 흔한 안티패턴은 "편의상 풀을 공유"하는 것이다.** 새 의존성을 추가할 때 기존 공용 풀에 얹는 쪽이 항상 더 쉬워 보이지만, 그 순간부터 격리 효과가 사라진다는 점을 팀 차원에서 인식하고 있어야 한다.
- **타임아웃 → 벌크헤드 → 서킷 브레이커 → 재시도** 순서로 계층을 쌓는 것이 일반적인 조합 전략이다. 벌크헤드로 장애 반경을 제한하고, 서킷 브레이커로 이미 죽은 의존성에 대한 무의미한 호출 자체를 끊고, 재시도는 이 두 방어선 뒤에서 짧고 제한적으로만 수행한다.

## 3줄 요약

- 벌크헤드 패턴은 의존성별로 스레드풀·커넥션풀 같은 리소스를 물리적으로 분리해, 한 곳의 장애가 다른 요청 처리 능력까지 갉아먹지 않게 만드는 격리 전략이다.
- 구현은 스레드풀 격리와 세마포어 격리 두 방식이 있으며, 신뢰도가 낮은 외부 호출일수록 스레드풀 격리가 유리하다.
- 타임아웃·벌크헤드·서킷 브레이커·재시도를 계층적으로 조합해야 연쇄 장애를 실질적으로 예방할 수 있다.

<img src="/assets/images/posts/2026-08-19-bulkhead-isolation-pattern-1.svg" alt="벌크헤드 패턴 - 의존성별 스레드풀·커넥션풀 격리 구조도" style="width:100%;">

## 참고 자료

- [Resilience4j — Bulkhead](https://resilience4j.readme.io/docs/bulkhead)
- [Microsoft Azure Architecture Center — Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
- [HikariCP — About Pool Sizing](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
