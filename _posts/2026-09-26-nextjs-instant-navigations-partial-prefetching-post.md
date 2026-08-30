---
layout: single
title: "Next.js 16.3 Instant Navigations — Partial Prefetching은 페이지 전환을 어떻게 즉시로 만드나"
date: 2026-09-26 12:30:00 +0530
categories: frontend
tags: ["Nextjs", "InstantNavigations", "PartialPrefetching", "AppRouter", "웹성능"]
toc: true
toc_sticky: true
excerpt: "링크를 클릭한 순간 로딩 스피너부터 보여주던 App Router 내비게이션을, 클릭 전에 이미 화면 셸을 캐시해두고 클릭 즉시 렌더링하는 Next.js 16.3의 Instant Navigations와 Partial Prefetching 내부 동작을 정리했다."
---

## 왜 지금 내비게이션 캐싱을 다시 봐야 하는가

Next.js App Router는 서버 컴포넌트 덕분에 초기 로드는 빠르지만, 페이지 전환 시점에는 여전히 서버에 다시 요청을 보내고 응답을 기다리는 구간이 존재했다. 특히 동적 데이터가 섞인 라우트에서는 매번 서버 렌더링을 처음부터 다시 수행해야 했기 때문에, 링크를 눌러도 곧바로 화면이 바뀌지 않고 짧은 지연이나 로딩 상태가 노출되는 경우가 많았다. 사용자 입장에서는 이 몇백 밀리초의 공백이 "느린 앱"이라는 인상을 만든다. Next.js 16.3의 Instant Navigations는 이 공백을 프리페치 시점에 미리 채워 넣는 방식으로 없애려는 시도다.

## 핵심 개념 1 — 정적 셸과 동적 데이터의 분리 캐싱

Partial Prefetching의 핵심 아이디어는 라우트를 정적인 부분(레이아웃, 스켈레톤 UI처럼 사용자마다 달라지지 않는 셸)과 동적인 부분(로그인한 사용자 데이터, 실시간 값)으로 나눠 서로 다르게 취급하는 것이다. 링크가 뷰포트에 들어오는 순간 Next.js는 정적 셸 전체를 즉시 프리페치해 클라이언트 캐시에 저장한다. 이 정적 셸은 Suspense 경계로 감싸인 컴포넌트 트리 중 정적으로 렌더링 가능한 부분을 빌드 타임 혹은 첫 요청 시점에 미리 렌더링해 만들어둔 결과물이다. 사용자가 실제로 링크를 클릭하면, 캐시된 정적 셸이 그 즉시 화면에 그려지고, 그 안의 동적 슬롯만 별도로 서버에 스트리밍 요청을 보내 채워진다. 즉 "전체를 기다렸다 한 번에 보여주기"에서 "뼈대는 즉시, 살은 스트리밍으로"로 전환되는 것이다.

## 핵심 개념 2 — 캐시 무효화와 스테일 데이터 트레이드오프

정적 셸을 미리 캐싱해둔다는 것은 필연적으로 "그 셸이 오래된 상태일 수 있다"는 위험을 동반한다. Next.js는 이를 완화하기 위해 캐시 유효 기간(staleTime)을 라우트별로 설정할 수 있게 하고, 서버 액션이나 재검증(revalidate) 호출이 일어나면 해당 라우트의 캐시된 셸을 무효화해 다음 프리페치 때 새로 받아오게 한다. 실무에서 주의할 점은 정적 셸 자체에 사용자별로 달라지는 정보(예: 장바구니 개수 배지)를 넣으면, 캐시가 다른 사용자 세션 간에 재사용되면서 오정보가 노출될 위험이 있다는 것이다. 이런 값은 반드시 동적 슬롯으로 분리해야 한다.

| 방식 | 클릭 시 첫 화면 | 데이터 신선도 | 서버 요청 시점 |
|---|---|---|---|
| 기존 App Router 내비게이션 | 전체 렌더링 완료까지 대기 | 항상 최신 | 클릭 시점 |
| Partial Prefetching(정적 셸만) | 정적 셸만 즉시 표시 | 동적 부분은 최신, 셸은 캐시 시점 | 뷰포트 진입 시 셸 프리페치 |
| Instant Navigations(셸+스트리밍) | 셸 즉시 + 동적 슬롯 스트리밍 채움 | 동적 부분 최신 유지 | 셸은 사전, 동적 데이터는 클릭 시점 |

## 코드 예제 — 동적 슬롯을 Suspense로 분리하기

```tsx
// app/dashboard/page.tsx
import { Suspense } from "react";
import StaticShell from "./static-shell";
import DynamicUserStats from "./dynamic-user-stats";

export default function DashboardPage() {
  return (
    <StaticShell>
      {/* 이 부분만 프리페치 캐시에서 제외되고 클릭 시점에 스트리밍된다 */}
      <Suspense fallback={<StatsSkeleton />}>
        <DynamicUserStats />
      </Suspense>
    </StaticShell>
  );
}
```

Suspense 경계 바깥의 `StaticShell`은 프리페치 시점에 정적으로 렌더링돼 캐시되고, 경계 안의 `DynamicUserStats`만 실제 네비게이션이 일어날 때 서버에서 새로 가져온다.

## 실무 포인트

- **정적 셸 안에 사용자별 개인화 데이터를 넣지 말아야 한다.** 캐시가 공유되므로 다른 사용자의 오래된 정보가 잠깐 노출될 수 있다. 개인화 값은 항상 Suspense로 감싼 동적 슬롯에 둬야 한다.
- **프리페치 대상 링크가 너무 많으면 오히려 네트워크·메모리 낭비다.** 뷰포트에 동시에 보이는 링크 수가 많은 리스트 페이지에서는 `prefetch={false}`로 선택적으로 끄는 것이 필요할 수 있다.
- **staleTime 설정은 라우트의 데이터 변경 빈도에 맞춰야 한다.** 거의 안 바뀌는 정적 페이지는 길게, 실시간성이 중요한 라우트는 짧게 잡아야 캐시 이득과 신선도 사이의 균형이 맞는다.

## 마무리 요약

- Instant Navigations는 라우트를 정적 셸과 동적 데이터로 분리해, 셸은 뷰포트 진입 시점에 미리 프리페치·캐시하고 동적 데이터만 클릭 시점에 스트리밍하는 방식으로 체감 전환 속도를 끌어올린다.
- 이 구조는 "전체 완료까지 대기"에서 "뼈대 즉시 표시 + 나머지 스트리밍"으로 렌더링 전략 자체를 바꾼 것이며, 캐시 무효화 시점과 staleTime 설정이 신선도를 좌우한다.
- 사용자별 개인화 데이터는 반드시 Suspense 동적 슬롯으로 분리해야 캐시 공유로 인한 오정보 노출을 막을 수 있다.

## 참고 자료

- [Next.js 공식 블로그 — Next.js 16.3](https://nextjs.org/blog)
- [Next.js 공식 문서 — Partial Prerendering](https://nextjs.org/docs/app/building-your-application/rendering/partial-prerendering)
