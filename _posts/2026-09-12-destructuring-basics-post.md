---
layout: single
title: "구조 분해 할당이 뭔가요 — 객체·배열에서 값 꺼내기"
date: 2026-09-12 12:30:00 +0530
categories: frontend
tags: ["구조분해", "destructuring", "자바스크립트", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "객체와 배열에서 값을 간결하게 꺼내는 자바스크립트 구조 분해 할당의 문법과 활용을 처음 배우는 사람 기준으로 정리했다."
---

## 객체에서 값을 하나씩 꺼내기 번거롭다

객체나 배열에서 값을 꺼낼 때 `const name = user.name; const age = user.age;`처럼 하나씩 쓰면 반복이 많다. **구조 분해 할당(destructuring)**은 **객체·배열의 값을 한 번에 여러 변수로 꺼내는** 문법이다.

## 객체와 배열

```javascript
// 객체 구조 분해
const user = { name: "철수", age: 20 };
const { name, age } = user;   // name="철수", age=20

// 배열 구조 분해
const arr = [1, 2, 3];
const [first, second] = arr;  // first=1, second=2
```

객체는 `{}`와 키 이름으로, 배열은 `[]`와 순서로 값을 꺼낸다.

## 자주 쓰는 형태

| 문법 | 의미 |
|---|---|
| `const {a = 1} = obj` | 없으면 기본값 1 |
| `const {a: x} = obj` | a를 x라는 이름으로 |
| `const [, b] = arr` | 첫 값 건너뛰고 두 번째만 |
| `function f({a, b})` | 매개변수에서 바로 분해 |

## 실무 포인트

- **함수 매개변수에 자주 쓴다.** `function api({url, method, body})`처럼 옵션 객체를 받아 바로 분해하면, 인자 순서를 외울 필요 없이 이름으로 넘길 수 있어 가독성이 좋다. React props도 이렇게 많이 받는다.
- **기본값으로 안전하게.** `const {timeout = 5000} = options`처럼 기본값을 주면, 값이 없어도 `undefined` 대신 기본값이 들어가 오류를 줄인다.
- **깊은 분해는 적당히.** `const {a: {b: {c}}} = obj`처럼 너무 깊게 분해하면 읽기 어렵고, 중간이 `undefined`면 에러가 난다. 너무 깊으면 단계를 나누는 것이 안전하다.

## 마무리 요약

- 구조 분해 할당은 객체·배열의 값을 한 번에 여러 변수로 꺼내는 문법이다.
- 객체는 키 이름으로, 배열은 순서로 꺼내며 기본값·이름 바꾸기·건너뛰기가 가능하다.
- 함수 매개변수·React props에 유용하고, 기본값으로 안전하게 쓰되 너무 깊은 분해는 피한다.

## 참고 자료

- [MDN - 구조 분해 할당](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Destructuring_assignment)
