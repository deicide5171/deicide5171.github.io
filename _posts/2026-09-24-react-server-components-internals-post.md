---
layout: single
title: "React Server Components 내부 동작 원리 — 서버와 클라이언트 경계는 어떻게 나뉘나"
date: 2026-09-24 12:30:00 +0530
categories: frontend
tags: ["React", "ServerComponents", "NextJS", "RSC", "번들최적화"]
toc: true
toc_sticky: true
excerpt: "Next.js App Router가 기본값으로 채택한 React Server Components가 use client 지시어 하나로 서버·클라이언트 경계를 어떻게 나누고, 실제로 어떤 직렬화 프로토콜로 서버 트리를 클라이언트에 전달하는지 내부 동작을 정리했다."
---

## 왜 지금 RSC 내부 동작을 알아야 하는가

Next.js App Router를 쓰다 보면 `use client`를 어디에 붙여야 하는지, 왜 서버 컴포넌트 안에서 `useState`를 쓰면 에러가 나는지, 왜 서버 컴포넌트에 props로 함수를 넘기면 실패하는지처럼 표면적인 규칙은 금방 외울 수 있다. 하지만 그 규칙이 왜 그렇게 정해졌는지, RSC가 실제로 무엇을 서버에서 클라이언트로 전달하는지를 이해하지 못하면 번들 크기 최적화나 데이터 페칭 구조 설계에서 잘못된 판단을 내리기 쉽다. RSC는 단순히 "서버에서 렌더링해서 HTML을 준다"는 SSR과는 다른, 별도의 직렬화 프로토콜에 기반한 메커니즘이다.

## 핵심 개념 1 — RSC가 실제로 전달하는 것은 HTML이 아니다

전통적인 SSR은 서버에서 React 트리를 렌더링해 완성된 HTML 문자열을 클라이언트에 보낸다. RSC는 다르다. 서버 컴포넌트는 렌더링된 결과를 HTML이 아니라 React가 정의한 독자적인 직렬화 포맷(흔히 "RSC Payload" 또는 "Flight" 포맷이라 불린다)으로 직렬화해 전송한다. 이 포맷은 JSON과 비슷하지만, 클라이언트 컴포넌트가 등장하는 지점에는 실제 렌더 결과 대신 "이 지점에 이 클라이언트 컴포넌트 모듈을 로드해서 끼워 넣어라"는 참조(reference)만 담긴다.

이 방식 덕분에 클라이언트는 서버 컴포넌트가 사용한 라이브러리 코드를 전혀 다운로드하지 않고도, 서버가 만든 트리 구조와 클라이언트 컴포넌트의 결합 지점만 알면 최종 UI를 구성할 수 있다. 즉 RSC의 핵심 이점은 "서버 전용 코드(DB 클라이언트, 무거운 마크다운 파서 등)가 클라이언트 번들에 전혀 포함되지 않는다"는 점이다.

## 핵심 개념 2 — `use client`는 경계선이지 컴포넌트 속성이 아니다

`use client` 지시어를 파일 최상단에 붙이면, 그 파일에서 export하는 컴포넌트와 그 컴포넌트가 import하는 모든 하위 모듈이 클라이언트 번들에 포함되는 경계가 그어진다. 중요한 점은 이 경계가 "그 컴포넌트 자체만 클라이언트에서 실행된다"가 아니라 "그 지점부터 트리 아래쪽 전체가 클라이언트 모듈 그래프에 편입된다"는 것이다. 반대로 서버 컴포넌트는 클라이언트 컴포넌트를 자식(children)으로 받을 수는 있지만, 클라이언트 컴포넌트가 서버 컴포넌트를 직접 import할 수는 없다 — 이미 클라이언트 모듈 그래프에 편입된 지점에서는 서버 전용 코드를 되돌릴 수 없기 때문이다.

| 상황 | 가능 여부 | 이유 |
|---|---|---|
| 서버 컴포넌트가 클라이언트 컴포넌트를 렌더 | 가능 | 참조만 Payload에 담고 실제 실행은 클라이언트가 |
| 클라이언트 컴포넌트가 서버 컴포넌트를 import | 불가능 | 이미 클라이언트 번들 그래프에 편입됨 |
| 서버 컴포넌트를 클라이언트 컴포넌트의 children으로 전달 | 가능 | children은 이미 렌더된 결과(참조)로 전달되므로 |
| 서버 컴포넌트에서 이벤트 핸들러를 props로 전달 | 불가능 | 함수는 직렬화할 수 없음 |

## 예제 — children 패턴으로 서버 컴포넌트를 클라이언트 안에 끼워 넣기

```jsx
// ClientWrapper.jsx ('use client')
'use client';
export default function ClientWrapper({ children }) {
  const [open, setOpen] = useState(false);
  return (
    <div onClick={() => setOpen(!open)}>
      {open && children}
    </div>
  );
}

// page.jsx (서버 컴포넌트)
import ClientWrapper from './ClientWrapper';
import ServerHeavyContent from './ServerHeavyContent'; // DB 조회 포함

export default function Page() {
  return (
    <ClientWrapper>
      <ServerHeavyContent /> {/* 서버에서 렌더된 결과가 children으로 전달됨 */}
    </ClientWrapper>
  );
}
```

`ClientWrapper`가 `ServerHeavyContent`를 직접 import하지 않고 children으로 받는 이 패턴이, 클라이언트 상호작용이 필요한 UI 안에 서버 전용 데이터 페칭 로직을 끼워 넣는 표준적인 방법이다.

## 실무 포인트

- **`use client` 경계는 가능한 한 트리의 리프(leaf)에 가깝게 배치하라.** 최상단 레이아웃 컴포넌트에 습관적으로 붙이면 그 아래 전체가 클라이언트 번들에 편입돼 RSC의 이점이 사라진다.
- **서버 컴포넌트에 넘기는 props는 직렬화 가능한 값(문자열, 숫자, 객체, 배열, JSX)으로 한정된다.** 함수나 Date가 아닌 커스텀 클래스 인스턴스를 props로 넘기면 런타임 에러가 난다.
- **RSC Payload 크기도 최적화 대상이다.** 서버 컴포넌트가 반환하는 트리가 크면 초기 로드 시 전송되는 Payload 자체가 커지므로, 불필요하게 깊은 트리를 한 번에 렌더링하지 않도록 Suspense 경계로 스트리밍을 나누는 것이 좋다.

## 마무리 요약

- RSC는 HTML이 아니라 독자적인 직렬화 포맷(RSC Payload)으로 서버 트리와 클라이언트 컴포넌트 참조를 함께 전달하는 메커니즘이다.
- `use client`는 컴포넌트 하나의 속성이 아니라 그 지점부터 하위 트리 전체를 클라이언트 모듈 그래프에 편입시키는 경계선이다.
- children 패턴을 활용하면 클라이언트 컴포넌트 안에 서버 전용 데이터 페칭 로직을 서버 번들 유출 없이 끼워 넣을 수 있다.

## 참고 자료

- [React - Server Components](https://react.dev/reference/rsc/server-components)
- [Next.js - Server and Client Components](https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns)
