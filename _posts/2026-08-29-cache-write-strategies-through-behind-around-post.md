---
layout: single
title: "쓸 때도 전략이 필요하다 — write-through/write-behind/write-around 캐시 쓰기 전략 비교"
date: 2026-08-29 13:45:00 +0530
categories: system-design
tags: ["caching", "write-through", "write-behind", "write-around", "system-design", "redis"]
toc: true
toc_sticky: true
excerpt: "캐시 읽기 전략(cache-aside 등)은 흔히 논의되지만, 쓰기 시점에 캐시와 DB를 어떤 순서로 갱신할지를 결정하는 write-through·write-behind·write-around 전략의 차이와 트레이드오프를 정리한다."
---

캐싱을 이야기할 때 대부분의 논의는 "캐시 미스 시 어떻게 채울 것인가", 즉 읽기 전략(cache-aside, read-through)에 집중된다. 하지만 쓰기 경로는 별개의 문제다. 데이터가 갱신될 때 캐시와 원본 저장소(DB) 중 어디를 먼저, 어떻게 갱신할지에 따라 데이터 일관성·쓰기 지연·캐시 신선도가 완전히 달라진다. 이 결정을 다루는 것이 write-through, write-behind(write-back), write-around라는 세 가지 캐시 쓰기 전략이다.

세 전략 모두 "캐시와 DB, 두 저장소를 일관되게 유지하면서 성능도 챙긴다"는 같은 목표를 갖지만, 그 균형점을 완전히 다른 곳에 둔다. 이 글에서는 각 전략의 동작 방식과, 어떤 워크로드에 어떤 전략이 맞는지를 정리한다.

## 핵심 개념 1: write-through — 캐시와 DB를 항상 함께 쓴다

write-through는 가장 단순하고 안전한 전략이다. 쓰기 요청이 오면 **캐시와 DB에 동시에(또는 순차적으로 둘 다) 쓰기를 완료한 뒤에야 응답을 반환**한다. 이 방식의 장점은 캐시가 항상 DB와 동기화된 상태를 유지한다는 것이다. 캐시에 있는 데이터는 곧 DB에도 반영된 데이터이므로, 캐시 미스가 나더라도 최신 데이터를 DB에서 그대로 가져올 수 있다.

대가는 쓰기 지연이다. 매 쓰기마다 두 저장소에 모두 쓰기를 완료해야 하므로, 쓰기 요청의 응답 시간이 두 저장소 중 느린 쪽에 좌우된다. 쓰기가 잦고 지연에 민감한 서비스라면 이 오버헤드가 누적될 수 있다.

## 핵심 개념 2: write-behind(write-back) — 캐시부터 응답하고 DB는 비동기로

write-behind는 정반대 방향으로 균형을 옮긴다. 쓰기 요청이 오면 **캐시에만 즉시 쓰고 응답을 반환**한 뒤, DB 반영은 별도의 큐나 백그라운드 프로세스가 비동기로, 때로는 여러 건을 묶어(batch) 처리한다. 쓰기 응답 속도가 캐시 쓰기 속도만큼 빨라지고, DB에 대한 쓰기 부하도 배칭을 통해 줄일 수 있다는 것이 강점이다.

문제는 캐시에만 반영되고 아직 DB에 반영되지 않은 상태에서 캐시 노드가 장애로 죽으면, 그 사이의 쓰기가 유실될 수 있다는 것이다. 이 위험을 감수할 수 있는 워크로드(조회수 카운터, 실시간 랭킹처럼 일부 유실이 치명적이지 않은 데이터)에 적합하고, 금융 거래처럼 유실이 허용되지 않는 데이터에는 write-behind만 단독으로 쓰기 어렵다. 실무에서는 캐시 계층 자체에 영속성(예: Redis AOF)을 두거나, WAL 방식으로 쓰기를 먼저 로그에 남기는 보완책을 함께 쓰는 경우가 많다.

## 핵심 개념 3: write-around — 캐시를 건너뛰고 DB에만 쓴다

write-around는 쓰기 시점에 **캐시를 아예 건드리지 않고 DB에만 쓴다.** 이후 그 데이터를 읽을 때는 캐시 미스가 나고, 그때 비로소 cache-aside 패턴처럼 DB에서 읽어와 캐시를 채운다. 이 전략은 "쓰긴 했지만 곧바로 다시 읽히지 않을 가능성이 높은 데이터"에 적합하다. 예를 들어 대량으로 적재되는 로그성 데이터나, 한 번 쓰고 나서 한동안 접근되지 않는 데이터라면, 쓸 때마다 캐시를 갱신하는 비용이 낭비가 된다.

반대로 "쓰고 나서 바로 다시 읽히는" 워크로드에 write-around를 쓰면 첫 조회가 항상 캐시 미스로 시작되어 지연이 늘어나는 결과를 낳는다. 즉 write-around는 쓰기와 읽기의 시간적 근접성(temporal locality)이 낮은 데이터에 특화된 선택이다.

