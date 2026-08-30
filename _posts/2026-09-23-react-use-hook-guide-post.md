---
layout: single
title: "React 19 use() 훅 제대로 쓰기 — Promise 언래핑과 useEffect의 차이"
date: 2026-09-23 13:30:00 +0530
categories: frontend
tags: ["react19", "use훅", "suspense", "비동기데이터", "리액트"]
toc: true
toc_sticky: true
excerpt: "비동기 데이터를 컴포넌트에서 다룰 때마다 useEffect와 로딩 상태 변수를 반복해서 작성하던 패턴을, React 19의 use() 훅과 Suspense 조합으로 단순화하는 방법과 흔히 헷갈리는 규칙을 정리했다."
---

## 왜 useEffect로 매번 로딩 상태를 관리하는 게 번거로울까

컴포넌트 안에서 API를 호출할 때마다 `useEffect`로 fetch를 트리거하고, `useState`로 데이터·로딩·에러 상태를 따로따로 선언하는 패턴을 몇 번이고 반복하게 된다. 이 패턴 자체가 틀린 것은 아니지만, 컴포넌트마다 같은 보일러플레이트가 늘어나고, 의존성 배열을 잘못 적어 무한 재요청이 발생하거나 언마운트 이후 상태 업데이트로 경고가 뜨는 실수가 반복된다.

React 19에서 정식 도입된 `use()`는 이 패턴을 대체하기 위한 훅이다. 다만 이름과 형태가 `useState`, `useEffect`와 비슷해서 "그냥 또 다른 훅이겠지" 하고 기존 규칙을 그대로 적용했다가 예상치 못한 동작을 마주치기 쉽다.

## 핵심 개념 1 — use()는 다른 훅들과 규칙이 다르다

일반적인 훅은 조건문이나 반복문 안에서 호출하면 안 된다는 규칙(Rules of Hooks)이 있다. 그런데 `use()`는 이 규칙에서 예외적으로 자유롭다 — 조건문 안에서 호출해도 되고, 심지어 `if` 문 뒤에서 조건부로 호출하는 것도 허용된다. 이는 `use()`가 "훅"이라는 이름을 달고 있지만 내부적으로는 Promise나 Context의 값을 그 자리에서 즉시 꺼내오는 특수한 메커니즘이기 때문이다.

```javascript
function Comments({ commentsPromise, showComments }) {
  // 일반 훅이었다면 이렇게 조건부 호출은 규칙 위반이지만, use()는 허용된다
  if (showComments) {
    const comments = use(commentsPromise);
    return comments.map(c => <Comment key={c.id} text={c.text} />);
  }
  return null;
}
```

## 핵심 개념 2 — Promise를 넘기면 컴포넌트가 Suspense로 "정지"한다

`use()`에 아직 완료되지 않은 Promise를 넘기면, 그 컴포넌트는 실행을 멈추고 가장 가까운 `<Suspense>` 경계의 폴백 UI를 보여준다. Promise가 resolve되면 React가 컴포넌트를 다시 렌더링하고, 이번에는 `use()`가 resolve된 값을 즉시 반환한다. 즉 로딩 상태를 위한 `if (loading) return <Spinner />` 같은 분기를 컴포넌트 안에 직접 쓸 필요가 없어지고, 그 책임이 `<Suspense>` 경계로 옮겨간다.

<img src="/assets/images/posts/2026-09-23-react-use-hook-guide-1.svg" alt="use() 훅에 아직 완료되지 않은 Promise를 넘기면 컴포넌트가 실행을 멈추고 Suspense 폴백을 보여주다가, Promise가 resolve되면 다시 렌더링해 use()가 값을 즉시 반환하는 흐름을 useEffect 방식과 비교하는 다이어그램" style="width:100%;">

## 예제 — useEffect 패턴과 use() 패턴 비교

