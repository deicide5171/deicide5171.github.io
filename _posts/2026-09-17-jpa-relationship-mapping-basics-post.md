---
layout: single
title: "JPA 연관관계 매핑이 뭔가요 — @OneToMany 첫걸음"
date: 2026-09-17 12:25:00 +0530
categories: backend
tags: ["jpa", "연관관계", "onetomany", "spring", "입문"]
toc: true
toc_sticky: true
excerpt: "JPA에서 테이블 간 관계를 객체로 연결하는 연관관계 매핑(@OneToMany 등)의 기본과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 테이블의 외래키를 객체에서 어떻게 다루나

회원과 주문처럼 DB에서 외래키로 연결된 테이블을, JPA에서는 **객체 간 참조**로 표현한다. 회원 객체가 주문 목록을 필드로 갖는 식이다. 이렇게 **테이블 관계를 객체 관계로 연결**하는 것이 연관관계 매핑이다.

## 관계 종류

| 애너테이션 | 관계 |
|---|---|
| `@OneToMany` | 하나가 여럿을 가짐(회원-주문) |
| `@ManyToOne` | 여럿이 하나에 속함(주문-회원) |
| `@OneToOne` | 일대일(회원-프로필) |
| `@ManyToMany` | 다대다(학생-과목) |

## 예시

```java
@Entity
class Member {
    @Id Long id;
    @OneToMany(mappedBy = "member")
    List<Order> orders; // 회원이 가진 주문들
}

@Entity
class Order {
    @Id Long id;
    @ManyToOne
    Member member;      // 주문이 속한 회원(외래키 주인)
}
```

## 실무 포인트

- **연관관계 주인을 이해하라.** 외래키를 실제로 관리하는 쪽이 "주인"이다. 보통 `@ManyToOne` 쪽(외래키를 가진 테이블)이 주인이고, 반대쪽 `@OneToMany`에는 `mappedBy`로 주인을 가리킨다. 주인이 아닌 쪽만 바꾸면 DB에 반영이 안 된다.
- **지연 로딩(LAZY)을 기본으로.** 연관 객체를 즉시 다 불러오면(EAGER) 불필요한 조회가 많아진다. `@ManyToOne`은 기본이 즉시라, LAZY로 바꿔 필요할 때만 조회하는 것이 성능에 좋다.
- **N+1 문제를 조심하라.** 회원 목록을 불러온 뒤 각 회원의 주문을 하나씩 조회하면 쿼리가 폭증한다(N+1). 연관 데이터가 필요하면 `fetch join`이나 `@EntityGraph`로 한 번에 가져온다.

## 마무리 요약

- JPA 연관관계 매핑은 테이블의 외래키 관계를 객체 간 참조로 연결한다.
- `@OneToMany`·`@ManyToOne` 등으로 관계를 표현하며, 외래키를 관리하는 쪽이 "주인"이다.
- 지연 로딩을 기본으로 하고 N+1 문제를 fetch join 등으로 방지해야 한다.

## 참고 자료

- [Spring Data JPA 공식 문서](https://docs.spring.io/spring-data/jpa/reference/jpa.html)