<img src="/assets/images/posts/2026-08-29-cache-write-strategies-through-behind-around-1.svg" alt="write-through는 캐시와 DB를 동시에 쓰고 응답, write-behind는 캐시만 쓰고 즉시 응답 후 DB는 비동기 반영, write-around는 DB만 쓰고 캐시는 갱신하지 않는 세 가지 흐름 비교" style="width:100%;">

| 구분 | write-through | write-behind | write-around |
|---|---|---|---|
| 쓰기 응답 시점 | 캐시+DB 모두 완료 후 | 캐시 완료 즉시(DB는 비동기) | DB 완료 후(캐시 미반영) |
| 쓰기 지연 | 높음(두 저장소 동기) | 낮음 | DB 단독 지연 |
| 캐시-DB 일관성 | 항상 동기화 | 일시적 불일치 가능(비동기 반영 전) | 쓴 직후 캐시 미스 발생 |
| 장애 시 데이터 유실 위험 | 낮음 | 있음(캐시 장애 시 미반영분 유실) | 없음(DB에는 이미 반영) |
| 적합 워크로드 | 강한 일관성 필요, 쓰기 빈도 중간 | 쓰기 폭주, 일부 유실 허용 | 쓰기 후 재조회 드묾(로그성 데이터) |

## 예제: 세 전략의 의사코드 비교

```python
# write-through — 캐시와 DB를 함께 쓰고 둘 다 끝나야 응답
def write_through(key, value):
    db.write(key, value)
    cache.set(key, value)
    return "OK"  # 두 저장소 쓰기가 모두 끝난 뒤에만 반환

# write-behind — 캐시만 즉시 쓰고, DB 반영은 큐에 위임
def write_behind(key, value):
    cache.set(key, value)
    write_queue.push({"key": key, "value": value})  # 비동기 배치 처리 대상
    return "OK"  # DB 반영을 기다리지 않고 바로 응답

def write_behind_flush_worker():
    batch = write_queue.pop_batch(size=200)
    db.bulk_write(batch)   # 여러 건을 묶어 DB 부하 절감

# write-around — 캐시는 건드리지 않고 DB에만 반영
def write_around(key, value):
    db.write(key, value)
    cache.invalidate(key)  # 갱신이 아니라 무효화만 (다음 조회 시 캐시 미스 유도)
    return "OK"
```

## 실무 포인트

- **하나의 전략을 시스템 전체에 강제하지 않는다**: 같은 서비스 안에서도 데이터 성격에 따라 다른 쓰기 전략을 조합하는 것이 자연스럽다. 사용자 프로필처럼 강한 일관성이 필요한 데이터는 write-through, 조회수·좋아요 카운트처럼 유실을 감내할 수 있는 데이터는 write-behind로 나누는 식이다.
- **write-behind는 유실 허용 범위를 사전에 합의한다**: "몇 초 분량까지의 쓰기 유실은 허용 가능한가"를 팀 차원에서 명시적으로 정의하고, 그 범위를 벗어나면 WAL이나 메시지 큐의 영속성 보장(ack 기반 재처리)을 추가로 도입해야 한다.
- **write-around는 invalidate와 갱신을 혼동하지 않는다**: 쓰기 후 캐시를 미리 채우는(update) 대신 무효화(invalidate)만 하는 것이 write-around의 핵심이다. 무효화 대신 실수로 갱신 로직을 넣으면 사실상 write-through가 되어 버려, 애초에 write-around를 선택한 이유(쓰기 시 캐시 갱신 비용 회피)가 무의미해진다.

## 3줄 요약

- write-through는 캐시와 DB를 항상 함께 갱신해 일관성이 강하지만 쓰기 지연이 늘어나고, write-behind는 캐시만 즉시 쓰고 DB 반영은 비동기로 미뤄 지연은 줄지만 장애 시 유실 위험이 있다.
- write-around는 쓰기 시점에 캐시를 건드리지 않고 DB에만 반영해, 쓰기 후 곧바로 재조회되지 않는 데이터에 적합하지만 첫 조회는 항상 캐시 미스로 시작된다.
- 세 전략은 배타적이지 않으며, 데이터 성격(일관성 요구 수준, 유실 허용 범위, 쓰기-읽기 시간적 근접성)에 따라 시스템 안에서 함께 조합해 쓰는 것이 실무의 표준이다.

## 참고 자료

- [AWS 공식 문서: Caching Strategies (Write-through/Write-behind)](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Strategies.html)
- [Redis 공식 문서: Caching Patterns](https://redis.io/docs/latest/develop/use/patterns/)
- [Google Cloud 아키텍처 센터: Caching strategies](https://cloud.google.com/architecture/caching-strategies)
