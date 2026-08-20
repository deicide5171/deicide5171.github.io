---
layout: single
title: "프로미스(Promise)가 뭔가요 — 자바스크립트 비동기의 기본"
date: 2026-09-09 12:30:00 +0530
categories: frontend
tags: ["promise", "비동기", "자바스크립트", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트에서 비동기 작업의 결과를 다루는 프로미스의 개념과 then/catch 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 결과가 나중에 오는 작업을 어떻게 다루나

서버에서 데이터를 받아오는 작업은 시간이 걸린다. 자바스크립트는 이 결과를 기다리며 멈추지 않고 다음 코드를 계속 실행한다(비동기). 그럼 결과는 어떻게 받을까? **프로미스(Promise)**는 **"나중에 완료될 작업의 결과를 담는 약속 상자"**다. 작업이 끝나면 성공값이나 실패 이유가 이 상자에 담긴다.

## 프로미스의 3가지 상태

| 상태 | 의미 |
|---|---|
| 대기(pending) | 아직 결과가 안 나옴 |
| 이행(fulfilled) | 성공, 결과값이 있음 |
| 거부(rejected) | 실패, 에러 이유가 있음 |

## then / catch로 결과 받기

```javascript
fetch('/api/user')
  .then(response => response.json())  // 성공하면 실행
  .then(data => console.log(data))    // 그 결과로 다시 실행
  .catch(error => console.log('실패:', error)); // 실패하면 실행
```

`then`은 성공했을 때, `catch`는 실패했을 때 실행된다. `then`을 이어 붙여(체이닝) 여러 단계를 순서대로 처리할 수 있다.

## async/await로 더 깔끔하게

```javascript
async function loadUser() {
  try {
    const response = await fetch('/api/user'); // 결과를 기다림
    const data = await response.json();
    console.log(data);
  } catch (error) {
    console.log('실패:', error);
  }
}
```

`await`는 프로미스의 결과가 나올 때까지 기다렸다가 값을 꺼내준다. 동기 코드처럼 읽혀서 더 이해하기 쉽다.

## 실무 포인트

- **에러 처리를 빼먹지 마라.** `catch`나 `try/catch`가 없으면 실패가 조용히 묻힌다. 네트워크 요청은 언제든 실패할 수 있으므로 항상 실패 경로를 다뤄야 한다.
- **여러 작업을 동시에 하려면 `Promise.all`.** 서로 독립적인 요청 여러 개를 기다릴 땐 `await`를 하나씩 하지 말고 `Promise.all([...])`로 병렬 처리하면 훨씬 빠르다.
- **await는 async 함수 안에서만.** `await`는 `async` 함수 안에서만 쓸 수 있다. 최상위에서 쓰려면 모듈의 top-level await 지원 여부를 확인한다.

## 마무리 요약

- 프로미스는 나중에 완료될 비동기 작업의 결과(성공/실패)를 담는 객체다.
- `then`(성공)·`catch`(실패)로 결과를 받고, `async/await`로 더 읽기 쉽게 쓸 수 있다.
- 에러 처리를 반드시 넣고, 독립 작업은 `Promise.all`로 병렬 처리하면 좋다.

## 참고 자료

- [MDN - Promise](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Global_Objects/Promise)
