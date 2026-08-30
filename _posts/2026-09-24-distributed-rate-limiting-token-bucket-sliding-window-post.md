---
layout: single
title: "분산 레이트 리미팅 알고리즘 비교 — Token Bucket vs Sliding Window Log"
date: 2026-09-24 13:45:00 +0530
categories: system-design
tags: ["레이트리미팅", "TokenBucket", "SlidingWindow", "분산시스템", "Redis"]
toc: true
toc_sticky: true
excerpt: "API 요청 제한을 단일 서버의 카운터로 구현하면 여러 인스턴스로 트래픽이 분산되는 순간 무력화되는 이유를 짚고, Token Bucket과 Sliding Window Log 알고리즘의 경계 문제 처리 방식 차이를 Redis 구현과 함께 정리했다."
---

## 왜 지금 레이트 리미팅 알고리즘을 다시 봐야 하는가

레이트 리미팅을 처음 구현할 때는 각 서버 프로세스 안에서 인메모리 카운터로 요청 수를 세는 것으로 충분해 보인다. 문제는 서비스가 여러 인스턴스로 스케일아웃되는 순간 나타난다. 로드밸런서가 요청을 인스턴스마다 분산시키면, 사용자가 초당 100건으로 제한돼야 하는데도 인스턴스 10대에 걸쳐 각각 100건씩 통과시켜 실제로는 1000건이 통과하는 상황이 벌어진다. 이를 막으려면 모든 인스턴스가 공유하는 중앙 저장소(대개 Redis)에서 카운터를 관리해야 하는데, 이때 어떤 알고리즘으로 카운팅하느냐에 따라 정확도와 메모리 사용량, 그리고 경계 시점의 버스트 허용 정도가 크게 달라진다.

## 핵심 개념 1 — Fixed Window의 경계 버스트 문제

가장 단순한 구현은 고정 시간 창(fixed window)마다 카운터를 0으로 리셋하는 방식이다. 초당 100건 제한이라면 매초 정각에 카운터를 초기화한다. 문제는 이 방식이 "1초당 100건"이라는 규칙의 의도를 실제로 지키지 못하는 경우가 있다는 점이다. 0.9초 시점에 99건이 몰리고, 1.0초가 되어 카운터가 리셋된 직후 다시 100건이 몰리면, 실제로는 0.2초라는 매우 짧은 구간에 199건이 통과하게 된다. 이는 시스템이 실제로 감당해야 하는 순간 부하를 과소평가하게 만드는 근본적인 결함이다.

## 핵심 개념 2 — Token Bucket과 Sliding Window Log의 접근 차이

Token Bucket은 일정한 속도로 토큰이 채워지는 버킷을 상상하면 된다. 요청이 오면 버킷에서 토큰을 하나 꺼내 쓰고, 토큰이 없으면 요청을 거부한다. 버킷 용량만큼은 순간적으로 몰리는 버스트 트래픽도 허용하면서, 장기적으로는 토큰 채워지는 속도로 처리량이 수렴한다는 것이 장점이다. Sliding Window Log는 각 요청의 타임스탬프를 모두 기록해두고, 매 요청마다 "현재 시점부터 1초 전까지" 구간에 있는 로그 개수를 세어 제한을 초과했는지 판단한다. Fixed Window의 경계 버스트 문제를 정확하게 해결하지만, 모든 요청의 타임스탬프를 개별적으로 저장해야 해서 트래픽이 많을수록 메모리 사용량이 커진다는 단점이 있다. 이 둘을 절충한 것이 Sliding Window Counter로, 이전 창과 현재 창의 카운트를 가중 평균해 로그 전체를 저장하지 않고도 근사적으로 경계 문제를 완화한다.

| 알고리즘 | 경계 정확도 | 메모리 사용량 | 버스트 허용 |
|---|---|---|---|
| Fixed Window | 낮음 (경계에서 최대 2배 통과 가능) | 매우 낮음 | 창 경계에서만 과도하게 허용 |
| Token Bucket | 중간 (설계상 의도된 버스트) | 낮음 | 버킷 용량만큼 의도적으로 허용 |
| Sliding Window Log | 높음 (정확) | 높음 (요청마다 로그) | 정밀하게 제한 |
| Sliding Window Counter | 높음에 근접 (근사) | 낮음 | 정밀에 가깝게 근사 |

## 예제 — Redis로 구현하는 Token Bucket (Lua 스크립트)

```lua
-- KEYS[1]: 버킷 키, ARGV[1]: 버킷 용량, ARGV[2]: 초당 토큰 채움 속도, ARGV[3]: 현재 시각
local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or tonumber(ARGV[1])
local last_refill = tonumber(bucket[2]) or tonumber(ARGV[3])

local elapsed = tonumber(ARGV[3]) - last_refill
local refill = elapsed * tonumber(ARGV[2])
tokens = math.min(tonumber(ARGV[1]), tokens + refill)

if tokens < 1 then
    redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', ARGV[3])
    return 0  -- 거부
else
    tokens = tokens - 1
    redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', ARGV[3])
    return 1  -- 허용
end
```

이 로직을 Lua 스크립트로 Redis에서 원자적으로 실행하면, 여러 인스턴스가 동시에 같은 키에 접근하더라도 읽기-계산-쓰기 사이의 경쟁 조건(race condition) 없이 정확하게 토큰을 소비할 수 있다.

## 실무 포인트

- **API 특성에 따라 알고리즘을 다르게 골라라.** 결제나 로그인처럼 정밀한 제한이 중요한 API는 Sliding Window 계열이, 검색이나 조회처럼 순간적인 버스트를 어느 정도 허용해도 되는 API는 Token Bucket이 더 적합한 경우가 많다.
- **레이트 리미팅 로직은 반드시 원자적 연산으로 구현하라.** Redis에서 GET 후 SET을 별도 명령으로 나눠 호출하면 동시 요청 사이에 경쟁 조건이 생겨 제한이 새어나갈 수 있으므로, Lua 스크립트나 Redis의 원자적 자료구조를 활용해야 한다.
- **클라이언트에게 제한 상태를 명시적으로 알려라.** `X-RateLimit-Remaining`, `Retry-After` 같은 응답 헤더를 표준적으로 내려주면, 클라이언트가 자체적으로 백오프하도록 유도할 수 있어 불필요한 재시도 폭주를 줄일 수 있다.

## 마무리 요약

- Fixed Window는 구현이 단순하지만 창 경계에서 의도한 제한의 최대 2배까지 통과시키는 구조적 결함이 있다.
- Token Bucket은 의도된 버스트를 허용하며 처리량을 장기적으로 수렴시키고, Sliding Window Log는 정확하지만 메모리 비용이 크며 Sliding Window Counter가 그 사이를 근사적으로 절충한다.
- 분산 환경에서는 반드시 원자적 연산(Lua 스크립트 등)으로 구현해야 여러 인스턴스가 공유하는 카운터의 경쟁 조건을 막을 수 있다.

## 참고 자료

- [Cloudflare - How we built rate limiting capable of scaling to millions of domains](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
- [Redis - Rate limiting patterns](https://redis.io/docs/latest/develop/use/patterns/rate-limiter/)
