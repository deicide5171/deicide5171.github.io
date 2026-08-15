---
layout: single
title: "Next.js App Router 데이터 페칭 패턴 총정리 — fetch 위치, 병렬 처리, 스트리밍"
date: 2026-08-17 13:30:00 +0530
categories: frontend
tags: ["nextjs", "app-router", "server-components", "data-fetching", "streaming", "suspense"]
toc: true
toc_sticky: true
excerpt: "Next.js App Router에서 데이터를 어디서 가져오고, 병렬로 처리하고, Suspense로 스트리밍할지를 캐싱과 분리해서 정리한다."
---

## 왜 지금 데이터 페칭 방식을 다시 봐야 하나

Pages Router 시절에는 `getServerSideProps` 하나에 데이터 로딩을 몰아넣고 결과를 props로 뿌리는 구조가 사실상 유일한 선택지였다. App Router에서는 트리 안 **어떤 Server Component에서든 직접 `fetch`를 호출**할 수 있게 됐고, "데이터를 어디서 가져올 것인가"가 그 자체로 설계 결정이 됐다.

캐시 전략(`revalidate`, `revalidateTag` 등)과 페칭 위치·순서 문제는 자주 뒤섞여 다뤄진다. 캐시를 잘 설계해도 fetch 호출이 트리에 순차적으로 쌓여 워터폴을 만들면 체감 성능은 그대로 나쁘다. 이 글은 캐시 무효화 대신 **fetch를 어디에 두고, 병렬로 묶고, 스트리밍으로 내보낼지**에 집중한다.

## 핵심 개념 1: fetch는 어디서 호출해야 하나

App Router의 기본 원칙은 "데이터가 필요한 컴포넌트에서 직접 fetch한다"이다. 최상위 페이지에서 한 번에 가져와 props로 내려주던 관성을 버려야 한다.

| 방식 | 위치 | 특징 |
|---|---|---|
| Pages Router | `getServerSideProps` | 페이지 하나당 한 번, props로 하향 전달 |
| App Router 권장 | 필요한 Server Component 각각 | 컴포넌트별 독립 fetch, 트리 어디서든 호출 |
| 클라이언트 상태 필요 시 | Client Component + SWR 등 | 인터랙션 후 재요청, 폴링 |

Server Component는 `async function`으로 선언하고 그 안에서 `await fetch(...)`를 호출하면 된다. React가 동일 렌더 패스 내 중복 요청을 자동 메모이제이션하므로, 여러 컴포넌트가 같은 데이터를 필요로 해도 각자 fetch하는 편이 오히려 단순하다. 클릭·입력에 반응해 다시 가져와야 하는 경우만 Client Component에서 직접 요청하도록 남겨둔다.

## 핵심 개념 2: Server/Client Component 경계와 데이터 전달

Server Component는 서버에서만 실행되므로 DB 접근이나 비밀 키를 쓰는 fetch를 안전하게 둘 수 있지만 `onClick`이나 `useState`는 쓸 수 없다. `"use client"`가 붙은 컴포넌트는 반대로 인터랙션은 가능하지만 서버 전용 자원에 접근하지 못한다.

실무에서 자주 쓰는 패턴은 **Server Component가 fetch한 결과를 props로 Client Component에 넘기는 것**이다. 좋아요 버튼처럼 상태가 필요한 부분만 Client Component로 분리하고 나머지는 Server Component에 남기면 클라이언트 JS 번들과 하이드레이션 비용을 최소화할 수 있다. Client Component 안에서 다시 fetch하는 것은 값이 인터랙션에 따라 계속 바뀌어야 하는 경우로 한정한다.

## 핵심 개념 3: 병렬 페칭 vs 순차 페칭 (워터폴 문제)

컴포넌트 A에서 사용자 정보를 fetch한 뒤 그 결과를 컴포넌트 B에 넘겨 B가 다시 게시글을 fetch하면, 의존 관계가 없는데도 순차 실행되는 **워터폴**이 생긴다. 의존성이 없는 요청은 같은 컴포넌트에서 `Promise.all`로 동시에 시작해야 한다. 반면 형제 컴포넌트 각각의 독립 fetch는 트리 렌더링 중 사실상 동시에 시작되므로 별도 처리가 필요 없다. 워터폴은 대개 "A의 응답이 B의 요청 파라미터로 쓰이는" 진짜 의존 관계가 있을 때만 생긴다.

