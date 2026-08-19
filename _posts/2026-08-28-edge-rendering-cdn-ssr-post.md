---
layout: single
title: "SSR을 서울 데이터센터가 아니라 사용자 옆에서 — 엣지 렌더링과 CDN 기반 SSR"
date: 2026-08-28 12:30:00 +0530
categories: frontend
tags: ["frontend", "edge-rendering", "ssr", "cloudflare-workers", "vercel-edge", "cdn"]
toc: true
toc_sticky: true
excerpt: "SSR을 단일 리전 서버가 아니라 사용자와 물리적으로 가장 가까운 CDN 엣지에서 실행하는 엣지 렌더링의 동작 원리와, Node.js 런타임을 그대로 못 쓰는 이유·제약을 정리한다."
---

전통적인 SSR(Server-Side Rendering)은 도쿄나 버지니아 같은 단일 리전에 있는 서버가 전 세계 요청을 받아 HTML을 렌더링해 내려보낸다. 서버 자체의 렌더링 속도가 아무리 빨라도, 시드니나 상파울루의 사용자에게는 요청이 그 리전까지 왕복하는 네트워크 지연이 렌더링 시간 위에 그대로 얹힌다. 엣지 렌더링(edge rendering)은 이 문제를 "서버를 더 빠르게"가 아니라 "서버를 사용자 옆으로" 옮겨서 푸는 접근이다. Vercel Edge Functions, Cloudflare Workers, Deno Deploy 같은 플랫폼은 전 세계 수백 개 PoP(Point of Presence)에 동일한 코드를 배포해두고, 요청이 들어오면 지리적으로 가장 가까운 PoP에서 즉시 실행한다.

문제는 이 PoP들이 일반적인 Node.js 서버가 아니라 V8 isolate 같은 경량 런타임 위에서 동작한다는 점이다. 콜드 스타트를 밀리초 단위로 줄이기 위해 Node.js API 전체를 지원하지 않고, 파일 시스템 접근이나 장시간 실행 같은 기능도 의도적으로 제한한다. 이 글에서는 엣지 런타임이 왜 이런 제약을 갖는지, 그리고 이 제약 안에서 SSR을 설계할 때 무엇을 신경 써야 하는지 정리한다.

## 핵심 개념 1: 리전 서버 SSR vs 엣지 렌더링 — 무엇이 옮겨가는가

리전 서버 SSR은 요청이 특정 데이터센터까지 이동한 뒤 그곳에서 렌더링이 일어난다. 엣지 렌더링은 코드 자체가 배포 시점에 전 세계 PoP에 미리 뿌려져 있고, 요청은 그중 지리적으로 가장 가까운 곳에서 처리된다. 즉 "요청이 코드를 찾아가는" 구조에서 "코드가 이미 요청 근처에 있는" 구조로 바뀐 것이다.

| 구분 | 리전 서버 SSR | 엣지 렌더링 |
|---|---|---|
| 실행 위치 | 고정된 1~2개 리전 | 요청과 가장 가까운 PoP (수십~수백 곳) |
| 런타임 | 완전한 Node.js | V8 isolate 기반 경량 런타임(Web API 서브셋) |
| 콜드 스타트 | 상대적으로 길 수 있음(수백ms) | 매우 짧음(수ms 단위 목표) |
| 파일 시스템 접근 | 가능 | 대부분 불가능 |
| DB 커넥션 풀 | 안정적 유지 가능 | 매 요청 신규 연결에 가까운 경우 많음 |
| 원거리 사용자 지연 | 네트워크 왕복 그대로 발생 | 물리적 거리 자체가 줄어듦 |

## 핵심 개념 2: 왜 완전한 Node.js를 못 쓰는가 — V8 isolate의 트레이드오프

엣지 플랫폼 대부분은 컨테이너나 VM 대신 **V8 isolate**를 실행 단위로 쓴다. isolate는 V8 엔진 안에서 격리된 하나의 JS 실행 컨텍스트로, 별도 프로세스나 컨테이너를 새로 띄우는 것보다 시작 비용이 훨씬 낮다. 이 덕분에 요청마다 수백ms가 아니라 수ms 안에 새 실행 환경을 준비할 수 있고, 이는 전 세계 수백 곳에 코드를 뿌려두고 순간적으로 스핀업하는 엣지 모델의 전제 조건이다.

대신 isolate는 Node.js의 네이티브 애드온, 파일 시스템 API(`fs`), 일부 저수준 네트워킹 API를 지원하지 않는다. 대부분의 엣지 런타임은 Node.js API 대신 `fetch`, `Request`/`Response`, `ReadableStream` 같은 **웹 표준 API**만 제공하는데, 이는 브라우저와 서버 코드 사이의 이식성을 높이는 대신 Node 전용 라이브러리(특히 네이티브 바인딩에 의존하는 이미지 처리나 암호화 라이브러리)를 그대로는 쓸 수 없게 만든다.

