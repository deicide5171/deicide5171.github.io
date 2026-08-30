---
layout: single
title: "다단계 캐싱 아키텍처 — Write-Through와 Write-Behind 전략 비교"
date: 2026-09-24 13:45:00 +0530
categories: system-design
tags: ["캐싱전략", "WriteThrough", "WriteBehind", "다단계캐시", "캐시일관성"]
toc: true
toc_sticky: true
excerpt: "단일 Redis 캐시로는 한계에 부딪힌 대규모 트래픽 서비스에서 로컬 캐시-분산 캐시-DB로 이어지는 다단계 캐싱을 설계할 때, Write-Through와 Write-Behind 중 어떤 쓰기 전략을 선택해야 하는지 트레이드오프를 정리했다."
---

## 왜 지금 다단계 캐싱을 다시 봐야 하는가

읽기 트래픽이 늘어나면 가장 먼저 도입하는 것이 Redis 같은 분산 캐시다. 하지만 트래픽이 특정 임계치를 넘으면 분산 캐시 자체에 대한 네트워크 왕복(round trip)이 병목이 되는 순간이 온다. 이때 등장하는 것이 애플리케이션 프로세스 안에 두는 로컬(인메모리) 캐시를 앞단에 추가하는 다단계(multi-tier) 캐싱이다. 로컬 캐시 → 분산 캐시 → DB로 이어지는 계층을 만들면 대부분의 요청이 네트워크 홉 없이 로컬 캐시에서 끝나 지연시간이 극적으로 줄어든다.

문제는 계층이 늘어날수록 "쓰기가 발생했을 때 각 계층을 언제, 어떤 순서로 갱신할 것인가"라는 캐시 일관성 문제가 훨씬 복잡해진다는 점이다. Write-Through와 Write-Behind는 이 문제에 대한 두 가지 근본적으로 다른 접근이며, 어느 쪽을 택하느냐에 따라 일관성 보장 수준과 쓰기 지연시간이 크게 달라진다.

## 핵심 개념 1 — Write-Through: 캐시와 DB를 동기적으로 함께 쓴다

Write-Through는 쓰기 요청이 들어오면 캐시와 DB를 같은 트랜잭션 흐름 안에서 동기적으로 갱신하고, 두 곳 모두 쓰기가 성공한 뒤에야 클라이언트에 응답한다. 이 방식은 캐시와 DB 사이의 데이터가 항상 일치한다는 강한 보장을 준다는 것이 장점이다. 대신 쓰기 경로에 캐시 쓰기 지연시간이 그대로 더해지므로, 쓰기가 빈번한 워크로드에서는 전체 응답 시간이 늘어난다.

## 핵심 개념 2 — Write-Behind: 캐시만 먼저 쓰고 DB는 비동기로 반영한다

Write-Behind(Write-Back이라고도 한다)는 쓰기 요청이 오면 캐시만 즉시 갱신하고 클라이언트에 응답한 뒤, DB 반영은 별도의 백그라운드 큐나 배치 작업으로 나중에 처리한다. 쓰기 지연시간이 캐시 쓰기 수준으로 짧아진다는 것이 가장 큰 장점이며, 동일 키에 대한 짧은 시간 내 반복 쓰기를 배치로 묶어 DB 부하 자체를 줄이는 효과도 있다. 하지만 캐시에는 반영됐지만 DB에는 아직 반영되지 않은 시간 구간이 항상 존재하므로, 이 구간에 캐시 노드가 죽으면 데이터가 유실될 수 있다는 근본적인 위험을 안고 있다.

| 전략 | 쓰기 지연시간 | 일관성 보장 | 데이터 유실 위험 |
|---|---|---|---|
| Write-Through | 캐시+DB 쓰기 시간 합산 | 강함 (항상 동기화) | 낮음 |
| Write-Behind | 캐시 쓰기 시간만 | 약함 (지연된 동기화) | 있음 (캐시 장애 시) |
| Write-Around | DB만 쓰고 캐시는 무효화 | 중간 (다음 읽기에서 갱신) | 낮음 |

## 예제 — Write-Behind 큐 기반 구현 스케치

```java
@Service
public class ProductCacheService {

    private final BlockingQueue<WriteTask> writeQueue = new LinkedBlockingQueue<>();

    public void updateProduct(Long id, Product product) {
        // 1) 캐시는 즉시 갱신
        redisTemplate.opsForValue().set("product:" + id, product);
        // 2) DB 반영은 큐에 적재만 하고 즉시 반환
        writeQueue.offer(new WriteTask(id, product));
    }

    @Scheduled(fixedDelay = 500)
    public void flushToDatabase() {
        List<WriteTask> batch = new ArrayList<>();
        writeQueue.drainTo(batch, 100);
        if (!batch.isEmpty()) {
            productRepository.batchUpdate(batch); // 배치로 묶어 DB 부하 절감
        }
    }
}
```

## 실무 포인트

- **금융·결제처럼 데이터 유실이 허용되지 않는 도메인에는 Write-Behind를 쓰지 마라.** 캐시 장애 시 유실 가능성 자체를 제거해야 하는 경우 Write-Through가 유일한 선택지에 가깝다.
- **Write-Behind를 쓴다면 큐 자체의 내구성을 확보하라.** 인메모리 큐만 쓰면 애플리케이션 프로세스가 죽는 순간 큐에 있던 쓰기가 통째로 사라지므로, Kafka 같은 내구성 있는 메시지 큐를 백엔드로 두는 것이 안전하다.
- **다단계 캐싱에서는 각 계층의 TTL을 계층별로 다르게 가져가라.** 로컬 캐시 TTL을 분산 캐시보다 짧게 두면, 분산 캐시가 갱신된 뒤 로컬 캐시가 이를 반영하는 데 걸리는 지연을 최소화할 수 있다.

## 마무리 요약

- 다단계 캐싱은 대부분의 읽기를 네트워크 홉 없는 로컬 캐시에서 끝내 지연시간을 크게 줄이지만, 계층이 늘어날수록 쓰기 일관성 설계가 복잡해진다.
- Write-Through는 강한 일관성을, Write-Behind는 짧은 쓰기 지연시간을 대가로 데이터 유실 위험을 감수하는 트레이드오프 관계다.
- 도메인의 데이터 유실 허용 수준과 쓰기 빈도를 먼저 파악한 뒤 전략을 선택하고, Write-Behind를 쓴다면 큐의 내구성을 반드시 별도로 확보해야 한다.

## 참고 자료

- [AWS - Caching Patterns](https://aws.amazon.com/caching/best-practices/)
- [Redis - Write patterns](https://redis.io/docs/latest/develop/use/patterns/)
