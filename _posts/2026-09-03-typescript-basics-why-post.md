---
layout: single
title: "TypeScript를 왜 쓰나요 — 자바스크립트와 무엇이 다른지 기초부터"
date: 2026-09-03 12:30:00 +0530
categories: frontend
tags: ["typescript", "javascript", "타입", "입문", "프론트엔드기초"]
toc: true
toc_sticky: true
excerpt: "자바스크립트만 쓰던 사람이 TypeScript를 처음 접할 때, 타입이 실제로 어떤 문제를 막아주는지 예제로 정리했다."
---

## 왜 잘 돌아가는 JS에 타입을 굳이 붙이나

자바스크립트는 변수에 어떤 값이든 넣을 수 있어 유연하지만, 그 유연함이 실행 중에야 드러나는 버그로 돌아온다. `user.name`을 썼는데 `user`가 사실은 `undefined`였다거나, 숫자를 기대한 함수에 문자열이 들어가는 실수가 대표적이다. **TypeScript**는 이런 오류를 코드를 실행하기 전, 즉 작성하는 순간에 잡아준다.

## 타입이 막아주는 대표적 실수

```typescript
// 자바스크립트: 실행해봐야 에러를 안다
function getDiscount(price) {
  return price * 0.9;
}
getDiscount("1000"); // "1000" * 0.9 = 900이 아니라 이상한 결과... 실행 후에야 발견

// TypeScript: 작성하는 순간 빨간 줄
function getDiscount(price: number): number {
  return price * 0.9;
}
getDiscount("1000"); // 에러: string은 number에 할당할 수 없습니다
```

TypeScript는 결국 컴파일되면 평범한 자바스크립트가 되지만, 그 전 단계에서 타입 검사를 통해 명백한 실수를 걸러준다.

## 자바스크립트 vs 타입스크립트

| 항목 | JavaScript | TypeScript |
|---|---|---|
| 타입 검사 시점 | 없음(실행 중 오류) | 작성/컴파일 시점 |
| 자동완성 | 제한적 | 타입 기반으로 강력함 |
| 학습 부담 | 낮음 | 타입 문법을 추가로 배워야 함 |
| 리팩터링 | 이름 바꾸면 놓치기 쉬움 | 타입이 어긋나면 바로 알려줌 |

## 기본 타입 문법 맛보기

```typescript
let name: string = "김철수";
let age: number = 30;
let isActive: boolean = true;

// 객체 형태를 미리 정의(인터페이스)
interface User {
  id: number;
  name: string;
  email?: string; // ?는 있어도 되고 없어도 되는 선택적 속성
}

function greet(user: User): string {
  return `안녕하세요, ${user.name}님`;
}
```

`interface`로 데이터 형태를 미리 정의해두면, 그 형태와 다른 값을 넣으려 할 때 즉시 오류가 표시되고 에디터 자동완성도 그 형태를 기억해준다.

## 실무 포인트

- **처음부터 모든 것에 완벽한 타입을 붙이려 하지 마라.** `any` 타입으로 일단 넘기고 점진적으로 구체화하는 것도 가능하다. 다만 `any`를 남발하면 TypeScript를 쓰는 의미가 사라지므로 임시방편으로만 써야 한다.
- **타입은 문서 역할도 한다.** 함수의 매개변수·반환 타입만 봐도 그 함수가 무엇을 받고 무엇을 주는지 알 수 있어, 협업 시 별도 문서 없이도 의도가 전달된다.
- **컴파일 결과물은 결국 자바스크립트다.** 브라우저는 TypeScript를 직접 실행하지 못하므로, 빌드 단계에서 JS로 변환하는 과정이 반드시 필요하다는 점을 기억해야 한다.

## 마무리 요약

- TypeScript는 자바스크립트에 타입을 더해, 실행 전에 명백한 실수를 잡아주는 언어다.
- 타입은 오류 방지뿐 아니라 자동완성·리팩터링·문서화의 이점도 함께 준다.
- `any` 남용을 피하고 점진적으로 타입을 붙여가는 것이 현실적인 도입 방법이다.

## 참고 자료

- [TypeScript 공식 문서](https://www.typescriptlang.org/docs/)
- [TypeScript 핸드북 - 기본 타입](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html)
