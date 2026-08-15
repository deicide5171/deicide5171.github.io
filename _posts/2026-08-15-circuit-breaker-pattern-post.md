---
layout: single
title: "서킷 브레이커 패턴, 장애 전파를 막는 방법"
date: 2026-08-15 22:40:00 +0530
categories: system-design
tags: ["서킷브레이커", "장애복원력", "마이크로서비스", "재시도전략"]
toc: true
toc_sticky: true
excerpt: "서킷 브레이커의 상태머신 동작 원리와 재시도/백오프 조합으로 연쇄 장애를 막는 방법을 정리한다."
---

## 왜 지금 이 이야기인가

마이크로서비스 아키텍처가 보편화되면서 서비스 하나의 장애가 시스템 전체로 번지는 "연쇄 장애(cascading failure)" 사례가 계속 보고되고 있다. 결제 서비스가 잠깐 느려졌을 뿐인데 주문, 재고, 알림 서비스까지 스레드 풀이 고갈되며 전체가 멈추는 식이다. 이런 문제를 막기 위한 대표적인 패턴이 서킷 브레이커(Circuit Breaker)다.

서킷 브레이커라는 이름은 전기 회로의 차단기에서 따왔다. 회로에 과부하가 걸리면 차단기가 전류를 끊어 화재를 막듯, 소프트웨어에서도 특정 의존성이 계속 실패하면 호출 자체를 차단해 장애가 번지는 것을 막는다. 이 패턴은 Michael Nygard의 저서 "Release It!"을 통해 널리 알려졌고, 이후 Netflix Hystrix, resilience4j 같은 라이브러리로 구현되며 실무 표준처럼 자리잡았다.

## 상태머신으로 보는 동작 원리

서킷 브레이커는 보통 세 가지 상태를 오가는 상태머신으로 구현된다.

| 상태 | 동작 | 전이 조건 |
|---|---|---|
| Closed(닫힘) | 정상적으로 요청을 통과시키며 실패율을 관찰 | 실패율이 임계치를 넘으면 Open으로 전환 |
| Open(열림) | 요청을 즉시 차단하고 폴백 응답 반환 | 일정 시간(타임아웃) 경과 후 Half-Open으로 전환 |
| Half-Open(반열림) | 제한된 수의 시험 요청만 통과시킴 | 시험 요청이 성공하면 Closed, 실패하면 다시 Open |

이 구조의 핵심은 "실패를 감지하면 잠시 쉬었다가 조심스럽게 다시 시도한다"는 점이다. Open 상태에서 무의미한 요청을 계속 보내지 않기 때문에 장애가 발생한 다운스트림 서비스가 회복할 시간을 벌 수 있고, 호출하는 쪽도 스레드나 커넥션을 낭비하지 않는다.

## 타임아웃·재시도(Backoff)와의 조합

서킷 브레이커 단독으로는 충분하지 않다. 실무에서는 보통 다음 조합으로 함께 쓰인다.

- 타임아웃: 개별 요청이 무한정 대기하지 않도록 상한을 둔다
- 재시도(retry with exponential backoff): 일시적 장애일 경우 점진적으로 대기 시간을 늘려가며 재시도
- 서킷 브레이커: 재시도가 반복적으로 실패하면 아예 호출을 차단
- 벌크헤드(bulkhead): 의존성별로 스레드 풀/커넥션 풀을 분리해 한 곳의 문제가 다른 곳까지 못 번지게 격리

이 네 가지를 계층적으로 쌓으면, 짧은 순간 장애는 재시도로 흡수하고, 지속적인 장애는 서킷 브레이커가 차단하며, 장애의 영향 범위는 벌크헤드로 제한하는 방어선이 만들어진다. 재시도만 하고 서킷 브레이커가 없으면 오히려 장애가 난 서비스에 재시도 트래픽이 몰려 상황을 악화시킬 수 있다는 점은 실무에서 자주 지적되는 함정이다.

## 예제

```yaml
# resilience4j 스타일 설정 예시 (개념적 형태)
resilience4j.circuitbreaker:
  instances:
    paymentService:
      failureRateThreshold: 50
      waitDurationInOpenState: 10s
      slidingWindowSize: 20
      permittedNumberOfCallsInHalfOpenState: 5
```

```python
# 상태머신 개념을 단순화한 의사코드
class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=30):
        self.state = "CLOSED"
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.opened_at = None

    def call(self, func, *args):
        if self.state == "OPEN":
            if time_since(self.opened_at) > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("fallback 필요")
        try:
            result = func(*args)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = now()

    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
```

## 실무 포인트와 주의사항

- 임계치(failure threshold)와 타임아웃 값은 서비스마다 트래픽 패턴이 다르므로 일괄 적용보다 개별 튜닝이 필요하다
- Open 상태일 때 사용자에게 보여줄 폴백 응답(캐시된 데이터, 기본값, 안내 메시지)을 미리 설계해둘 것
- 서킷 브레이커 상태 전이 자체를 메트릭/로그로 남겨 옵저버빌리티 대시보드에서 추적할 것
- 재시도와 서킷 브레이커를 동시에 쓸 때는 재시도 횟수가 서킷을 너무 빨리 열게 만들지 않는지 함께 검증할 것

## 3줄 요약

- 서킷 브레이커는 Closed/Open/Half-Open 상태를 오가며 반복적으로 실패하는 의존성 호출을 차단한다
- 타임아웃, 재시도(백오프), 벌크헤드와 계층적으로 결합해야 연쇄 장애를 실질적으로 예방할 수 있다
- 임계치와 폴백 전략은 서비스별로 다르게 설계하고, 상태 전이를 반드시 모니터링해야 한다

## 참고 자료

- [Martin Fowler - CircuitBreaker](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Microsoft Azure Architecture - Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [resilience4j CircuitBreaker 공식 문서](https://resilience4j.readme.io/docs/circuitbreaker)
- [Netflix Hystrix (아카이브)](https://github.com/Netflix/Hystrix)
