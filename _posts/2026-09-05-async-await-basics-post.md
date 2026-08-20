---
layout: single
title: "async/await 기초 — 콜백 지옥에서 벗어나기"
date: 2026-09-05 12:30:00 +0530
categories: frontend
tags: ["async", "await", "promise", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트 비동기 처리의 핵심인 Promise와 async/await가 콜백 지옥을 어떻게 해결하는지 예제로 정리했다."
---

## 왜 비동기 처리가 헷갈리나

자바스크립트에서 서버에 데이터를 요청하는 것 같은 작업은 결과가 즉시 오지 않는다(비동기). "요청을 보내고, 결과가 오면 그때 처리하라"고 코드를 짜야 하는데, 이걸 콜백 함수로 중첩하다 보면 코드가 오른쪽으로 계속 밀려나는 **콜백 지옥**에 빠진다.

## 콜백 지옥의 모습

```javascript
// 순서대로 실행해야 하는 세 작업을 콜백으로 중첩
getUser(1, (user) => {
  getOrders(user.id, (orders) => {
    getOrderDetail(orders[0].id, (detail) => {
      console.log(detail); // 계속 들여쓰기가 깊어진다...
    });
  });
});
```

## async/await로 펼치기

`async/await`를 쓰면 비동기 코드를 마치 순차적으로 실행되는 것처럼 위에서 아래로 읽히게 쓸 수 있다.

```javascript
async function showOrderDetail() {
  const user = await getUser(1);
  const orders = await getOrders(user.id);
  const detail = await getOrderDetail(orders[0].id);
  console.log(detail); // 들여쓰기 없이 평평하게!
}
```

`await`는 "이 작업이 끝날 때까지 기다렸다가 결과를 받아라"는 뜻이다. `await`를 쓰는 함수는 반드시 `async`로 선언해야 한다.

## 에러 처리는 try/catch로

```javascript
async function showOrderDetail() {
  try {
    const user = await getUser(1);
    const orders = await getOrders(user.id);
    console.log(orders);
  } catch (error) {
    console.error("실패:", error); // 어느 단계에서 실패해도 여기서 잡힘
  }
}
```

콜백 방식에서는 단계마다 에러를 따로 처리해야 했지만, async/await에서는 일반 동기 코드처럼 `try/catch`로 한 번에 처리할 수 있다.

## 실무 포인트

- **순서가 상관없는 작업은 병렬로 처리하라.** 세 개의 독립적인 요청을 `await`로 하나씩 기다리면 순차 실행되어 느리다. `Promise.all([a(), b(), c()])`로 묶으면 동시에 실행되어 훨씬 빠르다.

```javascript
// 느림: 순차 (총 3초)
const a = await fetchA(); // 1초
const b = await fetchB(); // 1초
const c = await fetchC(); // 1초

// 빠름: 병렬 (총 1초)
const [a, b, c] = await Promise.all([fetchA(), fetchB(), fetchC()]);
```

- **`await`는 async 함수 안에서만 쓸 수 있다.** 최상위(모듈 최상단)에서 쓰려면 top-level await를 지원하는 환경이어야 한다.
- **에러 처리를 빼먹지 마라.** async 함수에서 처리 안 된 에러(unhandled rejection)는 조용히 사라지거나 예상치 못한 곳에서 터질 수 있으므로, `try/catch`나 `.catch()`로 반드시 처리해야 한다.

## 마무리 요약

- async/await는 콜백 지옥을 해결해 비동기 코드를 위에서 아래로 읽히게 만든다.
- `await`는 작업 완료를 기다리며, 이를 쓰는 함수는 `async`로 선언해야 한다.
- 에러는 `try/catch`로 처리하고, 순서가 상관없는 작업은 `Promise.all`로 병렬 실행해 성능을 높인다.

## 참고 자료

- [MDN - async/await](https://developer.mozilla.org/ko/docs/Learn/JavaScript/Asynchronous/Promises)
- [javascript.info - async/await](https://ko.javascript.info/async-await)
