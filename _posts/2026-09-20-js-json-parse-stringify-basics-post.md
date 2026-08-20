---
layout: single
title: "JSON.parse와 JSON.stringify가 뭔가요 — 객체와 문자열 변환"
date: 2026-09-20 12:30:00 +0530
categories: frontend
tags: ["javascript", "json", "parse", "stringify", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트 객체와 JSON 문자열을 서로 바꾸는 JSON.parse·JSON.stringify의 사용법과 함정을 처음 배우는 사람 기준으로 정리했다."
---

## "서버에서 온 데이터가 문자열인데 객체처럼 못 쓴다"

서버 응답이나 localStorage 값은 문자열이라, `data.name`처럼 바로 접근하면 안 된다. 문자열을 객체로 바꾸려면 `JSON.parse`, 반대로 객체를 문자열로 바꾸려면 `JSON.stringify`를 쓴다.

## 두 함수의 방향

```js
// 문자열 → 객체
const text = '{"name":"김","age":20}';
const obj = JSON.parse(text);
obj.name;              // "김"

// 객체 → 문자열
const user = { name: "김", age: 20 };
const json = JSON.stringify(user);
// '{"name":"김","age":20}'
```

| 함수 | 방향 | 쓰임 |
|---|---|---|
| JSON.parse | 문자열 → 객체 | 응답·저장값 읽기 |
| JSON.stringify | 객체 → 문자열 | 전송·저장 |

## 자주 쓰는 옵션

```js
// 보기 좋게 들여쓰기 (2칸)
JSON.stringify(user, null, 2);

// 특정 키만 포함
JSON.stringify(user, ["name"]);   // {"name":"김"}
```

## 실무 포인트

- **parse는 실패할 수 있다.** 잘못된 JSON 문자열이면 예외를 던진다. 신뢰할 수 없는 입력은 `try/catch`로 감싼다.
- **일부 값은 사라진다.** `undefined`, 함수, `Symbol`은 stringify에서 빠지고, `Date`는 문자열로 바뀐다. 복원 시 원래 타입이 아님에 주의한다.
- **얕은 깊은 복사 트릭의 한계.** `JSON.parse(JSON.stringify(obj))`로 깊은 복사를 흉내 낼 수 있지만, 위 사라지는 값들 때문에 완전하지 않다.

## 마무리 요약

- JSON.parse는 문자열을 객체로, JSON.stringify는 객체를 문자열로 바꾼다.
- 전송·저장 전엔 stringify, 읽을 땐 parse가 짝을 이룬다.
- parse는 예외 처리를 하고, stringify에서 undefined·함수·Date 처리에 주의한다.

## 참고 자료

- [MDN - JSON](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON)
