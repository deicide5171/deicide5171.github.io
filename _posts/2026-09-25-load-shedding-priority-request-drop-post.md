---
layout: single
title: "Load Shedding — 트래픽 폭주 시 우선순위 기반으로 요청을 의도적으로 버리는 설계"
date: 2026-09-25 12:45:00 +0530
categories: system-design
tags: ["LoadShedding", "과부하대응", "우선순위큐", "가용성", "적응형동시성제한"]
toc: true
toc_sticky: true
excerpt: "트래픽이 순간적으로 폭주하면 서버가 모든 요청을 처리하려다 전체가 느려져 결국 아무 응답도 못 주는 상태에 빠지는 문제를, 덜 중요한 요청을 의도적으로 즉시 거절하는 Load Shedding 설계로 해결하는 방법을 정리했다."
---

## 왜 지금 Load Shedding을 다시 봐야 하는가

서버 증설과 오토스케일링이 당연해진 시대에도, 트래픽이 순간적으로 용량을 초과하는 상황 자체를 막을 수는 없다. 이때 흔히 나타나는 최악의 패턴은 "모든 요청을 어떻게든 처리해보려는" 태도다. 큐가 계속 쌓이고, 스레드 풀이 고갈되고, GC가 빈번해지면서 처리량 자체가 무너져 결국 정상 트래픽까지 타임아웃으로 실패하는 congestive collapse 상태에 빠진다. 이 지점에서 필요한 건 "더 열심히 처리하기"가 아니라 "일부는 처리하지 않기로 결정하기"다. Load Shedding은 시스템이 감당할 수 있는 용량을 넘어서면, 낮은 가치의 요청을 초입에서 즉시 거절해 남은 용량으로 중요한 요청만이라도 정상 처리하는 설계 원칙이다. Virtual Waiting Room이 사용자를 서버 밖에서 미리 줄 세운다면, Load Shedding은 서버 안에서 이미 들어온 요청 중 무엇을 버릴지 실시간으로 판단한다는 점에서 다르다.

## 핵심 개념 1 — 언제, 무엇을 기준으로 버릴 것인가

Load Shedding의 첫 번째 설계 결정은 "과부하 여부를 어떻게 판단하는가"다. CPU 사용률이나 큐 길이 같은 정적 임계값도 쓸 수 있지만, 더 정교한 방식은 최근 요청들의 실제 지연시간 분포를 관찰해 적응적으로 동시 처리 한도를 조절하는 것이다(적응형 동시성 제한, adaptive concurrency limit). Netflix의 concurrency-limits 라이브러리가 대표적으로, TCP의 AIMD(Additive Increase Multiplicative Decrease)와 유사하게 지연시간이 임계값을 넘으면 허용 동시성을 줄이고, 안정적이면 서서히 늘린다. 두 번째 결정은 "과부하 상태에서 무엇을 버릴 것인가"다. 모든 요청을 동등하게 취급하면 안 되므로, 결제 완료 요청과 추천 로그 수집 요청에 서로 다른 우선순위를 부여하고 낮은 우선순위부터 먼저 거절하는 방식이 일반적이다.

## 핵심 개념 2 — LIFO 큐와 데드라인 전파

직관과 다르게, 과부하 상황에서는 FIFO(선입선출) 큐보다 LIFO(후입선출) 큐가 전체 처리량 유지에 유리할 때가 많다. FIFO는 오래 기다린 요청을 순서대로 처리하지만, 이미 큐에서 너무 오래 대기해 클라이언트 쪽 타임아웃이 지난 요청까지 붙들고 처리하느라 리소스를 낭비한다. LIFO는 방금 들어온, 아직 클라이언트가 응답을 기다리고 있을 가능성이 높은 요청을 먼저 처리하고, 오래된 요청은 통째로 버림으로써 "이미 버려진 요청에 리소스를 쓰는 낭비"를 줄인다. 이와 짝을 이루는 것이 데드라인 전파(deadline propagation)다. 클라이언트가 "5초 안에 응답이 없으면 포기한다"는 정보를 요청 헤더로 전달하면, 서비스 체인 중간의 어느 지점에서든 이미 데드라인이 지난 요청을 즉시 버릴 수 있어 하위 서비스까지 무의미한 부하가 전파되지 않는다.

