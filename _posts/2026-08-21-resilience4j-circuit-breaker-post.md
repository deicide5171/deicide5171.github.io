---
layout: single
title: "Resilience4j로 서킷 브레이커 구현하기 — 장애 전파를 막는 실전 패턴"
date: 2026-08-21 12:25:00 +0530
categories: backend
tags: ["backend", "resilience4j", "circuit-breaker", "spring-boot", "fault-tolerance"]
toc: true
toc_sticky: true
excerpt: "장애가 난 하위 서비스를 계속 호출하다 스레드 풀을 고갈시키는 대신, Resilience4j 서킷 브레이커로 장애를 감지하고 빠르게 실패시키는 실전 구현을 정리한다."
---

마이크로서비스 환경에서 A 서비스가 B 서비스를 호출하는데, B가 응답 지연이나 장애를 겪기 시작했다고 하자. A는 별다른 방어 로직이 없다면 B에 계속 요청을 보내고, 각 요청은 타임아웃 시간까지 스레드를 붙잡은 채 대기한다. 요청이 쌓일수록 A의 스레드 풀이나 커넥션 풀이 하나씩 소진되고, 결국 B와 무관한 다른 요청들까지 처리하지 못하는 상태에 빠진다. 하나의 하위 서비스 장애가 호출부 전체의 장애로 번지는 전형적인 케스케이딩 실패(cascading failure) 시나리오다.

이 문제의 핵심은 "이미 실패하고 있다는 게 뻔한데도 계속 시도한다"는 데 있다. 서킷 브레이커 패턴은 호출 실패가 일정 수준을 넘으면 회로를 끊어(open) 이후 요청을 하위 서비스로 보내지 않고 즉시 실패 처리한다. 자원을 낭비하지 않고 하위 서비스에도 회복할 시간을 준다는 점에서, 응답을 늦게 실패시키는 대신 빠르게 실패시킨다는 "fail fast" 사고방식이 이 패턴의 기본 전제다.

Resilience4j는 이런 서킷 브레이커를 포함한 내결함성(fault tolerance) 컴포넌트 모음을 자바 진영에 가벼운 형태로 제공하는 라이브러리다. Spring Boot와의 통합이 잘 되어 있어, 어노테이션 몇 줄만으로 기존 코드에 적용할 수 있다.

## 핵심 개념 1: CLOSED / OPEN / HALF_OPEN 상태 전이

서킷 브레이커는 세 가지 상태를 오간다. 평상시에는 **CLOSED** 상태로, 모든 호출이 그대로 하위 서비스에 전달된다. 이 상태에서 실패율(또는 느린 호출 비율)이 설정된 임계치를 넘으면 **OPEN** 상태로 전환되고, 이후 들어오는 호출은 하위 서비스에 도달하지도 않은 채 곧바로 예외(또는 폴백)로 처리된다.

OPEN 상태는 영구적이지 않다. 설정된 대기 시간(wait duration)이 지나면 **HALF_OPEN** 상태로 넘어가, 제한된 개수의 시험 호출만 실제로 하위 서비스에 보내본다. 이 시험 호출들의 성공률이 임계치를 충족하면 CLOSED로 복귀하고, 여전히 실패율이 높으면 다시 OPEN으로 돌아간다.

<img src="/assets/images/posts/2026-08-21-resilience4j-circuit-breaker-1.svg" alt="서킷 브레이커의 CLOSED, OPEN, HALF_OPEN 상태 전이도" style="width:100%;">

## 핵심 개념 2: 슬라이딩 윈도우 기반 실패율 계산

Resilience4j는 실패율을 판단할 때 고정된 시간 구간이 아니라 **슬라이딩 윈도우(sliding window)** 를 기준으로 삼는다. 윈도우 타입은 두 가지로, 최근 N번의 호출을 기준으로 삼는 **COUNT_BASED**와 최근 N초 동안의 호출을 기준으로 삼는 **TIME_BASED**가 있다. 윈도우 안의 호출 수가 설정된 최소 호출 수(minimum-number-of-calls)를 넘어야 비로소 실패율 계산이 시작되며, 그렇지 않으면 호출 몇 건만으로 성급하게 회로를 여는 일을 막는다.

실패율뿐 아니라 **느린 호출 비율(slow call rate)** 도 별도로 추적할 수 있다. 응답은 오지만 지정한 시간(slow-call-duration-threshold)보다 오래 걸리는 호출의 비율이 임계치를 넘으면, 명시적인 예외가 없어도 회로를 열 수 있다. 하위 서비스가 완전히 죽지는 않았지만 응답만 느려져도 호출부의 자원이 잠식된다는 점을 감안한 설계다.

## 핵심 개념 3: Hystrix 대비 Resilience4j의 위치

