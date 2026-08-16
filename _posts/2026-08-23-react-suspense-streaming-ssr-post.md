---
layout: single
title: "첫 바이트는 먼저, 느린 데이터는 나중에 — React Suspense 스트리밍 SSR의 동작 원리"
date: 2026-08-23 12:30:00 +0530
categories: frontend
tags: ["frontend", "react", "suspense", "ssr", "streaming", "hydration"]
toc: true
toc_sticky: true
excerpt: "renderToString의 '전부 준비될 때까지 대기' 구조를 renderToPipeableStream과 Suspense가 어떻게 깨뜨리는지 — 셸 우선 전송, fallback 교체, 선택적 하이드레이션까지 스트리밍 SSR의 내부 동작을 정리한다."
---

전통적인 React SSR의 병목은 `renderToString`이라는 함수 이름에 이미 드러나 있다. 문자열 하나를 반환해야 하므로, 페이지에서 가장 느린 데이터(예: 외부 API로 가져오는 추천 목록)가 준비될 때까지 서버는 단 한 바이트도 브라우저에 보내지 못한다. 페이지의 99%가 이미 렌더링 가능해도, 남은 1% 때문에 전체 응답이 인질로 잡히는 구조다.

문제는 서버에서 끝나지 않는다. HTML이 도착한 뒤에도 브라우저는 번들 전체를 로드하고 페이지 전체를 하이드레이션해야 비로소 클릭에 반응한다. 즉 기존 SSR은 "데이터 전부 → 렌더 전부 → 하이드레이션 전부"라는 세 개의 전부-아니면-전무(all-or-nothing) 단계가 직렬로 이어진 폭포수였다.

React 18에서 도입된 `renderToPipeableStream`과 `<Suspense>` 조합은 이 세 단계를 각각 조각낸다. Next.js App Router의 스트리밍이나 React Router v7의 SSR도 결국 이 기반 위에 서 있으므로, 프레임워크를 쓰더라도 밑에서 무슨 일이 일어나는지 알아두면 디버깅과 튜닝의 관점이 달라진다. 이 글은 프레임워크 없이 그 원리 자체를 들여다본다.

## 핵심 개념 1: 셸(shell)과 Suspense 경계

스트리밍 SSR에서 서버는 페이지를 두 부류로 나눈다. `<Suspense>` 경계 바깥의 모든 것이 **셸**이고, 경계 안쪽은 나중에 채워도 되는 조각이다. 서버는 셸 렌더링이 끝나는 즉시 HTML 전송을 시작하는데, 이때 아직 준비되지 않은 Suspense 경계 자리에는 `fallback`으로 지정한 스피너나 스켈레톤의 HTML이 대신 실려 나간다.

이후 느린 데이터가 준비되면 서버는 같은 HTTP 응답 위에(chunked transfer 방식으로) 추가 청크를 흘려보낸다. 각 청크에는 완성된 콘텐츠가 `hidden` 상태의 태그로 들어 있고, 그 뒤에 붙는 작은 인라인 스크립트가 DOM에서 fallback을 찾아 실제 콘텐츠로 교체한다. 브라우저 입장에서는 자바스크립트 번들이 로드되기 전이라도, 스트리밍만으로 화면이 점진적으로 완성되는 셈이다.

<img src="/assets/images/posts/2026-08-23-react-suspense-streaming-ssr-1.svg" alt="기존 SSR과 스트리밍 SSR의 HTML 전송 타임라인 비교 및 fallback 교체 과정" style="width:100%;">

## 핵심 개념 2: 선택적 하이드레이션(Selective Hydration)

스트리밍이 "HTML을 조각으로 보내기"라면, 선택적 하이드레이션은 "자바스크립트를 조각으로 붙이기"다. React 18부터 하이드레이션은 페이지 전체가 아니라 Suspense 경계 단위로 진행된다. 아직 HTML이 도착하지 않은 경계가 있어도 나머지 부분은 먼저 하이드레이션되어 인터랙티브해진다.

더 흥미로운 것은 우선순위 조정이다. 사용자가 아직 하이드레이션되지 않은 영역을 클릭하면, React는 그 이벤트를 기록해두고 해당 경계의 하이드레이션을 앞당긴 뒤 이벤트를 재생(replay)한다. 페이지 하단의 무거운 위젯 때문에 상단 버튼이 늦게 반응하는 문제가 구조적으로 줄어드는 것이다. 다시 말해 Suspense 경계는 로딩 UI의 단위이자, 스트리밍 청크의 단위이자, 하이드레이션 스케줄링의 단위라는 세 가지 역할을 겸한다.

## renderToString vs renderToPipeableStream

| 구분 | renderToString | renderToPipeableStream |
|---|---|---|
| 첫 바이트 시점 | 전체 렌더 완료 후 | 셸 완료 즉시 |
| 느린 데이터 처리 | 전체 응답이 대기 | fallback 먼저, 청크로 교체 |
| Suspense 서버 지원 | fallback만 출력하고 끝 | 준비되는 대로 스트리밍 |
| 하이드레이션 | 사실상 전체 단위 | 경계 단위 + 우선순위 조정 |
| 적합한 환경 | 간단한 페이지, 레거시 호환 | 느린 데이터 소스가 섞인 동적 페이지 |

