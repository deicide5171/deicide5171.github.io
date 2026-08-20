---
layout: single
title: "자바스크립트 전개/나머지(...) 연산자가 뭔가요"
date: 2026-09-19 13:30:00 +0530
categories: frontend
tags: ["javascript", "spread", "rest", "연산자", "입문"]
toc: true
toc_sticky: true
excerpt: "같은 점 세 개(...)가 상황에 따라 펼치기(spread)와 모으기(rest)로 다르게 동작하는 이유를 처음 배우는 사람 기준으로 정리했다."
---

## "점 세 개(...)가 어떨 땐 펼치고 어떨 땐 모은다?"

`...`는 같은 기호인데 쓰는 위치에 따라 반대로 동작한다. 값을 **펼칠 때**는 전개(spread), 여러 값을 **모을 때**는 나머지(rest)다. 둘을 구분하면 배열·객체를 훨씬 간결하게 다룰 수 있다.

## 전개(spread) — 펼치기

```js
// 배열 합치기
const a = [1, 2];
const b = [...a, 3, 4];        // [1, 2, 3, 4]

// 객체 복사·병합
const user = { name: "김" };
const updated = { ...user, age: 20 };  // {name:"김", age:20}

// 함수 인자로 펼치기
Math.max(...[3, 1, 5]);        // 5
```

## 나머지(rest) — 모으기

```js
// 나머지 인자를 배열로 모음
function sum(...nums) {
  return nums.reduce((a, b) => a + b, 0);
}
sum(1, 2, 3);                  // 6

// 구조분해에서 나머지를 모음
const [first, ...others] = [1, 2, 3];  // first=1, others=[2,3]
```

## 언제 무엇인가

| 위치 | 의미 |
|---|---|
| 값을 만드는 쪽(우변, 인자 전달) | 전개(펼치기) |
| 값을 받는 쪽(함수 파라미터, 구조분해 좌변) | 나머지(모으기) |

## 실무 포인트

- **얕은 복사에 유용.** `{...obj}`는 새 객체를 만들지만 한 겹만 복사한다(얕은 복사). 중첩 객체는 여전히 참조를 공유하니 주의한다.
- **불변 업데이트에 자주 쓴다.** React 등에서 기존 상태를 건드리지 않고 `{...state, key: value}`로 새 객체를 만들 때 핵심 도구다.
- **rest는 항상 마지막에.** 나머지 파라미터·구조분해의 `...`는 맨 뒤에만 올 수 있다.

## 마무리 요약

- `...`는 만드는 쪽에선 전개(펼치기), 받는 쪽에선 나머지(모으기)로 동작한다.
- 배열·객체 병합, 함수 인자 처리, 불변 업데이트에 두루 쓰인다.
- 객체 전개는 얕은 복사이며, rest는 항상 마지막 위치에 둔다.

## 참고 자료

- [MDN - Spread syntax](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Spread_syntax)
