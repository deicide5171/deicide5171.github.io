---
layout: single
title: "Spring Boot Whitelabel Error Page, 뭘 확인해야 할까"
date: 2026-08-31 13:25:00 +0530
categories: backend
tags: ["spring boot", "whitelabel error", "트러블슈팅", "예외처리", "java"]
toc: true
toc_sticky: true
excerpt: "Spring Boot에서 Whitelabel Error Page가 뜰 때 확인해야 할 순서와, 실제 원인을 찾기 위한 로그·요청 매핑 점검 방법을 정리했다."
---

## Whitelabel Error Page가 알려주지 않는 것

`Whitelabel Error Page`는 Spring Boot가 별도의 에러 페이지를 설정하지 않았을 때 보여주는 기본 화면이다. 화면에는 HTTP 상태 코드와 짧은 메시지만 나올 뿐, 정작 개발자가 궁금한 "어디서 왜 터졌는지"는 알려주지 않는다. 문제는 이 화면 자체가 아니라, 이 화면 뒤에 숨은 실제 예외를 찾는 방법을 모르는 것이다.

## 상태 코드별 확인 우선순위

| 상태 코드 | 의미 | 가장 먼저 확인할 것 |
|---|---|---|
| 404 | 매핑된 컨트롤러 없음 | URL 경로와 `@RequestMapping` 오타, HTTP 메서드 일치 여부 |
| 400 | 잘못된 요청 | `@RequestBody` DTO의 필드명·타입 불일치 |
| 401/403 | 인증/인가 실패 | Security 설정의 경로 패턴, 토큰 유효성 |
| 500 | 서버 내부 에러 | 애플리케이션 로그의 스택트레이스 |

## 진짜 원인을 보는 방법

기본적으로 Whitelabel 페이지는 스택트레이스를 화면에 노출하지 않는다. 개발 환경에서만 아래 설정으로 자세한 정보를 켤 수 있다.

```yaml
# application-dev.yml (개발 환경 전용, 운영에는 절대 넣지 않는다)
server:
  error:
    include-message: always
    include-stacktrace: always
    include-binding-errors: always
```

이 설정보다 더 확실한 방법은 **콘솔/파일 로그를 직접 보는 것**이다. Whitelabel 페이지가 떠도 서버 로그에는 항상 전체 스택트레이스가 출력된다.

```bash
# 로그에서 예외 발생 지점 바로 찾기
tail -f application.log | grep -A 20 "Exception"
```

## 코드 예제: 커스텀 예외 핸들러로 Whitelabel 자체를 없애기

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> handleValidation(
            MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldError().getDefaultMessage();
        return ResponseEntity.badRequest().body(Map.of("error", message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, String>> handleGeneral(Exception ex) {
        return ResponseEntity.internalServerError()
                .body(Map.of("error", "서버 내부 오류가 발생했습니다."));
    }
}
```

`@RestControllerAdvice`로 전역 예외 처리기를 두면 Whitelabel 페이지 대신 일관된 JSON 에러 응답을 내려줄 수 있다.

## 실무 포인트

- **404가 예상 밖으로 떴다면 `@RequestMapping`의 HTTP 메서드(GET/POST 등)를 가장 먼저 의심하라.** 경로는 맞는데 메서드가 다른 경우가 매우 흔하다.
- **운영 환경에서 `include-stacktrace: always`를 켜두면 내부 구조가 그대로 노출되는 보안 문제가 된다.** 반드시 프로파일별로 분리해야 한다.
- **전역 예외 핸들러를 만들 때 `Exception.class`를 너무 광범위하게 잡으면 원래 의도한 예외별 처리가 묻힐 수 있다.** 구체적인 예외부터 순서대로 등록하는 것이 안전하다.

## 마무리 요약

- Whitelabel Error Page는 화면 자체보다 그 뒤의 실제 예외를 로그에서 찾는 것이 핵심이다.
- 상태 코드별로 확인 우선순위를 정해두면 원인 탐색 시간을 크게 줄일 수 있다.
- `@RestControllerAdvice`로 전역 예외 처리를 구성하면 일관된 에러 응답과 함께 Whitelabel 화면 자체를 없앨 수 있다.

## 참고 자료

- [Spring Boot 공식 문서 - Error Handling](https://docs.spring.io/spring-boot/reference/web/servlet.html#web.servlet.spring-mvc.error-handling)