## 예제: Express에서 스트리밍 SSR 구성

```jsx
// App.jsx — 느린 데이터 영역만 Suspense로 감싼다
import { Suspense } from 'react';
import Layout from './Layout';
import Recommendations from './Recommendations'; // 내부에서 use()로 느린 데이터 대기

export default function App() {
  return (
    <Layout>
      <main>빠르게 렌더링되는 본문(셸)</main>
      <Suspense fallback={<p>추천 목록 불러오는 중…</p>}>
        <Recommendations />
      </Suspense>
    </Layout>
  );
}
```

```js
// server.js — Node.js + Express
import express from 'express';
import { renderToPipeableStream } from 'react-dom/server';
import App from './App';

const app = express();

app.get('/', (req, res) => {
  let didError = false;
  const { pipe } = renderToPipeableStream(<App />, {
    bootstrapScripts: ['/main.js'],
    onShellReady() {
      // 셸이 준비된 순간 전송 시작 — 느린 데이터는 기다리지 않는다
      res.statusCode = didError ? 500 : 200;
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      pipe(res);
    },
    onShellError(err) {
      // 셸 자체가 실패하면 아직 아무것도 안 보냈으므로 온전한 에러 응답 가능
      res.statusCode = 500;
      res.send('<h1>일시적인 오류가 발생했습니다</h1>');
    },
    onError(err) {
      didError = true; // 셸 이후의 에러는 상태코드를 못 바꾼다 — 로깅이 최선
      console.error(err);
    },
  });
});

app.listen(3000);
```

핵심은 `onShellReady`에서 `pipe(res)`를 호출하는 시점이다. 검색엔진 크롤러처럼 완성된 HTML이 필요한 요청에는 `onAllReady`에서 pipe하도록 분기하면, 같은 코드로 스트리밍과 완전 렌더링을 모두 제공할 수 있다.

## 흔한 함정: 스트리밍을 삼켜버리는 중간 버퍼

코드를 다 맞춰놓고도 스트리밍이 동작하지 않는 가장 흔한 원인은 React가 아니라 **인프라의 버퍼링**이다. Nginx의 `proxy_buffering`, 일부 CDN, Node의 압축 미들웨어(compression)는 기본 설정에서 응답을 모아뒀다가 한 번에 내보내는 경우가 있다. 이러면 서버는 분명 청크를 흘려보내는데 브라우저에는 응답이 완료된 뒤 통째로 도착해, 기존 SSR과 다를 게 없어진다. 프록시의 버퍼링을 끄거나(`X-Accel-Buffering: no`), 압축 미들웨어의 flush 동작을 확인해야 한다.

또 하나의 안티패턴은 상태코드 처리다. `onShellReady`에서 이미 200을 보낸 뒤 발생한 에러는 HTTP 상태코드로 표현할 방법이 없다. 그래서 셸에는 반드시 성공해야 하는 최소한만 남기고, 실패 가능성이 있는 영역은 Suspense 경계 안으로 밀어 넣어 에러 바운더리와 함께 격리하는 것이 올바른 설계다. 반대로 페이지의 모든 것을 하나의 거대한 Suspense로 감싸면 경계가 하나뿐이라 스트리밍의 이점이 사라진다 — 경계는 "독립적으로 늦어도 되는 단위"마다 쪼개야 한다.

## 언제 쓰고, 언제 쓰지 말아야 하나

스트리밍 SSR이 빛나는 경우는 응답 시간이 제각각인 데이터 소스가 한 페이지에 섞여 있을 때다. 커머스 상품 페이지에서 상품 정보는 빠르지만 리뷰·추천은 느릴 때, 셸을 먼저 보내고 느린 부분을 흘려보내면 TTFB와 FCP가 동시에 좋아진다. 반면 페이지 전체가 정적이라면 SSG + CDN 캐시가 언제나 더 빠르고 싸다. 또한 스트리밍 응답은 전체 HTML이 완성되기 전에 전송이 시작되므로 응답 단위 CDN 캐싱과 궁합이 나쁘다는 점, 개인화가 없는 페이지에 굳이 적용하면 서버 비용만 늘어난다는 점도 계산에 넣어야 한다.

## 마무리 요약

- 스트리밍 SSR은 Suspense 경계 바깥(셸)을 즉시 보내고, 느린 조각은 fallback → hidden 콘텐츠 → 인라인 스크립트 교체 순서로 같은 응답에 흘려보낸다.
- 하이드레이션도 경계 단위로 쪼개지며, 사용자가 클릭한 영역이 먼저 하이드레이션되는 우선순위 조정까지 이뤄진다.
- 프록시·압축의 버퍼링이 스트리밍을 무효화하는 함정, 셸 전송 후 상태코드를 바꿀 수 없다는 제약을 설계 단계에서 고려해야 한다.

## 참고 자료

- [React 공식 문서 — renderToPipeableStream](https://react.dev/reference/react-dom/server/renderToPipeableStream)
- [React 공식 문서 — Suspense](https://react.dev/reference/react/Suspense)
- [React 18 Working Group — New Suspense SSR Architecture](https://github.com/reactwg/react-18/discussions/37)
