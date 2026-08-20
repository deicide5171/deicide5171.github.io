---
layout: single
title: "Redis가 뭔가요 — 언제 캐시로 쓰고 언제 DB로 쓸까"
date: 2026-09-02 13:35:00 +0530
categories: database
tags: ["redis", "캐시", "인메모리db", "입문", "데이터베이스기초"]
toc: true
toc_sticky: true
excerpt: "Redis를 처음 접하면 헷갈리는 '캐시로 쓰는 것'과 'DB로 쓰는 것'의 차이를, 데이터 지속성과 사용 목적 기준으로 정리했다."
---

## Redis는 캐시인가 DB인가

Redis는 "인메모리 데이터 저장소"로 소개되는데, 실무에서는 캐시로도 쓰이고 어떤 팀은 아예 메인 DB처럼 쓰기도 한다. 둘 다 가능한 이유는 Redis가 메모리 기반이라 빠르면서도, 디스크에 데이터를 백업하는 기능(영속성)을 함께 제공하기 때문이다. 다만 "가능하다"와 "그렇게 써도 안전하다"는 다른 문제다.

## 캐시로 쓸 때 vs DB로 쓸 때

| 관점 | 캐시로 사용 | 주 DB로 사용 |
|---|---|---|
| 데이터 유실 허용 여부 | 유실돼도 원본 DB에서 다시 채우면 됨 | 유실되면 안 됨(영속성 설정 필수) |
| TTL(만료 시간) | 대부분의 키에 설정 | 명시적으로 관리하지 않으면 없음 |
| 데이터 원본 | 다른 DB(MySQL 등)가 원본 | Redis 자체가 원본 |
| 실무 비중 | 압도적으로 흔한 사용법 | 특정 용도(세션, 실시간 랭킹 등)에 한정 |

## 코드 예제: 캐시로 쓰는 전형적인 패턴

```python
def get_product(product_id, redis_client, db):
    cache_key = f"product:{product_id}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    product = db.query("SELECT * FROM products WHERE id = %s", product_id)
    redis_client.setex(cache_key, 300, json.dumps(product))  # 5분 TTL
    return product
```

`setex`로 TTL을 걸어두면 Redis 메모리가 무한히 쌓이지 않고, 원본 DB의 데이터가 바뀌어도 일정 시간 후 자동으로 갱신된다.

## Redis가 DB처럼 쓰이는 대표 사례

```text
1. 세션 저장소: 로그인 세션은 원본이 따로 없고 Redis 자체가 정본이다
2. 실시간 랭킹: Sorted Set 자료구조로 순위를 초저지연으로 계산
3. 분산 락: 여러 서버가 동시에 같은 자원에 접근하지 못하게 막는 용도
4. 메시지 브로커(Pub/Sub): 간단한 실시간 알림 전달
```

이런 경우에는 Redis 자체가 유일한 데이터 소스이므로, 데이터가 사라지면 복구할 원본이 없다. 그래서 이 용도로 쓸 때는 반드시 영속성 설정(RDB 스냅샷 또는 AOF)과 복제를 구성해야 한다.

## 실무 포인트

- **캐시 용도라면 영속성 설정에 크게 신경 쓰지 않아도 된다.** 서버가 재시작돼 캐시가 날아가도 원본 DB에서 다시 채워지기 때문이다.
- **DB 대체 용도로 쓴다면 반드시 백업과 복제를 갖춰야 한다.** 기본 설정 그대로 두면 서버 재시작 시 데이터가 통째로 사라질 수 있다.
- **메모리가 가득 차면 Redis는 설정된 정책(`maxmemory-policy`)에 따라 오래된 키를 자동으로 지운다.** 캐시 용도로는 이 동작이 자연스럽지만, 중요한 데이터를 저장하는 용도라면 이 정책이 예상치 못한 데이터 유실로 이어질 수 있다.

## 마무리 요약

- Redis는 캐시로도 DB로도 쓸 수 있지만, 두 용도는 영속성과 데이터 유실 허용 범위가 근본적으로 다르다.
- 캐시 용도는 TTL로 관리하고 원본 DB가 있어 유실돼도 복구 가능하다.
- DB 대체 용도(세션, 랭킹, 분산 락 등)로 쓸 때는 영속성과 복제 설정이 필수다.

## 참고 자료

- [Redis 공식 문서 - 영속성](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis 공식 문서 - 캐싱 패턴](https://redis.io/docs/latest/develop/use/patterns/)