## 핵심 개념 3: 데이터 접근 지연이라는 새로운 병목

렌더링 자체는 사용자 옆에서 실행돼 빨라졌지만, 그 렌더링에 필요한 데이터(DB, 원본 API)는 여전히 특정 리전에만 있는 경우가 대부분이다. 이 경우 엣지에서 렌더링을 시작해도 데이터를 가져오는 왕복 지연이 그대로 남아, "렌더링은 빨라졌는데 전체 응답은 그대로"인 상황이 생길 수 있다. 그래서 엣지 렌더링을 제대로 활용하려면 데이터 계층도 함께 분산시켜야 한다 — 읽기 전용 데이터는 엣지에 가까운 리전 복제본이나 엣지 KV 스토어(Cloudflare KV, Vercel Edge Config)에 캐싱하고, 쓰기가 필요한 요청만 원본 리전으로 보내는 식이다.

<img src="/assets/images/posts/2026-08-28-edge-rendering-cdn-ssr-1.svg" alt="사용자 요청이 전 세계 PoP 중 가장 가까운 곳에서 렌더링되지만, 데이터가 여전히 단일 리전에 있으면 그 왕복 지연이 병목으로 남는 구조" style="width:100%;">

## 예제: Next.js에서 엣지 런타임 선택

```typescript
// app/product/[id]/page.tsx
export const runtime = "edge"; // 이 라우트만 엣지 런타임에서 렌더링

export default async function ProductPage({ params }: { params: { id: string } }) {
  // fetch는 웹 표준 API라 엣지 런타임에서도 동일하게 동작
  const res = await fetch(`https://api.example.com/products/${params.id}`, {
    next: { revalidate: 60 }, // 엣지 캐시와 결합해 60초간 재사용
  });
  const product = await res.json();

  return (
    <main>
      <h1>{product.name}</h1>
      <p>{product.price}원</p>
    </main>
  );
}
```

```javascript
// Cloudflare Workers: KV로 지연 없는 읽기 전용 데이터 접근
export default {
  async fetch(request, env) {
    const cached = await env.PRODUCT_KV.get("featured-products", "json");
    if (cached) {
      return new Response(renderHTML(cached), {
        headers: { "content-type": "text/html" },
      });
    }
    // KV 미스 시에만 원본 리전으로 폴백
    const fresh = await fetch("https://origin.example.com/api/featured");
    return new Response(await fresh.text());
  },
};
```

Next.js처럼 라우트 단위로 `runtime`을 선택할 수 있는 프레임워크에서는, 전체 앱을 엣지로 옮기기보다 **지연에 민감하고 무거운 Node 의존성이 없는 라우트만** 선별적으로 엣지에 배치하는 것이 현실적인 접근이다.

## 실무 포인트

- **Node 전용 패키지 의존성을 먼저 감사할 것**: 이미지 처리(sharp), 일부 ORM의 네이티브 드라이버, 인증 라이브러리 중 파일 시스템에 의존하는 것들은 엣지 런타임에서 그대로 동작하지 않는다. 마이그레이션 전에 의존성 트리를 점검해야 한다.
- **DB 커넥션 전략을 다시 짤 것**: 엣지 함수는 매 요청마다 새로 실행되는 경우가 많아 전통적인 커넥션 풀을 유지하기 어렵다. HTTP 기반 DB 드라이버(Neon, PlanetScale의 HTTP 인터페이스 등)나 커넥션 풀러(PgBouncer, Prisma Accelerate)를 앞단에 두는 것이 일반적이다.
- **엣지가 항상 정답은 아니다**: 무거운 연산, 긴 실행 시간이 필요한 작업, Node 전용 라이브러리에 강하게 의존하는 로직은 여전히 리전 서버가 적합하다. 지연에 민감한 얕은 렌더링 경로만 골라 엣지로 옮기는 것이 과도한 마이그레이션 비용을 피하는 길이다.

## 3줄 요약

- 엣지 렌더링은 SSR 코드를 전 세계 PoP에 미리 배포해 사용자와 물리적으로 가장 가까운 곳에서 즉시 실행하는 방식이다.
- 콜드 스타트를 줄이기 위해 V8 isolate 기반 경량 런타임을 쓰는 대가로 완전한 Node.js API 대신 웹 표준 API 서브셋만 지원한다.
- 렌더링만 옮겨서는 부족하고, 데이터도 엣지 KV·리전 복제본으로 함께 분산시켜야 실제 응답 지연이 줄어든다.

## 참고 자료

- [Vercel 공식 문서: Edge Runtime](https://vercel.com/docs/functions/runtimes/edge)
- [Cloudflare Workers 공식 문서: How Workers Works](https://developers.cloudflare.com/workers/reference/how-workers-works/)
- [Next.js 공식 문서: Edge and Node.js Runtimes](https://nextjs.org/docs/app/building-your-application/rendering/edge-and-nodejs-runtimes)
