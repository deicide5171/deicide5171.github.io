---
layout: single
title: "폼 검증 규칙을 타입과 함께 — Zod·Valibot 스키마 기반 검증 패턴"
date: 2026-08-28 13:30:00 +0530
categories: frontend
tags: ["frontend", "zod", "valibot", "form-validation", "typescript"]
toc: true
toc_sticky: true
excerpt: "폼 검증 로직을 TypeScript 타입과 별개로 관리하다 둘이 어긋나는 문제를, 스키마 하나에서 타입과 런타임 검증을 동시에 얻는 Zod와, 번들 크기를 줄인 Valibot으로 해결하는 패턴을 정리한다."
---

TypeScript의 타입은 컴파일 시점에만 존재하고 런타임에는 완전히 사라진다. 그래서 폼 입력값처럼 실행 중에 들어오는 데이터는 아무리 `interface FormData { email: string }`라고 선언해봤자, 실제로 그 값이 이메일 형식인지, 빈 문자열이 아닌지는 별도의 검증 로직을 직접 짜야 한다. 문제는 이 검증 로직과 타입 선언이 서로 다른 곳에 따로 존재하면, 타입을 고쳤는데 검증 로직은 안 고치거나 그 반대인 상황이 반복된다는 것이다.

**Zod**와 **Valibot** 같은 스키마 검증 라이브러리는 이 문제를 "스키마를 하나만 정의하면 타입과 런타임 검증이 동시에 나온다"는 방식으로 해결한다. 스키마가 유일한 진실의 원천(single source of truth)이 되고, TypeScript 타입은 그 스키마에서 자동으로 추론된다. 이 글에서는 스키마 기반 검증의 핵심 패턴과, Zod와 Valibot 중 무엇을 고를지 정리한다.

## 핵심 개념 1: 스키마에서 타입을 추론한다 — 반대 방향의 흐름

전통적인 흐름은 "타입을 먼저 정의하고, 그 타입에 맞는지 검증하는 함수를 따로 짠다"였다. 스키마 기반 라이브러리는 이 순서를 뒤집는다. 스키마(런타임에 실제로 존재하는 객체)를 먼저 정의하면, TypeScript의 타입 추론 기능(`z.infer`, `v.InferOutput`)이 그 스키마로부터 타입을 자동으로 뽑아낸다. 스키마를 고치면 타입도 자동으로 따라 바뀌므로, 둘이 어긋나는 상황 자체가 구조적으로 발생하지 않는다.

```typescript
import { z } from "zod";

const signupSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  age: z.number().int().min(14),
});

// 타입은 스키마에서 자동으로 추론됨 - 별도로 interface를 쓸 필요 없음
type SignupInput = z.infer<typeof signupSchema>;
```

## 핵심 개념 2: 파싱은 타입 단언이 아니라 실제 검증이다

`as` 타입 단언은 컴파일러에게 "이 값이 이 타입이라고 믿어달라"고 말할 뿐, 실제로 그 값이 맞는지는 전혀 확인하지 않는다. 외부에서 들어온 데이터(폼 입력, API 응답)에 `as`를 쓰면 타입 체커는 통과하지만 런타임에 실제 값이 다르면 그대로 버그가 된다. 스키마의 `.parse()`나 `.safeParse()`는 이와 다르게 **실제로 값을 검사하고, 검증에 성공한 경우에만** 타입이 보장된 값을 반환한다. `.parse()`는 실패 시 예외를 던지고, `.safeParse()`는 예외 없이 `{ success: true, data }` 또는 `{ success: false, error }` 형태의 결과 객체를 반환해 에러 처리를 분기문으로 다룰 수 있게 한다.

## 핵심 개념 3: Zod vs Valibot — 번들 크기와 API 스타일의 차이

Zod는 메서드 체이닝 스타일(`z.string().email().min(3)`)로 널리 쓰이는 사실상의 표준이지만, 이 체이닝 구조 특성상 트리 셰이킹(사용하지 않는 코드 제거)이 제한적이어서 번들에 필요 이상의 코드가 포함되는 경향이 있다. **Valibot**은 함수 조합 스타일(`v.pipe(v.string(), v.email(), v.minLength(3))`)로 같은 기능을 제공하면서, 각 검증 규칙이 독립적인 함수로 분리돼 있어 사용하지 않는 검증 규칙은 번들에서 완전히 제외된다. 그 결과 같은 수준의 검증 로직에서 Valibot 쪽 번들 크기가 훨씬 작게 나오는 경우가 많다.

