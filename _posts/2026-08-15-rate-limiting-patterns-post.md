---
layout: single
title: "레이트 리밋 구현 패턴 — 토큰 버킷부터 분산 환경까지"
date: 2026-08-15 21:40:00 +0530
categories: system-design
tags: ["레이트리밋", "시스템설계", "Redis", "APIGateway"]
toc: true
toc_sticky: true
excerpt: "토큰버킷·리키버킷·슬라이딩윈도우 알고리즘을 비교하고 단일 서버와 분산 환경에서의 구현 방식을 정리한다."
---

## 왜 지금 이 이야기인가

API를 외부에 개방하거나 마이크로서비스 간 호출이 늘어날수록 "누군가 과도하게 호출해서 시스템 전체가 흔들리는" 상황을 피할 수 없다. 특히 LLM API처럼 요청 단가가 비싼 서비스가 늘면서 레이트 리밋은 단순한 방어 로직을 넘어 비용 관리 수단으로도 쓰이고 있다. 문제는 알고리즘 선택과 구현 위치(애플리케이션 코드 vs 게이트웨이)에 따라 정확성과 운영 난이도가 크게 달라진다는 점이다. 단일 서버에서는 잘 동작하던 로직이 서버를 여러 대로 늘리는 순간 카운트가 어긋나는 경우도 흔하다.

## 핵심 개념: 알고리즘 비교

| 알고리즘 | 동작 방식 | 버스트 허용 | 구현 난이도 |
|---|---|---|---|
| 고정 윈도우(Fixed Window) | 일정 시간 구간마다 카운터 리셋 | 경계에서 2배 버스트 가능 | 매우 쉬움 |
| 슬라이딩 윈도우 로그 | 요청 타임스탬프를 모두 기록 | 정확함 | 메모리 사용량 큼 |
| 슬라이딩 윈도우 카운터 | 이전/현재 윈도우 가중 평균 | 근사적으로 정확 | 중간 |
| 토큰 버킷(Token Bucket) | 버킷에 토큰이 일정 속도로 채워짐 | 허용(버스트 처리에 유리) | 중간 |
| 리키 버킷(Leaky Bucket) | 큐에 쌓고 일정 속도로만 처리 | 평탄화(버스트 억제) | 중간 |

토큰 버킷은 "평균 처리율은 제한하되 순간적인 버스트는 어느 정도 허용하고 싶을 때" 적합하고, 리키 버킷은 "출력 속도 자체를 항상 일정하게 유지하고 싶을 때" 적합하다. API 게이트웨이에서는 대체로 토큰 버킷 계열이 많이 쓰이는 것으로 보인다.

## 단일 서버 vs 분산 환경 구현

단일 프로세스에서는 메모리 내 카운터나 락 없는 자료구조로 충분하다. 하지만 서버가 여러 대이거나 오토스케일링이 걸려 있으면 각 인스턴스가 독립적으로 카운트를 관리해 실제 허용량보다 훨씬 많은 요청이 통과할 수 있다. 이 문제를 해결하려면 Redis 같은 중앙 저장소에 원자적 연산(INCR + EXPIRE, 또는 Lua 스크립트)으로 카운터를 두는 방식이 널리 쓰인다. Redis는 단일 스레드로 명령을 처리하므로 Lua 스크립트로 "토큰 확인 후 차감"을 한 번의 원자적 연산으로 묶을 수 있다.

## 예제

```lua
-- Redis Lua 스크립트: 토큰 버킷 방식 레이트 리밋 (개념 예시)
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- 초당 토큰 수
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local delta = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + delta * refill_rate)

if tokens >= 1 then
  tokens = tokens - 1
  redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
  redis.call("EXPIRE", key, 60)
  return 1
else
  redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
  return 0
end
```

```python
import redis
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def is_allowed(client_id: str, limit: int = 100, window_sec: int = 60) -> bool:
    key = f"rl:{client_id}:{int(time.time() // window_sec)}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_sec)
    return count <= limit
```

## 실무 포인트와 주의사항

- 클라이언트에게는 429 Too Many Requests와 함께 `Retry-After` 헤더를 반환해 언제 재시도하면 되는지 명확히 알려주는 것이 좋다.
- 사용자 등급별, 엔드포인트별로 정책을 다르게 두는 경우가 많다 — 예를 들어 쓰기 API는 읽기 API보다 훨씬 낮은 한도를 두는 식이다.
- API 게이트웨이(Kong, Envoy, nginx 등) 레벨에서 1차 방어를 걸고, 애플리케이션 레벨에서 더 세밀한 정책(사용자별 쿼터 등)을 얹는 이중 구조가 흔히 쓰인다.
- 분산 환경에서 Redis에 의존하면 Redis 자체가 장애 지점이 될 수 있으므로, Redis 장애 시 fail-open(허용) 또는 fail-closed(차단) 중 어떤 전략을 쓸지 미리 정해둬야 한다.

## 3줄 요약

- 토큰 버킷은 버스트를 허용하고 리키 버킷은 출력을 평탄화한다는 차이를 이해하고 상황에 맞게 골라야 한다.
- 분산 환경에서는 로컬 메모리 카운터 대신 Redis 등 중앙 저장소의 원자적 연산으로 정확한 카운팅을 보장해야 한다.
- 429 응답과 Retry-After, 등급별/엔드포인트별 정책 설계까지 함께 고려해야 실무에서 안정적으로 동작한다.

## 참고 자료

- [Redis - Rate limiter pattern](https://redis.io/docs/latest/develop/use/patterns/rate-limiter/)
- [MDN - 429 Too Many Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429)
- [Kong Rate Limiting Plugin 공식 문서](https://docs.konghq.com/hub/kong-inc/rate-limiting/)
