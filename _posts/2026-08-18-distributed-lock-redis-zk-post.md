---
layout: single
title: "분산 락 구현 비교 — Redis Redlock vs ZooKeeper, 무엇을 선택할 것인가"
date: 2026-08-18 13:45:00 +0530
categories: system-design
tags: ["distributed-lock", "redis", "redlock", "zookeeper", "system-design"]
toc: true
toc_sticky: true
excerpt: "여러 서버 인스턴스가 같은 리소스에 동시 접근할 때 필요한 분산 락을 Redis Redlock과 ZooKeeper 방식으로 각각 구현해보고, 일관성·가용성·복잡도 관점에서 언제 무엇을 선택해야 하는지 비교한다."
---

## 왜 지금 분산 락인가

인스턴스가 하나였을 때는 `synchronized`나 `ReentrantLock` 같은 언어 차원의 락으로 충분했다. 하지만 서비스를 여러 대의 서버로 수평 확장하는 순간, 이 락들은 각 프로세스 안에서만 유효하다는 근본적인 한계가 드러난다. 재고 차감, 쿠폰 발급, 배치 작업 중복 실행 방지처럼 "여러 인스턴스 중 오직 하나만 이 작업을 수행해야 한다"는 요구사항은 프로세스 경계를 넘어서는 락, 즉 **분산 락(Distributed Lock)** 없이는 해결되지 않는다.

분산 락을 구현하는 방법은 여러 가지지만, 실무에서 가장 자주 비교 대상에 오르는 두 축은 **Redis 기반 Redlock**과 **ZooKeeper 기반 락**이다. 둘 다 "락을 어딘가에 저장하고, 획득·해제를 조율한다"는 목표는 같지만, 이를 달성하는 방식과 그로 인한 트레이드오프가 완전히 다르다. 이미 캐시용 Redis를 운영 중이라 추가 인프라 없이 락을 붙이고 싶은 팀과, 정합성이 생명인 리소스를 다루는 팀의 선택은 갈릴 수밖에 없다.

## 핵심 개념 1: 분산 락에 요구되는 성질

분산 락이 실제로 안전하려면 최소 세 가지를 만족해야 한다. 첫째, 특정 시점에 한 클라이언트만 락을 보유해야 한다(상호 배제). 둘째, 락을 획득한 클라이언트가 죽거나 응답을 멈춰도 시스템 전체가 영구히 멈추면 안 된다(데드락 방지). 셋째, 락을 실제로 획득한 클라이언트만 해제할 수 있어야 한다. 이 세 가지 균형을 어떻게 잡느냐에서 Redlock과 ZooKeeper는 서로 다른 길을 택한다.

<img src="/assets/images/posts/2026-08-18-distributed-lock-redis-zk-1.svg" alt="Redis Redlock과 ZooKeeper의 분산 락 획득·해제 흐름 비교도" style="width:100%;">

## 핵심 개념 2: Redis Redlock — TTL 기반 낙관적 접근

Redlock은 서로 독립된 N개(홀수, 통상 5개)의 Redis 인스턴스에 동일한 키를 `SET key value NX PX ttl`로 동시에 설정 시도하고, **과반수(예: 3/5)** 가 성공하면 락을 획득한 것으로 간주하는 방식이다. 클라이언트가 살아있는 동안 락을 계속 쥐고 있는 게 아니라, TTL이라는 "시간 예산"을 미리 걸어두고 그 안에 작업을 끝내는 것을 전제로 한다. 그래서 별도의 코디네이터 클러스터 없이, 이미 쓰고 있는 Redis 몇 대만으로 빠르게 도입할 수 있다는 것이 가장 큰 매력이다.

다만 TTL 기반이라는 점 자체가 약점이기도 하다. GC 정지, 네트워크 지연, 클록 드리프트로 인해 클라이언트가 작업을 끝내기 전에 TTL이 만료되면, 다른 클라이언트가 같은 락을 획득해 두 클라이언트가 동시에 임계 구역에 들어가는 상황이 이론적으로 가능하다. 이 문제는 Redlock 알고리즘 자체의 안전성에 대한 논쟁으로 이어진 바 있어("고칠 수 없는 결함이다" vs "실무적으로 충분하다"), 도입 전에 이 논쟁의 존재를 인지하고 있는 것이 중요하다.

## 핵심 개념 3: ZooKeeper — 합의 기반 순번 대기열

ZooKeeper는 **순번이 매겨진 임시(ephemeral) znode**를 이용해 락을 구현한다. 클라이언트는 `/lock/lock-` 접두사로 순번이 자동 부여되는 znode를 생성하고, 자신보다 순번이 낮은 znode가 없으면 락을 획득한 것으로 본다. 낮은 순번이 있다면 바로 앞 순번의 znode만 watch해 대기한다(공평한 대기열 구조). 락을 쥔 클라이언트의 세션이 끊기면 임시 znode가 ZooKeeper에 의해 자동 삭제되므로, TTL을 추측할 필요 없이 장애가 즉시 반영된다.

이 방식은 ZooKeeper 앙상블 자체가 ZAB(ZooKeeper Atomic Broadcast) 합의 프로토콜로 강한 일관성을 보장하기 때문에, Redlock처럼 "과반수 성공을 락 획득으로 간주"하는 낙관적 판단이 아니라 앙상블이 확정한 순서를 그대로 신뢰할 수 있다. 대신 별도의 ZooKeeper 클러스터를 구축·운영해야 하고, 쓰기 처리량이 Redis보다 낮아 락 획득·해제가 매우 빈번한 고QPS 상황에는 부담이 될 수 있다.

