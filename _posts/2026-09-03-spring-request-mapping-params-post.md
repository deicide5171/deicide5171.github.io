---
layout: single
title: "@RequestParam vs @PathVariable vs @RequestBody, 언제 뭘 쓸까"
date: 2026-09-03 12:25:00 +0530
categories: backend
tags: ["spring", "requestparam", "pathvariable", "requestbody", "입문"]
toc: true
toc_sticky: true
excerpt: "Spring 컨트롤러에서 요청 데이터를 받는 세 가지 방법 @RequestParam, @PathVariable, @RequestBody의 차이를 예제로 명확히 정리했다."
---

## 셋 다 요청 데이터를 받는데 뭐가 다른가

Spring으로 API를 만들면 클라이언트가 보낸 데이터를 받아야 하는데, `@RequestParam`, `@PathVariable`, `@RequestBody` 세 가지 애노테이션이 헷갈린다. 이 셋은 **데이터가 요청의 어느 위치에 담겨 오는지**에 따라 나뉜다. 위치를 알면 어떤 것을 써야 할지 자연스럽게 결정된다.

## 세 가지의 차이

| 애노테이션 | 데이터 위치 | 예시 URL/요청 |
|---|---|---|
| `@PathVariable` | URL 경로 자체 | `GET /users/{id}` → `/users/1` |
| `@RequestParam` | URL 쿼리 스트링 | `GET /users?page=2&size=10` |
| `@RequestBody` | 요청 본문(주로 JSON) | `POST /users` + JSON 바디 |

## 코드 예제

```java
// @PathVariable: 경로에 포함된 값 (특정 자원 식별)
@GetMapping("/users/{id}")
public User getUser(@PathVariable Long id) { ... }

// @RequestParam: 쿼리 스트링 (필터·페이징 등)
@GetMapping("/users")
public List<User> getUsers(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(required = false) String status) { ... }

// @RequestBody: 본문의 JSON을 객체로 변환 (생성·수정 데이터)
@PostMapping("/users")
public User createUser(@RequestBody CreateUserRequest request) { ... }
```

## 언제 무엇을 쓰는가

```text
- 특정 자원을 식별하는 값(회원 ID, 게시글 번호) -> @PathVariable
  (그 자원의 "주소"의 일부이므로 경로에 넣는 것이 REST 원칙에 맞다)

- 조회 조건(페이지 번호, 정렬, 검색어) -> @RequestParam
  (선택적이고 여러 개 조합되는 값이라 쿼리 스트링이 적합)

- 생성·수정할 데이터 덩어리(회원 정보 전체) -> @RequestBody
  (구조가 복잡하고 크므로 JSON 본문으로 받는다)
```

## 실무 포인트

- **GET 요청에는 보통 `@RequestBody`를 쓰지 않는다.** GET은 본문을 갖지 않는 것이 관례이므로, 조회 조건은 `@RequestParam`으로 받는 것이 표준이다.
- **`@RequestParam`의 `required`와 `defaultValue`를 잘 활용하라.** 파라미터가 없어도 되는 경우 `required = false`나 `defaultValue`를 지정하지 않으면, 파라미터 누락 시 400 에러가 나서 당황할 수 있다.
- **`@RequestBody`로 받는 DTO에는 검증 애노테이션(`@Valid`, `@NotNull` 등)을 함께 쓰는 것이 좋다.** 잘못된 형식의 데이터가 서비스 로직까지 들어가기 전에 컨트롤러 단계에서 걸러낼 수 있다.

## 마무리 요약

- 세 애노테이션은 데이터가 URL 경로·쿼리 스트링·요청 본문 중 어디에 담겨 오는지로 구분된다.
- 자원 식별은 `@PathVariable`, 조회 조건은 `@RequestParam`, 생성·수정 데이터는 `@RequestBody`가 기본 공식이다.
- GET에는 본문을 쓰지 않고, `@RequestBody` DTO에는 검증 애노테이션을 함께 붙이는 것이 실무 관례다.

## 참고 자료

- [Spring 공식 문서 - 요청 매핑](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-methods.html)
