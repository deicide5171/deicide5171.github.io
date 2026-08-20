---
layout: single
title: "자바스크립트 this가 뭔가요 — 호출 방법이 값을 정한다"
date: 2026-09-11 12:30:00 +0530
categories: frontend
tags: ["this", "자바스크립트", "javascript", "바인딩", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트의 this가 왜 상황마다 다른 값을 가리키는지, 화살표 함수는 어떻게 다른지 처음 배우는 사람 기준으로 정리했다."
---

## this가 매번 다른 걸 가리킨다

자바스크립트의 **this**는 다른 언어와 달리 "선언한 위치"가 아니라 **"어떻게 호출했느냐"**에 따라 값이 정해진다. 그래서 같은 함수라도 호출 방법에 따라 this가 달라져 초보자를 혼란스럽게 한다.

## 호출 방식별 this

| 호출 방식 | this가 가리키는 것 |
|---|---|
| 일반 함수 호출 | 전역 객체 또는 undefined(strict) |
| 메서드 호출 `obj.fn()` | 그 객체(`obj`) |
| 생성자 `new Fn()` | 새로 만들어진 객체 |
| 화살표 함수 | 바깥 스코프의 this(고정) |

## 예시

```javascript
const user = {
  name: "철수",
  greet() { console.log(this.name); }
};
user.greet();          // "철수" (obj.method 호출 -> this=user)

const fn = user.greet;
fn();                  // undefined (일반 호출 -> this가 user 아님!)
```

메서드를 변수에 담아 그냥 호출하면 this 연결이 끊긴다. "누가 호출했나"가 사라지기 때문이다.

## 화살표 함수는 다르다

```javascript
const obj = {
  name: "영희",
  hi() {
    setTimeout(() => console.log(this.name), 100); // "영희"
  }
};
```

화살표 함수는 자기만의 this가 없고 **바깥의 this를 그대로** 쓴다. 그래서 콜백 안에서도 바깥 객체를 안정적으로 가리킨다.

## 실무 포인트

- **콜백에선 화살표 함수를 써라.** `setTimeout`·이벤트 핸들러 등 콜백 안에서 일반 함수를 쓰면 this가 엉뚱한 것을 가리키기 쉽다. 화살표 함수를 쓰면 바깥 this를 유지해 문제가 준다.
- **메서드를 떼어 넘길 땐 조심하라.** `obj.method`를 콜백으로 넘기면 this 연결이 끊긴다. `obj.method.bind(obj)`로 묶거나 `() => obj.method()`로 감싸 넘긴다.
- **클래스에서 특히 자주 겪는다.** 리액트 클래스 컴포넌트나 이벤트 핸들러에서 this 문제가 흔하다. 필드에 화살표 함수로 정의하거나 생성자에서 `bind`하는 패턴을 알아두면 좋다.

## 마무리 요약

- 자바스크립트 this는 선언 위치가 아니라 "어떻게 호출했느냐"로 값이 정해진다.
- 메서드 호출은 그 객체, 일반 호출은 전역/undefined, 생성자는 새 객체를 가리킨다.
- 화살표 함수는 바깥 this를 그대로 쓰므로 콜백에서 유용하며, 메서드를 떼어 넘길 땐 bind로 묶는다.

## 참고 자료

- [MDN - this](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/this)