| 항목 | Redis Redlock | ZooKeeper |
|---|---|---|
| 일관성 모델 | 과반수 기반 낙관적 추정 | 합의(ZAB) 기반 강한 일관성 |
| 장애 감지 방식 | TTL 만료(시간 추정) | 세션 종료 시 즉시 삭제 |
| 대기 순서 보장 | 없음(재시도 경쟁) | 순번 기반 공평한 대기열 |
| 인프라 부담 | 기존 Redis 재사용 가능 | 별도 앙상블 구축·운영 필요 |
| 처리량 | 높음 | 상대적으로 낮음 |
| 적합한 상황 | 대략적 중복 실행 방지, 캐시 갱신 | 강한 정합성이 필요한 코디네이션 |

## 예제 1: Redisson으로 Redis 분산 락 구현 (Java)

```java
RedissonClient redisson = Redisson.create(config);
RLock lock = redisson.getLock("inventory:item:1001");

boolean acquired = false;
try {
    // 최대 10초 대기, 획득 후 30초 지나면 자동 해제(TTL)
    acquired = lock.tryLock(10, 30, TimeUnit.SECONDS);
    if (acquired) {
        // 임계 구역: 재고 차감 등 단일 실행 보장이 필요한 로직
        decreaseStock(itemId);
    }
} finally {
    if (acquired) {
        lock.unlock();
    }
}
```

Redisson은 내부적으로 락을 쥔 클라이언트가 살아있는 동안 TTL을 자동 연장(watchdog)해주기 때문에, 순수 Redlock 스펙보다 실무에서 다루기 쉽다. 다만 watchdog도 결국 네트워크와 타이밍에 의존하므로 절대적 안전 보장은 아니라는 점은 동일하다.

## 예제 2: Curator로 ZooKeeper 분산 락 구현 (Java)

```java
CuratorFramework client = CuratorFrameworkFactory.newClient(
    "zk1:2181,zk2:2181,zk3:2181", new ExponentialBackoffRetry(1000, 3));
client.start();

InterProcessMutex lock = new InterProcessMutex(client, "/locks/inventory-item-1001");

if (lock.acquire(10, TimeUnit.SECONDS)) {
    try {
        decreaseStock(itemId);
    } finally {
        lock.release();
    }
}
```

Curator의 `InterProcessMutex`가 순번 znode 생성·watch·삭제를 캡슐화해주므로, 개발자는 저수준 znode 조작 없이 표준 락 API처럼 사용할 수 있다.

## 실무 포인트

- **정합성 요구 수준으로 먼저 판단한다**: "가끔 중복 실행돼도 재시도로 복구 가능"이면 Redlock, "절대 두 번 실행되면 안 된다"면 ZooKeeper(또는 DB 기반 락 + 트랜잭션) 쪽이 안전하다.
- **펜싱 토큰을 병행 고려한다**: 어느 방식이든 락 보유 중 처리 지연이 발생하면 위험이 남으므로, 락 획득 시 증가하는 토큰 값을 리소스 접근 시점에 함께 검증하면 안전성을 한 단계 더 높일 수 있다.
- **이미 있는 인프라를 우선 활용한다**: ZooKeeper를 이미 Kafka 등에서 운영 중이면 락 도입 비용이 낮아지고, Redis만 있다면 Redlock이 실용적 출발점이 된다.
- **성능 수치는 환경마다 다르므로 벤치마크 없이 단정하지 않는다**: 네트워크 토폴로지, 인스턴스 사양, 락 경합 빈도에 따라 결과가 크게 갈리므로 실제 트래픽 패턴으로 직접 검증하는 것이 안전하다.

## 3줄 요약

- 분산 락은 상호 배제·데드락 방지·안전한 해제 세 가지를 프로세스 경계 너머에서 보장해야 하며, Redlock과 ZooKeeper는 이를 각각 TTL 추정과 합의 기반 확정이라는 다른 방식으로 풀어낸다.
- Redlock은 기존 Redis를 재사용해 빠르게 도입할 수 있지만 시간 기반 추정이라는 근본적 한계가 있고, ZooKeeper는 강한 일관성과 공평한 대기열을 제공하는 대신 별도 앙상블 운영 부담이 따른다.
- 선택은 요구되는 정합성 수준과 기존 인프라 구성으로 결정하며, 어느 쪽이든 펜싱 토큰 같은 보조 장치로 안전성을 보강하는 것이 바람직하다.

## 참고 자료

- [Redis — Distributed Locks with Redis (Redlock)](https://redis.io/docs/latest/develop/use/patterns/distributed-locks/)
- [Martin Kleppmann — How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
- [Apache ZooKeeper — Recipes and Solutions: Locks](https://zookeeper.apache.org/doc/current/recipes.html#sc_recipes_Locks)
- [Apache Curator — Recipes: Shared Reentrant Lock](https://curator.apache.org/curator-recipes/shared-reentrant-lock.html)
- [Redisson — Distributed Locks and Synchronizers](https://github.com/redisson/redisson/wiki/8.-distributed-locks-and-synchronizers)
