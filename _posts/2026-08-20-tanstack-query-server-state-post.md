---
layout: single
title: "TanStack Query 제대로 쓰기 — staleTime·캐시 무효화·Optimistic Update로 서버 상태 다스리기"
date: 2026-08-20 13:30:00 +0530
categories: frontend
tags: ["tanstack-query", "react-query", "서버상태", "캐시전략", "optimistic-update", "typescript"]
toc: true
toc_sticky: true
excerpt: "서버 상태를 useState/전역 스토어에 그대로 욱여넣다 겪는 문제를 TanStack Query의 staleTime·gcTime·쿼리 키 무효화·Optimistic Update로 풀어내는 방법을 정리한다."
---

## 왜 지금 다시 TanStack Query인가

"서버 상태와 클라이언트 상태를 분리해야 한다"는 원칙은 이제 React 생태계에서 상식에 가깝다. 문제는 그 다음이다. TanStack Query(구 React Query)를 도입해놓고도 여전히 `useEffect`로 수동 refetch를 걸거나, 캐시 무효화 타이밍을 감으로 맞추다가 화면에 낡은 데이터가 남는 버그를 겪는 팀이 많다. 라이브러리를 설치하는 것과 "서버 상태를 제대로 다루는 것" 사이에는 꽤 큰 간극이 있다.

TanStack Query v5는 `useQuery`/`useMutation` 등 훅 시그니처를 객체 하나로 통일하고, `useSuspenseQuery`로 React의 Suspense 데이터 페칭과 자연스럽게 통합되도록 다듬어왔다. React 19의 Actions·`useTransition`과 서버 상태 갱신을 조합하는 패턴도 늘고 있다. 도구는 성숙했으니, 이제는 "캐시가 정확히 언제 오래된 것으로 취급되고, 언제 지워지는가"라는 핵심 모델을 제대로 이해할 차례다.

## 핵심 개념 1: staleTime과 gcTime은 서로 다른 질문에 답한다

가장 많이 헷갈리는 지점이 이 두 옵션의 역할 구분이다.

| 옵션 | 기본값 | 답하는 질문 | 경과 후 동작 |
|---|---|---|---|
| `staleTime` | 0 | 이 데이터를 얼마나 믿을 수 있는가? | 재마운트·창 포커스·재연결 시 백그라운드 refetch 트리거 |
| `gcTime` (구 `cacheTime`) | 5분 | 화면에서 사라진 데이터를 얼마나 더 들고 있을 것인가? | 구독자가 0명인 채로 시간이 지나면 캐시 완전 삭제 |

기본값 `staleTime: 0`은 "항상 최신을 우선"하는 안전한 기본값이지만, 자주 안 바뀌는 데이터(예: 코드성 목록, 설정값)까지 매번 재요청하면 네트워크 낭비다. 반대로 실시간성이 중요한 데이터에 `staleTime`을 길게 잡으면 오래된 값이 화면에 남는다. 데이터 성격별로 값을 다르게 주는 것이 핵심이다.

## 핵심 개념 2: 쿼리 키는 캐시의 "주소"다

쿼리 키는 단순 문자열이 아니라 캐시를 식별하는 구조화된 값이다. 배열에 필터·페이지 같은 변수를 포함시키면, TanStack Query가 이를 기준으로 캐시를 분리하고 무효화 범위를 계산한다.

| 쿼리 키 패턴 | 의미 |
|---|---|
| `['todos']` | todos 관련 캐시 전체 |
| `['todos', { status: 'done' }]` | 완료된 todos만 별도 캐시 |
| `['todo', todoId]` | 특정 todo 단건 캐시 |

`queryClient.invalidateQueries({ queryKey: ['todos'] })`처럼 앞부분만 지정하면 하위 키를 가진 캐시들이 함께 무효화된다(prefix 매칭). 이 구조를 이해하지 못하면 뮤테이션 성공 후 "어디까지 무효화해야 화면이 최신 상태가 되는지" 매번 감으로 판단하게 된다.

## 예제: Optimistic Update로 체감 속도 끌어올리기

낙관적 업데이트는 서버 응답을 기다리지 않고 캐시를 먼저 갱신해, 사용자에게 즉각적인 반응을 보여주는 패턴이다. 실패 시 롤백 로직이 반드시 짝을 이뤄야 한다.

```tsx
function useToggleTodo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (todo: Todo) =>
      api.patch(`/todos/${todo.id}`, { done: !todo.done }),

    onMutate: async (todo) => {
      // 진행 중인 refetch와 충돌 방지
      await queryClient.cancelQueries({ queryKey: ['todos'] });

      const previous = queryClient.getQueryData<Todo[]>(['todos']);

      queryClient.setQueryData<Todo[]>(['todos'], (old) =>
        old?.map((t) => (t.id === todo.id ? { ...t, done: !t.done } : t))
      );

      return { previous }; // 롤백용 스냅샷
    },

    onError: (_err, _todo, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['todos'], context.previous);
      }
    },

    onSettled: () => {
      // 성공이든 실패든 서버 값으로 최종 동기화
      queryClient.invalidateQueries({ queryKey: ['todos'] });
    },
  });
}
```

`onMutate`에서 캐시를 미리 바꾸고, `onError`에서 스냅샷으로 되돌리고, `onSettled`에서 실제 서버 값으로 다시 맞추는 세 단계가 한 세트라는 점이 핵심이다. 이 중 하나라도 빠지면 실패 시 화면에 거짓 상태가 그대로 남는다.

## 실무 포인트

- **`staleTime`을 0으로 방치하지 말 것**: 자주 안 바뀌는 리소스(카테고리 목록, 사용자 프로필 등)는 `staleTime`을 수 분 단위로 늘려 불필요한 네트워크 요청을 줄인다.
- **뮤테이션 성공 후 무효화 범위를 최소화**: `['todos']` 전체를 매번 무효화하기보다, 실제로 영향을 받은 쿼리 키만 골라 무효화하면 화면 깜빡임과 재요청 비용을 줄일 수 있다.
- **낙관적 업데이트는 롤백 경로가 있을 때만 도입**: 실패 시나리오를 테스트하지 않은 채 `onMutate`만 구현하면, 네트워크 오류 상황에서 오히려 신뢰도가 떨어지는 UI가 된다.
- **Suspense와 조합 시 에러 바운더리를 함께 설계**: `useSuspenseQuery`는 로딩을 Suspense에 위임하는 대신 에러 처리를 상위 에러 바운더리에 맡기므로, 두 경계를 짝지어 배치해야 한다.

## 3줄 요약

- `staleTime`은 "얼마나 믿을지", `gcTime`은 "얼마나 들고 있을지"를 결정하는 서로 다른 옵션이며, 데이터 성격별로 값을 나눠 주는 것이 기본이다.
- 쿼리 키는 캐시의 주소이므로, 구조를 이해해야 뮤테이션 후 정확한 범위만 무효화할 수 있다.
- Optimistic Update는 `onMutate`(선반영) → `onError`(롤백) → `onSettled`(최종 동기화) 세 단계가 한 세트로 구현되어야 안전하다.

## 참고 자료

- [TanStack Query — Caching Guide](https://tanstack.com/query/latest/docs/framework/react/guides/caching)
- [TanStack Query — Query Invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [TanStack Query — Optimistic Updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)

<img src="/assets/images/posts/2026-08-20-tanstack-query-server-state-1.svg" alt="staleTime과 gcTime에 따른 쿼리 캐시 생명주기 - Fresh, Stale, gcTime 대기, 삭제 단계" style="width:100%;">
