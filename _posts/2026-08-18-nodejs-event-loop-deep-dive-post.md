---
layout: single
title: "Node.js 이벤트 루프 심화 이해하기 — 마이크로태스크와 매크로태스크 실행 순서 정리"
date: 2026-08-18 12:25:00 +0530
categories: backend
tags: ["nodejs", "event-loop", "microtask", "macrotask", "javascript", "async"]
toc: true
toc_sticky: true
excerpt: "setTimeout과 Promise.then, process.nextTick과 setImmediate 중 무엇이 먼저 실행되는지 헷갈렸던 적이 있다면, Node.js 이벤트 루프의 단계 구조와 마이크로태스크·매크로태스크 처리 순서를 코드로 정리했다."
---

## 왜 지금 이벤트 루프를 다시 봐야 하는가

Node.js는 단일 스레드로 동작하면서도 대량의 동시 I/O를 처리한다는 것이 가장 큰 특징이다. 이 특징을 가능하게 하는 것이 바로 **이벤트 루프(Event Loop)** 다. 그런데 실무에서는 정작 이벤트 루프의 세부 동작을 정확히 모른 채로 코드를 짜는 경우가 많다. `setTimeout(fn, 0)`과 `setImmediate(fn)` 중 무엇이 먼저 실행되는지, `process.nextTick()`과 `Promise.then()`이 같은 우선순위인지, 콜백 안에서 재귀적으로 뭔가를 계속 등록하면 이벤트 루프가 멈추는 이유가 무엇인지 — 이런 질문에 자신 있게 답하지 못하면, 비동기 로직의 실행 순서가 꼬였을 때 원인을 찾기가 어려워진다.

특히 async/await, Promise 체이닝, 콜백 기반 API(fs, net 모듈 등)가 한 함수 안에 뒤섞여 있는 실무 코드베이스에서는 "이 코드가 정확히 언제 실행되는가"를 예측하지 못하면 레이스 컨디션이나 응답 지연의 원인을 잘못 짚기 쉽다. 이 글은 Node.js 이벤트 루프의 단계(phase) 구조와, 그 사이사이에 끼어드는 마이크로태스크 큐의 처리 순서를 정리한다.

## 핵심 개념 1: 이벤트 루프의 6단계

Node.js의 이벤트 루프는 libuv가 관리하는 여러 단계(phase)를 순서대로, 그리고 반복해서 순환한다. 각 단계는 자신만의 콜백 큐를 가지고 있고, 큐가 비거나 정해진 콜백 개수 제한에 도달하면 다음 단계로 넘어간다.

| 단계 | 처리하는 콜백 | 대표 API |
|---|---|---|
| timers | 예약 시간이 지난 타이머 콜백 | `setTimeout`, `setInterval` |
| pending callbacks | 일부 시스템 레벨 콜백(TCP 에러 등) | 내부적으로 지연된 I/O 콜백 |
| poll | I/O 콜백 실행, 새 I/O 이벤트 대기 | 파일 읽기, 네트워크 소켓 |
| check | poll 단계 직후 실행되는 콜백 | `setImmediate` |
| close callbacks | 리소스 종료 시 콜백 | `socket.on('close', ...)` |

여기서 "idle, prepare" 같은 Node.js 내부 전용 단계는 애플리케이션 코드가 직접 다룰 일이 거의 없어 생략했다. 실무에서 자주 마주치는 것은 timers, poll, check 세 단계이며, 특히 poll 단계는 대기 중인 콜백이 없으면 새 I/O 이벤트를 기다리며 잠깐 블로킹된다는 점이 특징이다.

## 핵심 개념 2: 마이크로태스크 vs 매크로태스크

이벤트 루프의 각 단계가 처리하는 콜백을 흔히 **매크로태스크(macrotask)** 라 부른다. 반면 `Promise`, `process.nextTick()`, `queueMicrotask()`로 등록되는 콜백은 **마이크로태스크(microtask)** 라 부르며, 이는 단계 구조와 별도로 독립된 큐에서 관리된다.

| 구분 | 큐 종류 | 대표 API | 처리 시점 |
|---|---|---|---|
| 마이크로태스크 | nextTick 큐 (우선), microtask 큐 | `process.nextTick`, `Promise.then/catch/finally`, `queueMicrotask` | 현재 실행 중인 콜백이 콜 스택에서 빠지는 즉시, 다음 매크로태스크로 넘어가기 전에 큐가 빌 때까지 전부 처리 |
| 매크로태스크 | 단계별 콜백 큐 | `setTimeout`, `setInterval`, I/O 콜백, `setImmediate` | 자신이 속한 단계 차례가 왔을 때, 한 번에 하나씩 실행 |

핵심은 **마이크로태스크 큐는 매크로태스크 하나와 다음 매크로태스크 하나 사이에 반드시 끼어든다**는 점이다. 심지어 마이크로태스크 실행 중에 새로운 마이크로태스크가 등록되면, 그것도 큐가 완전히 빌 때까지 이번 비우기 사이클 안에서 함께 처리된다. `setTimeout`이나 `setImmediate`는 아무리 짧은 지연이라도 다음 단계 순번을 기다려야 하지만, `Promise.then`은 그 대기가 없다.

