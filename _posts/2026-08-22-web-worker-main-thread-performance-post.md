---
layout: single
title: "Web Worker로 메인 스레드 해방시키기 — 프론트엔드 성능의 마지막 퍼즐"
date: 2026-08-22 13:30:00 +0530
categories: frontend
tags: ["frontend", "web-worker", "performance", "main-thread", "javascript"]
toc: true
toc_sticky: true
excerpt: "무거운 연산 하나가 스크롤·클릭 응답을 멈추게 하는 메인 스레드 병목을, Web Worker로 별도 스레드에 위임해 해소하는 실전 패턴과 통신 오버헤드 트레이드오프를 정리한다."
---

자바스크립트는 기본적으로 싱글 스레드에서 동작한다. 화면을 그리는 렌더링, 사용자의 클릭이나 스크롤을 처리하는 입력 이벤트, 그리고 우리가 작성한 로직 실행이 모두 같은 스레드 위에서 순서를 다툰다. 문제는 이 중 하나가 오래 걸리면 나머지 전부가 멈춘다는 점이다. 대용량 JSON을 파싱하거나, 이미지를 픽셀 단위로 가공하거나, 복잡한 필터링 연산을 동기적으로 돌리는 순간 브라우저는 그 작업이 끝날 때까지 화면 갱신도, 클릭 반응도 미룰 수밖에 없다.

이런 병목은 최근 들어 INP(Interaction to Next Paint)라는 지표로 더 뚜렷하게 드러나고 있다. INP는 사용자가 상호작용을 시작한 시점부터 다음 화면이 그려질 때까지의 지연을 측정하는데, 메인 스레드가 무거운 연산으로 막혀 있으면 이 값이 그대로 나빠진다. 결국 "느린 페이지"라는 체감은 대부분 메인 스레드가 한 가지 작업에 붙잡혀 있는 상황에서 비롯된다.

Web Worker는 이 문제에 대한 브라우저 표준의 답이다. 메인 스레드와 별도로 동작하는 스레드를 하나 띄워, 무거운 연산을 그쪽으로 넘기고 메인 스레드는 렌더링과 입력 처리에만 집중하게 만드는 방식이다. 이 글에서는 Web Worker가 어떻게 동작하는지, 어떤 작업을 옮기는 게 적절한지, 그리고 통신 과정에서 생기는 비용을 어떻게 줄이는지를 정리한다.

## 핵심 개념 1: Web Worker의 기본 동작 원리

Web Worker는 브라우저가 제공하는 별도의 실행 스레드다. 메인 스레드와 완전히 분리된 컨텍스트에서 자바스크립트 파일을 실행하기 때문에, 워커 안에서 아무리 무거운 연산을 돌려도 메인 스레드의 렌더링 루프나 이벤트 루프는 영향을 받지 않는다. 다만 이 분리에는 대가가 따르는데, 워커는 `window` 객체나 DOM에 직접 접근할 수 없다. `document.querySelector` 같은 호출은 워커 안에서 존재하지 않는다.

대신 메인 스레드와 워커는 `postMessage`를 통해서만 데이터를 주고받는다. 메인 스레드가 워커에게 작업 데이터를 보내면 워커는 그 데이터를 받아 연산을 수행하고, 결과를 다시 `postMessage`로 돌려보낸다. 두 컨텍스트가 메모리를 공유하지 않으므로, 이 메시지를 주고받을 때 데이터는 참조가 아니라 값으로 전달된다. 이 값 전달 방식이 다음 개념에서 다룰 비용 문제와 직결된다.

## 핵심 개념 2: 워커로 옮기기 좋은 연산 패턴

모든 무거운 작업이 워커로 옮길 가치가 있는 것은 아니다. 워커로 위임하기 적합한 대표적인 사례는 대용량 텍스트나 JSON의 파싱, 이미지 리사이징이나 픽셀 단위 필터 처리, 정렬이나 검색 같은 CPU 집약적 연산, 암호화나 해시 계산처럼 DOM과 무관하게 입력을 받아 출력을 계산하는 순수 연산들이다. 이런 작업들은 공통적으로 "입력 데이터를 받아 DOM 조작 없이 결과값만 계산한다"는 특징을 가진다.

반대로 DOM을 직접 조작해야 하거나, 결과를 즉시 화면에 반영해야 하는 작업은 워커로 옮기기 어렵다. 실무에서는 무거운 계산 부분만 워커로 분리하고, 계산이 끝난 결과를 메인 스레드가 받아 DOM에 반영하는 식으로 역할을 나누는 패턴이 일반적이다.

