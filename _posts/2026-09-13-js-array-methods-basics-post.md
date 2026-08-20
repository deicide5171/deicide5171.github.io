---
layout: single
title: "map, filter, reduce가 뭔가요 — 반복문 없이 배열 다루기"
date: 2026-09-13 12:30:00 +0530
categories: frontend
tags: ["배열메서드", "map", "filter", "reduce", "입문"]
toc: true
toc_sticky: true
excerpt: "자바스크립트에서 for 반복문 대신 배열을 간결하게 다루는 map·filter·reduce의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## for 문을 매번 쓰기 번거롭다

배열의 각 값을 변형하거나, 조건에 맞는 것만 고르거나, 합계를 구하는 일은 아주 흔하다. `for` 문으로도 되지만 코드가 길다. 자바스크립트의 **map·filter·reduce**는 **이런 배열 처리를 한 줄로 간결하게** 표현하는 메서드다.

## 세 메서드의 역할

| 메서드 | 하는 일 | 결과 |
|---|---|---|
| `map` | 각 값을 변형 | 같은 길이 새 배열 |
| `filter` | 조건 맞는 것만 남김 | 더 짧을 수 있는 배열 |
| `reduce` | 하나의 값으로 합침 | 단일 값(합계 등) |

## 예시

```javascript
const nums = [1, 2, 3, 4];

// map: 각 값을 2배로
nums.map(n => n * 2);          // [2, 4, 6, 8]

// filter: 짝수만
nums.filter(n => n % 2 === 0); // [2, 4]

// reduce: 전부 더하기
nums.reduce((sum, n) => sum + n, 0); // 10
```

## 실무 포인트

- **원본을 바꾸지 않는다.** map·filter는 새 배열을 반환하고 원본은 그대로 둔다. 그래서 React 상태처럼 불변성이 중요한 곳에서 안전하게 쓸 수 있다.
- **체이닝으로 이어 쓴다.** `arr.filter(...).map(...)`처럼 이어 쓰면 "조건 거르고 → 변형"을 읽기 쉽게 표현한다. 단, 큰 배열에서 여러 번 순회하니 성능이 중요하면 한 번에 처리하는 방법도 고려한다.
- **reduce는 강력하지만 남용 금지.** reduce로 거의 모든 걸 할 수 있지만, 복잡하게 쓰면 읽기 어렵다. 단순 합계·개수는 reduce, 그 외엔 map/filter나 명시적 반복이 더 읽기 쉬울 때가 많다.

## 마무리 요약

- map은 각 값 변형, filter는 조건 필터링, reduce는 하나의 값으로 합치는 배열 메서드다.
- 원본을 바꾸지 않고 새 배열/값을 반환해 불변성이 중요한 곳에 적합하다.
- 체이닝으로 간결하게 쓰되, reduce 남용과 대용량 다중 순회 성능에 주의한다.

## 참고 자료

- [MDN - Array.prototype.map](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Global_Objects/Array/map)