## 핵심 개념 4: Suspense로 스트리밍하기

App Router는 `loading.tsx`와 `<Suspense>` 경계 단위로 HTML을 점진적으로 스트리밍한다. 느린 컴포넌트를 `<Suspense fallback={...}>`로 감싸면 나머지 페이지는 먼저 보내고, 느린 부분은 준비되는 대로 채워 넣는다. 사용자는 빈 화면 대신 뼈대를 먼저 보고 콘텐츠가 하나씩 채워지는 경험을 하게 된다.

아래 다이어그램은 이 흐름을 정리한 것이다.

<img src="/assets/images/posts/2026-08-17-nextjs-app-router-data-fetching-1.svg" alt="Next.js 컴포넌트 트리에서 병렬로 fetch가 시작되고 Suspense 경계 단위로 순서대로 스트리밍되는 흐름도" style="width:100%;">

## 예제: 병렬 페칭 + 스트리밍 적용

```tsx
// app/dashboard/page.tsx
import { Suspense } from "react";

async function getUser() {
  return fetch("https://api.example.com/user").then((r) => r.json());
}
async function getStats() {
  return fetch("https://api.example.com/stats").then((r) => r.json());
}

// 의존 관계 없는 두 요청을 명시적으로 병렬 실행
export default async function DashboardPage() {
  const [user, stats] = await Promise.all([getUser(), getStats()]);
  return (
    <div>
      <h1>{user.name}님의 대시보드</h1>
      <StatsPanel stats={stats} />
      {/* 느린 컴포넌트는 별도 Suspense 경계로 분리해 스트리밍 */}
      <Suspense fallback={<p>최근 활동을 불러오는 중...</p>}>
        <RecentActivity userId={user.id} />
      </Suspense>
    </div>
  );
}

async function RecentActivity({ userId }: { userId: string }) {
  const res = await fetch(`https://api.example.com/activity/${userId}`, { cache: "no-store" });
  const activity = await res.json();
  return <ul>{activity.map((a: any) => <li key={a.id}>{a.text}</li>)}</ul>;
}
```

`RecentActivity`가 느리더라도 `user`, `stats`가 준비되는 즉시 뼈대는 먼저 렌더링되고 활동 목록은 준비되는 대로 스트리밍되어 교체된다.

## 실무 포인트

- **fetch 위치를 억지로 최상위로 몰지 않는다**: 같은 데이터를 여러 형제가 쓴다면 각자 fetch해도 요청 메모이제이션이 중복을 처리해준다.
- **`await`가 연속으로 나열돼 있으면 병렬화 가능 여부부터 점검한다**: 진짜 의존 관계가 아니라면 `Promise.all`로 묶는다.
- **Suspense 경계는 콘텐츠 블록 단위로 적당히 묶는다**: 과도하게 잘게 쪼개면 화면이 계속 흔들리는 부작용이 생긴다.
- **서버·클라이언트 fetch 경계를 설계 초기에 정한다**: 최초 렌더링 데이터는 서버에서, 사용자 액션에 따른 갱신은 클라이언트에서 가져오도록 나눠두면 리팩터링 비용이 준다.
- 캐시 무효화(`revalidateTag` 등)는 이 글의 범위 밖이며, 별도로 정리해둔 캐싱 전략 글에서 다룬다.

## 3줄 요약

- App Router에서는 데이터가 필요한 Server Component 각각에서 직접 fetch하는 것이 기본이며, 인터랙션에 따라 변하는 데이터만 Client Component로 내린다.
- 의존 관계 없는 요청은 `Promise.all`로 명시적으로 병렬화해야 워터폴을 피할 수 있고, 형제 컴포넌트의 개별 fetch는 렌더링 과정에서 자연히 동시에 시작된다.
- 느린 데이터는 `<Suspense>` 경계로 분리해 스트리밍하면 가장 느린 요청 하나가 전체 페이지를 막지 않는다.

## 참고 자료

- [Next.js 공식 문서 - Fetching Data](https://nextjs.org/docs/app/building-your-application/data-fetching/fetching)
- [Next.js 공식 문서 - Loading UI and Streaming](https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming)
- [React 공식 문서 - Suspense](https://react.dev/reference/react/Suspense)
