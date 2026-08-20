---
layout: single
title: "전역 예외 처리 입문 — @RestControllerAdvice로 에러 응답 통일하기"
date: 2026-09-09 12:25:00 +0530
categories: backend
tags: ["예외처리", "exception", "spring", "restcontrolleradvice", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 컨트롤러마다 try-catch를 반복하지 않고 예외를 한곳에서 처리하는 @RestControllerAdvice 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 컨트롤러마다 try-catch를 반복해야 하나

API마다 예외를 잡아 에러 응답을 만들면, 컨트롤러마다 비슷한 `try-catch`가 반복되고 응답 형식도 제각각이 된다. 스프링의 **`@RestControllerAdvice`**는 **애플리케이션 전역의 예외를 한곳에서 잡아** 일관된 에러 응답으로 바꿔준다.

## 동작 개념

| 없을 때 | 있을 때 |
|---|---|
| 컨트롤러마다 try-catch 반복 | 예외 처리 코드 한곳에 모음 |
| 에러 응답 형식 제각각 | 형식 통일 |
| 처리 안 한 예외는 500 뭉뚱그림 | 예외별로 알맞은 상태코드 |

## 예제

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    // 특정 예외를 잡아 404로 응답
    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(UserNotFoundException e) {
        return ResponseEntity
            .status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse("USER_NOT_FOUND", e.getMessage()));
    }

    // 그 외 모든 예외는 500으로
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleEtc(Exception e) {
        return ResponseEntity
            .status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("INTERNAL_ERROR", "서버 오류"));
    }
}
```

컨트롤러에서 예외가 던져지면, 여기서 예외 타입에 맞는 메서드가 잡아 응답을 만든다. 컨트롤러 코드는 깔끔해진다.

## 실무 포인트

- **에러 응답 형식을 정해두라.** `{ code, message }` 같은 일관된 형식을 만들면 프론트가 에러를 다루기 쉽다. 상태코드와 별개로, 앱 내부 에러 코드를 담으면 원인 구분이 편하다.
- **내부 정보를 노출하지 마라.** 스택 트레이스나 SQL 오류 원문을 그대로 응답에 담으면 보안에 취약하다. 사용자에겐 일반적인 메시지를, 상세 내용은 서버 로그에만 남긴다.
- **예상 예외와 예상 밖 예외를 구분하라.** "없는 유저 조회"처럼 예상되는 것은 알맞은 4xx로, 예상 못한 것은 500으로 처리하고 로그로 추적한다.

## 마무리 요약

- `@RestControllerAdvice`는 전역 예외를 한곳에서 잡아 에러 응답을 통일한다.
- `@ExceptionHandler`로 예외 타입별로 알맞은 상태코드와 메시지를 반환한다.
- 응답 형식을 정하고 내부 정보 노출을 막으며, 예상/예상 밖 예외를 구분해 처리한다.

## 참고 자료

- [Spring 공식 문서 - Exception Handling](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-exceptionhandler.html)