| 기준 | Zod | Valibot |
|---|---|---|
| API 스타일 | 메서드 체이닝 | 함수 조합(pipe) |
| 번들 크기 | 상대적으로 큼(트리 셰이킹 제한적) | 매우 작음(트리 셰이킹 친화적) |
| 생태계·자료 | 매우 성숙, 대부분의 폼 라이브러리 지원 | 빠르게 성장 중, 지원 늘어나는 중 |
| 학습 곡선 | 낮음(직관적 체이닝) | 약간 있음(pipe 문법 적응 필요) |
| 적합한 상황 | 서버 코드, 번들 크기 민감도 낮은 곳 | 클라이언트 번들 크기가 중요한 곳 |

<img src="/assets/images/posts/2026-08-28-form-validation-zod-valibot-1.svg" alt="스키마 하나를 정의하면 타입 추론과 런타임 파싱이 동시에 나오는 구조, 그리고 Zod의 메서드 체이닝과 Valibot의 함수 조합 스타일 비교" style="width:100%;">

## 예제: React Hook Form과 결합한 폼 검증

```typescript
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const signupSchema = z.object({
  email: z.string().email("올바른 이메일 형식이 아닙니다"),
  password: z.string().min(8, "비밀번호는 8자 이상이어야 합니다"),
});

type SignupForm = z.infer<typeof signupSchema>;

function SignupPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<SignupForm>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = (data: SignupForm) => {
    // 이 시점의 data는 스키마 검증을 통과한 값이므로 타입과 실제 값이 100% 일치함
    submitSignup(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register("email")} />
      {errors.email && <span>{errors.email.message}</span>}
      <input type="password" {...register("password")} />
      {errors.password && <span>{errors.password.message}</span>}
      <button type="submit">가입하기</button>
    </form>
  );
}
```

`zodResolver`는 React Hook Form의 검증 로직을 Zod 스키마로 위임하는 어댑터로, 필드별 에러 메시지가 자동으로 `formState.errors`에 매핑된다. 같은 스키마를 서버 API의 요청 바디 검증에도 그대로 재사용하면, 클라이언트와 서버의 검증 규칙이 어긋나는 문제도 함께 없어진다.

## 실무 포인트

- **클라이언트 검증과 서버 검증에 같은 스키마를 재사용할 것**: 클라이언트 폼과 서버 API가 각자 다른 검증 로직을 갖고 있으면 결국 어긋난다. 스키마를 공유 패키지로 분리해 두 곳에서 import하는 구조가 일관성을 보장한다.
- **`.safeParse()`를 기본으로 쓰고 예외 기반 `.parse()`는 신중히 쓸 것**: 외부 입력을 다루는 코드에서 예외가 예상치 못한 곳까지 전파되면 디버깅이 어려워진다. 실패를 값으로 다루는 `safeParse` 스타일이 에러 처리 흐름을 더 명시적으로 만든다.
- **번들 크기가 실제로 문제인지 먼저 측정할 것**: 대부분의 애플리케이션에서 검증 라이브러리의 번들 기여도는 크지 않다. Valibot으로의 전환은 실제 번들 분석 결과(예: `source-map-explorer`)로 문제를 확인한 뒤 결정하는 것이 순서다.

## 3줄 요약

- Zod·Valibot 같은 스키마 기반 검증 라이브러리는 스키마 하나로 TypeScript 타입 추론과 런타임 검증을 동시에 얻어, 타입과 검증 로직이 어긋나는 문제를 구조적으로 없앤다.
- `.safeParse()`는 타입 단언과 달리 실제로 값을 검사하고 성공한 값에만 타입을 보장하므로 외부 입력을 다루는 표준 방식이 되어야 한다.
- Zod는 성숙한 생태계와 직관적 체이닝이, Valibot은 트리 셰이킹 친화적인 작은 번들 크기가 강점이므로 번들 크기 민감도에 따라 선택하면 된다.

## 참고 자료

- [Zod 공식 문서](https://zod.dev/)
- [Valibot 공식 문서](https://valibot.dev/)
- [React Hook Form 공식 문서: Schema Validation](https://react-hook-form.com/get-started#SchemaValidation)
