---
layout: single
title: "Next.js Hydration 에러 해결하기 — 서버와 클라이언트가 다를 때"
date: 2026-09-02 13:30:00 +0530
categories: frontend
tags: ["nextjs", "hydration", "ssr", "트러블슈팅", "react"]
toc: true
toc_sticky: true
excerpt: "Next.js에서 Hydration failed 에러가 나는 이유를 서버 렌더링 결과와 클라이언트 렌더링 결과의 불일치 관점에서 짚고 해결법을 정리했다."
---

## 이 에러가 정확히 무엇을 말하는가

`Hydration failed because the initial UI does not match what was rendered on the server`라는 에러 메시지는, **서버에서 생성한 HTML과 브라우저가 처음 렌더링한 결과가 다르다**는 뜻이다. Next.js는 서버에서 HTML을 미리 만들어 보내고, 브라우저에서 React가 그 HTML에 이벤트 핸들러 등을 "붙이는" 과정(하이드레이션)을 거친다. 이때 두 결과가 다르면 React가 어느 쪽을 믿어야 할지 알 수 없어 에러를 낸다.

## 흔한 원인 4가지

| 원인 | 예시 코드 |
|---|---|
| 시간 관련 값 사용 | `new Date().toLocaleString()`을 렌더링에 직접 사용 |
| 랜덤 값 사용 | `Math.random()`으로 key나 스타일 생성 |
| 브라우저 전용 API 접근 | `window.innerWidth`를 렌더링 중에 읽음 |
| localStorage 값으로 초기 상태 결정 | 서버에는 localStorage가 없으므로 값이 다름 |

## 왜 시간·랜덤 값이 문제인가

```jsx
// 문제가 되는 코드
function Clock() {
  return <p>{new Date().toLocaleTimeString()}</p>;
}
```

서버가 HTML을 만든 시각과 브라우저가 하이드레이션하는 시각이 다르므로, 같은 코드가 서로 다른 문자열을 만들어낸다. 결과적으로 서버 HTML과 클라이언트 렌더링 결과가 불일치해 에러가 난다.

## 해결 방법

```jsx
// 방법 1: useEffect로 클라이언트에서만 렌더링
function Clock() {
  const [time, setTime] = useState(null);

  useEffect(() => {
    setTime(new Date().toLocaleTimeString()); // 하이드레이션 후에 실행됨
  }, []);

  if (!time) return <p>--:--:--</p>; // 서버·클라이언트 모두 같은 초기 화면
  return <p>{time}</p>;
}
```

```jsx
// 방법 2: 클라이언트 전용 컴포넌트로 분리 (dynamic import)
import dynamic from 'next/dynamic';

const ClientOnlyClock = dynamic(() => import('./Clock'), { ssr: false });
```

`ssr: false`로 지정하면 그 컴포넌트는 서버에서 렌더링하지 않으므로 애초에 불일치가 발생하지 않는다.

## 실무 포인트

- **`suppressHydrationWarning`으로 경고만 숨기는 것은 근본 해결이 아니다.** 정말로 불일치가 불가피한 특정 요소(예: 서버·클라이언트 시간 표시)에 한정해서만 써야 하고, 원인을 모른 채 남용하면 실제 UI 버그를 숨기게 된다.
- **로그인 상태에 따라 다른 UI를 보여주는 경우가 대표적인 함정이다.** 인증 정보를 localStorage에서 읽는 구조라면 서버는 항상 "로그아웃 상태"로 렌더링하므로 불일치가 발생한다. 쿠키 기반 인증으로 바꾸면 서버에서도 로그인 상태를 알 수 있어 이 문제가 해결된다.
- **개발 모드에서는 에러로 표시되지만 프로덕션에서는 조용히 넘어가는 경우가 있다.** 이때도 실제로는 잘못된 UI가 표시될 수 있으므로 개발 중에 반드시 해결해야 한다.

## 마무리 요약

- Hydration 에러는 서버가 만든 HTML과 브라우저의 첫 렌더링 결과가 다를 때 발생한다.
- 시간, 랜덤 값, window·localStorage 접근이 가장 흔한 원인이다.
- useEffect로 클라이언트 렌더링을 미루거나 `dynamic(..., { ssr: false })`로 분리하는 것이 표준적인 해결책이다.

## 참고 자료

- [Next.js 공식 문서 - Hydration 에러](https://nextjs.org/docs/messages/react-hydration-error)
- [React 공식 문서 - hydrateRoot](https://react.dev/reference/react-dom/client/hydrateRoot)
