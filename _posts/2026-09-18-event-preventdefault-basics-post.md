---
layout: single
title: "preventDefault가 뭔가요 — 브라우저 기본 동작 막기"
date: 2026-09-18 12:30:00 +0530
categories: frontend
tags: ["preventdefault", "이벤트", "자바스크립트", "폼", "입문"]
toc: true
toc_sticky: true
excerpt: "폼 제출로 페이지가 새로고침되는 것을 막는 등 브라우저의 기본 동작을 취소하는 preventDefault의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 폼을 제출했더니 페이지가 새로고침된다

폼의 제출 버튼을 누르면 브라우저는 기본적으로 페이지를 새로고침하며 데이터를 전송한다. 하지만 요즘은 자바스크립트로 직접 처리(fetch 등)하고 싶을 때가 많다. **preventDefault()**는 **이런 브라우저의 기본 동작을 취소**한다.

## 사용법

```javascript
form.addEventListener('submit', (e) => {
  e.preventDefault();  // 새로고침 막기
  // 대신 자바스크립트로 직접 처리
  const data = new FormData(form);
  fetch('/api/submit', { method: 'POST', body: data });
});
```

`e.preventDefault()`를 호출하면 원래 일어날 동작(폼 제출 → 새로고침)이 취소된다.

## 어디에 쓰나

| 기본 동작 | preventDefault로 막는 이유 |
|---|---|
| 폼 제출 새로고침 | JS로 직접 처리하려고 |
| 링크 이동(a 태그) | SPA 라우팅으로 처리하려고 |
| 우클릭 메뉴 | 커스텀 메뉴를 띄우려고 |

## 실무 포인트

- **stopPropagation과 헷갈리지 마라.** `preventDefault`는 "기본 동작 취소", `stopPropagation`은 "이벤트가 부모로 전파되는 것 막기"로 서로 다르다. 목적에 맞는 것을 쓴다. 둘 다 필요하면 둘 다 호출한다.
- **접근성을 해치지 마라.** 링크(`<a>`)의 기본 이동을 막고 JS로만 처리하면, JS가 실패했을 때 이동이 안 된다. 가능하면 실제 `href`를 두고 JS로 보강하는 편이 안전하다.
- **모든 이벤트에 기본 동작이 있는 건 아니다.** `preventDefault`는 취소 가능한 기본 동작이 있는 이벤트(submit, click on link 등)에서만 의미가 있다. `event.cancelable`로 취소 가능한지 확인할 수 있다.

## 마무리 요약

- preventDefault()는 폼 제출 새로고침·링크 이동 같은 브라우저 기본 동작을 취소한다.
- 폼을 JS로 직접 처리하거나 SPA 라우팅을 할 때 자주 쓴다.
- 이벤트 전파를 막는 stopPropagation과 다르며, 접근성을 해치지 않게 주의한다.

## 참고 자료

- [MDN - preventDefault](https://developer.mozilla.org/ko/docs/Web/API/Event/preventDefault)
