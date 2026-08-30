---
layout: single
title: "분산 환경에서 Rate Limiting이 새는 이유 — 토큰 버킷과 슬라이딩 윈도우 카운터의 원자성 문제"
date: 2026-09-27 12:45:00 +0530
categories: system-design
tags: ["RateLimiting", "토큰버킷", "슬라이딩윈도우", "Redis", "분산시스템"]
toc: true
toc_sticky: true
excerpt: "단일 서버에서는 완벽했던 rate limiting 로직이 여러 인스턴스로 확장되는 순간 한도를 초과하는 이유와, Redis Lua 스크립트로 원자성을 확보하는 슬라이딩 윈도우 카운터 구현을 정리했다."
---

## 왜 분산 환경에서 Rate Limiting이 어려운가

싱글 인스턴스에서 메모리 변수 하나로 요청 수를 세는 rate limiter는 완벽하게 동작한다. 문제는 서비스를 스케일 아웃하는 순간 시작된다. 인스턴스가 5대라면 각 인스턴스가 독립적으로 카운트를 세게 되고, 로드밸런서가 요청을 고르게 분산시킨다는 전제 하에 설계한 "인스턴스당 한도 = 전체 한도 / 5"라는 계산은 실제 트래픽 패턴에서 쉽게 무너진다. 특정 클라이언트의 요청이 커넥션 재사용이나 라우팅 정책 때문에 한두 인스턴스에 몰리면, 그 인스턴스만 한도를 초과해서 통과시키거나 반대로 다른 클라이언트를 부당하게 차단한다. 결국 rate limiting을 정확하게 하려면 상태를 중앙화하거나, 중앙화된 저장소에서 원자적으로 카운트를 갱신해야 한다.

## 핵심 개념 1 — 알고리즘 선택: 고정 윈도우, 슬라이딩 윈도우, 토큰 버킷

가장 단순한 고정 윈도우(fixed window)는 "1분마다 카운터를 초기화"하는 방식인데, 윈도우 경계에서 버스트가 두 배로 통과하는 결함이 있다. 예를 들어 0:59에 한도만큼 요청이 몰리고 1:00에 카운터가 리셋되자마자 다시 한도만큼 몰리면, 실제로는 2초 사이에 한도의 두 배가 통과한다. 슬라이딩 윈도우 로그(sliding window log)는 모든 요청의 타임스탬프를 저장해 정확하지만 메모리 비용이 크다. 실무에서 가장 널리 쓰이는 절충안은 **슬라이딩 윈도우 카운터**로, 현재 윈도우와 이전 윈도우의 카운트를 가중 평균해 근사치를 계산한다. 토큰 버킷(token bucket)은 여기에 더해 버스트를 일정 수준 허용하면서도 장기 평균 속도를 제한하고 싶을 때 선호된다.

| 알고리즘 | 정확도 | 메모리 비용 | 버스트 허용 |
|---|---|---|---|
| 고정 윈도우 | 낮음(경계 결함) | 최소 | 경계에서 의도치 않게 허용 |
| 슬라이딩 윈도우 로그 | 매우 높음 | 요청당 저장(높음) | 정밀 제어 |
| 슬라이딩 윈도우 카운터 | 근사치(충분히 정확) | 낮음 | 근사적으로 제어 |
| 토큰 버킷 | 높음 | 낮음 | 명시적으로 설정 가능 |

## 핵심 개념 2 — 분산 환경의 진짜 문제: 원자성

여러 인스턴스가 Redis 같은 공유 저장소에 카운트를 두더라도, "읽고 → 비교하고 → 증가시키는" 세 단계를 별도의 명령으로 실행하면 두 요청이 동시에 같은 값을 읽어 둘 다 통과시키는 경쟁 조건(race condition)이 생긴다. 이를 막으려면 이 세 단계를 하나의 원자적 연산으로 묶어야 한다. Redis에서는 Lua 스크립트가 표준적인 해법인데, Redis가 싱글 스레드로 스크립트를 실행하기 때문에 스크립트 내부의 모든 명령이 다른 클라이언트의 명령과 끼어들 여지 없이 순차 실행된다.

## 코드 예제 — Redis Lua 스크립트로 원자적 토큰 버킷 구현

```lua
-- KEYS[1]: 버킷 키, ARGV[1]: 버킷 용량, ARGV[2]: 초당 리필 속도, ARGV[3]: 현재 시각(초)
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- 경과 시간만큼 토큰 리필 (최대 capacity까지)
local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
    redis.call("EXPIRE", key, 3600)
    return 1  -- 허용
else
    redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
    return 0  -- 거부
end
```

이 스크립트를 `EVALSHA`로 호출하면 읽기·계산·쓰기가 하나의 원자적 단위로 실행되어, 인스턴스가 몇 대든 정확한 한도를 보장한다.

## 실무 포인트

- **로컬 캐시로 Redis 왕복을 줄이되 정확도와 트레이드오프하라.** 매 요청마다 Redis를 호출하면 지연이 늘어나므로, 대략적인 한도 초과 여부는 로컬에서 먼저 걸러내고(예: 로컬 한도를 전체 한도의 80%로 설정) 정밀한 최종 판단만 Redis에 위임하는 2단계 구조가 흔히 쓰인다.
- **시계 드리프트에 주의하라.** 여러 인스턴스의 시각이 미세하게 다르면 토큰 버킷의 리필 계산이 왜곡될 수 있으므로, 가능하면 Redis 서버의 `TIME` 명령으로 기준 시각을 통일하는 것이 안전하다.
- **한도 초과 응답에 `Retry-After` 헤더를 반드시 포함하라.** 클라이언트가 언제 다시 시도할 수 있는지 명시하지 않으면 즉시 재시도 폭주로 이어져 오히려 부하를 키운다.

## 마무리 요약

- 인스턴스별 독립 카운팅은 트래픽 분산이 불균등할 때 한도를 초과시키므로, 분산 rate limiting은 공유 저장소 기반의 중앙화된 카운트가 필요하다.
- 슬라이딩 윈도우 카운터와 토큰 버킷은 정확도와 메모리 비용의 합리적 절충안으로 실무에서 가장 널리 쓰인다.
- Redis Lua 스크립트로 읽기·계산·쓰기를 원자적으로 묶어야 여러 인스턴스가 동시에 같은 값을 읽는 경쟁 조건을 막을 수 있다.

## 참고 자료

- [Redis 공식 문서 — Rate limiting 패턴](https://redis.io/docs/manual/patterns/)
- [Cloudflare Blog — 슬라이딩 윈도우 카운터 알고리즘](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
