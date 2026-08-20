---
layout: single
title: "얕은 복사와 깊은 복사가 뭔가요 — 객체 복사의 함정"
date: 2026-09-12 13:30:00 +0530
categories: frontend
tags: ["얕은복사", "깊은복사", "자바스크립트", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트에서 객체를 복사했는데 원본이 같이 바뀌는 문제의 원인인 얕은 복사와 깊은 복사의 차이를 처음 배우는 사람 기준으로 정리했다."
---

## 복사했는데 원본이 같이 바뀐다

객체를 복사해 값을 바꿨더니 원본까지 바뀌는 당황스러운 경험이 있다. 자바스크립트에서 객체는 **값이 아니라 참조(주소)**로 다뤄지기 때문이다. 복사에는 **얕은 복사(shallow copy)**와 **깊은 복사(deep copy)**가 있고, 이 차이를 모르면 버그가 생긴다.

## 얕은 복사 vs 깊은 복사

| 구분 | 얕은 복사 | 깊은 복사 |
|---|---|---|
| 1단계 값 | 새로 복사됨 | 새로 복사됨 |
| 중첩 객체 | 참조 공유(같이 바뀜) | 완전히 별도 복사 |
| 방법 | `{...obj}`, `Object.assign` | `structuredClone` 등 |

## 예시

```javascript
const a = { name: "철수", info: { age: 20 } };

// 얕은 복사
const b = { ...a };
b.info.age = 99;
console.log(a.info.age); // 99 (원본도 바뀜!)

// 깊은 복사
const c = structuredClone(a);
c.info.age = 50;
console.log(a.info.age); // 99 (원본 안 바뀜)
```

`{...a}`는 1단계 속성만 복사하고, 중첩된 `info`는 여전히 같은 객체를 가리킨다.

## 실무 포인트

- **중첩 객체가 없으면 얕은 복사로 충분.** 1단계 값(문자열·숫자)만 있는 평평한 객체는 `{...obj}`로 안전하게 복사된다. 중첩 구조일 때만 깊은 복사가 필요하다.
- **깊은 복사는 `structuredClone`을 쓴다.** 예전엔 `JSON.parse(JSON.stringify(obj))`를 썼지만, 이는 함수·`undefined`·`Date`를 제대로 못 다룬다. 최신 브라우저의 `structuredClone`이 더 안전하다.
- **불변성 유지에 중요하다.** React 상태 등은 원본을 직접 수정하지 않고 복사본을 바꿔야 한다. 중첩 상태를 얕게만 복사하면 원본이 변해 버그가 나므로, 바꾸는 부분까지 새로 복사한다.

## 마무리 요약

- 자바스크립트 객체는 참조로 다뤄져, 복사 방식에 따라 원본이 함께 바뀔 수 있다.
- 얕은 복사(`{...obj}`)는 1단계만, 깊은 복사(`structuredClone`)는 중첩까지 별도로 복사한다.
- 평평한 객체는 얕은 복사로 충분하고, 중첩 구조·불변성이 필요하면 깊은 복사를 쓴다.

## 참고 자료

- [MDN - 얕은 복사](https://developer.mozilla.org/ko/docs/Glossary/Shallow_copy)
