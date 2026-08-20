---
layout: single
title: "API 문서 자동화 — OpenAPI와 Swagger 처음 써보기"
date: 2026-09-07 13:25:00 +0530
categories: backend
tags: ["openapi", "swagger", "api문서", "백엔드기초", "입문"]
toc: true
toc_sticky: true
excerpt: "API 문서를 손으로 관리하는 대신 코드에서 자동 생성하는 OpenAPI/Swagger의 개념과 이점을 처음 배우는 사람 기준으로 정리했다."
---

## 문서와 실제 API가 자꾸 어긋난다면

API를 만들면 프론트엔드나 다른 팀에 "이런 엔드포인트가 있고 이런 값을 받는다"고 문서로 알려줘야 한다. 그런데 문서를 위키나 노션에 손으로 쓰면, API가 바뀔 때마다 문서를 따로 고쳐야 하고 곧 실제와 어긋난다. **OpenAPI**는 API 명세를 표준 형식으로 기술하는 규격이고, **Swagger**는 그 명세로 문서를 보여주고 테스트하게 해주는 도구다.

## OpenAPI/Swagger가 해주는 것

| 기능 | 설명 |
|---|---|
| 문서 자동 생성 | 코드에서 엔드포인트·파라미터·응답을 추출 |
| 인터랙티브 UI | 브라우저에서 API를 바로 호출해보기(Try it out) |
| 클라이언트 생성 | 명세로 여러 언어의 API 호출 코드 자동 생성 |
| 계약 공유 | 프론트·백엔드가 같은 명세를 기준으로 협업 |

## Spring에서 적용 예시

```java
// springdoc-openapi 의존성을 추가하면
// 컨트롤러에서 자동으로 API 문서가 생성된다

@RestController
@RequestMapping("/api/users")
public class UserController {

    @Operation(summary = "사용자 조회")  // 설명 애노테이션(선택)
    @GetMapping("/{id}")
    public UserResponse getUser(@PathVariable Long id) { ... }
}
// -> /swagger-ui.html 에서 대화형 문서를 볼 수 있다
```

코드에 애노테이션을 조금 붙이거나 그대로 두기만 해도, 실제 컨트롤러를 기반으로 문서가 만들어진다. 코드가 바뀌면 문서도 자동으로 최신이 된다.

## 실무 포인트

- **문서가 코드에서 생성되므로 실제와 어긋날 일이 적다.** 손으로 쓰는 문서의 가장 큰 문제(실제와 불일치)를 근본적으로 줄여준다. 이것이 자동 생성의 핵심 이점이다.
- **Swagger UI를 운영 환경에 그대로 노출하는 것은 주의해야 한다.** API 구조가 그대로 공개되므로, 외부에 열린 서비스라면 운영에서는 비활성화하거나 접근을 제한하는 것이 안전하다.
- **명세 우선(design-first) 방식도 있다.** 코드에서 문서를 뽑는 대신, 먼저 OpenAPI 명세를 작성해 프론트·백엔드가 합의한 뒤 그 명세대로 개발하는 방식이다. 협업 규모가 크면 이 방식이 유리할 수 있다.

## 마무리 요약

- OpenAPI는 API 명세를 기술하는 표준 규격이고, Swagger는 그 명세로 문서·테스트 UI를 제공하는 도구다.
- 코드에서 문서가 자동 생성되므로 손으로 쓴 문서처럼 실제와 어긋날 일이 적다.
- 운영 환경에서 Swagger UI 노출은 주의하고, 협업 규모가 크면 명세 우선 방식도 검토할 만하다.

## 참고 자료

- [OpenAPI 명세](https://spec.openapis.org/oas/latest.html)
- [springdoc-openapi 공식 문서](https://springdoc.org/)