| 전략 | 판단 기준 | 장점 | 주의점 |
|---|---|---|---|
| 정적 임계값 셰딩 | CPU/메모리/큐 길이 고정값 | 구현 단순 | 워크로드 변화에 둔감, 튜닝 필요 |
| 적응형 동시성 제한 | 실측 지연시간 추이 | 실제 성능 저하 시점에 반응 | 초기 튜닝·관찰 기간 필요 |
| 우선순위 기반 셰딩 | 요청 타입·비즈니스 가치 | 중요 트래픽 보호 | 우선순위 분류 체계 설계 필요 |
| LIFO + 데드라인 전파 | 대기 시간·클라이언트 데드라인 | 낭비된 처리 감소 | 순서 보장이 필요한 요청엔 부적합 |

## 코드 예제 — 우선순위 기반 셰딩 필터(Spring 의사코드)

```java
@Component
public class LoadSheddingFilter implements Filter {

    private final AdaptiveLimiter limiter; // 적응형 동시성 한도 계산기

    public void doFilter(HttpServletRequest req, HttpServletResponse res, FilterChain chain) {
        Priority priority = classify(req); // CRITICAL, NORMAL, BEST_EFFORT

        if (!limiter.tryAcquire(priority)) {
            // 낮은 우선순위부터 즉시 503으로 거절 — 대기시키지 않는다
            res.setStatus(503);
            res.setHeader("Retry-After", "1");
            return;
        }

        // 클라이언트가 보낸 데드라인이 이미 지났으면 처리 자체를 포기
        Duration deadline = parseDeadline(req.getHeader("X-Deadline-Ms"));
        if (deadline.isNegative()) {
            res.setStatus(504);
            return;
        }

        try {
            chain.doFilter(req, res);
        } finally {
            limiter.release(priority);
        }
    }
}
```

## 실무 포인트

- **셰딩은 부끄러운 실패가 아니라 설계된 성공이다.** 일부 요청에 명확한 503을 즉시 돌려주는 것이, 모든 요청이 30초씩 걸리다 타임아웃되는 것보다 시스템 전체와 사용자 경험 모두에 낫다. 셰딩된 요청 비율을 SLO 위반이 아니라 정상 동작 지표로 대시보드에 노출하는 것이 좋다.
- **우선순위 분류는 비즈니스팀과 미리 합의해야 한다.** 결제·인증처럼 되돌릴 수 없는 트랜잭션은 최고 우선순위로, 추천·로깅처럼 없어도 서비스가 굴러가는 요청은 최저 우선순위로 명시적으로 분류해두지 않으면, 장애 상황에서 즉흥적으로 판단하다 정말 중요한 요청까지 버려질 수 있다.
- **셰딩 지점은 가능한 한 앞단(로드밸런서·게이트웨이)에 두는 것이 자원 효율적이다.** 애플리케이션 서버까지 요청이 들어와 DB 커넥션까지 소모한 뒤에 버리는 것보다, 게이트웨이 단계에서 버리는 것이 하위 리소스를 아낀다.

## 마무리 요약

- Load Shedding은 과부하 상황에서 모든 요청을 처리하려다 시스템 전체가 무너지는 congestive collapse를 막기 위해, 낮은 우선순위 요청을 의도적으로 즉시 거절하는 설계다.
- 적응형 동시성 제한으로 과부하 시점을 실측 지연시간 기반으로 판단하고, LIFO 큐와 데드라인 전파로 이미 버려질 요청에 리소스를 낭비하지 않도록 설계한다.
- 우선순위 분류 체계는 장애가 나기 전에 비즈니스팀과 미리 합의해두어야 실제 장애 상황에서 신뢰할 수 있게 동작한다.

## 참고 자료

- [Netflix Tech Blog - Performance Under Load](https://netflixtechblog.medium.com/performance-under-load-3e6fa9a60581)
- [Google SRE Book - Handling Overload](https://sre.google/sre-book/handling-overload/)
