---
layout: single
title: "API 에러 응답을 표준화하기 — RFC 7807 Problem Details와 Spring ProblemDetail 활용"
date: 2026-09-23 13:25:00 +0530
categories: backend
tags: ["rfc7807", "problemdetail", "springboot", "api설계", "에러핸들링"]
toc: true
toc_sticky: true
excerpt: "컨트롤러마다 제각각인 에러 응답 형식 때문에 프론트엔드가 매번 다르게 파싱해야 하는 문제를, RFC 7807 표준과 Spring Boot 3의 ProblemDetail 클래스로 통일하는 방법을 정리했다."
---

## 왜 에러 응답 형식이 API마다 제각각일까

여러 사람이 오랫동안 기능을 추가해온 API 서버를 보면, 에러 응답 형식이 엔드포인트마다 미묘하게 다른 경우가 흔하다. 어떤 곳은 `{"error": "..."}`, 어떤 곳은 `{"message": "...", "code": 400}`, 또 어떤 곳은 `{"errors": [...]}`처럼 배열을 쓴다. 프론트엔드 개발자는 API를 호출할 때마다 "이 엔드포인트는 에러가 어떤 모양으로 올까"를 문서에서 다시 확인해야 하고, 공통 에러 처리 로직을 만들기도 어려워진다.

이 문제는 각 개발자가 그때그때 편한 대로 예외를 응답으로 변환하면서 누적된다. 표준이 없으니 리뷰에서도 걸러지지 않고, 새 엔드포인트를 만들 때마다 또 다른 형식이 하나 더 늘어난다.

## 핵심 개념 1 — RFC 7807은 HTTP API 에러 응답의 공식 표준이다

RFC 7807(Problem Details for HTTP APIs)은 API 에러를 표현하는 공통 JSON 필드 구조를 정의한 인터넷 표준이다. 핵심 필드는 다섯 가지다.

| 필드 | 의미 |
|---|---|
| `type` | 문제 유형을 식별하는 URI (사람이 읽을 수 있는 문서로 연결 가능) |
| `title` | 문제 유형에 대한 짧고 사람이 읽을 수 있는 요약 |
| `status` | HTTP 상태 코드 (응답 자체의 상태 코드와 일치해야 함) |
| `detail` | 이번 특정 요청에서 발생한 문제에 대한 구체적인 설명 |
| `instance` | 문제가 발생한 구체적인 요청을 식별하는 URI |

이 구조는 필드가 고정돼 있지만 확장도 허용한다 — 검증 실패 시 어떤 필드가 문제인지 알려주는 `errors` 배열 같은 커스텀 필드를 추가로 넣을 수 있다. 중요한 것은 이 다섯 개 기본 필드만큼은 모든 API에서 동일한 이름과 의미로 나온다는 점이다.

<img src="/assets/images/posts/2026-09-23-rfc7807-problem-details-spring-1.svg" alt="여러 컨트롤러가 제각각 다른 형식으로 에러를 반환하던 상태에서 GlobalExceptionHandler가 모든 예외를 RFC 7807의 type, title, status, detail, instance 다섯 필드로 통일해 응답하는 구조를 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — Spring Boot 3는 ProblemDetail을 표준으로 내장하고 있다

Spring Framework 6(Spring Boot 3 기반)부터는 `ProblemDetail`이라는 클래스가 내장돼 있어, 별도 라이브러리 없이도 RFC 7807 형식의 응답을 만들 수 있다. `ResponseEntityExceptionHandler`를 상속한 전역 예외 처리기에서 이 클래스를 반환하면 자동으로 `application/problem+json` 콘텐츠 타입과 표준 필드 구조로 응답이 나간다.

## 예제 — 전역 예외 처리기에 ProblemDetail 적용하기

```java
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("리소스를 찾을 수 없음");
        problem.setType(URI.create("https://api.example.com/errors/not-found"));
        problem.setProperty("resourceId", ex.getResourceId());  // 확장 필드
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.BAD_REQUEST, "입력값 검증에 실패했습니다");
        problem.setTitle("Validation Failed");
        List<Map<String, String>> errors = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> Map.of("field", e.getField(), "reason", e.getDefaultMessage()))
                .toList();
        problem.setProperty("errors", errors);  // 필드별 검증 실패 정보 추가
        return problem;
    }
}
```

```json
{
  "type": "https://api.example.com/errors/not-found",
  "title": "리소스를 찾을 수 없음",
  "status": 404,
  "detail": "ID 42인 주문을 찾을 수 없습니다",
  "instance": "/api/orders/42",
  "resourceId": 42
}
```

`setProperty()`로 추가한 커스텀 필드는 표준 다섯 필드와 함께 JSON에 평평하게(flat) 포함된다. 이 방식 덕분에 표준을 지키면서도 서비스별 세부 정보를 자유롭게 덧붙일 수 있다.

## 도입 시 흔한 실수

| 실수 | 결과 |
|---|---|
| type을 항상 "about:blank"로 방치 | 클라이언트가 에러 유형을 프로그래밍적으로 구분 못 함 |
| status 필드와 실제 HTTP 상태 코드가 불일치 | 표준 위반, 클라이언트 파싱 로직 혼란 |
| detail에 스택 트레이스나 내부 구현 정보 노출 | 보안 정보 유출 위험 |
| 기존 레거시 엔드포인트를 마이그레이션 없이 방치 | 결국 두 가지 형식이 공존하는 반쪽짜리 표준화 |

특히 `detail` 필드에 예외 메시지를 그대로 노출하는 경우, 데이터베이스 제약조건 이름이나 내부 클래스 경로 같은 정보가 그대로 클라이언트에 전달될 위험이 있다. 사용자에게 보여줄 메시지와 서버 로그에만 남길 상세 정보를 분리해서 다뤄야 한다.

## 실무 포인트

- **`type` URI는 실제로 접근 가능한 문서로 연결하는 것이 이상적이다.** 당장 문서 페이지를 만들 여력이 없다면 최소한 에러 코드처럼 고유하고 일관된 값으로만이라도 유지해 클라이언트가 분기 처리할 수 있게 해야 한다.
- **OpenAPI 스펙에도 ProblemDetail 스키마를 명시하라.** springdoc-openapi를 쓰고 있다면 공통 에러 응답 스키마로 한 번만 정의해두면 모든 엔드포인트 문서에 일관되게 반영된다.
- **레거시 엔드포인트는 한 번에 다 바꾸려 하지 말고 점진적으로 전환하라.** 새 엔드포인트부터 표준을 적용하고, 트래픽이 큰 기존 엔드포인트를 우선순위로 옮기는 것이 현실적인 마이그레이션 전략이다.

## 마무리 요약

- RFC 7807은 type, title, status, detail, instance 다섯 필드로 API 에러 응답 형식을 표준화한 인터넷 표준이다.
- Spring Boot 3의 ProblemDetail 클래스를 쓰면 별도 라이브러리 없이도 전역 예외 처리기에서 이 표준 형식을 손쉽게 만들 수 있다.
- detail 필드에 내부 구현 정보를 그대로 노출하지 않도록 주의하고, 레거시 엔드포인트는 점진적으로 전환하는 것이 현실적이다.

## 참고 자료

- [RFC 7807 - Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc7807)
- [Spring Framework 공식 문서 - ProblemDetail](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html)
