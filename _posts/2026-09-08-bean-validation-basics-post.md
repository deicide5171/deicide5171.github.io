---
layout: single
title: "Bean Validation 입문 — @NotNull로 입력값 검증하기"
date: 2026-09-08 13:25:00 +0530
categories: backend
tags: ["beanvalidation", "spring", "검증", "validation", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 요청 데이터를 검증할 때 쓰는 Bean Validation의 기본 애너테이션과 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 입력값 검증을 if문으로 다 짜야 하나

회원가입 요청에서 이메일이 비었는지, 나이가 음수인지 등을 일일이 `if`로 검사하면 코드가 지저분해진다. **Bean Validation**은 검증 규칙을 **애너테이션으로 선언**해 이 반복을 없애준다. 스프링에서는 요청 객체 필드에 `@NotNull` 같은 애너테이션만 붙이면 자동으로 검사해준다.

## 자주 쓰는 애너테이션

| 애너테이션 | 의미 |
|---|---|
| `@NotNull` | null이 아니어야 함 |
| `@NotBlank` | 문자열이 비거나 공백만이면 안 됨 |
| `@Size(min, max)` | 길이/크기 범위 |
| `@Min` / `@Max` | 숫자 최소/최대 |
| `@Email` | 이메일 형식 |

## 사용 예제

```java
public class SignupRequest {
    @NotBlank
    private String name;

    @Email
    @NotBlank
    private String email;

    @Min(0) @Max(150)
    private int age;
}

// 컨트롤러에서 @Valid로 검증 실행
@PostMapping("/signup")
public String signup(@Valid @RequestBody SignupRequest req) {
    // 검증 통과한 값만 여기 도달
}
```

`@Valid`를 붙이면 스프링이 요청을 받을 때 자동으로 규칙을 검사하고, 위반 시 예외를 던진다.

## 실무 포인트

- **검증 실패 응답을 다듬어라.** 기본 예외 메시지는 사용자에게 불친절하다. `@ControllerAdvice`로 `MethodArgumentNotValidException`을 잡아 어떤 필드가 왜 틀렸는지 깔끔한 JSON으로 돌려주면 프론트가 쓰기 좋다.
- **메시지를 커스터마이즈하라.** `@NotBlank(message = "이름은 필수입니다")`처럼 메시지를 지정하면 의미가 명확해진다. 다국어가 필요하면 메시지 프로퍼티 파일로 분리한다.
- **서버 검증은 필수다.** 프론트엔드에서 이미 검증했더라도, 요청은 조작될 수 있으므로 서버에서도 반드시 검증해야 한다. Bean Validation은 그 마지막 방어선을 간단하게 만들어준다.

## 마무리 요약

- Bean Validation은 입력 검증 규칙을 애너테이션으로 선언해 반복 코드를 없앤다.
- `@NotBlank`, `@Email`, `@Min` 등을 필드에 붙이고 컨트롤러에서 `@Valid`로 검사한다.
- 검증 실패 응답을 다듬고, 프론트 검증과 별개로 서버 검증은 반드시 해야 한다.

## 참고 자료

- [Spring 공식 문서 - Validation](https://docs.spring.io/spring-framework/reference/core/validation/beanvalidation.html)
