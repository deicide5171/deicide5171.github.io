---
layout: single
title: "Spring Boot API 레이트 리밋 실전 구현 — Bucket4j로 토큰 버킷 붙이기"
date: 2026-08-19 12:25:00 +0530
categories: backend
tags: ["bucket4j", "spring-boot", "rate-limiting", "java", "redis"]
toc: true
toc_sticky: true
excerpt: "레이트 리밋 알고리즘 이론을 넘어, Bucket4j 라이브러리로 Spring Boot 애플리케이션에 실제로 요청 제한 로직을 붙이는 필터·설정·분산 환경 구현 코드를 정리한다."
---

## 왜 지금 이 이야기인가

레이트 리밋의 알고리즘 선택(토큰 버킷 vs 슬라이딩 윈도우)이나 Redis Lua 스크립트로 카운터를 직접 짜는 방법은 이미 여러 곳에서 다뤄졌다. 하지만 실제로 Spring Boot 프로젝트에 "지금 당장 붙일 수 있는 코드"를 찾으면 의외로 정리된 자료가 많지 않다. 매번 카운터 로직을 손으로 짜는 대신, JVM 생태계에서 가장 널리 쓰이는 레이트 리밋 라이브러리인 **Bucket4j**를 Spring Boot 필터에 연결하는 실전 패턴을 정리한다.

Bucket4j는 순수 토큰 버킷 알고리즘 구현체이면서, 단일 인스턴스의 로컬 메모리 버킷과 Redis·Hazelcast·Caffeine 등을 백엔드로 쓰는 분산 버킷을 같은 API(`Bucket`, `ConsumptionProbe`)로 다룰 수 있게 해준다. 즉 로컬 개발 단계에서는 인메모리로 붙였다가, 인스턴스를 여러 대로 늘릴 때 백엔드 구현체만 바꾸면 되는 구조라 마이그레이션 부담이 적다.

## 핵심 개념 1: Bucket4j가 해결하는 문제

Bucket4j의 핵심은 "버킷(bucket)에 담긴 토큰을 요청마다 하나씩 소비하고, 정해진 속도로 토큰을 다시 채운다"는 토큰 버킷 알고리즘을 스레드 안전하게, 그리고 로컬/분산 환경 모두에서 동일한 API로 제공하는 것이다.

| 구성 요소 | 역할 |
|---|---|
| `Bandwidth` | 용량(capacity)과 리필 속도(refill rate)를 정의하는 정책 |
| `BucketConfiguration` | 하나 이상의 Bandwidth를 묶은 버킷 설정 |
| `Bucket` | 실제로 토큰을 소비(`tryConsume`)하는 인스턴스 |
| `ProxyManager` | 버킷 상태를 로컬 메모리 또는 외부 저장소(Redis 등)에 위임하는 계층 |
| `ConsumptionProbe` | 소비 성공 여부 + 남은 토큰 수 + 다음 리필까지 대기 시간(nanos)을 담은 결과 객체 |

## 핵심 개념 2: 어디에 붙일 것인가 — Filter vs Interceptor vs AOP

Spring Boot에서 레이트 리밋 로직을 끼워 넣을 수 있는 지점은 여러 곳이 있고, 각각 트레이드오프가 다르다.

| 위치 | 장점 | 단점 |
|---|---|---|
| Servlet Filter(`OncePerRequestFilter`) | DispatcherServlet 이전에 차단해 컨트롤러 진입 자체를 막음, 정적 리소스 포함 전역 제어 용이 | 컨트롤러 메타데이터(어노테이션 등)에 접근하려면 별도 매핑 필요 |
| HandlerInterceptor | `@RateLimit` 같은 커스텀 어노테이션과 자연스럽게 결합 가능 | 필터보다 늦게 실행되어 정적 리소스 등은 별도 처리 필요 |
| AOP(`@Around`) | 메서드 단위로 세밀하게 정책 분기 가능 | 웹 계층이 아닌 곳까지 걸리므로 범위 관리가 필요 |

전역적으로 모든 API에 기본 한도를 걸고 싶다면 Filter가 가장 단순하고, 엔드포인트별로 서로 다른 정책(예: 쓰기 API는 더 엄격하게)을 어노테이션으로 표현하고 싶다면 Interceptor나 AOP 조합이 유리하다.

## 예제 1: 기본 설정과 필터 구현

