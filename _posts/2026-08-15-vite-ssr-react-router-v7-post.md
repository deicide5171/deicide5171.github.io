---
layout: single
title: "Vite 위에서 SSR을 얻는 법 — React Router v7과 TanStack Start"
date: 2026-08-15 15:30:00 +0530
categories: web-dev
tags: ["vite", "ssr", "react-router", "tanstack-start", "nextjs", "프레임워크"]
toc: true
toc_sticky: true
excerpt: "Vite 기반 SSR 프레임워크(React Router v7, TanStack Start)가 Next.js의 실용적 대안이 될 수 있는 지점과 도입 시 고려사항을 정리한다."
---

## 왜 지금 이 이야기인가

몇 년 전까지만 해도 "Vite는 빠른 클라이언트 번들러, SSR이 필요하면 Next.js"라는 구도가 거의 상식처럼 통했다. 하지만 최근 흐름을 보면 이 구분이 점점 흐려지고 있다. Remix 팀이 React Router에 합류하면서 나온 React Router v7의 프레임워크 모드는 Vite 위에서 SSR, 중첩 라우팅, 라우트 단위 데이터 로딩을 제공한다. 여기에 TanStack 진영이 내놓은 TanStack Start까지 가세하면서, "Vite 생태계에서도 풀스택 SSR 프레임워크를 쓸 수 있다"는 선택지가 실질적인 옵션으로 자리잡는 중이다.

이런 변화가 나오는 배경에는 몇 가지 실무적 동기가 있다. 이미 Vite 기반 SPA로 운영 중인 서비스에서 SSR이나 스트리밍만 추가하고 싶은데, Next.js로 전체 라우팅·빌드 체계를 갈아엎기는 부담스러운 경우가 많았다. 또한 Vite의 빠른 HMR과 플러그인 생태계를 그대로 유지하면서 서버 사이드 기능만 얹고 싶다는 요구도 꾸준히 있었다. React Router v7과 TanStack Start는 정확히 이 지점을 겨냥한다.

이 글에서는 두 프레임워크가 Vite 위에서 SSR을 어떻게 구현하는지, Next.js와 비교했을 때 각각 어떤 상황에서 실용적 중간 지점이 되는지, 그리고 기존 SPA에서 마이그레이션하거나 신규 도입할 때 짚어야 할 포인트를 정리한다.

## 핵심 개념 1: 프레임워크 모드란 무엇인가

React Router는 원래 클라이언트 라우팅 라이브러리였지만, v7부터는 "라이브러리 모드"와 "프레임워크 모드"를 함께 제공한다. 프레임워크 모드를 켜면 `@react-router/dev` Vite 플러그인이 라우트 파일 구조를 읽어 서버 진입점과 클라이언트 번들을 동시에 생성하고, 각 라우트의 `loader`/`action` 함수를 서버에서 실행해 데이터를 미리 채워준다. 이는 사실상 Remix가 하던 일을 React Router 본체로 흡수한 형태다.

TanStack Start는 접근 방식이 조금 다르다. TanStack Router의 타입 안전한 라우팅 위에 서버 함수(server functions)와 SSR 엔트리를 얹는 구조로, Vite를 빌드 파이프라인으로 그대로 사용하면서 TanStack Query와의 결합을 전제로 설계됐다. 두 프레임워크 모두 "Vite 플러그인 + 파일 기반 또는 설정 기반 라우트 + 서버 데이터 로딩"이라는 공통 패턴을 공유하지만, 데이터 계층을 라우터 자체에 통합할지(React Router) TanStack Query에 위임할지(TanStack Start)에서 철학이 갈린다.

## 핵심 개념 2: Next.js와의 비교

