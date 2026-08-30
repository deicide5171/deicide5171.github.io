---
layout: single
title: "Adaptive Concurrency Limiting — 고정 스레드풀 대신 지연시간으로 동시성 한도를 자동 조절하기"
date: 2026-09-27 12:45:00 +0530
categories: system-design
tags: ["ConcurrencyLimiting", "적응형동시성제어", "부하제어", "TCP혼잡제어", "넷플릭스"]
toc: true
toc_sticky: true
excerpt: "서버의 스레드풀 크기나 최대 동시 요청 수를 고정값으로 튜닝하면 트래픽 패턴이 바뀔 때마다 다시 벤치마크해야 한다. TCP 혼잡 제어에서 영감을 받은 Adaptive Concurrency Limiting이 지연시간 변화를 관찰해 한도를 실시간으로 조절하는 원리를 정리했다."
---

## 왜 고정된 동시성 한도는 항상 틀린 값이 되는가

서비스의 스레드풀 크기나 최대 동시 처리 요청 수를 설정할 때, 많은 팀이 부하 테스트로 "이 정도면 안전하다"는 숫자를 한 번 정하고 고정한다. 문제는 이 숫자가 정확한 순간은 그 벤치마크를 수행한 그 순간뿐이라는 점이다. 백엔드 DB가 느려지거나, 다운스트림 서비스에 장애가 생기거나, GC 일시정지가 길어지면, 같은 동시 요청 수라도 실제로 처리 가능한 용량은 크게 달라진다. 고정된 한도를 너무 낮게 잡으면 여유가 있는데도 요청을 거부하는 낭비가 생기고, 너무 높게 잡으면 시스템이 과부하 상태에서도 계속 요청을 받아들이다가 전체가 무너지는 사태로 이어진다. Adaptive Concurrency Limiting은 이 숫자를 사람이 미리 정하는 대신, 시스템이 스스로 관찰하며 실시간으로 조절하게 만든다.

## 핵심 개념 1 — TCP 혼잡 제어에서 빌려온 아이디어

이 접근의 뿌리는 TCP의 혼잡 제어(congestion control) 알고리즘이다. TCP는 네트워크가 얼마나 혼잡한지 사전에 알 수 없으므로, 전송 속도를 점진적으로 늘려가며 패킷 손실이나 지연 증가가 관찰되면 속도를 줄이는 피드백 루프로 최적 전송량을 찾는다. Netflix가 오픈소스로 공개한 `concurrency-limits` 라이브러리는 이 원리를 애플리케이션 서버의 동시 요청 처리에 그대로 적용한다. 요청을 처리할 때마다 지연시간을 측정하고, 지연시간이 예상보다 늘어나기 시작하면(=시스템이 포화 상태에 가까워지고 있다는 신호) 동시성 한도를 낮추고, 지연시간이 안정적이면 한도를 서서히 늘려본다.

## 핵심 개념 2 — Little's Law와 그래디언트 기반 한도 계산

이 알고리즘의 수학적 기반은 대기행렬 이론의 Little's Law로, "동시성(진행 중인 요청 수) = 처리량 × 평균 응답시간"이라는 관계를 이용한다. 시스템이 포화 상태에 가까워지면 처리량은 정체되는데 응답시간은 계속 늘어나므로, 이 둘의 곱인 최적 동시성 수준을 실시간으로 역산할 수 있다. 대표적인 구현인 그래디언트 알고리즘(Gradient2)은 최근 관찰된 최소 지연시간(RTT_noload, 시스템이 여유로울 때의 기준 지연)과 현재 지연시간의 비율을 계산해, 이 비율이 1에 가까우면(지연이 늘지 않았으면) 한도를 늘리고, 비율이 커지면(지연이 급증했으면) 한도를 줄이는 방향으로 매 요청마다 미세 조정한다.

| 항목 | 고정 동시성 한도 | Adaptive Concurrency Limiting |
|---|---|---|
| 한도 결정 방식 | 사전 벤치마크로 고정값 설정 | 실시간 지연시간 관찰로 자동 조절 |
| 백엔드 상태 변화 대응 | 대응 불가(재배포·재설정 필요) | 자동으로 즉시 반영 |
| 과도한 보수적 설정 문제 | 여유 있어도 거부(낭비) | 여유를 실시간으로 활용 |
| 튜닝 부담 | 트래픽 패턴마다 재조정 필요 | 알고리즘 파라미터만 초기 설정 |

## 코드 예제 — Java 서버에 concurrency-limits 적용

```java
Limiter<Void> limiter = SimpleLimiter.newBuilder()
    .limit(Gradient2Limit.newBuilder()
        .initialLimit(20)          // 초기 동시성 한도
        .minLimit(10)              // 최소 한도(너무 낮아지지 않도록)
        .maxConcurrency(200)       // 절대 상한
        .build())
    .build();

public Response handleRequest(Request request) {
    Optional<Limiter.Listener> listener = limiter.acquire(null);
    if (!listener.isPresent()) {
        // 현재 시스템이 포화 상태로 판단되어 한도 초과 — 즉시 거부
        return Response.status(503).build();
    }
    try {
        Response result = processRequest(request);
        listener.get().onSuccess();   // 정상 처리: 지연시간을 알고리즘에 피드백
        return result;
    } catch (Exception e) {
        listener.get().onIgnore();    // 타임아웃 등은 지연시간 계산에서 제외
        throw e;
    }
}
```

## 실무 포인트

- **RTT_noload 측정 구간에 주의하라.** 알고리즘이 "여유로울 때의 기준 지연시간"을 잘못 학습하면(예: 배포 직후 캐시가 덜 데워진 상태를 기준으로 삼으면) 이후 정상 상태를 오히려 포화로 오판할 수 있다. 윈도우 크기와 기준값 갱신 주기를 신중히 설정해야 한다.
- **고정 한도와 병행 운용하는 것이 안전하다.** 적응형 한도가 예상치 못하게 너무 낮아지는 극단적 상황에 대비해, 최소·최대 한도를 명시적으로 설정해 알고리즘의 조정 범위를 제한하는 것이 실무에서 권장된다.
- **다운스트림 의존성별로 별도 한도를 두라.** 하나의 서비스가 여러 다운스트림을 호출한다면, 전체를 하나의 동시성 풀로 묶기보다 의존성별로 독립된 리미터를 두어야 한 다운스트림의 장애가 다른 다운스트림 호출까지 막지 않는다.

## 마무리 요약

- 고정된 동시성 한도는 벤치마크한 순간에만 정확하며, 백엔드 상태 변화에 따라 과도하게 보수적이거나 위험하게 느슨해질 수 있다.
- Adaptive Concurrency Limiting은 TCP 혼잡 제어와 Little's Law에서 착안해, 지연시간 변화를 관찰하며 동시성 한도를 실시간으로 자동 조절한다.
- 기준 지연시간 측정 구간과 최소·최대 한도 설정, 다운스트림별 리미터 분리가 안정적인 적용의 핵심이다.

## 참고 자료

- [Netflix concurrency-limits GitHub 저장소](https://github.com/Netflix/concurrency-limits)
- [Netflix TechBlog — Performance Under Load](https://netflixtechblog.medium.com/performance-under-load-3e6fa9a60581)
