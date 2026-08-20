---
layout: single
title: "setTimeout과 setInterval이 뭔가요 — 자바스크립트 타이머"
date: 2026-09-17 12:30:00 +0530
categories: frontend
tags: ["settimeout", "setinterval", "타이머", "자바스크립트", "입문"]
toc: true
toc_sticky: true
excerpt: "일정 시간 뒤 또는 주기적으로 코드를 실행하는 setTimeout·setInterval의 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## "3초 뒤에", "1초마다" 실행하려면

알림을 3초 뒤 닫거나, 1초마다 시계를 갱신하는 등 시간과 관련된 동작이 필요하다. 자바스크립트에서는 **setTimeout**(정해진 시간 뒤 한 번)과 **setInterval**(정해진 간격마다 반복)로 이를 한다.

## 사용법

```javascript
// 3초 뒤 한 번 실행
const t = setTimeout(() => console.log("3초 지남"), 3000);
clearTimeout(t); // 취소

// 1초마다 반복 실행
const i = setInterval(() => console.log("1초마다"), 1000);
clearInterval(i); // 멈춤
```

시간은 밀리초(ms) 단위다(1000ms = 1초). 반환값(id)을 `clearTimeout`/`clearInterval`에 넘겨 취소·중단한다.

## 실무 포인트

- **취소를 잊지 마라.** `setInterval`을 걸고 안 멈추면 컴포넌트가 사라져도 계속 돌아 메모리 누수·오류가 난다. React라면 `useEffect`의 정리(cleanup) 함수에서 `clearInterval`을 호출해 반드시 멈춘다.
- **정확한 시간은 보장 안 된다.** `setTimeout(fn, 1000)`은 "정확히 1초 후"가 아니라 "최소 1초 후, 그 시점에 여유가 생기면"이다. 자바스크립트는 한 번에 하나씩 처리하므로, 앞의 작업이 밀리면 타이머도 밀린다.
- **반복엔 setInterval 대신 재귀 setTimeout도.** 작업이 오래 걸리면 `setInterval`은 겹칠 수 있다. 이전 작업이 끝난 뒤 다음을 예약하는 재귀 `setTimeout`이 더 안전할 때가 있다.

## 마무리 요약

- setTimeout은 일정 시간 뒤 한 번, setInterval은 일정 간격마다 반복 실행한다(단위는 ms).
- 반환 id로 `clearTimeout`/`clearInterval`을 호출해 취소·중단하며, 정리를 꼭 해야 한다.
- 시간이 정확히 보장되지 않고, 반복은 상황에 따라 재귀 setTimeout이 더 안전하다.

## 참고 자료

- [MDN - setTimeout](https://developer.mozilla.org/ko/docs/Web/API/Window/setTimeout)
