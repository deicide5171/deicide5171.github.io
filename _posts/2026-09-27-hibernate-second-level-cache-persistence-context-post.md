---
layout: single
title: "Hibernate 2차 캐시 딥다이브 — 영속성 컨텍스트 캐시와 무엇이 다른가"
date: 2026-09-27 13:25:00 +0530
categories: backend
tags: ["Hibernate", "JPA", "2차캐시", "영속성컨텍스트", "캐시전략"]
toc: true
toc_sticky: true
excerpt: "1차 캐시(영속성 컨텍스트)만 이해하고 2차 캐시를 켜면 트랜잭션 경계를 넘나드는 캐시 무효화 문제와 동시성 전략 선택이라는 완전히 다른 난이도의 고민을 만나게 된다. 2차 캐시의 동작 원리와 동시성 전략별 트레이드오프를 정리했다."
---

## 왜 1차 캐시와 완전히 다른 문제인가

JPA를 처음 배울 때 "같은 영속성 컨텍스트 안에서 같은 엔티티를 두 번 조회하면 캐시된다"는 1차 캐시(영속성 컨텍스트 캐시)를 배운다. 이건 트랜잭션 하나의 생명주기 안에서만 유효한, 단순하고 예측 가능한 캐시다. 문제는 실무에서 정말 필요한 것은 대개 이게 아니라 **여러 트랜잭션, 여러 요청, 심지어 여러 서버 인스턴스에 걸쳐** 자주 조회되지만 잘 바뀌지 않는 데이터(공통 코드 테이블, 상품 카탈로그 등)를 캐싱하는 것이다. 이 역할을 하는 것이 Hibernate 2차 캐시(second-level cache)이며, 1차 캐시와 달리 애플리케이션 전체 생명주기 동안 살아있고, 다른 트랜잭션이 캐시된 데이터를 변경했을 때 무효화까지 신경 써야 하는 완전히 다른 난이도의 문제가 된다.

## 핵심 개념 1 — 2차 캐시의 구조: 엔티티 캐시와 쿼리 캐시는 다르다

2차 캐시는 하나가 아니라 여러 영역으로 나뉜다. **엔티티 캐시**는 PK로 조회한 개별 엔티티를 캐싱하는데, 실제로는 엔티티 객체 자체가 아니라 필드값을 담은 "디하이드레이트된(dehydrated)" 형태로 저장된다(연관 엔티티는 참조가 아니라 ID만 저장). **컬렉션 캐시**는 `@OneToMany` 등의 연관관계가 담고 있는 ID 목록을 캐싱한다. **쿼리 캐시**는 JPQL/HQL 쿼리의 결과 집합(엔티티 ID 목록)을 캐싱하는데, 이는 기본적으로 꺼져 있으며 활성화해도 엔티티 캐시와 함께 조합해야 실질적인 이득이 있다. 이 세 영역이 각각 별도로 캐시 프로바이더(Ehcache, Infinispan, Caffeine 등)의 리전(region)에 저장되고 독립적으로 무효화된다.

## 핵심 개념 2 — 동시성 전략이 실제 데이터 안전성을 결정한다

2차 캐시를 켤 때 반드시 지정해야 하는 것이 동시성 전략(`@Cache(usage = ...)`)이다. `READ_ONLY`는 절대 변경되지 않는 데이터(공통 코드 등)에만 써야 하며, 변경 시도 자체가 예외를 던진다. `READ_WRITE`는 쓰기 잠금을 이용해 캐시와 DB 간 정합성을 맞추는 소프트 락 방식으로, 대부분의 읽기 위주 가변 데이터에 적합하다. `NONSTRICT_READ_WRITE`는 잠금 없이 캐시를 업데이트하므로 짧은 순간 오래된 데이터를 읽을 가능성을 감수하는 대신 성능을 얻는다. `TRANSACTIONAL`은 JTA와 통합해 완전한 트랜잭션 정합성을 제공하지만 설정이 복잡하고 지원하는 캐시 프로바이더가 제한적이다.

| 전략 | 정합성 보장 수준 | 적합한 데이터 |
|---|---|---|
| READ_ONLY | 완벽(변경 자체가 불가) | 공통 코드, 국가 코드 등 불변 데이터 |
| READ_WRITE | 소프트 락으로 강한 보장 | 자주 읽고 가끔 바뀌는 데이터 |
| NONSTRICT_READ_WRITE | 약함(일시적 stale 허용) | 약간의 지연이 허용되는 통계성 데이터 |
| TRANSACTIONAL | 완전한 트랜잭션 정합성 | JTA 환경의 엄격한 정합성 요구 |

## 코드 예제 — 엔티티 캐시와 쿼리 캐시 활성화

```java
@Entity
@Cacheable
@org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class ProductCategory {
    @Id
    private Long id;
    private String name;

    @OneToMany(mappedBy = "category")
    @org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
    private List<Product> products;  // 컬렉션 캐시도 별도로 지정
}
```

```properties
# application.yml (Spring Boot + Hibernate)
spring.jpa.properties.hibernate.cache.use_second_level_cache=true
spring.jpa.properties.hibernate.cache.use_query_cache=true
spring.jpa.properties.hibernate.cache.region.factory_class=org.hibernate.cache.jcache.JCacheRegionFactory
```

## 실무 포인트

- **쓰기가 잦은 엔티티에 캐시를 걸면 오히려 손해다.** 캐시 무효화 오버헤드와 소프트 락 경합이 실제 조회 성능 이득보다 커질 수 있으므로, 캐시 히트율을 반드시 모니터링(Ehcache/Infinispan의 통계 API)하고 실제 이득을 확인한 뒤 유지해야 한다.
- **분산 환경에서는 캐시 프로바이더의 복제 방식을 이해해야 한다.** 여러 서버 인스턴스가 각자 로컬 캐시를 갖는 구조라면, 한 인스턴스에서 발생한 변경이 다른 인스턴스의 캐시에 즉시 반영되지 않을 수 있다. Infinispan의 분산 캐시나 Redis 기반 2차 캐시 프로바이더처럼 클러스터 전체가 캐시를 공유하는 구성을 검토해야 한다.
- **1차 캐시가 이미 반환한 엔티티는 2차 캐시를 거치지 않는다.** 같은 영속성 컨텍스트 안에서는 항상 1차 캐시가 우선하므로, 2차 캐시의 효과는 새로운 트랜잭션(새 영속성 컨텍스트)에서 같은 엔티티를 조회할 때만 체감된다.

## 마무리 요약

- 2차 캐시는 트랜잭션 하나에 국한된 1차 캐시와 달리 애플리케이션 전체에 걸쳐 살아있으며, 엔티티·컬렉션·쿼리 캐시가 별도 리전으로 관리된다.
- 동시성 전략(READ_ONLY/READ_WRITE/NONSTRICT_READ_WRITE/TRANSACTIONAL) 선택이 데이터 정합성과 성능 사이의 실제 트레이드오프를 결정한다.
- 쓰기가 잦은 데이터에는 오히려 역효과가 날 수 있으므로 캐시 히트율을 모니터링하고, 분산 환경에서는 캐시 복제·공유 방식을 별도로 검토해야 한다.

## 참고 자료

- [Hibernate 공식 문서 — Caching](https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html#caching)
- [Spring Data JPA 공식 문서](https://docs.spring.io/spring-data/jpa/reference/)
