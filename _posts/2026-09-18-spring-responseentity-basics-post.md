---
layout: single
title: "ResponseEntity가 뭔가요 — 상태코드·헤더까지 직접 정하기"
date: 2026-09-18 12:25:00 +0530
categories: backend
tags: ["responseentity", "spring", "http", "응답", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링에서 응답의 본문뿐 아니라 상태코드·헤더까지 세밀하게 제어하는 ResponseEntity의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 응답 본문만 반환하면 부족할 때

컨트롤러에서 객체를 반환하면 스프링이 JSON 본문으로 바꿔 200 OK로 응답한다. 그런데 "생성됐으면 201, 없으면 404" 같은 **상태코드**나 특정 **헤더**를 직접 정하고 싶을 때가 있다. **ResponseEntity**는 **본문·상태코드·헤더를 모두 담아 반환**하는 객체다.

## 사용법

```java
@GetMapping("/users/{id}")
public ResponseEntity<User> get(@PathVariable Long id) {
    User user = repo.find(id);
    if (user == null) {
        return ResponseEntity.notFound().build(); // 404
    }
    return ResponseEntity.ok(user);               // 200 + 본문
}

@PostMapping("/users")
public ResponseEntity<User> create(@RequestBody User u) {
    User saved = repo.save(u);
    return ResponseEntity.status(HttpStatus.CREATED).body(saved); // 201
}
```

## 무엇을 담나

| 요소 | 예 |
|---|---|
| 상태코드 | 200, 201, 404, 400 |
| 헤더 | Location, Cache-Control |
| 본문 | JSON 객체 |

## 실무 포인트

- **상황에 맞는 상태코드를 반환하라.** 조회 성공은 200, 생성은 201, 없으면 404, 잘못된 요청은 400이다. 무조건 200을 주지 말고 의미에 맞게 반환하면 클라이언트가 결과를 정확히 판단한다.
- **생성 시 Location 헤더.** 리소스를 만들면 201과 함께 `Location` 헤더에 새 리소스의 URL을 담는 것이 REST 관례다. `ResponseEntity.created(uri).body(...)`로 한다.
- **단순한 경우엔 굳이 안 써도 된다.** 항상 200에 본문만 주면 되는 단순 API는 객체를 그대로 반환해도 된다. 상태코드·헤더 제어가 필요할 때 ResponseEntity를 쓴다. `@ResponseStatus`로 상태코드만 지정하는 방법도 있다.

## 마무리 요약

- ResponseEntity는 응답의 본문·상태코드·헤더를 모두 담아 반환하는 객체다.
- `ok`, `notFound`, `status(...).body(...)` 등으로 상황에 맞는 응답을 만든다.
- 의미에 맞는 상태코드를 주고 생성 시 Location 헤더를 담으며, 단순한 경우엔 생략해도 된다.

## 참고 자료

- [Spring 공식 문서 - ResponseEntity](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-methods/responseentity.html)