<img src="/assets/images/posts/2026-08-18-nodejs-event-loop-deep-dive-1.svg" alt="Node.js 이벤트 루프 단계 순환 구조와 각 단계 사이 마이크로태스크 큐 비우기 시점" style="width:100%;">

## 핵심 개념 3: nextTick과 Promise 중 무엇이 먼저인가

마이크로태스크 안에서도 우선순위가 갈린다. Node.js는 `process.nextTick()`으로 등록된 콜백을 위한 별도의 nextTick 큐를 두고, 이를 Promise용 microtask 큐보다 **먼저** 전부 비운다. 즉 같은 시점에 `process.nextTick`과 `Promise.then`을 등록하면 nextTick 콜백이 항상 먼저 실행된다. 다만 `process.nextTick`을 콜백 안에서 재귀적으로 계속 등록하면 nextTick 큐가 절대 비지 않아 poll 단계로 넘어가지 못하는 "I/O 기아(starvation)" 상태에 빠질 수 있다는 점은 실무에서 반드시 주의해야 한다.

## 예제: 실행 순서 확인하기

```javascript
console.log('1: 동기 코드 시작');

setTimeout(() => {
  console.log('2: setTimeout (timers 단계, 매크로태스크)');
}, 0);

setImmediate(() => {
  console.log('3: setImmediate (check 단계, 매크로태스크)');
});

Promise.resolve().then(() => {
  console.log('4: Promise.then (마이크로태스크)');
});

process.nextTick(() => {
  console.log('5: process.nextTick (마이크로태스크, 최우선)');
});

console.log('6: 동기 코드 끝');

// 실행 순서: 1 -> 6 -> 5 -> 4 -> (2와 3 중 하나, 실행 컨텍스트에 따라 순서가 달라질 수 있음)
```

동기 코드(`1`, `6`)가 먼저 콜 스택을 모두 비운 뒤, 콜 스택이 완전히 빈 시점에 마이크로태스크 큐가 처리된다. 이때 nextTick 큐(`5`)가 Promise microtask 큐(`4`)보다 먼저 소진된다. 이후에야 매크로태스크(`2`, `3`)가 각자 속한 단계 순번에 따라 실행된다. 참고로 `setTimeout(fn, 0)`과 `setImmediate(fn)`을 최상위 모듈 스코프에서 함께 실행하면 어느 쪽이 먼저 실행될지는 타이머 정밀도 등 실행 환경에 따라 달라질 수 있어 이 둘의 순서를 코드로 단정하지는 않는다. 다만 I/O 콜백 내부에서 실행하면 poll 단계 직후 check 단계가 바로 이어지므로 `setImmediate`가 항상 먼저 실행된다는 점은 Node.js가 문서로 보장하는 동작이다.

## 실무 포인트

- **CPU 바운드 연산은 이벤트 루프를 블로킹한다는 점을 기억한다**: 이벤트 루프는 단일 스레드로 동작하므로, 무거운 동기 연산(대량 데이터 정렬, 정규식 백트래킹 등)이 콜 스택을 오래 점유하면 그동안 어떤 타이머·I/O 콜백도 실행되지 못한다. 무거운 연산은 워커 스레드(`worker_threads`)나 별도 프로세스로 분리하는 것을 검토한다.
- **`process.nextTick`의 재귀 호출을 피한다**: 콜백 안에서 조건 없이 `process.nextTick`을 계속 등록하면 nextTick 큐가 비워지지 않아 다음 매크로태스크(I/O 처리 포함)로 넘어가지 못한다. 재귀적인 지연 실행이 필요하다면 `setImmediate`나 `setTimeout`을 사용하는 편이 안전하다.
- **async/await 뒤에는 항상 마이크로태스크가 있다는 점을 이해한다**: `await`로 감싼 Promise가 resolve된 뒤 실행되는 코드는 마이크로태스크로 스케줄링된다. 콘솔 로그 순서가 예상과 다르게 나온다면, 동기 코드와 마이크로태스크·매크로태스크의 실행 시점 차이를 먼저 의심해본다.
- **디버깅에는 `async_hooks`나 프로파일러를 활용한다**: 복잡한 비동기 흐름에서 실행 순서를 눈으로 추적하기 어렵다면, 로그에 타임스탬프를 남기거나 Node.js 내장 프로파일링 도구로 실제 이벤트 루프 지연(latency)을 측정해 가정을 검증하는 것이 확실하다.

## 3줄 요약

- Node.js 이벤트 루프는 timers·poll·check 등 여러 단계를 순환하며, 각 단계가 처리하는 콜백을 매크로태스크라 부른다.
- Promise·process.nextTick·queueMicrotask로 등록되는 마이크로태스크는 매크로태스크 하나와 다음 매크로태스크 사이에 반드시 끼어들어, 큐가 빌 때까지 먼저 전부 처리된다.
- nextTick 큐가 Promise microtask 큐보다 먼저 소진되지만, nextTick을 재귀적으로 계속 등록하면 다음 단계로 넘어가지 못하는 I/O 기아 상태에 빠질 수 있어 주의가 필요하다.

## 참고 자료

- [Node.js 공식 문서 — The Node.js Event Loop, Timers, and process.nextTick()](https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick)
- [MDN — Microtasks](https://developer.mozilla.org/en-US/docs/Web/API/HTML_DOM_API/Microtask_guide)
- [Node.js 공식 문서 — Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop)
