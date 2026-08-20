---
layout: single
title: "React useState, useEffect 처음 배우기 — Hooks 기초"
date: 2026-09-01 12:30:00 +0530
categories: frontend
tags: ["react", "hooks", "usestate", "useeffect", "입문"]
toc: true
toc_sticky: true
excerpt: "React를 처음 배울 때 가장 먼저 마주치는 useState와 useEffect가 각각 무엇을 위한 훅인지, 예제와 함께 기초부터 정리했다."
---

## 왜 컴포넌트 안에서 일반 변수를 쓰면 화면이 안 바뀌나

React 컴포넌트 함수 안에 `let count = 0`처럼 일반 변수를 두고 값을 바꿔도 화면은 갱신되지 않는다. React는 "이 값이 바뀌면 화면을 다시 그려야 한다"는 것을 알 방법이 없기 때문이다. **useState**는 React에게 "이 값이 상태(state)이고, 바뀌면 화면을 다시 그려달라"고 알려주는 훅이다.

## useState 기본 사용법

```jsx
import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0); // 초기값 0

  return (
    <div>
      <p>현재 카운트: {count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  );
}
```

`useState(0)`은 `[현재값, 값을 바꾸는 함수]` 쌍을 반환한다. `setCount`를 호출하면 React가 새 값으로 상태를 갱신하고 컴포넌트를 다시 렌더링한다. `count = count + 1`처럼 직접 값을 바꾸면 화면이 갱신되지 않는다는 점이 처음 배울 때 가장 헷갈리는 부분이다.

## useEffect: 렌더링 이후에 할 일을 처리한다

컴포넌트가 화면에 그려진 뒤에 API를 호출하거나 타이머를 등록하는 등 **부수 효과(side effect)**를 처리할 때 `useEffect`를 쓴다.

```jsx
import { useState, useEffect } from 'react';

function UserProfile({ userId }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(data => setUser(data));
  }, [userId]); // userId가 바뀔 때만 다시 실행

  if (!user) return <p>로딩 중...</p>;
  return <p>{user.name}님 환영합니다</p>;
}
```

두 번째 인자인 **의존성 배열(dependency array)**이 핵심이다. `[userId]`를 넣으면 `userId`가 바뀔 때만 effect가 다시 실행된다. 이 배열을 빠뜨리면 렌더링될 때마다 매번 실행되고, 빈 배열 `[]`을 넣으면 최초 렌더링 시 딱 한 번만 실행된다.

## 실무 포인트

- **의존성 배열을 빠뜨리는 것이 초보자가 가장 자주 하는 실수다.** ESLint의 `react-hooks/exhaustive-deps` 규칙을 켜두면 빠진 의존성을 자동으로 경고해준다.
- **useEffect 안에서 등록한 이벤트 리스너나 타이머는 반드시 정리(cleanup) 함수로 해제해야 한다.** 정리하지 않으면 컴포넌트가 사라진 뒤에도 리스너가 남아 메모리 누수와 예상치 못한 동작을 일으킨다.

```jsx
useEffect(() => {
  const timer = setInterval(() => console.log('tick'), 1000);
  return () => clearInterval(timer); // 컴포넌트가 사라질 때 정리
}, []);
```

- **훅은 컴포넌트 최상위에서만 호출해야 한다.** `if`문이나 반복문 안에서 훅을 호출하면 React가 상태를 추적하지 못해 오류가 난다.

## 마무리 요약

- useState는 컴포넌트가 기억해야 할 값을 관리하고, 값이 바뀌면 화면을 다시 그리게 한다.
- useEffect는 렌더링 이후의 부수 효과(API 호출, 구독 등)를 처리하며, 의존성 배열로 실행 시점을 제어한다.
- 이벤트 리스너나 타이머는 반드시 cleanup 함수로 정리해야 메모리 누수를 막을 수 있다.

## 참고 자료

- [React 공식 문서 - useState](https://react.dev/reference/react/useState)
- [React 공식 문서 - useEffect](https://react.dev/reference/react/useEffect)
