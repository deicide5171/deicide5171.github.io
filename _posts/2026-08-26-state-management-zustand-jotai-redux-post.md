---
layout: single
title: "새 프로젝트에 Redux부터 까는 습관, 이제는 버려야 할까 — 상태관리 선택 기준"
date: 2026-08-26 13:30:00 +0530
categories: frontend
tags: ["frontend", "zustand", "jotai", "redux", "state-management", "react"]
toc: true
toc_sticky: true
excerpt: "Zustand, Jotai, Redux Toolkit, 그리고 서버 상태를 다루는 TanStack Query까지 — 상태의 종류에 따라 실제로 어떤 도구가 맞는지 판단하는 기준을 정리한다."
---

새 React 프로젝트를 시작할 때 "상태관리 라이브러리는 뭘 쓰죠?"라는 질문에 예전에는 관성적으로 Redux가 답이었다. 지금은 선택지가 늘었을 뿐 아니라, 애초에 "전역 상태관리 라이브러리 하나로 모든 상태를 관리한다"는 전제 자체가 낡은 접근이 됐다. 서버에서 가져온 데이터, UI 로컬 상태, 진짜 전역 클라이언트 상태는 성격이 완전히 다른데도 예전에는 이걸 다 Redux 스토어 하나에 욱여넣었다. 지금 실무에서 중요한 질문은 "Zustand냐 Redux냐"가 아니라 "이 상태는 애초에 어떤 종류의 상태인가"다.

이 글에서는 상태의 세 가지 범주를 먼저 구분하고, 그중 "클라이언트 전역 상태"에 한정해 Zustand·Jotai·Redux Toolkit이 실제로 어떤 상황에서 우위를 갖는지 판단 기준을 정리한다.

## 핵심 개념 1: 상태를 먼저 종류별로 나눈다

| 상태 종류 | 특징 | 적합한 도구 |
|---|---|---|
| 서버 상태 | 서버가 원본, 캐시·재검증 필요 | TanStack Query, SWR |
| UI 로컬 상태 | 컴포넌트 하나·트리 일부에만 필요 | `useState`, `useReducer` |
| 클라이언트 전역 상태 | 여러 트리에서 공유, 클라이언트가 원본 | Zustand, Jotai, Redux Toolkit |

서버 상태(API로 가져온 목록, 상세 데이터)를 전역 스토어에 직접 넣고 로딩·에러·캐시 무효화를 손으로 관리하던 시절의 패턴은, TanStack Query 같은 서버 상태 전용 라이브러리가 캐싱·재검증·중복 요청 제거를 대신해주면서 대부분 사라졌다. 그 결과 "전역 상태관리 라이브러리"가 실제로 책임져야 할 범위는 크게 줄었다 — 로그인 여부, 테마, 사이드바 열림 상태, 다단계 폼 진행 상태처럼 정말로 클라이언트에서만 존재하는 상태만 남는다.

## 핵심 개념 2: 남은 전역 상태를 무엇으로 관리할까

범위가 좁아진 클라이언트 전역 상태를 관리하는 도구들은 접근 방식이 갈린다.

| 구분 | Zustand | Jotai | Redux Toolkit |
|---|---|---|---|
| 모델 | 단일 스토어, 훅으로 구독 | 원자(atom) 단위 조합 | 단일 스토어 + 액션/리듀서 |
| 보일러플레이트 | 매우 적음 | 적음(atom 선언만) | RTK로 많이 줄었지만 여전히 구조 필요 |
| 세분화된 리렌더 최적화 | 선택자(selector)로 수동 관리 | atom 단위로 자동 세분화 | selector + memoization 필요 |
| 미들웨어·데브툴 생태계 | 기본 제공 + 확장 가능 | 비교적 단순 | 가장 성숙(타임트래블 디버깅 등) |
| 적합한 규모 | 중소~중대형, 빠른 도입 | 세분화된 리렌더가 중요한 대시보드류 | 액션 이력·감사가 중요한 대형 앱 |

