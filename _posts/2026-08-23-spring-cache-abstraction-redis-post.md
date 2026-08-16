---
layout: single
title: "@Cacheable 한 줄이 전부가 아니다 — Spring 캐시 추상화 + Redis 실전 설정"
date: 2026-08-23 13:25:00 +0530
categories: backend
tags: ["spring", "redis", "cacheable", "직렬화", "ttl", "캐시"]
toc: true
toc_sticky: true
excerpt: "Spring 캐시 추상화에 Redis를 붙일 때 반드시 짚어야 할 세 가지 — 직렬화 방식 교체, 캐시별 TTL 설계, 캐시 스탬피드 방지 — 를 복붙 가능한 설정 코드와 함께 정리한다."
---

조회 API가 느려지면 가장 먼저 떠오르는 처방이 캐시다. Spring 진영에서는 메서드에 `@Cacheable` 하나만 붙이면 반환값이 캐시에 저장되고, 같은 인자로 다시 호출하면 메서드 본문을 건너뛴 채 캐시된 값이 반환된다. `RedisTemplate`으로 get/set을 직접 짜던 코드와 비교하면 비즈니스 로직에서 캐싱 관심사가 완전히 분리되니, 도입 장벽이 아주 낮아 보인다.

문제는 이 낮은 장벽이 착시라는 점이다. Spring Boot에 Redis 의존성을 넣고 `@EnableCaching`만 켠 기본 상태는 JDK 직렬화로 사람이 읽을 수 없는 바이너리를 저장하고, TTL은 무기한이며, 캐시가 만료되는 순간 몰려든 요청이 전부 DB로 쏟아지는 것을 막아주지도 않는다. 이 글은 `@Cacheable`을 운영 환경에 올리기 전에 반드시 손봐야 할 세 가지 — 직렬화, TTL, 스탬피드 방지 — 를 실제 설정 코드와 함께 정리한다. 캐시 스탬피드의 일반 이론은 [이전 글](/system-design/cache-stampede-post/)에서 다뤘으니, 여기서는 Spring 구현 관점에 집중한다.

<img src="/assets/images/posts/2026-08-23-spring-cache-abstraction-redis-1.svg" alt="@Cacheable과 Redis의 요청 처리 흐름: 캐시 HIT 시 즉시 반환, MISS 시 sync 락을 거쳐 DB 조회 후 TTL과 지터를 적용해 저장" style="width:100%;">

## 동작 원리 먼저: AOP 프록시라는 사실이 모든 함정의 출발점

`@Cacheable`은 마법이 아니라 AOP다. Spring 컨테이너가 대상 빈을 프록시로 감싸고, 외부에서 그 빈을 호출할 때 프록시가 먼저 캐시를 조회한 뒤 미스일 때만 실제 메서드로 위임한다. 이 구조에서 바로 가장 흔한 함정이 나온다.

**안티패턴: 같은 클래스 안에서의 자기 호출(self-invocation).** 아래 코드에서 `getProductList()`가 내부적으로 `this.getProduct(id)`를 호출하면 캐시는 전혀 동작하지 않는다. `this`는 프록시가 아닌 원본 객체이므로 캐싱 어드바이스가 끼어들 지점이 없기 때문이다. 로그에는 아무 에러도 없이, DB 쿼리만 조용히 반복된다.

```java
@Service
public class ProductService {

    @Cacheable(cacheNames = "product", key = "#id")
    public ProductDto getProduct(Long id) { /* DB 조회 */ }

    public List<ProductDto> getProductList(List<Long> ids) {
        // 잘못된 코드: this 경유 호출은 프록시를 우회해 캐시가 무시된다
        return ids.stream().map(this::getProduct).toList();
    }
}
```

올바른 대안은 캐시 대상 메서드를 별도 빈으로 분리해 주입받아 호출하는 것이다. 같은 이유로 `private` 메서드나 `final` 메서드에 붙인 `@Cacheable`도 동작하지 않는다.

## 직렬화: 기본값 그대로 두면 나중에 반드시 후회한다

Spring Data Redis의 캐시 기본 직렬화는 JDK 직렬화다. 값 클래스가 `Serializable`을 구현해야 하고, 저장된 바이트는 `redis-cli`로 들여다볼 수 없으며, 클래스 필드가 바뀌면 배포 직후 기존 캐시 역직렬화가 `SerializationException`으로 터진다. 실무에서는 JSON 계열로 교체하는 것이 사실상 표준이다.

| 직렬화 방식 | 가독성 | 클래스 변경 내성 | 주의점 |
|---|---|---|---|
| JDK 직렬화 (기본값) | 없음 | 매우 취약 | `Serializable` 강제, 운영 디버깅 곤란 |
| `GenericJackson2JsonRedisSerializer` | JSON | 비교적 양호 | 타입 정보(`@class`)가 함께 저장됨 |
| `Jackson2JsonRedisSerializer<T>` | JSON | 양호 | 캐시마다 타입 고정 필요, 다형성 미지원 |
| 문자열 + 수동 변환 | JSON | 좋음 | 추상화 이점이 줄고 보일러플레이트 증가 |

범용으로는 `GenericJackson2JsonRedisSerializer`가 무난하다. 단, JSON에 `@class` 필드로 FQCN이 저장되므로 패키지 이동·클래스 리네임이 곧 캐시 호환성 깨짐이라는 점은 기억해야 한다. 스키마가 바뀌는 배포에서는 캐시 이름에 버전 접미사(`product:v2`)를 붙여 구버전 캐시와 자연스럽게 분리하는 방법이 실용적이다.

