---
layout: single
title: "서킷 브레이커 상태 머신 심화 — Half-Open 상태의 실제 동작과 튜닝"
date: 2026-09-24 13:45:00 +0530
categories: system-design
tags: ["서킷브레이커", "CircuitBreaker", "HalfOpen", "장애격리", "Resilience4j"]
toc: true
toc_sticky: true
excerpt: "서킷 브레이커를 도입했는데도 장애가 복구된 뒤 트래픽이 몰려 다시 장애가 재발하거나, 반대로 복구됐는데도 계속 Open 상태에 머무는 문제를 Half-Open 상태의 상세 동작과 파라미터 튜닝 관점에서 정리했다."
---

## 왜 지금 Half-Open 상태를 다시 봐야 하는가

서킷 브레이커의 Closed(정상)와 Open(차단) 두 상태는 개념적으로 직관적이라 대부분 쉽게 이해하고 넘어간다. 문제는 그 사이에 있는 Half-Open 상태다. 라이브러리 기본값만 그대로 쓰고 이 상태의 동작 방식을 제대로 이해하지 못하면, 실제 장애 상황에서 두 가지 정반대의 실패를 겪는다. 하나는 의존 서비스가 복구됐는데도 서킷 브레이커가 계속 Open 상태에 머물러 정상 트래픽까지 계속 차단하는 경우이고, 다른 하나는 반대로 Half-Open으로 전환되자마자 대기하고 있던 트래픽이 한꺼번에 밀려들어가 이제 막 복구되기 시작한 서비스를 다시 무너뜨리는 경우다. Half-Open 상태의 세부 동작을 정확히 이해해야 이 두 실패 모두를 피할 수 있다.

## 핵심 개념 1 — Half-Open은 "제한된 수의 시험 요청"을 흘려보내는 상태다

Open 상태에서 일정 시간(wait duration)이 지나면 서킷 브레이커는 자동으로 Half-Open 상태로 전환된다. 이 상태에서는 모든 요청을 막지도, 모든 요청을 통과시키지도 않는다. 미리 설정된 개수(permitted number of calls in half-open state)만큼의 "시험 요청"만 실제로 의존 서비스로 흘려보내고, 나머지 요청은 여전히 즉시 실패 처리(fail-fast)한다. 이 시험 요청들의 성공률을 관찰해, 설정된 임계치 이상 성공하면 Closed로 완전히 복귀하고, 실패율이 여전히 높으면 다시 Open으로 돌아간다. 이 시험 요청 개수를 너무 작게 잡으면 통계적으로 신뢰하기 어려운 소수의 샘플만으로 상태를 결정하게 되고, 너무 크게 잡으면 아직 완전히 회복되지 않은 서비스에 부하를 다시 줄 위험이 있다.

## 핵심 개념 2 — Wait Duration과 지수 백오프의 관계

Open에서 Half-Open으로 전환되는 대기 시간을 고정값으로 두면, 의존 서비스의 장애 성격에 따라 최적이 아닐 수 있다. 짧은 순간적 장애라면 짧은 대기 시간이 빠른 복구에 유리하지만, 근본적인 장애(DB 다운 등)라면 짧은 대기 시간마다 반복적으로 Half-Open을 시도하는 것 자체가 아직 복구 중인 서비스에 지속적인 부하를 준다. 이런 상황을 위해 일부 구현체는 Half-Open에서 다시 Open으로 돌아갈 때마다 다음 대기 시간을 지수적으로 늘리는 백오프 전략을 지원한다. 재시도 간격이 점점 벌어지면서 완전히 복구될 때까지 걸리는 시간에 맞춰 자연스럽게 시험 빈도가 줄어든다.

| 상태 | 요청 처리 방식 | 전환 조건 |
|---|---|---|
| Closed | 모든 요청 통과, 실패율 집계 | 실패율이 임계치 초과 시 Open으로 |
| Open | 모든 요청 즉시 실패(fail-fast) | wait duration 경과 시 Half-Open으로 |
| Half-Open | 제한된 수의 시험 요청만 통과 | 시험 요청 성공률에 따라 Closed 또는 Open으로 |

## 예제 — Resilience4j Half-Open 파라미터 설정

```java
CircuitBreakerConfig config = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)                          // 실패율 50% 초과 시 Open
    .waitDurationInOpenState(Duration.ofSeconds(30))   // Open 유지 후 Half-Open 전환까지 대기
    .permittedNumberOfCallsInHalfOpenState(10)         // Half-Open에서 흘려보낼 시험 요청 수
    .minimumNumberOfCalls(20)                          // 실패율 계산에 필요한 최소 호출 수
    .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
    .slidingWindowSize(50)
    .build();

CircuitBreaker circuitBreaker = CircuitBreaker.of("paymentService", config);
```

`permittedNumberOfCallsInHalfOpenState`를 10으로 설정하면, Half-Open 전환 후 딱 10개의 요청만 실제로 통과시키고 그 결과의 실패율로 다음 상태를 결정한다. 나머지 대기 중인 요청은 이 10개의 결과가 나오기 전까지 즉시 실패 처리된다.

## 실무 포인트

- **시험 요청 개수를 트래픽 규모에 맞춰 조정하라.** 초당 요청이 매우 많은 서비스에서 시험 요청을 너무 적게 설정하면, 통계적으로 우연히 그 몇 개만 성공해 실제로는 아직 불안정한 서비스가 Closed로 잘못 판정될 위험이 있다.
- **Half-Open 시험 요청도 실제 트래픽에 영향을 준다는 점을 감안하라.** 결제처럼 실패 비용이 큰 작업의 경우, 시험 요청을 별도의 저비용 헬스체크 엔드포인트로 대체하는 것을 고려할 수 있다.
- **여러 인스턴스가 각자 독립적인 서킷 브레이커 상태를 가진다는 점을 인지하라.** 인스턴스별로 Half-Open 진입 시점이 다르면, 전체 클러스터 관점에서는 항상 일부 인스턴스가 시험 요청을 흘려보내는 상태가 되어 예상보다 회복 판정이 늦어지거나 반대로 부하가 분산돼 보일 수 있다.

## 마무리 요약

- Half-Open 상태는 정해진 개수의 시험 요청만 실제로 통과시켜 의존 서비스의 실제 회복 여부를 확인하는 단계다.
- 시험 요청 개수와 최소 호출 수 설정이 통계적 신뢰도와 재장애 위험 사이의 균형을 결정한다.
- 근본적인 장애에는 지수 백오프로 Half-Open 재시도 간격을 늘려, 아직 회복 중인 서비스에 반복적인 부하를 주지 않도록 설계해야 한다.

## 참고 자료

- [Resilience4j - CircuitBreaker](https://resilience4j.readme.io/docs/circuitbreaker)
- [Microsoft - Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
