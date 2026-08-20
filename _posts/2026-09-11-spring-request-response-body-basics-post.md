---
layout: single
title: "@RequestBody와 @ResponseBody — 스프링에서 JSON 주고받기"
date: 2026-09-11 12:25:00 +0530
categories: backend
tags: ["requestbody", "responsebody", "spring", "json", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 JSON 요청을 객체로 받고 객체를 JSON 응답으로 내보내는 @RequestBody·@ResponseBody의 동작을 처음 배우는 사람 기준으로 정리했다."
---

## JSON과 자바 객체를 어떻게 오가나

프론트엔드가 보낸 JSON을 자바 코드에서 다루려면 객체로 바꿔야 하고, 반대로 자바 객체를 응답하려면 JSON으로 바꿔야 한다. 스프링에서는 **`@RequestBody`**가 **요청 JSON → 자바 객체**로, **`@ResponseBody`**가 **자바 객체 → 응답 JSON**으로 자동 변환해준다. 내부적으로 Jackson 같은 라이브러리가 변환을 담당한다.

## 두 애너테이션의 역할

| 애너테이션 | 방향 |
|---|---|
| `@RequestBody` | 요청 JSON → 자바 객체(역직렬화) |
| `@ResponseBody` | 자바 객체 → 응답 JSON(직렬화) |

## 예시

```java
@RestController
public class UserController {

    @PostMapping("/users")
    public UserResponse create(@RequestBody UserRequest req) {
        // req.getName() 등으로 JSON이 객체로 변환된 값 사용
        return new UserResponse(1L, req.getName());
        // 반환 객체가 자동으로 JSON 응답이 된다
    }
}
```

`@RestController`를 쓰면 모든 메서드에 `@ResponseBody`가 자동 적용되어, 반환 객체가 JSON으로 나간다.

## 실무 포인트

- **필드 이름이 매핑 기준이다.** JSON 키와 자바 필드 이름이 일치해야 값이 채워진다. 이름이 다르면 `@JsonProperty`로 매핑을 지정하거나, 스네이크/카멜 케이스 변환 설정을 맞춘다.
- **`@RequestBody`와 `@RequestParam`을 혼동 마라.** `@RequestBody`는 본문(JSON)을, `@RequestParam`은 쿼리 파라미터(`?key=value`)를 받는다. 용도가 다르니 상황에 맞게 쓴다.
- **요청 DTO에 검증을 붙여라.** `@RequestBody UserRequest`에 `@Valid`를 함께 쓰고 DTO 필드에 검증 애너테이션을 두면, 잘못된 JSON을 컨트롤러 진입 전에 걸러낼 수 있다.

## 마무리 요약

- `@RequestBody`는 요청 JSON을 자바 객체로, `@ResponseBody`는 자바 객체를 응답 JSON으로 자동 변환한다.
- `@RestController`를 쓰면 반환 객체가 자동으로 JSON 응답이 된다.
- JSON 키와 필드명이 매핑 기준이며, 본문은 `@RequestBody`·쿼리는 `@RequestParam`으로 구분하고 검증을 함께 쓴다.

## 참고 자료

- [Spring 공식 문서 - @RequestBody](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-methods/requestbody.html)
