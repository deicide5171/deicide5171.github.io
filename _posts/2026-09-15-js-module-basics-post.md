---
layout: single
title: "import/export가 뭔가요 — 자바스크립트 모듈 나눠 쓰기"
date: 2026-09-15 12:30:00 +0530
categories: frontend
tags: ["모듈", "import", "export", "자바스크립트", "입문"]
toc: true
toc_sticky: true
excerpt: "코드를 파일 단위로 나누고 서로 가져다 쓰는 자바스크립트 모듈(import/export)의 기본 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 코드를 한 파일에 다 넣으면 관리가 안 된다

모든 코드를 한 파일에 몰아넣으면 길고 재사용도 어렵다. **모듈(module)**은 **코드를 파일 단위로 나누고, 필요한 것만 서로 가져다 쓰는** 방식이다. 자바스크립트는 **export**로 내보내고 **import**로 가져온다.

## export와 import

```javascript
// math.js — 내보내기
export function add(a, b) { return a + b; }
export const PI = 3.14;

// main.js — 가져오기
import { add, PI } from './math.js';
add(1, 2); // 3
```

`export`한 것만 다른 파일에서 `import`할 수 있다. 내보내지 않은 것은 그 파일 안에서만 쓰인다.

## named vs default

| 방식 | 내보내기 | 가져오기 |
|---|---|---|
| named | `export const a` | `import { a }` |
| default | `export default fn` | `import fn` (이름 자유) |

## 실무 포인트

- **named export를 기본으로.** 이름이 정해진 named export는 자동완성·리팩터링이 쉽고, 오타를 잡기 좋다. default export는 파일당 하나만 가능하며 가져올 때 이름을 아무렇게나 지을 수 있어 일관성이 떨어질 수 있다.
- **경로와 확장자를 확인.** `./math.js`처럼 상대 경로로 가져온다. 브라우저 네이티브 모듈은 확장자가 필요하고, 번들러(Vite 등) 환경은 생략 가능한 경우가 많다. 환경에 맞춘다.
- **순환 참조를 피하라.** A가 B를 import하고 B가 다시 A를 import하면(순환) 값이 `undefined`가 되는 등 문제가 생긴다. 공통 코드를 별도 파일로 빼 순환을 끊는다.

## 마무리 요약

- 모듈은 코드를 파일 단위로 나누고 `export`로 내보내 `import`로 가져다 쓰는 방식이다.
- named export(이름 지정)와 default export(파일당 하나)가 있으며, named를 기본으로 권한다.
- 경로·확장자를 환경에 맞추고 순환 참조를 피해야 문제가 없다.

## 참고 자료

- [MDN - JavaScript 모듈](https://developer.mozilla.org/ko/docs/Web/JavaScript/Guide/Modules)