Zustand는 보일러플레이트가 거의 없고 훅 하나로 스토어를 만들 수 있어 신규 프로젝트에서 가장 빠르게 도입된다. Jotai는 상태를 원자 단위로 쪼개 관리하므로, 큰 대시보드에서 위젯 하나의 상태 변경이 다른 위젯을 리렌더시키지 않게 세분화하고 싶을 때 강점이 있다. Redux Toolkit은 여전히 유효한데, 특히 액션 이력을 남겨야 하거나(감사 요구), 타임트래블 디버깅처럼 성숙한 미들웨어 생태계가 필요한 대형 조직 프로젝트에서는 오히려 구조가 잡혀 있다는 점이 장점이 된다.

## 예제: 같은 요구사항을 Zustand와 Redux Toolkit으로

```javascript
// Zustand — 스토어 생성과 사용이 한 파일에서 끝난다
import { create } from 'zustand';

const useCartStore = create((set) => ({
  items: [],
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  clear: () => set({ items: [] }),
}));

// 컴포넌트에서는 필요한 슬라이스만 선택해 구독 — 불필요한 리렌더 방지
function CartBadge() {
  const itemCount = useCartStore((state) => state.items.length);
  return <span>{itemCount}</span>;
}
```

```javascript
// Redux Toolkit — 슬라이스 정의, 스토어 등록, Provider 연결이 각각 필요
import { createSlice, configureStore } from '@reduxjs/toolkit';

const cartSlice = createSlice({
  name: 'cart',
  initialState: { items: [] },
  reducers: {
    addItem: (state, action) => { state.items.push(action.payload); },
    clear: (state) => { state.items = []; },
  },
});

export const store = configureStore({ reducer: { cart: cartSlice.reducer } });
// 이후 <Provider store={store}> 로 앱 전체를 감싸야 사용 가능
```

같은 기능이라도 Redux Toolkit 쪽이 슬라이스 정의, 스토어 조합, Provider 연결까지 세 단계를 거쳐야 한다. 이 차이가 작은 프로젝트에서는 부담이지만, 팀 규모가 커지고 액션 흐름을 명시적으로 추적해야 하는 조직에서는 오히려 이 명시성이 유지보수 이점으로 작용한다.

## 실무 포인트

- **서버 상태를 전역 스토어에 넣지 않는다**: API 응답을 Zustand나 Redux 스토어에 그대로 저장하고 캐시 무효화를 손으로 짜는 패턴은 대부분의 경우 TanStack Query로 대체하는 게 낫다. 두 종류를 억지로 하나의 도구로 통합하려 하면 캐싱 로직이 애플리케이션 코드에 새어 나온다.
- **라이브러리 교체보다 상태 분류가 먼저다**: "우리 상태관리가 복잡하다"는 불만은 대개 도구 문제가 아니라 서버 상태·전역 상태·로컬 상태가 뒤섞여 있다는 신호다. 라이브러리를 바꾸기 전에 지금 스토어에 들어있는 상태를 세 범주로 다시 분류하는 작업이 먼저다.
- **팀 관례와 디버깅 요구를 무시하지 않는다**: 기술적으로는 Zustand가 더 가볍더라도, 이미 Redux DevTools 기반 디버깅·QA 프로세스가 자리 잡은 조직이라면 전환 비용이 기술적 이득보다 클 수 있다.

## 3줄 요약

- 상태관리 도구를 고르기 전에 서버 상태·UI 로컬 상태·클라이언트 전역 상태를 먼저 구분해야 하며, 서버 상태는 TanStack Query 같은 전용 도구로 넘기는 것이 먼저다.
- 남은 클라이언트 전역 상태에서 Zustand는 빠른 도입과 적은 보일러플레이트, Jotai는 세분화된 리렌더 최적화, Redux Toolkit은 성숙한 디버깅·감사 생태계가 강점이다.
- "상태관리가 복잡하다"는 불만은 대부분 도구 문제가 아니라 상태 분류가 안 된 신호이며, 도구 교체보다 분류 작업이 우선이다.

## 참고 자료

- [Zustand 공식 문서](https://zustand.docs.pmnd.rs/)
- [Jotai 공식 문서](https://jotai.org/docs/introduction)
- [Redux Toolkit 공식 문서](https://redux-toolkit.js.org/introduction/getting-started)
- [TanStack Query 공식 문서: Overview](https://tanstack.com/query/latest/docs/framework/react/overview)
