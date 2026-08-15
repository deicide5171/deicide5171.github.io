---
layout: single
title: "재시도가 장애를 키우는 순간 — 분산 시스템의 타임아웃·백오프·지터 설계법"
date: 2026-08-21 13:45:00 +0530
categories: system-design
tags: ["timeout", "retry", "exponential-backoff", "jitter", "retry-storm"]
toc: true
toc_sticky: true
excerpt: "타임아웃과 재시도를 대충 설정하면 장애를 막기는커녕 재시도 폭풍(Retry Storm)으로 장애를 증폭시킨다. 안전한 타임아웃·지수 백오프·지터 설계 원칙을 정리한다."
---

## 왜 지금 타임아웃·재시도 설계인가

MSA 환경에서 서비스 하나가 다른 서비스를 호출할 때, "느려지면 다시 시도한다"는 재시도 로직은 거의 반사적으로 붙는 방어 코드다. 문제는 이 재시도가 **잘못 설계되면 오히려 장애를 증폭시키는 무기가 된다**는 점이다. 다운스트림 서비스가 순간적으로 느려졌을 때 수백 개의 클라이언트가 동시에 같은 타이밍으로 재시도를 쏟아부으면, 가뜩이나 힘든 서버는 원래 부하에 재시도 트래픽까지 얹혀 완전히 무너진다. 이 현상을 **재시도 폭풍(Retry Storm)** 이라고 부른다.

서킷 브레이커나 벌크헤드가 "장애가 이미 발생한 뒤 그 영향 범위를 제한하는" 방어선이라면, 타임아웃·재시도 설계는 그보다 한 단계 앞서 "장애가 재시도로 인해 눈덩이처럼 불어나지 않도록" 만드는 기초 공사다. 이 둘을 다루지 않고 서킷 브레이커만 붙이면, 서킷이 열리기 직전까지 재시도 폭풍이 서버를 먼저 쓰러뜨리는 상황을 막을 수 없다.

## 핵심 개념 1: 재시도 폭풍은 왜 발생하는가

재시도 폭풍은 대체로 세 조건이 겹칠 때 발생한다. 모든 클라이언트가 **같은 타임아웃 값**을 쓰면 실패도 거의 동시에 발생하고, **고정 간격 재시도**를 쓰면 동기화된 실패가 동기화된 재시도로 계속 이어진다. 여기에 호출 체인이 A→B→C로 이어질 때 각 레이어가 독립적으로 재시도하면, C의 장애가 B에서 N배, A에서 다시 N배로 불어나는 **재시도 증폭(retry amplification)** 까지 겹친다.

| 상황 | 재시도 폭풍 위험 | 이유 |
|---|---|---|
| 타임아웃 고정 + 재시도 간격 고정 | 매우 높음 | 실패·재시도가 모두 동기화됨 |
| 타임아웃 고정 + 지수 백오프만 적용 | 중간 | 간격은 벌어지지만 초반 동시 파동은 남음 |
| 지터 있는 지수 백오프 | 낮음 | 재시도 시점 자체가 무작위로 분산됨 |
| 다계층 호출에서 계층별 독립 재시도 | 매우 높음 | 하위 장애가 상위로 갈수록 배수로 증폭 |

## 핵심 개념 2: 타임아웃, 얼마로 설정해야 하는가

타임아웃은 "감으로 3초" 식으로 정할 값이 아니다. 너무 짧으면 정상 응답도 실패로 처리해 불필요한 재시도를 유발하고, 너무 길면 실패 감지가 늦어져 스레드·커넥션이 오래 점유된 채 쌓인다. 실무에서는 대상 API의 **정상 응답 시간 분포(p50/p99)** 를 기준으로 잡는 방식이 안전하다.

| 기준 | 설명 |
|---|---|
| 연결 타임아웃(connect timeout) | TCP 연결 자체가 안 될 때 빠르게 실패시키는 값. 보통 수백 ms 수준으로 짧게 |
| 읽기 타임아웃(read timeout) | 응답 대기 시간. 해당 API의 p99 응답 시간보다 약간 여유를 둔 값 |
| 전체 요청 예산(request budget) | 호출 체인 전체에서 이 요청에 허용하는 총 시간. 재시도 포함해 상위 타임아웃을 넘지 않도록 역산 |
| 하위 계층 < 상위 계층 타임아웃 | A→B→C 호출에서 C의 타임아웃이 B보다 짧아야 B가 정상적으로 실패를 처리할 여유가 생긴다 |

