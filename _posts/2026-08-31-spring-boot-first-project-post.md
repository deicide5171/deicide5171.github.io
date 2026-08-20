---
layout: single
title: "Spring Boot 첫 프로젝트 만들기 — Initializr부터 첫 API 호출까지"
date: 2026-08-31 12:25:00 +0530
categories: backend
tags: ["spring boot", "java", "입문", "튜토리얼", "rest api"]
toc: true
toc_sticky: true
excerpt: "Spring Initializr로 프로젝트를 생성하고, 첫 REST API를 만들어 응답을 확인하기까지의 과정을 처음 시작하는 사람 기준으로 정리했다."
---

## 왜 이 순서로 시작해야 하는가

Spring Boot를 처음 배우면 자동 설정, 빈, 애노테이션 같은 개념이 한꺼번에 쏟아져서 정작 "화면에 뭐라도 찍어보는" 첫 성공 경험까지 오래 걸린다. 이 글은 개념 설명은 최소화하고, Initializr로 프로젝트를 만들어 브라우저에 JSON 응답이 뜨는 것까지 가장 빠른 경로로 정리했다.

## 필요한 준비물

| 준비물 | 버전 권장 |
|---|---|
| JDK | 21 이상 (LTS) |
| 빌드 도구 | Gradle 또는 Maven (Initializr에서 선택) |
| IDE | IntelliJ IDEA Community(무료)로 충분 |
| Spring Boot | 3.x 최신 안정 버전 |

## 프로젝트 생성

[start.spring.io](https://start.spring.io)에서 아래처럼 선택하고 `Generate`를 누르면 zip 파일이 다운로드된다.

```text
Project: Gradle - Kotlin (또는 Maven)
Language: Java
Spring Boot: 3.x 최신
Dependencies: Spring Web
```

압축을 풀고 IDE로 열면 바로 실행 가능한 프로젝트 구조가 갖춰져 있다.

## 코드 예제: 첫 REST 컨트롤러

```java
@RestController
@RequestMapping("/api/hello")
public class HelloController {

    @GetMapping
    public Map<String, String> hello() {
        return Map.of("message", "안녕하세요, Spring Boot!");
    }
}
```

이 클래스 하나만 추가하고 `main` 메서드가 있는 `Application` 클래스를 실행하면, 브라우저에서 `http://localhost:8080/api/hello`로 접속했을 때 JSON 응답을 확인할 수 있다. `@RestController`가 이 클래스의 반환값을 자동으로 JSON으로 직렬화해준다.

## 실무 포인트

- **`@SpringBootApplication`이 붙은 메인 클래스의 패키지 위치가 중요하다.** 이 클래스가 있는 패키지의 하위 패키지만 컴포넌트 스캔 대상이 되므로, 컨트롤러를 다른 패키지에 두면 "빈을 찾을 수 없다"는 에러가 난다.
- **`application.properties` 대신 `application.yml`을 쓰면 계층 구조를 표현하기 쉬워진다.** 프로젝트가 커질수록 설정 항목이 많아지므로 초반에 습관을 들이는 것이 좋다.
- **포트 충돌(`Port 8080 already in use`)은 초보자가 가장 자주 겪는 에러다.** `application.yml`에 `server.port: 8081`을 추가하거나 기존 프로세스를 종료하면 된다.

## 마무리 요약

- Spring Initializr로 프로젝트를 생성하면 설정 없이 바로 실행 가능한 구조가 만들어진다.
- `@RestController` + `@GetMapping` 조합만으로 첫 JSON API를 즉시 확인할 수 있다.
- 메인 클래스 패키지 위치와 포트 충돌이 입문자가 가장 먼저 만나는 함정이다.

## 참고 자료

- [Spring Initializr](https://start.spring.io)
- [Spring Boot 공식 문서](https://docs.spring.io/spring-boot/index.html)
