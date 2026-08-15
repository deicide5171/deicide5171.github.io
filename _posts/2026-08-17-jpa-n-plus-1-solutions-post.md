---
layout: single
title: "Spring Data JPA N+1 문제 완전 정복 — Fetch Join·EntityGraph·Batch Size 실전 비교"
date: 2026-08-17 13:25:00 +0530
categories: backend
tags: ["jpa", "hibernate", "spring-data-jpa", "n-plus-one", "fetch-join", "entitygraph"]
toc: true
toc_sticky: true
excerpt: "JPA를 쓰는 팀이라면 한 번쯤 겪는 N+1 문제를, 발생 원리부터 Fetch Join·EntityGraph·Batch Size 세 가지 해법의 장단점과 페이징 시 주의점까지 코드로 정리한다."
---

## 왜 지금도 N+1이 반복해서 터지는가

N+1 문제는 JPA·Hibernate를 다루는 팀이라면 신입 때 한 번, 트래픽이 늘어난 뒤 또 한 번 겪는 단골 장애 원인이다. 지연 로딩(LAZY)으로 설계된 연관관계를 반복문 안에서 그대로 순회하면, 목록 조회 쿼리 1번에 연관 엔티티를 가져오는 쿼리가 건수만큼(N번) 추가로 발생한다. 개발 환경에서는 데이터가 몇 건 안 되니 체감이 안 되다가, 운영에서 목록이 수백 건으로 늘어나는 순간 응답 시간이 급격히 나빠지는 전형적인 패턴이다.

최근 Spring Boot 3.x·Hibernate 6 조합이 주류가 되면서 상황이 조금 달라졌다. Hibernate 6은 페이징과 컬렉션 Fetch Join을 함께 쓸 때 메모리에서 전체 결과를 만든 뒤 잘라내는 위험한 패턴에 더 엄격한 경고를 추가했고, `default_batch_fetch_size` 같은 설정도 이전보다 널리 알려지며 실무 표준 대응법으로 자리잡았다. 또한 API 응답 지연이 동시 요청 처리량에 그대로 곱해지는 구조상, 트래픽이 몰리는 서비스일수록 N+1 하나가 전체 처리량에 미치는 영향이 커진다는 점도 다시 주목받는 이유다. 이 글은 N+1이 왜 생기는지부터 Fetch Join·EntityGraph·Batch Size 세 가지 해법을 언제 골라야 하는지까지 정리한다.

## 핵심 개념 1: N+1은 어디서 발생하는가

`@ManyToOne`, `@OneToMany` 같은 연관관계를 LAZY로 선언하면, 연관 엔티티는 실제로 접근하는 시점에 별도 쿼리로 조회된다. 문제는 목록을 조회한 뒤 각 항목에서 연관 엔티티를 꺼내 쓰는 로직 — 화면에 주문 목록과 주문자 이름을 함께 보여주는 것처럼 아주 흔한 요구사항 — 이 정확히 이 패턴을 반복문 안에서 실행한다는 데 있다.

<img src="/assets/images/posts/2026-08-17-jpa-n-plus-1-solutions-1.svg" alt="N+1 문제 발생 구조와 Fetch Join 적용 후 구조 비교, 쿼리 개수 변화" style="width:100%;">

`@ManyToOne`은 기본이 EAGER라 이런 함정에 특히 잘 걸린다. `Order`를 조회할 때마다 연관된 `Member`를 즉시 함께 가져오도록 설계되어 있어, 목록 조회 자체가 이미 N+1 구조를 내장하고 있는 경우가 많다. `@OneToMany`는 기본이 LAZY지만, 컬렉션을 반복 접근하는 로직에서는 마찬가지로 N+1이 발생한다.

## 핵심 개념 2: 세 가지 해법 비교

| 해법 | 동작 방식 | 장점 | 주의할 점 |
|---|---|---|---|
| Fetch Join (JPQL) | 조인으로 한 번에 조회 | 쿼리 1번으로 완전히 해결 | 컬렉션 2개 이상 fetch join 시 `MultipleBagFetchException`, 페이징과 병행 시 메모리 전체 로딩 위험 |
| `@EntityGraph` | 어노테이션으로 즉시 로딩 범위 지정 | 리포지토리 메서드별로 로딩 전략을 선언적으로 분리 가능 | 컬렉션 fetch 시 Fetch Join과 동일한 페이징 제약을 그대로 물려받음 |
| Batch Size (`@BatchSize`/`default_batch_fetch_size`) | N번 쿼리를 `IN` 절 묶음 쿼리로 축소 | 페이징·다중 컬렉션과 함께 써도 안전, 설정 한 줄로 전역 적용 가능 | 쿼리가 1번이 아니라 N/batch_size번으로 줄어드는 것(완전 제거 아님) |

