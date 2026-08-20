---
layout: single
title: "REST API가 뭔가요 — HTTP 메서드와 설계 기초"
date: 2026-09-01 12:25:00 +0530
categories: backend
tags: ["rest api", "http", "api설계", "입문", "백엔드기초"]
toc: true
toc_sticky: true
excerpt: "백엔드 개발을 시작하면 가장 먼저 만나는 REST API가 무엇이고, HTTP 메서드와 URL을 어떻게 설계해야 하는지 기초부터 정리했다."
---

## REST는 왜 이렇게 자주 언급되나

프론트엔드와 백엔드가 통신할 때, 또는 서버끼리 데이터를 주고받을 때 가장 널리 쓰이는 방식이 REST API다. REST(Representational State Transfer)는 특정 기술이 아니라 **HTTP를 활용해 자원(resource)을 다루는 설계 스타일**이다. 잘 설계된 REST API는 URL과 HTTP 메서드만 보고도 무슨 동작을 하는지 예측할 수 있다는 것이 핵심 장점이다.

## HTTP 메서드와 CRUD의 대응

| HTTP 메서드 | 의미 | 예시 URL |
|---|---|---|
| GET | 조회 | `GET /users/1` (1번 사용자 조회) |
| POST | 생성 | `POST /users` (새 사용자 생성) |
| PUT | 전체 수정 | `PUT /users/1` (1번 사용자 정보 전체 교체) |
| PATCH | 부분 수정 | `PATCH /users/1` (일부 필드만 수정) |
| DELETE | 삭제 | `DELETE /users/1` (1번 사용자 삭제) |

## 좋은 URL 설계 vs 나쁜 URL 설계

```text
나쁜 예:
GET /getUser?id=1        -> 동사가 URL에 들어감
POST /deleteUser         -> GET으로 조회, POST로 삭제 처리를 흉내
GET /users/1/delete      -> URL 자체에 동작을 명시

좋은 예:
GET /users/1             -> 자원은 명사로, 동작은 HTTP 메서드로
DELETE /users/1
POST /users/1/orders     -> 중첩 자원 표현
```

REST의 핵심 원칙 중 하나는 **URL은 "무엇"(자원)을 나타내고, "어떻게 할지"(동작)는 HTTP 메서드가 담당**한다는 것이다. URL에 동사가 들어간다면 설계를 다시 검토할 신호다.

## 코드 예제: Spring Boot로 보는 REST 컨트롤러

```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public UserDto getUser(@PathVariable Long id) { ... }

    @PostMapping
    public UserDto createUser(@RequestBody CreateUserRequest request) { ... }

    @PutMapping("/{id}")
    public UserDto updateUser(@PathVariable Long id, @RequestBody UpdateUserRequest request) { ... }

    @DeleteMapping("/{id}")
    public void deleteUser(@PathVariable Long id) { ... }
}
```

## 실무 포인트

- **적절한 HTTP 상태 코드를 반환하는 것이 URL 설계만큼 중요하다.** 생성 성공은 200이 아니라 `201 Created`, 자원이 없으면 `404`, 잘못된 요청은 `400`을 반환해야 클라이언트가 응답을 코드로 명확히 구분할 수 있다.
- **GET 요청은 상태를 변경하지 않아야 한다(멱등성/안전성).** GET으로 데이터를 삭제하거나 변경하는 API는 캐시나 크롤러에 의해 의도치 않게 호출될 위험이 있다.
- **페이지네이션, 정렬, 필터링은 쿼리 파라미터로 표현한다.** 예: `GET /users?page=2&sort=name&status=active`

## 마무리 요약

- REST는 URL로 자원을, HTTP 메서드로 동작을 표현하는 API 설계 스타일이다.
- URL에 동사가 들어가 있다면 설계를 다시 검토해야 할 신호다.
- 적절한 HTTP 상태 코드 반환과 GET의 안전성 유지가 실무에서 자주 놓치는 부분이다.

## 참고 자료

- [MDN - HTTP 요청 메서드](https://developer.mozilla.org/ko/docs/Web/HTTP/Methods)
- [RESTful API 설계 가이드 - Microsoft](https://learn.microsoft.com/ko-kr/azure/architecture/best-practices/api-design)
