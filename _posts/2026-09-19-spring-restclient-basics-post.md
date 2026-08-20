---
layout: single
title: "스프링 RestClient가 뭔가요 — 외부 API 호출 시작하기"
date: 2026-09-19 13:25:00 +0530
categories: backend
tags: ["spring", "restclient", "http", "api호출", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 외부 REST API를 호출할 때 쓰는 RestClient의 기본 사용법과 RestTemplate과의 관계를 처음 배우는 사람 기준으로 정리했다."
---

## "스프링에서 다른 서버 API를 호출하고 싶다"

결제 게이트웨이나 외부 데이터 API처럼, 내 스프링 앱이 다른 서버에 HTTP 요청을 보내야 할 때가 많다. 스프링 6부터 권장되는 동기식 HTTP 클라이언트가 **RestClient**다. 기존 `RestTemplate`을 대체하는, 체이닝 방식의 현대적 API다.

## 기본 사용법

```java
RestClient client = RestClient.create();

// GET
User user = client.get()
    .uri("https://api.example.com/users/{id}", 1)
    .retrieve()
    .body(User.class);

// POST
client.post()
    .uri("https://api.example.com/users")
    .body(new User("김", 20))
    .retrieve()
    .toBodilessEntity();
```

`get()`·`post()`로 시작해 `uri` → `body` → `retrieve` → 결과 변환으로 이어지는 흐름이다.

## RestTemplate과의 관계

| 클라이언트 | 상태 |
|---|---|
| RestTemplate | 여전히 동작하나 유지보수 모드 |
| RestClient | 동기 호출의 권장 방식(Spring 6.1+) |
| WebClient | 비동기·리액티브가 필요할 때 |

## 실무 포인트

- **에러 처리를 명시하라.** `retrieve()`는 4xx·5xx에서 예외를 던진다. `onStatus`로 상태별 처리를 붙이거나 `exchange`로 직접 다룬다.
- **빈으로 등록해 재사용.** 매 호출마다 새로 만들지 말고 `RestClient`를 빈으로 등록해 타임아웃·기본 헤더 등을 공통 설정한다.
- **타임아웃을 꼭 설정.** 외부 API가 느리면 내 스레드가 묶인다. 커넥션·읽기 타임아웃을 반드시 지정해 장애가 전파되지 않게 한다.

## 마무리 요약

- RestClient는 스프링 6.1+에서 권장되는 동기식 HTTP 클라이언트다.
- `get()`·`post()`부터 체이닝으로 요청을 구성하고 결과를 변환한다.
- 상태 코드 에러 처리와 타임아웃 설정을 반드시 챙긴다.

## 참고 자료

- [Spring 문서 - RestClient](https://docs.spring.io/spring-framework/reference/integration/rest-clients.html)