| 항목 | Next.js (App Router) | React Router v7 (프레임워크 모드) | TanStack Start |
|---|---|---|---|
| 번들러 | Turbopack/Webpack 자체 | Vite | Vite |
| 라우팅 | 파일 기반, 서버 컴포넌트 중심 | 설정 기반 라우트 트리 | 파일 기반, 타입 안전 |
| 데이터 로딩 | Server Components + fetch 캐시 | loader/action (라우트 단위) | 서버 함수 + TanStack Query |
| 배포 대상 | Vercel 최적화, 자체 호스팅도 가능 | 어댑터 기반(Node, Cloudflare 등) | 어댑터 기반(Node, Cloudflare 등) |
| 기존 SPA 이관 난이도 | 높음(구조 자체가 다름) | 낮음~중간(라우트만 이관) | 중간 |
| 생태계 성숙도 | 매우 높음 | 높음(Remix 자산 계승) | 상대적으로 신생, 빠르게 성장 중 |

정리하면 Next.js는 서버 컴포넌트를 중심에 둔 완결형 프레임워크로 기능이 가장 풍부하지만 그만큼 학습 곡선과 락인도 크다. React Router v7과 TanStack Start는 "이미 익숙한 Vite·React 방식에 SSR만 얹는다"는 실용주의에 가깝다.

## 설정 예제

React Router v7 프레임워크 모드의 최소 설정은 다음과 같은 형태를 띤다.

```ts
// vite.config.ts
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [reactRouter()],
});
```

```tsx
// app/routes/products.$id.tsx
import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";

export async function loader({ params }: LoaderFunctionArgs) {
  const product = await getProduct(params.id);
  return { product };
}

export default function ProductPage() {
  const { product } = useLoaderData<typeof loader>();
  return <h1>{product.name}</h1>;
}
```

기존 라이브러리 모드 SPA에서 넘어온다면, 대략 라우트 설정 파일(`app/routes.ts`)을 추가하고 각 컴포넌트에 `loader`를 붙이는 순서로 단계적 이관이 가능하다는 점이 특징이다.

## 실무 포인트와 주의사항

- **배포 타깃을 먼저 정하라.** React Router v7과 TanStack Start 모두 Node, Cloudflare Workers 등 여러 런타임 어댑터를 지원하지만, 어댑터별로 지원 범위와 성숙도가 다르므로 실제 배포 환경에서 먼저 검증하는 게 안전하다.
- **서버 컴포넌트는 없다.** 두 프레임워크 모두 React 서버 컴포넌트(RSC)를 기본 전제로 하지 않는다. RSC 자체가 필요한 요구사항이라면 Next.js 쪽이 아직 유리하다.
- **생태계 성숙도 차이를 인지하라.** Next.js 대비 미들웨어, 이미지 최적화, 캐싱 전략 등 부가 기능은 아직 직접 구성해야 하는 부분이 많다. 팀의 인프라 역량에 따라 체감 난이도가 달라진다.
- **점진적 도입이 강점이다.** 완전히 새 프레임워크로 갈아타는 것보다, 기존 Vite SPA에 라우트 단위로 SSR을 붙여나가는 마이그레이션 경로를 우선 검토할 가치가 있다.
- **버전과 로드맵은 유동적이다.** 두 프로젝트 모두 활발히 개발 중이므로, 구체적인 API나 기능 지원 여부는 실제 착수 시점에 공식 문서로 다시 확인하는 것이 필요하다.

## 3줄 요약

- React Router v7의 프레임워크 모드와 TanStack Start는 Vite 위에서 SSR·중첩 라우팅·데이터 로딩을 제공하는 실용적 대안으로 떠오르고 있다.
- Next.js는 서버 컴포넌트 중심의 완결형 프레임워크로 기능은 풍부하지만 락인이 크고, 두 대안은 기존 Vite·React 자산을 살리며 점진적으로 SSR을 도입하기 좋다.
- 배포 어댑터 성숙도와 RSC 필요 여부를 먼저 확인한 뒤, 라우트 단위 점진적 마이그레이션을 우선 고려하는 것이 안전하다.

## 참고 자료

- [React Router 공식 문서 - Framework Mode](https://reactrouter.com/start/framework/installation)
- [TanStack Start 공식 문서](https://tanstack.com/start/latest)
- [Vite 공식 문서 - Plugins](https://vitejs.dev/plugins/)
- [Remix Blog - React Router v7 발표](https://remix.run/blog/react-router-v7)