Hystrix는 Netflix가 만든 초기 서킷 브레이커 라이브러리로 업계에 이 패턴을 널리 알린 도구지만, 유지보수 모드로 전환된 지 오래다. Resilience4j는 그 이후 등장해 자바 8의 함수형 인터페이스를 기반으로 설계됐고, 서킷 브레이커·재시도(Retry)·요청 제한(RateLimiter)·격벽(Bulkhead)·타임아웃 등 각 기능을 독립된 모듈로 분리해 필요한 것만 골라 쓸 수 있게 했다. Hystrix가 별도 스레드 풀 격리를 기본 전제로 삼았던 것과 달리, Resilience4j는 데코레이터 패턴으로 함수를 가볍게 감싸는 방식이라 오버헤드가 적고 Spring Boot 통합도 자연스럽다. 새로 시작하는 프로젝트라면 Hystrix보다 Resilience4j가 사실상 기본 선택지다.

## 예제

Spring Boot 프로젝트에서는 `resilience4j-spring-boot3` 의존성을 추가한 뒤, `@CircuitBreaker` 어노테이션과 `fallbackMethod`만 지정하면 된다.

```java
@Service
public class InventoryClient {

    private final RestClient restClient;

    public InventoryClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @CircuitBreaker(name = "inventoryService", fallbackMethod = "fallbackStock")
    @TimeLimiter(name = "inventoryService")
    public CompletableFuture<StockResponse> getStock(String itemId) {
        return CompletableFuture.supplyAsync(() ->
            restClient.get()
                .uri("/inventory/{id}", itemId)
                .retrieve()
                .body(StockResponse.class)
        );
    }

    // 폴백 메서드는 원래 메서드와 동일한 반환 타입 + 마지막에 예외 파라미터를 받는다
    private CompletableFuture<StockResponse> fallbackStock(String itemId, Throwable t) {
        return CompletableFuture.completedFuture(StockResponse.unknown(itemId));
    }
}
```

설정은 `application.yml`에서 슬라이딩 윈도우, 실패율 임계치, 대기 시간 등을 세밀하게 조정할 수 있다.

```yaml
resilience4j:
  circuitbreaker:
    instances:
      inventoryService:
        sliding-window-type: COUNT_BASED
        sliding-window-size: 20
        minimum-number-of-calls: 10
        failure-rate-threshold: 50
        slow-call-rate-threshold: 80
        slow-call-duration-threshold: 2s
        wait-duration-in-open-state: 15s
        permitted-number-of-calls-in-half-open-state: 5
        automatic-transition-from-open-to-half-open-enabled: true
  timelimiter:
    instances:
      inventoryService:
        timeout-duration: 3s
```

## 실무 포인트

- **폴백은 "적당히 그럴듯한 응답"을 설계하는 문제다**: 예외를 그대로 던지는 폴백은 호출부에 부담을 떠넘길 뿐이다. 캐시된 이전 값을 돌려주거나 기능을 축소한 기본값을 제공하는 편이 낫다. 다만 폴백 자체가 무거운 로직(다른 원격 호출 등)을 포함하면 거기서도 지연이 쌓일 수 있으므로 최대한 가볍게 유지해야 한다.
- **타임아웃 없는 서킷 브레이커는 절반짜리 방어다**: 서킷 브레이커는 이미 발생한 실패나 느린 호출을 집계해 회로를 여는 도구이지, 개별 호출이 무한정 대기하는 것을 막아주지는 않는다. `TimeLimiter`나 HTTP 클라이언트 자체의 타임아웃을 함께 설정해야, 응답이 오지 않는 단일 호출이 스레드를 오래 붙잡는 상황을 방지할 수 있다. 타임아웃이 먼저 개별 호출의 상한을 정하고, 서킷 브레이커는 그 결과들을 모아 추세를 판단한다고 보는 편이 정확하다.

## 3줄 요약

- 하위 서비스 장애를 그대로 반복 호출하면 호출부의 스레드/커넥션 풀이 고갈되어 전체 장애로 번질 수 있고, 서킷 브레이커는 이를 빠르게 실패시켜 막는다.
- Resilience4j는 CLOSED/OPEN/HALF_OPEN 상태 전이와 슬라이딩 윈도우 기반 실패율(및 느린 호출 비율) 계산을 통해 회로 개폐를 판단하며, Hystrix 이후 사실상 기본 선택지로 자리잡았다.
- 실무에서는 폴백을 가볍고 의미 있게 설계하고, 타임아웃을 반드시 함께 조합해 개별 호출의 상한을 먼저 정해두어야 한다.

## 참고 자료

- [resilience4j/resilience4j GitHub 저장소](https://github.com/resilience4j/resilience4j)
- [Resilience4j CircuitBreaker 공식 문서](https://resilience4j.readme.io/docs/circuitbreaker)
- [Resilience4j Getting Started 문서](https://resilience4j.readme.io/docs/getting-started-3)