세 방법 모두 "N+1을 없앤다"는 목표는 같지만, Fetch Join·EntityGraph는 쿼리를 정말 1번으로 만드는 대신 페이징·복수 컬렉션 조합에 제약이 있고, Batch Size는 쿼리 수를 줄이는 데 그치는 대신 제약 없이 두루 안전하다는 점이 실무 선택의 핵심 기준이다.

## 핵심 개념 3: 페이징과 함께 쓸 때 특히 주의

컬렉션을 Fetch Join하면서 `Pageable`을 함께 쓰면, DB에서 조인된 전체 행을 애플리케이션 메모리로 가져온 뒤 메모리 안에서 페이징을 흉내 내는 문제가 생긴다. Hibernate 6는 이런 패턴을 감지하면 경고 로그를 남기도록 강화되어 있어, 운영 로그에서 관련 경고를 본 적이 있다면 이 문제일 가능성이 높다. 목록 화면처럼 페이징이 필수인 경우에는 컬렉션은 Fetch Join하지 않고 Batch Size로 처리하는 조합이 안전한 기본값이다.

## 예제: 세 가지 해법 적용 코드

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    // 1) Fetch Join — 단건/제한된 목록에서 연관 엔티티까지 한 번에
    @Query("select o from Order o join fetch o.member where o.status = :status")
    List<Order> findWithMemberByStatus(@Param("status") OrderStatus status);

    // 2) EntityGraph — 메서드별로 로딩 범위를 선언적으로 지정
    @EntityGraph(attributePaths = {"member", "member.address"})
    List<Order> findByStatus(OrderStatus status);

    // 3) 페이징이 필요한 목록 — 컬렉션은 Fetch Join하지 않고 Batch Size에 맡긴다
    Page<Order> findAll(Pageable pageable);
}
```

```yaml
# application.yml — 전역 Batch Size 설정
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 100
```

```java
// 엔티티별로 다르게 주고 싶다면 개별 어노테이션도 가능
@Entity
public class Order {

    @ManyToOne(fetch = FetchType.LAZY)
    @BatchSize(size = 100)
    private Member member;
}
```

`default_batch_fetch_size`를 설정하면, 지연 로딩된 연관 엔티티를 접근할 때 Hibernate가 이를 `WHERE id IN (?, ?, ...)` 형태의 묶음 쿼리로 자동 변환한다. 반복문에서 100건을 순회해도 쿼리가 100번이 아니라 (100/batch_size)번으로 줄어든다.

## 실무 포인트

- **목록 API는 우선 Batch Size를 기본값으로 검토한다**: 페이징이 있는 목록 화면에서는 Fetch Join보다 Batch Size 조합이 안전하고 유지보수 부담도 적다.
- **컬렉션을 2개 이상 fetch join하지 않는다**: `orders`와 `items`를 동시에 Fetch Join하면 `MultipleBagFetchException`이 발생한다. 하나만 Fetch Join하고 나머지는 Batch Size로 처리하거나, 컬렉션 타입을 `Set`으로 바꿔 회피하는 방법을 검토한다.
- **쿼리 로그로 실제 발생 횟수를 눈으로 확인한다**: `spring.jpa.show-sql`이나 p6spy 같은 쿼리 로깅 도구로 실제 실행되는 쿼리 수를 확인하지 않으면, 해법을 적용했다고 믿었지만 다른 지점에서 N+1이 여전히 남아있는 경우를 놓치기 쉽다.
- **연관관계 기본 fetch 전략을 팀 컨벤션으로 명시한다**: `@ManyToOne` 기본값 EAGER를 LAZY로 통일하는 규칙만 팀에 세워도 사고를 상당수 예방할 수 있다.

## 3줄 요약

- N+1은 지연 로딩된 연관관계를 반복문에서 순회할 때 목록 쿼리 1번에 건수만큼의 추가 쿼리가 붙는 구조적 문제다.
- Fetch Join·EntityGraph는 쿼리를 완전히 1번으로 줄이지만 페이징·다중 컬렉션 조합에 제약이 있고, Batch Size는 쿼리 수를 줄이는 대신 제약 없이 두루 안전하다.
- 페이징이 필요한 목록 API는 컬렉션 Fetch Join을 피하고 Batch Size를 기본값으로, 쿼리 로그로 실제 적용 여부를 항상 확인하는 것이 안전하다.

## 참고 자료

- [Hibernate ORM User Guide — Fetching](https://docs.jboss.org/hibernate/orm/6.4/userguide/html_single/Hibernate_User_Guide.html#fetching)
- [Spring Data JPA Reference — @EntityGraph](https://docs.spring.io/spring-data/jpa/reference/jpa/entity-graphs.html)
- [Hibernate ORM User Guide — Batch Fetching](https://docs.jboss.org/hibernate/orm/6.4/userguide/html_single/Hibernate_User_Guide.html#fetching-batch)
