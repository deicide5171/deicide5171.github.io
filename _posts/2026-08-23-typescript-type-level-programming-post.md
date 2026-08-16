---
layout: single
title: "문자열 URL이 타입 오류를 잡는다 — TypeScript 조건부 타입·infer·템플릿 리터럴 실무 활용"
date: 2026-08-23 13:30:00 +0530
categories: frontend
tags: ["typescript", "타입시스템", "조건부타입", "infer", "템플릿리터럴", "api"]
toc: true
toc_sticky: true
excerpt: "조건부 타입, infer, 템플릿 리터럴 타입을 조합해 API 경로 문자열에서 파라미터 타입을 자동 추출하는 타입 레벨 프로그래밍 기법과, 실무에서 어디까지 써야 하는지의 기준을 정리한다."
---

`fetch("/users/" + userId + "/posts/" + postId)` 같은 코드에서 파라미터 하나를 빼먹거나 오타를 내면, 컴파일러는 아무 말도 하지 않고 런타임에 404가 돌아온다. API 경로와 파라미터의 짝이 맞는지는 전통적으로 "사람이 잘 확인해야 하는 영역"이었다. 그런데 TypeScript의 타입 시스템은 이미 이 검증을 컴파일 타임으로 끌어올 수 있을 만큼 표현력이 좋아졌다. 조건부 타입(conditional types), `infer` 키워드, 그리고 템플릿 리터럴 타입(template literal types)을 조합하면 **문자열 리터럴 자체를 타입 수준에서 파싱**할 수 있기 때문이다.

이 조합의 대표적인 수혜자가 우리가 매일 쓰는 라이브러리들이다. tRPC는 서버 라우터 정의에서 클라이언트 타입을 통째로 추론하고, Hono나 최근의 Express 타입 정의는 `"/users/:id"` 같은 경로 문자열에서 `params`의 형태를 뽑아낸다. 이 글에서는 그 밑바닥에서 돌아가는 세 가지 도구를 하나씩 뜯어보고, 이것들을 조합해 경로 파라미터 타입을 추출하는 타입 안전한 API 클라이언트를 직접 만들어본다. 그리고 실무에서 더 중요한 질문 — **어디까지 직접 만들고, 어디서부터는 하지 말아야 하는가** — 도 함께 다룬다.

## 핵심 개념 1: 조건부 타입 — 타입 세계의 if문

조건부 타입은 `T extends U ? X : Y` 형태로, 타입 `T`가 `U`에 할당 가능하면 `X`, 아니면 `Y`가 되는 타입이다. 타입 레벨 프로그래밍에서 분기문 역할을 한다.

여기서 반드시 알아야 할 동작이 **분배 법칙(distributive conditional types)**이다. 조건부 타입의 검사 대상이 "벌거벗은(naked)" 타입 파라미터이면, 유니온 타입이 들어왔을 때 각 멤버에 조건이 **하나씩 분배**되어 적용된다.

```typescript
type ToArray<T> = T extends unknown ? T[] : never;

// string[] | number[] — (string | number)[] 가 아니다!
type A = ToArray<string | number>;

// 분배를 막고 싶으면 양쪽을 튜플로 감싼다
type ToArrayNonDist<T> = [T] extends [unknown] ? T[] : never;
type B = ToArrayNonDist<string | number>; // (string | number)[]
```

이 분배 동작은 `Exclude`, `Extract` 같은 유틸리티 타입의 원리이기도 하지만, 모르고 당하면 대표적인 함정이 된다. 뒤의 안티패턴 절에서 다시 짚는다.

## 핵심 개념 2: infer — 타입에서 정보를 "꺼내는" 유일한 방법

`infer`는 조건부 타입의 `extends` 절 안에서만 쓸 수 있는 키워드로, 매칭에 성공한 위치의 타입을 변수처럼 캡처한다. 내장 유틸리티 `ReturnType<T>`가 정확히 이 방식으로 구현되어 있다.

```typescript
type MyReturnType<T> = T extends (...args: never[]) => infer R ? R : never;

// Promise를 재귀적으로 벗겨내기 (내장 Awaited의 단순화 버전)
type UnwrapPromise<T> = T extends Promise<infer U> ? UnwrapPromise<U> : T;

type C = UnwrapPromise<Promise<Promise<number>>>; // number
```

함수의 반환 타입, 배열의 요소 타입, Promise의 내부 타입처럼 **다른 타입 안에 갇혀 있는 타입**을 꺼내려면 `infer` 외에 다른 수단이 없다. 타입 레벨 프로그래밍의 사실상 핵심 도구다.

## 핵심 개념 3: 템플릿 리터럴 타입 — 문자열을 타입으로 파싱하기

템플릿 리터럴 타입은 문자열 리터럴 타입을 조합·분해할 수 있게 해준다. `infer`와 결합하면 문자열 패턴 매칭이 가능해진다. 이 세 가지를 모두 조합한 실전 예제로, API 경로에서 파라미터를 추출하는 타입 안전 클라이언트를 만들어보자.

