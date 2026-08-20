---
layout: single
title: "JPA 영속성 컨텍스트가 뭔가요 — 엔티티를 관리하는 1차 캐시"
date: 2026-09-14 12:25:00 +0530
categories: backend
tags: ["jpa", "영속성컨텍스트", "spring", "orm", "입문"]
toc: true
toc_sticky: true
excerpt: "JPA가 엔티티를 저장·관리하는 공간인 영속성 컨텍스트와 1차 캐시·변경 감지 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 같은 데이터를 두 번 조회했는데 쿼리가 한 번만 나간다

JPA를 쓰다 보면 같은 엔티티를 두 번 조회해도 DB 쿼리가 한 번만 나가는 걸 본다. 이는 **영속성 컨텍스트(Persistence Context)** 덕분이다. 영속성 컨텍스트는 **엔티티를 담아 관리하는 논리적 공간**으로, 조회한 엔티티를 그 안(1차 캐시)에 보관한다.

## 핵심 기능

| 기능 | 설명 |
|---|---|
| 1차 캐시 | 조회한 엔티티를 보관, 재조회 시 DB 안 감 |
| 변경 감지 | 엔티티 값이 바뀌면 자동 UPDATE |
| 쓰기 지연 | INSERT를 모았다 커밋 시점에 실행 |
| 동일성 보장 | 같은 엔티티는 같은 객체로 |

## 변경 감지 예시

```java
@Transactional
public void updateName(Long id, String newName) {
    User user = userRepository.findById(id).get(); // 영속 상태
    user.setName(newName);
    // save()를 안 불러도, 트랜잭션 끝날 때
    // 변경이 감지되어 UPDATE 쿼리가 자동 실행됨
}
```

## 실무 포인트

- **`save()` 없이도 수정된다.** 영속 상태 엔티티의 값을 바꾸면, 트랜잭션 커밋 시 변경 감지(dirty checking)로 UPDATE가 자동 나간다. 처음엔 헷갈리지만 JPA의 핵심 편의다.
- **영속성 컨텍스트는 트랜잭션 범위다.** 보통 트랜잭션이 끝나면 컨텍스트도 닫힌다. 트랜잭션 밖에서 지연 로딩(lazy) 필드에 접근하면 `LazyInitializationException`이 난다. 필요한 데이터는 트랜잭션 안에서 조회한다.
- **1차 캐시는 한 트랜잭션 안에서만.** 이 캐시는 요청(트랜잭션)마다 새로 생기고 사라진다. 여러 요청·서버에 걸친 캐시가 필요하면 Redis 같은 2차 캐시를 따로 둔다.

## 마무리 요약

- 영속성 컨텍스트는 JPA가 엔티티를 담아 관리하는 공간으로, 1차 캐시·변경 감지·쓰기 지연을 제공한다.
- 영속 상태 엔티티는 `save()` 없이도 값만 바꾸면 커밋 시 UPDATE가 자동 실행된다.
- 컨텍스트는 트랜잭션 범위라, 지연 로딩은 트랜잭션 안에서 접근해야 한다.

## 참고 자료

- [Spring Data JPA 공식 문서](https://docs.spring.io/spring-data/jpa/reference/jpa.html)