## 핵심 개념 3: 구조화 복제 비용과 Transferable Objects

`postMessage`로 데이터를 넘길 때 브라우저는 구조화 복제 알고리즘(structured clone algorithm)을 사용해 객체를 통째로 복제한다. 이 복제는 참조 전달보다 안전하지만, 데이터 크기가 커질수록 복제 자체에 시간과 메모리가 든다. 특히 큰 배열이나 이미지 데이터를 매번 통째로 복제해서 주고받으면, 워커로 연산을 옮긴 이득이 통신 비용에 상쇄될 수 있다.

이를 줄이기 위한 수단이 Transferable Objects다. `ArrayBuffer`처럼 전송 가능한(transferable) 타입은 `postMessage`의 두 번째 인자로 명시하면 복제 없이 소유권 자체가 넘어간다. 데이터를 보낸 쪽에서는 그 시점부터 해당 버퍼에 접근할 수 없게 되지만, 대신 복제 비용이 사실상 사라진다. 대용량 이진 데이터를 주고받는 경우라면 Transferable Objects를 쓰는지 여부가 체감 성능을 크게 좌우한다.

## 예제

아래는 메인 스레드에서 워커를 생성해 무거운 연산을 위임하고 결과를 받는 기본 패턴이다.

```javascript
// main.js — 메인 스레드
const worker = new Worker("worker.js");

worker.postMessage({ type: "PROCESS", payload: largeArray });

worker.onmessage = (event) => {
  const { type, result } = event.data;
  if (type === "DONE") {
    // 결과를 받아 화면에 반영
    renderResult(result);
  }
};

worker.onerror = (err) => {
  console.error("워커 에러:", err.message);
};
```

```javascript
// worker.js — 워커 스레드
self.onmessage = (event) => {
  const { type, payload } = event.data;
  if (type === "PROCESS") {
    // DOM 접근 없이 순수 연산만 수행
    const result = payload.map((v) => heavyCompute(v));
    self.postMessage({ type: "DONE", result });
  }
};

function heavyCompute(value) {
  // 예시용 무거운 연산
  let acc = value;
  for (let i = 0; i < 1e6; i++) acc = (acc * 31 + i) % 1_000_000_007;
  return acc;
}
```

## 실무 포인트

- **작은 작업에는 워커가 오히려 손해일 수 있다.** 워커 생성과 스크립트 로딩, 그리고 메시지 전달 자체에도 시간이 든다. 연산이 몇 밀리초 수준으로 가벼운 경우라면, 워커를 새로 띄우고 데이터를 주고받는 오버헤드가 연산 자체보다 커질 수 있다. 워커 재사용(하나의 워커에 여러 작업을 계속 보내는 방식)이나 워커 풀 도입도 이런 오버헤드를 줄이는 방법으로 고려할 만하다.
- **디버깅이 메인 스레드 코드보다 까다롭다.** 워커는 별도의 실행 컨텍스트이기 때문에 브라우저 개발자 도구에서 스택 추적이나 브레이크포인트를 다루는 경험이 메인 스레드와 다르고, 콘솔 로그도 별도로 확인해야 하는 경우가 많다. 워커 내부 에러가 조용히 묻히지 않도록 `onerror` 핸들러를 항상 등록해두는 습관이 필요하다.

## 3줄 요약

- 자바스크립트는 싱글 스레드라 무거운 동기 연산이 렌더링과 입력 처리까지 막아버리며, 이는 INP 같은 지표로 체감된다.
- Web Worker는 별도 스레드에서 DOM 접근 없이 순수 연산을 수행하고 `postMessage`로 결과를 주고받는 방식으로 메인 스레드를 해방시킨다.
- 데이터가 크다면 구조화 복제 비용을 줄이기 위해 Transferable Objects를 고려하되, 작은 작업까지 워커로 옮기면 생성·통신 오버헤드가 오히려 손해가 될 수 있다.

## 참고 자료

- [MDN: Web Workers API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API)
- [MDN: Worker.postMessage()](https://developer.mozilla.org/en-US/docs/Web/API/Worker/postMessage)
- [MDN: Transferable objects](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Transferable_objects)
- [web.dev: Interaction to Next Paint (INP)](https://web.dev/articles/inp)
