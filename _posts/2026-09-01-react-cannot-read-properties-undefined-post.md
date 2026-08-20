---
layout: single
title: "React 'Cannot read properties of undefined' 에러 잡는 법"
date: 2026-09-01 13:30:00 +0530
categories: frontend
tags: ["react", "트러블슈팅", "자바스크립트에러", "undefined", "디버깅"]
toc: true
toc_sticky: true
excerpt: "React에서 가장 자주 마주치는 'Cannot read properties of undefined' 에러가 왜 나는지, 데이터 로딩 타이밍 관점에서 원인과 해결법을 정리했다."
---

## 왜 데이터가 분명히 오는데도 에러가 나는가

`Cannot read properties of undefined (reading 'name')` 같은 에러는 자바스크립트 자체의 에러지만, React에서는 특히 **비동기로 데이터를 가져오는 컴포넌트**에서 압도적으로 자주 발생한다. API 응답이 도착하기 전, 즉 `state`가 아직 초기값(`undefined` 또는 `null`)인 상태에서 그 값의 속성에 접근하려 하기 때문이다.

## 에러가 나는 전형적인 패턴

```jsx
function UserProfile({ userId }) {
  const [user, setUser] = useState(); // 초기값이 undefined!

  useEffect(() => {
    fetch(`/api/users/${userId}`).then(res => res.json()).then(setUser);
  }, [userId]);

  // 첫 렌더링 시점에는 user가 아직 undefined다
  return <p>{user.name}님 환영합니다</p>; // 여기서 에러 발생
}
```

컴포넌트는 API 응답이 오기 전에도 최소 한 번은 렌더링된다. 이 최초 렌더링 시점에 `user`는 여전히 `undefined`이므로 `user.name`에 접근하는 순간 에러가 난다.

## 해결 방법 3가지

```jsx
// 방법 1: 로딩 상태를 명시적으로 분기 처리 (가장 명확한 방법)
function UserProfile({ userId }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`/api/users/${userId}`).then(res => res.json()).then(setUser);
  }, [userId]);

  if (!user) return <p>로딩 중...</p>;
  return <p>{user.name}님 환영합니다</p>;
}

// 방법 2: 옵셔널 체이닝으로 방어 (간단하지만 로딩 UI는 따로 필요)
return <p>{user?.name}님 환영합니다</p>;

// 방법 3: 초기값 자체를 안전한 형태로 지정
const [user, setUser] = useState({ name: '' });
```

방법 1이 사용자 경험 측면에서 가장 바람직하다. 옵셔널 체이닝(`?.`)은 에러는 막아주지만 로딩 중이라는 사실을 사용자에게 보여주지 못한다.

## 실무 포인트

- **배열의 경우 `.map()`을 호출하기 전에 배열이 아직 `undefined`인지부터 확인해야 한다.** `items.map(...)`에서 `items`가 초기값 `undefined`라면 역시 같은 에러가 난다. 초기값을 빈 배열 `[]`로 지정해두면 이 문제를 원천적으로 피할 수 있다.
- **중첩된 객체 속성에 접근할 때는 옵셔널 체이닝을 체인 전체에 적용해야 한다.** `user.address.city`에서 `user`는 있지만 `address`가 없을 수도 있으므로 `user?.address?.city`처럼 모든 단계에 적용하는 것이 안전하다.
- **에러 바운더리(Error Boundary)를 최상위에 두면, 예상치 못한 undefined 접근 에러가 나도 앱 전체가 하얗게 죽는(White Screen) 대신 대체 UI를 보여줄 수 있다.**

## 마무리 요약

- 이 에러는 대부분 API 응답이 오기 전 초기 렌더링에서 아직 없는 데이터의 속성에 접근해서 발생한다.
- 로딩 상태를 명시적으로 분기 처리하는 것이 옵셔널 체이닝보다 사용자 경험 면에서 낫다.
- 배열 초기값은 `undefined`가 아니라 빈 배열로 지정해 `.map()` 에러를 원천 차단하는 것이 좋다.

## 참고 자료

- [React 공식 문서 - 조건부 렌더링](https://react.dev/learn/conditional-rendering)
- [MDN - 옵셔널 체이닝](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Optional_chaining)
