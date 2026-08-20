---
layout: single
title: "fetch로 API 호출하기 — 프론트에서 서버 데이터 받아오기"
date: 2026-09-14 13:30:00 +0530
categories: frontend
tags: ["fetch", "api", "자바스크립트", "http", "입문"]
toc: true
toc_sticky: true
excerpt: "브라우저에서 서버에 요청을 보내고 응답을 받는 fetch API의 기본 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 프론트에서 서버 데이터를 어떻게 받나

화면에 서버 데이터를 표시하려면 브라우저가 서버에 요청을 보내 응답을 받아야 한다. **fetch**는 **브라우저에 내장된, 서버에 HTTP 요청을 보내는 함수**다. 별도 라이브러리 없이 바로 쓸 수 있다.

## 기본 사용

```javascript
// GET: 데이터 받기
const res = await fetch('/api/users');
const data = await res.json(); // 응답 본문을 JSON으로 파싱

// POST: 데이터 보내기
await fetch('/api/users', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: '철수' })
});
```

`fetch`는 프로미스를 반환하므로 `await`이나 `.then`으로 결과를 받는다. 응답 본문은 `res.json()`으로 파싱한다.

## 실무 포인트

- **HTTP 에러는 catch로 안 잡힌다.** fetch는 404·500 같은 응답도 "성공"으로 본다(네트워크 자체가 실패해야 reject). `res.ok`나 `res.status`를 직접 확인해 에러를 처리해야 한다.
- **응답 파싱을 잊지 마라.** `fetch` 결과는 응답 객체일 뿐, 실제 데이터는 `res.json()`(또는 `res.text()`)로 한 번 더 꺼내야 한다. 이 단계도 비동기라 `await`이 필요하다.
- **CORS·인증 헤더를 챙겨라.** 다른 도메인 API를 부르면 CORS 정책이 적용된다. 인증이 필요하면 `headers`에 토큰을 넣거나 `credentials` 옵션으로 쿠키를 포함시킨다.

## 마무리 요약

- fetch는 브라우저 내장 함수로, 서버에 HTTP 요청을 보내고 프로미스로 응답을 받는다.
- GET은 `res.json()`으로 파싱하고, POST는 `method`·`headers`·`body`를 지정한다.
- 404·500은 catch로 안 잡히니 `res.ok`를 확인하고, CORS·인증 처리를 함께 해야 한다.

## 참고 자료

- [MDN - fetch()](https://developer.mozilla.org/ko/docs/Web/API/Window/fetch)
