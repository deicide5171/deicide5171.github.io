---
layout: single
title: "React 상태 관리 2026 — Zustand, Jotai, Server State"
date: 2026-08-15 20:30:00 +0530
categories: web-dev
tags: ["React", "상태관리", "Zustand", "TanStackQuery"]
toc: true
toc_sticky: true
excerpt: "클라이언트 상태와 서버 상태를 구분하고, 2026년 현재 상황에 맞는 상태 관리 도구를 고르는 기준을 정리한다."
---

## 왜 지금 상태 관리를 다시 이야기하는가

React 생태계에서 "상태 관리 라이브러리 논쟁"은 꾸준히 반복되는 주제다. Redux가 사실상 표준이던 시기를 지나, Recoil·Zustand·Jotai 같은 경량 라이브러리들이 등장했고, 여기에 TanStack Query(구 React Query) 같은 서버 상태 전용 도구가 자리를 잡으면서 "상태 관리"라는 말 자체가 예전보다 훨씬 세분화된 것으로 보인다. 이제는 하나의 라이브러리로 모든 상태를 관리하기보다, 상태의 성격에 맞춰 도구를 나눠 쓰는 방식이 자리 잡은 것으로 보인다.

이 글에서는 클라이언트 상태와 서버 상태를 구분하는 이유, 대표적인 경량 상태관리 라이브러리들의 차이, 그리고 Redux나 Context API가 여전히 유효한 상황이 무엇인지를 정리한다.

## 클라이언트 상태 vs 서버 상태

| 구분 | 클라이언트 상태 | 서버 상태 |
|---|---|---|
| 정의 | UI에서만 의미 있는 상태 (모달 열림 여부, 폼 입력값 등) | 원본이 서버/DB에 있고 클라이언트는 캐시된 사본을 보유 |
| 소유권 | 클라이언트가 완전히 소유 | 서버가 소유, 클라이언트는 동기화만 함 |
| 필요한 기능 | 값 저장, 구독, 렌더링 트리거 | 캐싱, 재검증(revalidation), 로딩/에러 상태, 낙관적 업데이트 |
| 대표 도구 | Zustand, Jotai, Context API, Redux | TanStack Query, SWR, RTK Query |

두 상태를 같은 방식으로 다루면 문제가 생기기 쉽다. 서버 상태를 일반 전역 상태 스토어에 그대로 넣으면 캐시 무효화, 재요청 타이밍, 중복 요청 방지 같은 로직을 직접 구현해야 하는데, 이는 이미 TanStack Query 같은 도구가 잘 해결해둔 문제다.

## 경량 상태관리 라이브러리 비교

| 라이브러리 | 특징 | 적합한 상황 |
|---|---|---|
| Zustand | 스토어 하나에 상태와 액션을 함께 정의, 보일러플레이트가 적음 | 컴포넌트 트리 전반에서 공유되는 단순~중간 복잡도 상태 |
| Jotai | atom 단위로 상태를 쪼개 관리, 필요한 atom만 구독 | 세밀한 단위의 리렌더링 최적화가 필요한 경우 |
| Context API | React 내장, 별도 라이브러리 불필요 | 변경 빈도가 낮은 값(테마, 로케일 등) 전파 |
| Redux (Toolkit) | 엄격한 단방향 흐름, 미들웨어·데브툴 생태계 성숙 | 대규모 팀, 복잡한 상태 전이 로직, 강한 규약이 필요한 조직 |

Zustand는 스토어를 하나의 훅처럼 다루는 단순함이 강점이고, Jotai는 원자(atom) 단위로 상태를 분리해 불필요한 리렌더링을 줄이는 데 강점이 있다고 알려져 있다. 둘 다 Redux 대비 보일러플레이트가 적어 소규모~중규모 프로젝트에서 선호되는 경향이 있는 것으로 보인다.

## 예제

```tsx
// Zustand: 간단한 클라이언트 상태 스토어
import { create } from 'zustand'

interface CartState {
  items: string[]
  addItem: (id: string) => void
}

const useCartStore = create<CartState>((set) => ({
  items: [],
  addItem: (id) => set((state) => ({ items: [...state.items, id] })),
}))
```

```tsx
// TanStack Query: 서버 상태 관리
import { useQuery } from '@tanstack/react-query'

function ProductList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetch('/api/products').then((res) => res.json()),
    staleTime: 60_000,
  })

  if (isLoading) return <p>로딩 중...</p>
  if (error) return <p>에러가 발생했습니다.</p>
  return <ul>{data.map((p: any) => <li key={p.id}>{p.name}</li>)}</ul>
}
```

## 실무 포인트와 주의사항

- 서버에서 온 데이터는 가능하면 TanStack Query 같은 전용 도구에 맡기고, 전역 스토어에는 순수 클라이언트 상태만 두는 편이 캐시 관리 로직 중복을 줄인다.
- Zustand·Jotai가 가볍다고 해서 무조건 Redux보다 낫다고 단정하기는 어렵다. 팀 규모가 크고 상태 전이 규약을 엄격히 강제해야 하는 조직에서는 Redux Toolkit의 명시적 구조가 여전히 유리할 수 있다.
- Context API는 상태관리 라이브러리라기보다 "값 전파" 도구에 가깝다. 값이 자주 바뀌는 상태를 Context에 올리면 하위 트리 전체가 리렌더링될 수 있어 주의가 필요하다.
- 라이브러리를 고를 때는 번들 크기나 유행보다, 프로젝트의 상태 종류(클라이언트/서버)와 팀의 기존 관례를 먼저 고려하는 것이 안전하다.

## 3줄 요약

- 클라이언트 상태와 서버 상태는 성격이 다르므로 서로 다른 도구로 관리하는 것이 일반적이다.
- Zustand·Jotai는 가벼운 클라이언트 상태 관리에, TanStack Query는 서버 상태 캐싱/동기화에 강점이 있다.
- Redux나 Context API도 팀 규모, 상태 전이 복잡도에 따라 여전히 합리적인 선택이 될 수 있다.

## 참고 자료

- [Zustand 공식 문서](https://zustand.docs.pmnd.rs/)
- [Jotai 공식 문서](https://jotai.org/)
- [TanStack Query 공식 문서](https://tanstack.com/query/latest)
- [Redux Toolkit 공식 문서](https://redux-toolkit.js.org/)
