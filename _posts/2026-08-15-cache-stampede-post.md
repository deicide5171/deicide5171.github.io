---
layout: single
title: "캐시 스탬피드, 트래픽 몰릴 때 캐시가 오히려 서비스를 무너뜨리는 이유"
date: 2026-08-15 13:40:00 +0530
categories: system-design
tags: ["caching", "system-design", "reliability", "scalability", "redis"]
toc: true
toc_sticky: true
excerpt: "인기 캐시 키 하나가 동시에 만료되는 순간 벌어지는 캐시 스탬피드(Thundering Herd)의 원리와, 락·확률적 조기 갱신·백그라운드 리프레시 등 실전 방지 전략을 비교한다."
---

## 왜 지금 캐시 스탬피드인가

캐시는 대개 "DB 부하를 줄이는 방패"로 소개되지만, 설계를 잘못하면 오히려 그 방패가 한순간에 사라지면서 DB를 직격하는 원인이 된다. 특히 조회량이 매우 많은 키(인기 상품, 메인 배너, 랭킹) 하나가 만료되는 순간, 그 짧은 틈에 몰린 수백~수천 개의 요청이 동시에 원본 데이터 소스로 몰려가는 **캐시 스탬피드(Cache Stampede, Thundering Herd)** 현상이 발생한다.

트래픽이 계속 커지는 서비스에서 이 문제는 점점 더 자주 재발한다. 캐시 TTL을 짧게 잡을수록, 그리고 캐시 히트율이 높을수록(=원본 조회 경로가 평소에 거의 쓰이지 않을수록) 만료 순간의 충격이 더 크다는 역설이 있어, 시스템 설계 초기에 반드시 짚고 넘어가야 하는 주제다.

## 방지 전략 네 가지 비교

| 전략 | 원리 | 장점 | 단점 |
|---|---|---|---|
| 분산 락(Mutex) | 첫 요청만 원본 조회, 나머지는 대기/재시도 | 원본 부하를 1건으로 제한 | 락 획득 실패 시 지연 증가, 락 자체가 병목 가능 |
| 확률적 조기 만료 | TTL 임박 시 확률적으로 미리 갱신 | 구현 단순, 만료 시점 분산 | 완벽한 방지는 아님(확률 기반) |
| 백그라운드 리프레시 | TTL 전에 별도 작업이 미리 갱신 | 사용자 요청 경로에 영향 없음 | 갱신 작업 스케줄링·장애 처리 필요 |
| Stale-While-Revalidate | 만료 후에도 잠깐 오래된 값을 서빙하며 뒤에서 갱신 | 응답 지연 거의 없음 | 짧은 시간 오래된 데이터 노출 |

실무에서는 이 중 하나만 쓰기보다, 인기 키에는 백그라운드 리프레시를, 나머지 키에는 확률적 조기 만료를 함께 쓰는 조합이 흔하다.

## 핵심 개념: 확률적 조기 재계산(XFetch)

가장 널리 알려진 경량 기법은 **확률적 조기 재계산**이다. 캐시 값에 계산 소요 시간을 함께 저장해두고, TTL이 가까워질수록 "지금 미리 갱신할 확률"을 높여 요청들을 시간축에 분산시킨다.

핵심 아이디어는 "TTL이 끝나기 직전 구간에서, 소수의 요청만 먼저 나서서 캐시를 갱신하고 나머지는 여전히 기존 값을 쓰게 만드는 것"이다. 이렇게 하면 만료 시각에 모든 요청이 한꺼번에 원본으로 몰리는 대신, 갱신 시점이 자연스럽게 흩어진다.

## 예제: XFetch 방식 의사 코드 (Python)

```python
import time
import random
import math

def get_with_xfetch(key, compute_fn, ttl=60, beta=1.0):
    value, expiry, delta = cache.get(key)  # delta: 이전 계산 소요 시간
    now = time.time()

    early_recompute = delta * beta * math.log(random.random())
    if value is None or now - early_recompute >= expiry:
        start = time.time()
        value = compute_fn()
        delta = time.time() - start
        cache.set(key, value, expiry=now + ttl, delta=delta)

    return value
```

`beta` 값을 키우면 조기 갱신이 더 자주 일어나 안전해지지만, 원본 조회 빈도도 함께 늘어나므로 트래픽 패턴에 맞춰 조정해야 한다.

## 실무 포인트

- **인기 키를 먼저 식별한다**: 접근 로그로 상위 트래픽 키를 뽑아, 그 키들에만 백그라운드 리프레시나 락을 적용해도 효과의 대부분을 얻을 수 있다.
- **락 타임아웃을 반드시 둔다**: 락을 잡은 요청이 실패·지연되면 나머지 요청이 무한 대기할 수 있으니, 락에는 항상 만료 시간을 건다.
- **캐시 워밍업을 배포 절차에 포함한다**: 배포 직후 캐시가 비어 있는 상태(콜드 스타트)도 스탬피드의 흔한 원인이므로, 배포 스크립트에 캐시 예열 단계를 넣는다.
- **모니터링 지표를 분리한다**: 캐시 히트율뿐 아니라 "동시 원본 조회 수"를 별도로 관찰해야 스탬피드 징후를 조기에 잡을 수 있다.

## 3줄 요약

- 캐시 스탬피드는 인기 키 하나가 만료되는 순간 다수 요청이 동시에 원본으로 몰리는 현상이다.
- 분산 락, 확률적 조기 만료, 백그라운드 리프레시, Stale-While-Revalidate를 조합해 만료 시점을 분산시키는 것이 핵심 대응이다.
- 인기 키 식별, 락 타임아웃 설정, 배포 시 캐시 예열이 실무에서 가장 효과가 큰 조치다.

## 참고 자료

- [Cache Stampede — Wikipedia](https://en.wikipedia.org/wiki/Cache_stampede)
- [Optimal Probabilistic Cache Stampede Prevention (VLDB)](https://cseweb.ucsd.edu/~avattani/papers/cache_stampede.pdf)
- [Redis — Cache Best Practices](https://redis.io/docs/latest/develop/use/patterns/)
