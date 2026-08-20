---
layout: single
title: "@RestController와 @Controller 차이 — 뷰냐 데이터냐"
date: 2026-09-12 12:25:00 +0530
categories: backend
tags: ["restcontroller", "controller", "spring", "mvc", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 비슷해 보이는 @Controller와 @RestController가 무엇이 다르고 언제 무엇을 써야 하는지 처음 배우는 사람 기준으로 정리했다."
---

## 둘 다 컨트롤러인데 뭐가 다른가

스프링에서 요청을 받는 클래스에 `@Controller`와 `@RestController`를 붙인다. 이름이 비슷해 헷갈리는데, 핵심 차이는 **반환값을 어떻게 다루느냐**다. `@Controller`는 **뷰(HTML 화면) 이름**을 반환하고, `@RestController`는 **데이터(JSON) 자체**를 반환한다.

## 두 애너테이션 비교

| 구분 | @Controller | @RestController |
|---|---|---|
| 반환값 | 뷰(HTML) 이름 | 데이터(JSON) |
| 용도 | 서버가 화면을 그림 | REST API |
| @ResponseBody | 필요 시 개별로 | 자동 적용 |

`@RestController`는 사실 `@Controller` + `@ResponseBody`를 합친 것이다. 그래서 메서드마다 `@ResponseBody`를 안 붙여도 반환 객체가 JSON이 된다.

## 예시

```java
// @Controller: 뷰 이름 반환 (화면 렌더링)
@Controller
public class PageController {
    @GetMapping("/home")
    public String home() { return "home"; } // home.html 뷰를 렌더
}

// @RestController: 데이터 반환 (API)
@RestController
public class UserApi {
    @GetMapping("/api/users/1")
    public User get() { return new User(1L, "철수"); } // JSON 반환
}
```

## 실무 포인트

- **API 서버라면 `@RestController`.** 프론트엔드(React 등)와 JSON으로 통신하는 요즘 구조에서는 대부분 `@RestController`를 쓴다. 화면은 프론트가 그리고 백엔드는 데이터만 준다.
- **서버 렌더링이면 `@Controller`.** 타임리프 등으로 서버에서 HTML을 만들어 내려주는 전통적 방식이면 `@Controller`로 뷰 이름을 반환한다.
- **하나에서 섞을 수도 있다.** `@Controller`에서 특정 메서드만 `@ResponseBody`를 붙이면 그 메서드만 데이터를 반환한다. 하지만 역할을 섞기보다 클래스를 나누는 것이 깔끔하다.

## 마무리 요약

- `@Controller`는 뷰(HTML) 이름을, `@RestController`는 데이터(JSON)를 반환한다.
- `@RestController` = `@Controller` + `@ResponseBody`라, 반환 객체가 자동으로 JSON이 된다.
- JSON API 서버는 `@RestController`, 서버 렌더링 화면은 `@Controller`를 쓴다.

## 참고 자료

- [Spring 공식 문서 - @RestController](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-restcontroller.html)
