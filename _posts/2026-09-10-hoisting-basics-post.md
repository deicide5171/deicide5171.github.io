---
layout: single
title: "호이스팅이 뭔가요 — 선언 전에 쓴 변수가 왜 undefined인가"
date: 2026-09-10 12:30:00 +0530
categories: frontend
tags: ["호이스팅", "hoisting", "자바스크립트", "var", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트에서 변수·함수 선언이 위로 끌어올려지는 호이스팅 현상과 var·let·const의 차이를 처음 배우는 사람 기준으로 정리했다."
---

## 선언보다 먼저 썼는데 에러가 안 난다

자바스크립트에서 아래 코드는 에러 대신 `undefined`를 출력한다. 상식과 다르다.

```javascript
console.log(x); // undefined (에러 아님!)
var x = 5;
```

이는 **호이스팅(hoisting)** 때문이다. 자바스크립트는 실행 전에 **변수·함수의 "선언"을 그 범위의 맨 위로 끌어올린 것처럼** 처리한다. 위 코드는 `var x;`(선언)가 위로 올라가고, 값 할당(`x = 5`)은 원래 자리에 남는다.

## var / let / const의 차이

| 종류 | 호이스팅 | 선언 전 사용 |
|---|---|---|
| `var` | 됨, `undefined`로 초기화 | undefined (버그 유발) |
| `let` / `const` | 됨, 하지만 초기화 안 됨 | 에러(TDZ) |

`let`·`const`도 끌어올려지지만, 선언 전 구간(TDZ, 일시적 사각지대)에서 쓰면 **에러**를 낸다. 이게 오히려 안전하다.

## 함수 호이스팅

```javascript
sayHi(); // 정상 동작! (함수 선언은 통째로 끌어올려짐)
function sayHi() { console.log("안녕"); }

sayBye(); // 에러 (함수 표현식은 변수 규칙 따름)
const sayBye = function() { console.log("잘가"); };
```

## 실무 포인트

- **`var` 대신 `let`·`const`를 써라.** `var`의 호이스팅은 "선언 전 undefined" 같은 헷갈리는 버그를 만든다. 최신 코드는 `let`·`const`를 기본으로 쓰고, 이러면 선언 전 사용이 에러로 잡혀 안전하다.
- **변수는 쓰기 직전에 선언하라.** 호이스팅에 기대지 말고 선언을 사용 지점 가까이 두면, 코드가 읽는 순서대로 동작해 혼란이 없다.
- **함수 선언과 표현식의 차이를 알아두라.** `function foo(){}`(선언문)는 통째로 끌어올려져 위에서 호출 가능하지만, `const foo = () => {}`(표현식)는 변수 규칙을 따라 선언 전 호출 시 에러다.

## 마무리 요약

- 호이스팅은 변수·함수 선언이 범위의 맨 위로 끌어올려진 것처럼 처리되는 현상이다.
- `var`는 선언 전 `undefined`가 되지만, `let`·`const`는 선언 전 사용 시 에러(TDZ)로 더 안전하다.
- 함수 선언문은 통째로 끌어올려지고, 함수 표현식은 변수 규칙을 따른다. `let`·`const` 사용을 권한다.

## 참고 자료

- [MDN - 호이스팅](https://developer.mozilla.org/ko/docs/Glossary/Hoisting)
