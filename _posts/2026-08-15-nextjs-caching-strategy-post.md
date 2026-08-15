---
layout: single
title: "Next.js 캐싱 전략 완전 정복"
date: 2026-08-15 21:30:00 +0530
categories: web-dev
tags: ["Next.js", "캐싱", "프론트엔드", "RSC"]
toc: true
toc_sticky: true
excerpt: "Next.js의 네 가지 캐시 레이어 구조와 무효화 전략, 그리고 "캐시가 안 지워진다"는 흔한 실수의 원인을 정리한다."
---

## 왜 지금 이 이야기인가

Next.js의 App Router로 넘어오면서 캐싱 구조가 이전보다 훨씬 다층적으로 바뀌었다. Pages Router 시절에는 `getStaticProps`의 `revalidate` 정도만 신경 쓰면 됐지만, App Router에서는 요청 메모이제이션, 데이터 캐시, 풀 라우트 캐시, 라우터 캐시가 각각 다른 생명주기로 동작한다. 그 결과 "분명히 revalidate를 호출했는데 화면이 안 바뀐다"는 질문이 커뮤니티에서 반복적으로 올라온다. 캐시 레이어를 구분하지 못하면 디버깅에 시간을 많이 쓰게 되므로, 각 레이어의 역할과 무효화 방법을 정리해둘 필요가 있다.

## 핵심 개념: 네 가지 캐시 레이어

| 레이어 | 위치 | 지속 범위 | 무효화 방법 |
|---|---|---|---|
| 요청 메모이제이션 | 서버, React 렌더 트리 | 단일 렌더 요청 동안만 | 자동(요청 종료 시 소멸) |
| 데이터 캐시 | 서버 | 여러 요청/배포 간 지속 | `revalidatePath`, `revalidateTag`, `fetch` 옵션 |
| 풀 라우트 캐시 | 서버(빌드/ISR 결과) | 정적 렌더링 결과 전체 | 위 함수 호출 시 함께 무효화됨 |
| 라우터 캐시 | 클라이언트 | 브라우저 세션 동안 | 자동 만료 시간 또는 `router.refresh()` |

요청 메모이제이션은 같은 렌더링 패스 안에서 동일한 `fetch` 호출이 중복 실행되지 않도록 막아주는 React의 기능이고, 데이터 캐시는 그 결과를 다음 요청에서도 재사용할 수 있게 서버에 영속적으로 저장하는 계층이다. 풀 라우트 캐시는 정적으로 렌더링 가능한 라우트의 결과물(HTML + RSC 페이로드) 자체를 캐시하는 것이고, 라우터 캐시는 클라이언트에서 방문했던 라우트의 RSC 페이로드를 브라우저 메모리에 잠깐 들고 있는 계층이다.

## 무효화 전략: revalidatePath vs revalidateTag

`revalidatePath`는 특정 경로(예: `/blog/[slug]`)의 캐시된 데이터를 무효화하고, `revalidateTag`는 `fetch` 호출 시 붙인 태그를 기준으로 여러 경로에 걸쳐 있는 캐시를 한 번에 무효화한다. 여러 페이지에서 같은 데이터를 참조한다면 태그 기반 무효화가 관리 포인트를 줄여준다.

## 예제

```typescript
// 데이터 페칭 시 태그를 붙여 캐싱
async function getPost(slug: string) {
  const res = await fetch(`https://api.example.com/posts/${slug}`, {
    next: { revalidate: 3600, tags: [`post-${slug}`] },
  });
  return res.json();
}
```

```typescript
// Server Action에서 태그 기반 무효화
"use server";
import { revalidateTag } from "next/cache";

export async function updatePost(slug: string) {
  await fetch(`https://api.example.com/posts/${slug}`, { method: "PUT" });
  revalidateTag(`post-${slug}`);
}
```

## "캐시가 안 지워진다" 흔한 실수와 원인

- `revalidateTag`를 서버에서 호출했지만, 클라이언트가 이미 라우터 캐시에 이전 RSC 페이로드를 들고 있어 화면이 즉시 반영되지 않는 경우 — `router.refresh()`나 실제 네비게이션이 필요할 수 있다.
- `fetch`에 태그를 아예 붙이지 않고 `revalidateTag`만 호출하면 무효화 대상 자체가 없어 아무 일도 일어나지 않는다.
- 개발 모드(`next dev`)에서는 기본적으로 캐시 동작이 프로덕션과 다르게 보일 수 있어, 로컬에서 "캐시가 잘 지워진다"고 확인했는데 배포 후 다르게 동작하는 경우가 있다고 알려져 있다.
- `cache: "no-store"`나 `force-dynamic`을 특정 라우트에만 걸어야 하는데 레이아웃 전체에 걸어버려 의도치 않게 하위 라우트까지 항상 동적 렌더링되는 경우도 흔하다.

## 실무 포인트와 주의사항

- 태그는 데이터 단위로, 경로 무효화는 화면 단위로 설계하는 편이 일관성 있는 캐시 정책을 만들기 쉽다.
- 재검증 주기(`revalidate` 초 단위)와 온디맨드 무효화(`revalidateTag`)를 함께 쓸 때는 어느 쪽이 우선인지 팀 내에서 명확히 합의해야 한다.
- 정적 콘텐츠와 사용자별 동적 콘텐츠가 섞인 페이지는 부분적으로 컴포넌트를 분리해 캐시 가능한 부분만 정적으로 남기는 것이 유리하다.
- 캐시 무효화 버그는 로컬 개발 환경에서 재현이 안 되는 경우가 많으므로, 프리뷰 배포 환경에서 실제 캐시 동작을 반드시 검증해야 한다.

## 3줄 요약

- Next.js는 요청 메모이제이션, 데이터 캐시, 풀 라우트 캐시, 라우터 캐시 네 개 레이어가 각각 다른 생명주기로 동작한다.
- `revalidatePath`는 경로 단위, `revalidateTag`는 태그 단위로 무효화하며 태그가 없으면 무효화 대상 자체가 없다.
- 서버 캐시를 지워도 클라이언트 라우터 캐시가 남아있으면 화면이 안 바뀔 수 있어 `router.refresh()` 등을 함께 고려해야 한다.

## 참고 자료

- [Next.js 공식 문서 - Caching](https://nextjs.org/docs/app/building-your-application/caching)
- [Next.js 공식 문서 - revalidateTag](https://nextjs.org/docs/app/api-reference/functions/revalidateTag)
- [Next.js 공식 문서 - revalidatePath](https://nextjs.org/docs/app/api-reference/functions/revalidatePath)