## 핵심 개념 3: 지수 백오프 + 지터

재시도 간격을 매번 두 배씩 늘리는 **지수 백오프(exponential backoff)** 는 간격은 벌려주지만, 모든 클라이언트가 같은 시각에 실패했다면 여전히 같은 시각에 재시도한다는 문제가 남는다. 여기에 무작위 편차를 더하는 것이 **지터(jitter)** 다.

| 지터 방식 | 계산 방식(개념) | 특징 |
|---|---|---|
| No Jitter | `base * 2^n` | 재시도 동기화 위험 그대로 |
| Full Jitter | `random(0, base * 2^n)` | 완전 무작위, 분산 효과 가장 큼 |
| Equal Jitter | `base*2^n/2 + random(0, base*2^n/2)` | 최소 대기 보장 + 절반은 무작위 |
| Decorrelated Jitter | `random(base, 이전 대기값 * 3)` | 이전 값에 연동해 점진적으로 분산 |

일반적으로 **Full Jitter**나 **Decorrelated Jitter**가 재시도 폭풍 방지 효과가 크다고 알려져 있다. 다만 실제 개선 폭은 트래픽 패턴과 장애 유형에 따라 달라지므로, 도입 전후 지표를 직접 비교해 확인하는 것이 안전하다.

## 예제: Resilience4j로 백오프 + 지터 설정하기 (Java)

```java
RetryConfig config = RetryConfig.custom()
    .maxAttempts(3)
    .intervalFunction(
        IntervalFunction.ofExponentialRandomBackoff(
            500,   // 초기 대기(ms)
            2.0,   // 배수
            0.5    // 지터 계수(±50% 무작위 편차)
        )
    )
    .retryOnException(e -> e instanceof java.io.IOException
        || e instanceof java.util.concurrent.TimeoutException)
    .build();

Retry retry = Retry.of("downstreamCall", config);

Supplier<String> decorated = Retry.decorateSupplier(retry, () -> downstreamClient.call());
```

위 설정은 초기 대기 500ms부터 시작해 매 시도마다 두 배로 늘리되(`2.0`), 각 대기 시간에 ±50%의 무작위 편차(`0.5`)를 더한다. `retryOnException`으로 일시적 오류(IO 예외, 타임아웃)만 재시도 대상으로 한정하는 점도 중요하다 — 비즈니스 로직상의 실패(4xx 등)까지 재시도하면 안 될 요청을 반복하는 것이라 폭풍의 씨앗이 될 뿐이다.

## 실무 포인트

- **멱등성 없는 요청은 재시도하지 않는다**: 결제·주문 생성처럼 중복 실행이 부작용을 낳는 API는 재시도 전에 멱등성 키 등으로 중복 실행을 막는 장치가 있어야 한다.
- **재시도할 오류와 하지 말아야 할 오류를 구분한다**: 5xx·타임아웃 같은 일시적 오류만 재시도하고, 4xx 클라이언트 오류는 즉시 실패 처리한다.
- **호출 체인 전체의 재시도 정책을 한 곳에서 조율한다**: 레이어마다 독립적으로 재시도하면 총 횟수가 배수로 불어난다. 진입점에서 전체 예산(budget)을 정하고 하위 레이어가 이를 나눠 쓰는 편이 안전하다.
- **관측 지표와 함께 튜닝한다**: p99 응답 시간, 재시도율, 재시도 성공률을 계속 확인하며 값을 조정하고, 최초 설정값을 고정해두고 방치하지 않는다.

## 3줄 요약

- 재시도는 타임아웃·간격이 모든 클라이언트에서 동기화될수록 재시도 폭풍으로 번져 장애를 증폭시킨다.
- 타임아웃은 API의 p99 응답 시간 기준으로, 재시도 간격은 지수 백오프에 지터를 더해 분산시키는 것이 기본 원칙이다.
- 멱등성 있는 요청·일시적 오류만 재시도 대상으로 삼고, 호출 체인 전체의 재시도 예산을 한 곳에서 조율해야 안전하다.

<img src="/assets/images/posts/2026-08-21-timeout-retry-strategy-distributed-1.svg" alt="재시도 폭풍과 지수 백오프+지터 비교 개념도 - 동기화된 재시도로 인한 부하 스파이크 대 지터로 분산된 완만한 부하" style="width:100%;">

## 참고 자료

- [AWS Architecture Blog — Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Resilience4j Reference — Retry](https://resilience4j.readme.io/docs/retry)
- [Google SRE Workbook — Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
