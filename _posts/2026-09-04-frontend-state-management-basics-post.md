---
layout: single
title: "상태관리가 왜 필요한가 — props drilling부터 Context까지"
date: 2026-09-04 12:30:00 +0530
categories: frontend
tags: ["상태관리", "react", "context", "props", "입문"]
toc: true
toc_sticky: true
excerpt: "React를 배우다 상태관리 라이브러리가 왜 필요한지 막막할 때, props 전달의 한계와 Context의 등장 배경을 예제로 정리했다."
---

## 왜 useState만으로는 부족해지는가

React를 처음 배울 때는 `useState`로 컴포넌트 안에서 상태를 관리한다. 문제는 그 상태를 멀리 떨어진 자식 컴포넌트에서 써야 할 때 생긴다. 상태를 쓰려는 컴포넌트가 트리에서 깊은 곳에 있으면, 중간에 있는 컴포넌트들이 자기는 쓰지도 않는 데이터를 props로 계속 전달만 해줘야 한다. 이것을 **props drilling(프롭스 내려꽂기)**이라 부른다.

## props drilling의 문제

```jsx
// user 정보를 최상위에서 관리하는데, 깊은 곳의 Avatar에서 써야 한다
function App() {
  const [user, setUser] = useState(...);
  return <Layout user={user} />;
}
function Layout({ user }) {
  return <Header user={user} />;   // Layout은 user를 안 쓰는데 전달만 함
}
function Header({ user }) {
  return <Avatar user={user} />;   // Header도 전달만 함
}
function Avatar({ user }) {
  return <img src={user.avatarUrl} />; // 여기서야 실제로 씀
}
```

중간 컴포넌트들이 자기와 상관없는 `user`를 계속 넘기느라 코드가 지저분해지고, `user`의 구조가 바뀌면 거쳐가는 모든 컴포넌트를 수정해야 한다.

## Context: 전역으로 꺼내 쓰기

React의 **Context**는 이 문제를 해결한다. 데이터를 특정 지점에 "보관"해두면, 그 아래 어느 컴포넌트든 중간 전달 없이 직접 꺼내 쓸 수 있다.

```jsx
const UserContext = createContext(null);

function App() {
  const [user, setUser] = useState(...);
  return (
    <UserContext.Provider value={user}>
      <Layout /> {/* 이제 user를 props로 안 넘겨도 된다 */}
    </UserContext.Provider>
  );
}

function Avatar() {
  const user = useContext(UserContext); // 직접 꺼내 씀
  return <img src={user.avatarUrl} />;
}
```

## Context와 상태관리 라이브러리

| 도구 | 언제 적합한가 |
|---|---|
| useState | 한 컴포넌트 안에서만 쓰는 지역 상태 |
| Context | 로그인 정보·테마처럼 자주 안 바뀌는 전역 값 |
| Redux/Zustand 등 | 복잡한 전역 상태, 잦은 업데이트, 디버깅 도구 필요 시 |

## 실무 포인트

- **Context를 남용하면 오히려 성능 문제가 생길 수 있다.** Context 값이 바뀌면 그것을 구독하는 모든 컴포넌트가 리렌더링되므로, 자주 바뀌는 값을 하나의 큰 Context에 몰아넣으면 불필요한 렌더링이 늘어난다.
- **모든 상태를 전역으로 만들 필요는 없다.** 한 컴포넌트와 그 자식 몇 개만 쓰는 상태는 그냥 `useState`로 두는 것이 낫다. 전역화는 정말 여러 곳에서 공유해야 할 때만 한다.
- **상태관리 라이브러리는 프로젝트가 복잡해진 뒤에 도입해도 늦지 않다.** 처음부터 Redux 같은 무거운 도구를 넣기보다, props와 Context로 시작해 필요성이 명확해지면 도입하는 것이 좋다.

## 마무리 요약

- props drilling은 중간 컴포넌트들이 쓰지도 않는 데이터를 계속 전달해야 하는 문제다.
- Context는 데이터를 상위에 보관하고 하위에서 직접 꺼내 써서 props 전달을 없앤다.
- Context 남용은 리렌더링 성능 문제를 부르므로, 정말 공유가 필요한 값만 전역화하는 것이 좋다.

## 참고 자료

- [React 공식 문서 - Context로 데이터 전달하기](https://react.dev/learn/passing-data-deeply-with-context)
- [React 공식 문서 - 상태 관리](https://react.dev/learn/managing-state)
