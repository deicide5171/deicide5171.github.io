---
layout: single
title: "React 19 Actions로 폼 상태관리 다시 설계하기 — useActionState 실전 가이드"
date: 2026-08-16 12:30:00 +0530
categories: frontend
tags: ["react", "react19", "actions", "useactionstate", "form-state"]
toc: true
toc_sticky: true
excerpt: "React 19 정식 릴리스로 안정화된 Actions와 useActionState, useFormStatus, useOptimistic을 조합해 onSubmit + useState로 짜던 폼 상태관리 코드를 어떻게 다시 설계할 수 있는지 정리한다."
---

## 왜 지금 Actions인가

React 19가 정식 릴리스되면서 `useActionState`, `useFormStatus`, `useOptimistic`, `use` 같은 훅이 실험 단계를 벗어나 안정 API로 자리 잡았다. 이 훅들의 공통 배경이 **Actions**다. `<form action={fn}>`처럼 폼 제출을 비동기 함수(Action)로 다루면, React가 제출 중(pending) 상태와 결과 상태를 자동으로 추적해준다.

지금까지 폼 하나를 제대로 다루려면 `isLoading`, `error`, `data` 같은 state 서너 개를 `useState`로 따로 선언하고, `onSubmit` 안에서 `setIsLoading(true)` → 요청 → `setError` 또는 `setData` → `setIsLoading(false)`를 손으로 맞춰야 했다. 요청이 겹치거나 컴포넌트가 언마운트되는 경계 케이스까지 챙기면 코드가 금세 지저분해진다. Actions는 이 반복 패턴 자체를 훅으로 표준화해, 폼 상태관리 코드의 기본 형태를 바꿔놓았다.

## 핵심 개념 1: Actions와 useActionState

Action은 "폼 데이터를 받아 새로운 상태를 반환하는 비동기 함수"다. `useActionState(action, initialState)`에 이 함수를 넘기면 현재 상태, `form`에 바로 꽂을 수 있는 `formAction`, 그리고 진행 중 여부(`isPending`)를 반환한다.

| 이전 방식 (useState 수동 관리) | React 19 Actions |
|---|---|
| `isLoading`, `error`, `data`를 각각 useState로 선언 | `useActionState`가 하나의 state 객체로 통합 |
| `onSubmit`에서 `preventDefault` + 수동 try/catch | Action 함수가 결과를 반환하면 자동 반영 |
| pending 상태를 props로 계속 내려줘야 함 | 하위 컴포넌트가 `useFormStatus`로 직접 구독 |
| 낙관적 업데이트를 별도 로직으로 직접 구현 | `useOptimistic`으로 응답 전 상태를 선언적으로 표현 |

## 핵심 개념 2: 함께 쓰는 훅의 역할 분담

- **useActionState** — 폼 전체의 제출 결과(성공/실패, 에러 메시지)와 pending 여부를 관리하는 최상위 훅
- **useFormStatus** — `<form>` 내부의 자식 컴포넌트(예: 제출 버튼)가 부모의 pending 상태를 props 전달 없이 직접 읽는 훅
- **useOptimistic** — 서버 응답이 오기 전에 "성공했다고 가정한" 화면을 먼저 보여주고, 실제 응답이 오면 정정하는 훅

세 훅은 역할이 겹치지 않고 조합해서 쓰도록 설계돼 있다. 아래 다이어그램은 제출부터 상태 갱신까지의 흐름을 정리한 것이다.

<img src="/assets/images/posts/2026-08-16-react19-actions-form-state-1.svg" alt="React 19 Actions 폼 제출 데이터 흐름 - form action, Action 함수, state 반환과 useActionState/useFormStatus/useOptimistic 관계도" style="width:100%;">

## 예제: useActionState로 회원가입 폼 다시 짜기

```tsx
import { useActionState } from "react";

type FormState = { error: string | null; success: boolean };

async function signupAction(
  prevState: FormState,
  formData: FormData
): Promise<FormState> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  if (!email.includes("@")) {
    return { error: "올바른 이메일을 입력하세요.", success: false };
  }

  const res = await fetch("/api/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    return { error: "가입에 실패했습니다. 잠시 후 다시 시도하세요.", success: false };
  }
  return { error: null, success: true };
}

export function SignupForm() {
  const [state, formAction, isPending] = useActionState(signupAction, {
    error: null,
    success: false,
  });

  return (
    <form action={formAction}>
      <input name="email" type="email" placeholder="이메일" />
      <input name="password" type="password" placeholder="비밀번호" />
      {state.error && <p style={{ color: "red" }}>{state.error}</p>}
      {state.success && <p>가입이 완료되었습니다.</p>}
      <button type="submit" disabled={isPending}>
        {isPending ? "처리 중..." : "가입하기"}
      </button>
    </form>
  );
}
```

`isLoading`/`error`/`success`를 각각 useState로 선언하던 코드가 `useActionState` 하나로 정리됐고, 버튼의 `disabled` 처리도 별도 state 없이 `isPending` 값 그대로 쓴다.

## 실무 포인트

- **기존 useState 기반 폼을 전부 마이그레이션할 필요는 없다.** 검증 로직이 단순한 폼은 그대로 두고, 서버 왕복이 있고 pending/에러 처리가 반복되는 폼부터 우선 전환하는 편이 비용 대비 효과가 크다.
- **useFormStatus는 반드시 `<form>` 하위 컴포넌트에서만 동작한다.** form과 같은 레벨이나 부모에서 호출하면 상태를 읽지 못하므로, 제출 버튼을 별도 컴포넌트로 분리해야 값이 정상적으로 들어온다.
- **useOptimistic은 실패 시 롤백을 스스로 처리하지 않는다.** 실제 요청이 실패하면 최종 state를 실패 값으로 되돌리는 로직을 Action 함수 안에 명시적으로 넣어야, 화면이 낙관적 상태에 머물러 있는 문제를 피할 수 있다.
- **서버 컴포넌트/서버 액션과 함께 쓰는 경우 프레임워크 버전을 확인한다.** Next.js 등 메타프레임워크의 Server Actions 통합 방식은 프레임워크별로 세부 동작이 다르므로, 도입 전 해당 프레임워크의 React 19 지원 버전을 먼저 확인하는 것이 안전하다.

## 3줄 요약

- React 19에서 정식 안정화된 Actions는 `useState`로 손수 관리하던 폼의 pending/에러 상태를 `useActionState` 하나로 표준화한다.
- `useFormStatus`는 하위 컴포넌트의 pending 구독을, `useOptimistic`은 응답 전 낙관적 UI 표현을 각각 담당하며 세 훅은 조합해서 쓰도록 설계됐다.
- 전면 마이그레이션보다는 서버 왕복이 잦고 상태 처리가 반복되는 폼부터 우선 적용하고, 낙관적 업데이트의 실패 롤백은 직접 챙겨야 한다.

## 참고 자료

- [React 공식 문서 — useActionState](https://react.dev/reference/react/useActionState)
- [React 공식 문서 — useFormStatus](https://react.dev/reference/react-dom/hooks/useFormStatus)
- [React 공식 문서 — useOptimistic](https://react.dev/reference/react/useOptimistic)
- [React Blog — React 19](https://react.dev/blog/2024/12/05/react-19)