```java
// build.gradle(.kts) 의존성
// implementation("com.bucket4j:bucket4j_jdk17-core:8.10.1")

@Component
public class RateLimitFilter extends OncePerRequestFilter {

    // 클라이언트별(API Key 또는 IP) 버킷을 보관하는 로컬 캐시
    // 단일 인스턴스 기준 예제 — 분산 환경은 아래 ProxyManager 참고
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {

        String clientKey = resolveClientKey(request); // API Key 헤더 우선, 없으면 IP
        Bucket bucket = buckets.computeIfAbsent(clientKey, key -> newBucket());

        ConsumptionProbe probe = bucket.tryConsumeAndReturnRemaining(1);

        if (probe.isConsumed()) {
            response.addHeader("X-RateLimit-Remaining", String.valueOf(probe.getRemainingTokens()));
            chain.doFilter(request, response);
        } else {
            long waitSeconds = probe.getNanosToWaitForRefill() / 1_000_000_000L;
            response.setStatus(429); // Too Many Requests
            response.addHeader("Retry-After", String.valueOf(waitSeconds));
            response.getWriter().write("{\"error\":\"rate_limit_exceeded\"}");
        }
    }

    private Bucket newBucket() {
        // 분당 60개, 최대 버스트 10개 허용 정책 예시(값은 서비스 특성에 맞춰 조정)
        Bandwidth limit = Bandwidth.classic(60,
            Refill.greedy(60, Duration.ofMinutes(1)));
        return Bucket.builder().addLimit(limit).build();
    }

    private String resolveClientKey(HttpServletRequest request) {
        String apiKey = request.getHeader("X-API-Key");
        return apiKey != null ? apiKey : request.getRemoteAddr();
    }
}
```

## 예제 2: 분산 환경 — Redis 기반 ProxyManager

인스턴스가 여러 대면 위 코드의 `ConcurrentHashMap`은 인스턴스마다 별도로 카운트하므로 실제 허용량을 훌쩍 넘긴다. Bucket4j는 `bucket4j-redis` 모듈로 이 문제를 해결한다.

```java
@Configuration
public class Bucket4jRedisConfig {

    @Bean
    public ProxyManager<String> proxyManager(RedisClient redisClient) {
        // Lettuce 기반 Redis 커넥션을 Bucket4j ProxyManager에 위임
        return LettuceBasedProxyManager
            .builderFor(redisClient)
            .build();
    }

    public Bucket resolveBucket(ProxyManager<String> proxyManager, String key) {
        Supplier<BucketConfiguration> configSupplier = () -> BucketConfiguration.builder()
            .addLimit(Bandwidth.classic(60, Refill.greedy(60, Duration.ofMinutes(1))))
            .build();
        return proxyManager.builder().build(key, configSupplier);
    }
}
```

`ProxyManager`를 쓰면 버킷의 실제 상태(토큰 수, 마지막 리필 시각)가 Redis에 원자적으로 저장·갱신되므로, 인스턴스가 몇 대든 동일한 키에 대해 일관된 카운트를 유지한다. 애플리케이션 코드 입장에서는 로컬 `Bucket.builder()`를 `proxyManager.builder().build(key, ...)`로 바꾸는 정도의 차이만 있다.

## 실무 포인트

- **버킷 키 설계가 정책의 핵심이다.** API Key 단위, 사용자 ID 단위, IP 단위 중 무엇으로 묶을지에 따라 실제 체감 한도가 달라진다. 프록시 뒤에 있다면 `X-Forwarded-For`를 신뢰할지 여부도 미리 정해야 한다.
- **429 응답에는 `Retry-After` 헤더를 반드시 포함한다.** 클라이언트가 무작정 재시도를 반복하지 않고 대기 시간을 준수하도록 유도할 수 있다.
- **분산 환경에서는 Redis 장애 시 동작을 미리 정의한다.** ProxyManager 호출이 실패했을 때 요청을 통과시킬지(fail-open), 막을지(fail-closed)는 서비스 성격에 따라 다르며, 어느 쪽이든 관측 가능하게 로깅해야 한다.
- **필터 안에서 블로킹 I/O(Redis 호출 등)가 발생한다는 점을 인지한다.** 가상 스레드(virtual thread) 환경에서는 상대적으로 부담이 적지만, 플랫폼 스레드 기반이라면 Redis 왕복 지연이 필터 체인 전체 지연에 그대로 더해진다는 점을 감안해 타임아웃을 짧게 설정해두는 것이 안전하다.
- **정책 값 자체는 트래픽 패턴을 관찰하며 튜닝 대상으로 다룬다.** 특정 수치를 정답처럼 못박기보다, 초기값을 보수적으로 잡고 모니터링 지표를 보며 조정하는 편이 안전하다.

## 3줄 요약

- Bucket4j는 토큰 버킷 알고리즘을 로컬 메모리와 분산(Redis 등) 환경 모두에서 동일한 API로 다룰 수 있게 해주는 라이브러리다.
- Spring Boot에서는 `OncePerRequestFilter`로 전역 진입점을 막거나, Interceptor/AOP로 엔드포인트별 세밀한 정책을 어노테이션으로 표현할 수 있다.
- 실제 도입 시에는 버킷 키 설계, `Retry-After` 응답, Redis 장애 시 fail-open/closed 전략까지 함께 설계해야 안정적으로 동작한다.

## 참고 자료

- [Bucket4j 공식 GitHub — 문서 및 예제](https://github.com/bucket4j/bucket4j)
- [Bucket4j-Redis 모듈 문서](https://github.com/bucket4j/bucket4j/tree/master/bucket4j-redis)
- [Baeldung — Rate Limiting a Spring API Using Bucket4j](https://www.baeldung.com/spring-bucket4j)
