---
layout: single
title: "DTO와 엔티티를 왜 분리하나요 — 계층 간 데이터 전달 기초"
date: 2026-09-05 12:25:00 +0530
categories: backend
tags: ["dto", "entity", "레이어드아키텍처", "백엔드기초", "입문"]
toc: true
toc_sticky: true
excerpt: "엔티티를 그대로 API 응답으로 내보내면 왜 문제가 되는지, DTO로 분리하는 이유와 기본 패턴을 처음 배우는 사람 기준으로 정리했다."
---

## 엔티티를 그대로 응답으로 주면 안 되나

Spring이나 JPA를 배우면 DB 테이블과 매핑되는 **엔티티(Entity)**를 만든다. 처음에는 이 엔티티를 그대로 API 응답으로 반환해도 잘 동작하는 것처럼 보인다. 하지만 프로젝트가 커지면 이 방식이 여러 문제를 일으킨다. **DTO(Data Transfer Object)**는 계층 사이에 데이터를 전달하기 위한 전용 객체로, 엔티티를 직접 노출하지 않기 위해 쓴다.

## 엔티티를 그대로 노출할 때의 문제

| 문제 | 설명 |
|---|---|
| 민감정보 노출 | User 엔티티의 비밀번호 해시까지 응답에 딸려 나감 |
| 강한 결합 | DB 구조가 바뀌면 API 응답 형태도 함께 바뀜 |
| 순환 참조 | 연관관계가 얽힌 엔티티를 직렬화하다 무한 루프 |
| 유연성 부족 | 화면마다 다른 형태로 데이터를 주기 어려움 |

## DTO로 분리하기

```java
// 엔티티: DB와 매핑, 민감정보 포함
@Entity
public class User {
    private Long id;
    private String email;
    private String passwordHash; // 절대 노출되면 안 됨
    private LocalDateTime createdAt;
}

// DTO: 응답에 필요한 것만 담는다
public record UserResponse(Long id, String email) {
    public static UserResponse from(User user) {
        return new UserResponse(user.getId(), user.getEmail());
        // passwordHash는 담지 않음 -> 노출 위험 원천 차단
    }
}
```

응답용 DTO는 클라이언트에게 보여줄 필드만 담는다. 비밀번호 해시처럼 내보내면 안 되는 필드는 애초에 DTO에 넣지 않으므로, 실수로 노출되는 사고를 원천 차단할 수 있다.

## 요청도 DTO로 받는다

```java
// 요청 DTO: 클라이언트가 보낼 수 있는 것만 받는다
public record CreateUserRequest(String email, String password) { }

@PostMapping("/users")
public UserResponse create(@RequestBody CreateUserRequest request) {
    // request에는 id나 createdAt이 없으므로
    // 클라이언트가 그런 값을 임의로 조작해 넣을 수 없다
}
```

## 실무 포인트

- **엔티티를 요청 본문으로 그대로 받는 것도 위험하다.** 클라이언트가 `id`나 권한 관련 필드를 임의로 넣어 보낼 수 있기 때문이다. 요청도 필요한 필드만 담은 DTO로 받으면 이런 조작을 막을 수 있다.
- **엔티티-DTO 변환 코드가 늘어나는 것은 감수할 만한 비용이다.** 매번 변환하는 것이 번거롭게 느껴지지만, 그 분리 덕분에 DB 구조 변경이 API에 미치는 영향을 차단할 수 있다. MapStruct 같은 도구로 변환을 자동화할 수도 있다.
- **작은 프로젝트에서는 과하다고 느낄 수 있다.** 학습용 토이 프로젝트라면 엔티티를 바로 써도 되지만, 실제 서비스나 협업 프로젝트에서는 DTO 분리가 사실상 표준이다.

## 마무리 요약

- 엔티티를 그대로 API에 노출하면 민감정보 유출, DB-API 강한 결합, 순환 참조 등의 문제가 생긴다.
- DTO는 계층 간 전달용 전용 객체로, 필요한 필드만 담아 노출 위험과 결합을 줄인다.
- 응답뿐 아니라 요청도 DTO로 받으면 클라이언트의 필드 조작을 막을 수 있다.

## 참고 자료

- [Spring 공식 가이드 - REST 서비스](https://spring.io/guides/gs/rest-service)
- [Martin Fowler - Data Transfer Object](https://martinfowler.com/eaaCatalog/dataTransferObject.html)