```typescript
// api-client.ts — 그대로 복사해 사용 가능

// 1) 경로 문자열에서 ":param" 이름들을 유니온으로 추출 (재귀)
type ExtractParams<Path extends string> =
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : Path extends `${string}:${infer Param}`
      ? Param
      : never;

// 2) 유니온을 매핑 타입으로 객체 형태로 변환
type PathParams<Path extends string> = {
  [K in ExtractParams<Path>]: string | number;
};

// 3) 파라미터가 없으면 인자를 아예 받지 않는 시그니처
type RequestArgs<Path extends string> =
  ExtractParams<Path> extends never
    ? [path: Path]
    : [path: Path, params: PathParams<Path>];

export async function apiGet<Path extends string>(
  ...[path, params]: RequestArgs<Path>
): Promise<unknown> {
  const url = params
    ? path.replace(/:([A-Za-z0-9_]+)/g, (_, k) =>
        encodeURIComponent(String((params as Record<string, unknown>)[k])),
      )
    : path;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.json();
}

// 사용 예 — 전부 컴파일 타임에 검증된다
await apiGet("/users/:userId/posts/:postId", { userId: 1, postId: 42 }); // OK
await apiGet("/health"); // OK — 파라미터 없는 경로는 두 번째 인자 금지
// await apiGet("/users/:userId/posts/:postId", { userId: 1 });
//   ^ 컴파일 오류: 'postId' 속성이 없습니다
```

`ExtractParams<"/users/:userId/posts/:postId">`는 `"userId" | "postId"`로 평가되고, 매핑 타입이 이를 `{ userId: string | number; postId: string | number }`로 바꾼다. 경로 문자열이 곧 스키마가 되는 셈이다.

<img src="/assets/images/posts/2026-08-23-typescript-type-level-programming-1.svg" alt="템플릿 리터럴 타입과 infer가 URL 문자열에서 파라미터 객체 타입을 추출하는 단계별 흐름도" style="width:100%;">

## 언제 쓰고, 언제 쓰지 말아야 하나

타입 레벨 프로그래밍은 강력하지만 공짜가 아니다. 판단 기준을 표로 정리하면 다음과 같다.

| 상황 | 권장 접근 | 이유 |
|---|---|---|
| 사내 공용 라이브러리·SDK의 공개 API | 타입 레벨 추론 적극 활용 | 한 번의 복잡도 투자로 수십 개 호출부가 안전해짐 |
| 백엔드에 OpenAPI/GraphQL 스키마가 있음 | openapi-typescript 등 **코드 생성** | 직접 파싱 타입을 만들 이유가 없음. 생성기가 유지보수까지 대신함 |
| 런타임 검증도 필요한 외부 입력 | Zod 등 스키마 라이브러리 + `z.infer` | 타입만으로는 런타임 데이터를 못 막음 |
| 앱 내부 비즈니스 로직의 일회성 타입 | 그냥 손으로 타입 작성 | 읽는 사람의 비용이 얻는 안전성보다 큼 |

핵심 기준은 **"이 타입을 읽고 고칠 사람이 몇 명이고, 이 타입이 지켜주는 호출부가 몇 곳인가"**다. 호출부가 많은 경계(라이브러리, 공용 클라이언트)에서는 복잡한 타입이 값을 하고, 호출부가 한두 곳인 내부 코드에서는 부채가 된다.

## 흔한 함정: 분배 조건부 타입과 boolean

실무에서 가장 자주 마주치는 안티패턴은 분배 법칙을 모른 채 유니온을 조건부 타입에 넣는 것이다. 특히 `boolean`이 위험한데, TypeScript에서 `boolean`은 내부적으로 `true | false` 유니온이라 조건이 두 번 분배된다.

```typescript
type IsBool<T> = T extends boolean ? "yes" : "no";
type Wrong = IsBool<boolean | string>;
// "yes" | "no" — 의도한 단일 답이 아니라 유니온이 돼버린다

// 올바른 대안: 튜플로 감싸 분배를 차단
type IsBoolStrict<T> = [T] extends [boolean] ? "yes" : "no";
type Right = IsBoolStrict<boolean | string>; // "no"
```

또 하나 주의할 점은 **재귀 깊이와 컴파일 성능**이다. 템플릿 리터럴 재귀는 컴파일러의 인스턴스화 깊이 제한에 걸릴 수 있고, 거대한 유니온(예: 수백 개 경로의 조합)을 만들면 IDE 자동완성이 눈에 띄게 느려진다. 타입이 복잡해질수록 오류 메시지도 난해해져서, 팀원이 오류를 읽고 스스로 고칠 수 없다면 그 타입은 이미 과했다는 신호다. 복잡한 타입에는 `tsd`나 Vitest의 `expectTypeOf` 같은 **타입 테스트**를 붙여 리팩터링 시 회귀를 잡는 것이 좋다.

## 마무리 요약

- 조건부 타입은 타입의 분기, `infer`는 타입 속 정보의 추출, 템플릿 리터럴 타입은 문자열의 타입 레벨 파싱을 담당하며, 셋을 조합하면 API 경로 문자열에서 파라미터 타입을 자동 추론할 수 있다.
- 호출부가 많은 경계(공용 클라이언트·SDK)에는 투자 가치가 충분하지만, OpenAPI 스키마가 있다면 코드 생성이 먼저고, 일회성 내부 타입은 손으로 쓰는 편이 낫다.
- 벌거벗은 타입 파라미터의 분배 법칙(특히 `boolean`)과 재귀 깊이·컴파일 성능은 대표적인 함정이므로, 튜플 감싸기와 타입 테스트로 방어하자.

## 참고 자료

- [TypeScript Handbook — Conditional Types](https://www.typescriptlang.org/docs/handbook/2/conditional-types.html)
- [TypeScript Handbook — Template Literal Types](https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html)
- [TypeScript Handbook — Mapped Types](https://www.typescriptlang.org/docs/handbook/2/mapped-types.html)
- [openapi-typescript 공식 문서](https://openapi-ts.dev/)
- [Zod 공식 문서](https://zod.dev/)