## TTL 설계: 캐시 이름별로 다르게, 그리고 무기한 금지

기본 설정의 TTL은 무기한이다. 갱신 로직(`@CacheEvict`)이 한 군데라도 빠지면 낡은 데이터가 영원히 남는다는 뜻이다. TTL은 "이 데이터가 최대 얼마나 오래되어도 서비스가 견딜 수 있는가"를 기준으로 캐시 이름별로 다르게 잡아야 한다. 아래는 직렬화 교체와 캐시별 TTL을 한 번에 처리하는 설정이다.

```java
import java.time.Duration;
import java.util.Map;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext.SerializationPair;
import org.springframework.data.redis.serializer.StringRedisSerializer;

@Configuration
@EnableCaching
public class RedisCacheConfig {

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
        RedisCacheConfiguration base = RedisCacheConfiguration.defaultCacheConfig()
                .serializeKeysWith(SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()))
                .disableCachingNullValues()
                .entryTtl(Duration.ofMinutes(5));  // 지정하지 않은 캐시의 기본 TTL

        return RedisCacheManager.builder(factory)
                .cacheDefaults(base)
                .withInitialCacheConfigurations(Map.of(
                        "product",  base.entryTtl(Duration.ofMinutes(30)),
                        "ranking",  base.entryTtl(Duration.ofSeconds(60)),
                        "codeMeta", base.entryTtl(Duration.ofHours(12))
                ))
                .build();
    }
}
```

`disableCachingNullValues()`는 양날의 검이다. null 캐싱을 막으면 "존재하지 않는 키"를 반복 조회하는 캐시 관통(cache penetration)에 무방비가 되므로, 없는 데이터 조회가 잦은 캐시라면 오히려 null을 짧은 TTL로 캐싱하는 편이 낫다. 일괄 적용하지 말고 캐시 성격별로 판단하자.

## 스탬피드 방지: sync=true의 효용과 명확한 한계

인기 키의 TTL이 만료되는 순간, 대기하던 요청 수백 개가 동시에 캐시 미스를 맞고 전부 DB로 향하는 것이 캐시 스탬피드다. Spring이 제공하는 1차 방어선은 `@Cacheable(sync = true)`다. 같은 키에 대한 동시 호출 중 하나만 메서드를 실행하고 나머지는 그 결과를 기다리게 한다.

```java
@Cacheable(cacheNames = "ranking", key = "#category", sync = true)
public RankingDto getRanking(String category) {
    return rankingRepository.calculate(category); // 무거운 집계 쿼리
}
```

단, 이 락은 **JVM 프로세스 로컬**이다. 인스턴스가 10대라면 최악의 경우 10개의 요청이 동시에 DB를 때린다. 요청이 수만 단위로 몰리는 상황에서 10개로 줄어드는 것만으로도 충분한 경우가 대부분이므로, 복잡도를 높이기 전에 sync부터 켜는 것이 옳은 순서다. 그래도 부족하다면 TTL에 무작위 지터를 더해 여러 키의 만료 시점이 겹치지 않게 하고, 그 다음 단계로 분산 락(Redisson 등)이나 만료 전 비동기 재계산(logical expiration)을 검토한다. 뒤로 갈수록 운영 복잡도가 가파르게 오르니, 트래픽 근거 없이 미리 도입하지 않는 것이 좋다.

## 언제 쓰고, 언제 쓰지 말아야 하나

`@Cacheable`이 어울리는 곳은 읽기가 압도적으로 많고, 약간의 낡음(staleness)이 허용되며, 키-값 형태로 떨어지는 조회다. 상품 상세, 코드성 메타데이터, 랭킹 집계가 전형적이다. 반대로 잔액·재고처럼 정합성이 돈과 직결되는 데이터, 조건 조합이 많아 히트율이 낮은 검색 쿼리, 트랜잭션 안에서 갱신 직후 재조회가 일어나는 흐름에는 캐시 추상화가 오히려 버그의 온상이 된다. 특히 `@Transactional`과 함께 쓸 때 커밋 전에 캐시가 갱신되는 타이밍 문제가 있으므로, 쓰기 경로가 얽힌 데이터라면 캐시 계층 없이 DB 튜닝으로 해결하는 쪽이 단순하고 안전한 경우가 많다.

## 마무리 요약

- `@Cacheable`은 AOP 프록시로 동작한다 — 자기 호출·private 메서드에서는 조용히 무시되므로 캐시 대상은 별도 빈으로 분리한다.
- 기본 JDK 직렬화와 무기한 TTL은 운영 사고의 예약이다 — `GenericJackson2JsonRedisSerializer`와 캐시 이름별 TTL을 첫 배포 전에 설정한다.
- 스탬피드 방어는 `sync = true` → TTL 지터 → 분산 락/논리적 만료 순으로, 트래픽 근거가 생길 때마다 한 단계씩 올린다.

## 참고 자료

- [Spring Framework — Cache Abstraction](https://docs.spring.io/spring-framework/reference/integration/cache.html)
- [Spring Boot — Caching](https://docs.spring.io/spring-boot/reference/io/caching.html)
- [Spring Data Redis — Redis Cache](https://docs.spring.io/spring-data/redis/reference/redis/redis-cache.html)
