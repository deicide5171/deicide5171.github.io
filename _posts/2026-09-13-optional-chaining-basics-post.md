---
layout: single
title: "옵셔널 체이닝 ?.이 뭔가요 — undefined 에러 안 나게 접근하기"
date: 2026-09-13 13:30:00 +0530
categories: frontend
tags: ["옵셔널체이닝", "optionalchaining", "자바스크립트", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "중첩된 객체 속성에 안전하게 접근하는 옵셔널 체이닝(?.)과 널 병합(??)의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## `Cannot read properties of undefined` 에러

`user.address.city`처럼 중첩 속성에 접근할 때, `address`가 없으면 "Cannot read properties of undefined" 에러로 앱이 멈춘다. 예전엔 `user && user.address && user.address.city`처럼 일일이 확인해야 했다. **옵셔널 체이닝(`?.`)**은 이 확인을 **간결하게** 해준다.

## 사용법

```javascript
// 예전 방식
const city = user && user.address && user.address.city;

// 옵셔널 체이닝
const city = user?.address?.city;
// address가 없으면 에러 대신 undefined 반환
```

`?.`은 앞의 값이 `null`/`undefined`면 거기서 멈추고 `undefined`를 돌려준다. 에러가 안 난다.

## 널 병합 연산자 ??와 함께

```javascript
const city = user?.address?.city ?? "미입력";
// city가 없으면(undefined/null) "미입력"을 기본값으로
```

`??`(널 병합)는 왼쪽이 `null`/`undefined`일 때만 오른쪽 기본값을 쓴다. `?.`과 자주 짝지어 쓴다.

## 실무 포인트

- **API 응답 다룰 때 유용.** 서버 응답이 항상 모든 필드를 주는 건 아니다. `data?.user?.profile?.name`처럼 쓰면 중간이 비어도 앱이 안 죽는다. 방어적 코드가 짧아진다.
- **`??`와 `||`는 다르다.** `||`는 `0`·`""`·`false`도 "없음"으로 보고 기본값을 쓴다. `??`는 오직 `null`/`undefined`만 없음으로 본다. `0`이 유효한 값이면 `??`를 써야 한다.
- **함수·배열에도 쓸 수 있다.** `obj.method?.()`(메서드가 있으면 호출), `arr?.[0]`(배열이 있으면 접근)처럼 함수 호출·인덱스 접근에도 쓴다.

## 마무리 요약

- 옵셔널 체이닝(`?.`)은 중첩 속성 접근 시 중간이 없으면 에러 대신 `undefined`를 반환한다.
- 널 병합(`??`)과 함께 쓰면 값이 없을 때 기본값을 깔끔하게 지정할 수 있다.
- `??`는 `null`/`undefined`만, `||`는 `0`·`""`도 없음으로 보니 구분해서 쓴다.

## 참고 자료

- [MDN - 옵셔널 체이닝](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Optional_chaining)