```javascript
// Before: useEffect + useState로 로딩/에러/데이터를 각각 관리
function ProfileOld({ userId }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchUser(userId)
      .then(data => { if (!cancelled) setUser(data); })
      .catch(err => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [userId]);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;
  return <div>{user.name}</div>;
}

// After: use() + Suspense + ErrorBoundary로 관심사 분리
function Profile({ userPromise }) {
  const user = use(userPromise);  // 로딩 중이면 여기서 자동으로 정지
  return <div>{user.name}</div>;
}

// 상위 컴포넌트에서 Suspense/ErrorBoundary로 감싼다
<ErrorBoundary fallback={<ErrorMessage />}>
  <Suspense fallback={<Spinner />}>
    <Profile userPromise={fetchUser(userId)} />
  </Suspense>
</ErrorBoundary>
```

로딩·에러 처리 코드가 컴포넌트 밖으로 옮겨가면서, `Profile` 컴포넌트 자체는 "데이터가 있을 때 무엇을 그릴지"에만 집중할 수 있게 된다.

## 흔한 실수

| 실수 | 결과 | 대응 |
|---|---|---|
| 렌더링 중에 매번 새 Promise 생성 | 렌더링마다 새 요청이 나가 무한 루프 유발 | Promise를 캐싱하거나 상위에서 한 번만 생성해 props로 전달 |
| ErrorBoundary 없이 use() 사용 | Promise가 reject되면 앱 전체가 크래시 | 반드시 ErrorBoundary로 감싸기 |
| 클라이언트 컴포넌트에서 매 렌더마다 fetch 호출 | 캐싱 없이 use()만 붙이면 여전히 중복 요청 | 데이터 페칭 라이브러리(TanStack Query 등)나 서버 컴포넌트와 병행 |

가장 치명적인 실수는 첫 번째다. `use(fetchUser(userId))`처럼 컴포넌트 함수 본문에서 매번 새 Promise를 만들어 넘기면, 렌더링될 때마다 새 요청이 나가고 그 Promise가 다시 컴포넌트를 정지시키는 악순환에 빠질 수 있다. Promise는 컴포넌트 바깥(서버 컴포넌트, 캐싱 레이어, 혹은 상위 컴포넌트의 안정적인 참조)에서 만들어 전달해야 한다.

## 실무 포인트

- **서버 컴포넌트와 함께 쓸 때 진가를 발휘한다.** Next.js App Router 같은 서버 컴포넌트 환경에서는 서버에서 만든 Promise를 클라이언트 컴포넌트로 그대로 넘기고, 클라이언트에서 `use()`로 풀어내는 패턴이 자연스럽게 맞아떨어진다.
- **Context를 조건부로 읽을 때도 유용하다.** `use()`는 Promise뿐 아니라 Context 값도 받을 수 있어, 기존 `useContext`로는 불가능했던 조건부·early-return 이후의 Context 읽기가 가능해진다.
- **기존 데이터 페칭 라이브러리를 완전히 대체하는 것은 아니다.** 캐싱, 재시도, 중복 요청 제거 같은 기능은 `use()` 자체에는 없으므로, TanStack Query 같은 라이브러리와 조합하거나 프레임워크가 제공하는 캐싱 레이어에 의존하는 편이 현실적이다.

## 마무리 요약

- `use()`는 조건문 안에서 호출 가능하다는 점에서 다른 훅들의 규칙과 다르며, Promise나 Context 값을 그 자리에서 꺼내오는 특수한 메커니즘이다.
- 아직 완료되지 않은 Promise를 넘기면 컴포넌트가 Suspense 경계까지 실행을 멈추므로, 로딩 상태 관리 책임이 컴포넌트 밖으로 옮겨간다.
- 렌더링마다 새 Promise를 생성하면 무한 재요청에 빠지므로 Promise는 반드시 안정적인 참조로 컴포넌트 바깥에서 전달해야 한다.

## 참고 자료

- [React 공식 문서 - use](https://react.dev/reference/react/use)
- [React 공식 문서 - Suspense](https://react.dev/reference/react/Suspense)
