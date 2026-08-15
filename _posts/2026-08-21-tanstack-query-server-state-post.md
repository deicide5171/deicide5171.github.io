---
layout: single
title: "TanStack Query로 서버 상태 관리 다시 배우기 — 캐싱과 무효화 전략"
date: 2026-08-21 12:30:00 +0530
categories: frontend
tags: ["frontend", "tanstack-query", "react-query", "caching", "state-management"]
toc: true
toc_sticky: true
excerpt: "서버 데이터를 클라이언트 상태 관리 도구에 억지로 우겨넣던 방식 대신, TanStack Query가 서버 상태를 캐싱·재검증하는 전용 모델로 다루는 방식을 정리한다."
---

Redux 같은 클라이언트 상태 관리 도구로 프로젝트를 시작하면, 서버에서 받아온 데이터도 결국 같은 스토어에 집어넣게 되는 경우가 많다. 문제는 서버 데이터가 클라이언트에서 직접 만든 상태(모달 열림 여부, 폼 입력값 등)와 근본적으로 다르다는 점이다. 로딩 상태를 표시하려면 `isLoading` 플래그를 액션과 리듀서로 직접 관리해야 하고, 에러가 나면 `error` 필드를 따로 두어야 하며, 데이터가 오래됐는지 판단해 다시 불러오는 로직도 컴포넌트마다 흩어져 반복된다.

같은 API를 여러 컴포넌트가 동시에 호출하면 중복 요청을 막기 위한 별도의 캐싱 계층도 필요해진다. 결국 "서버에서 데이터를 가져와 화면에 보여준다"는 단순한 작업 하나를 위해 로딩·에러·캐시·재요청·중복 방지까지 전부 손으로 짜는 보일러플레이트가 쌓인다. 이 반복 작업 자체가 버그의 원천이 되기도 한다.

**TanStack Query**(구 React Query)는 이 문제를 다른 각도에서 접근한다. 서버에서 가져온 데이터를 클라이언트 상태처럼 저장·동기화하는 대신, 애초에 "서버 상태"라는 별도의 카테고리로 취급하고 캐싱·재검증·무효화를 라이브러리 차원에서 자동화한다. 상태 관리 도구를 대체한다기보다, 서버 상태라는 영역을 전담하는 도구로 역할을 나누는 셈이다.

## 핵심 개념 1: 서버 상태와 클라이언트 상태는 다르다

클라이언트 상태는 애플리케이션이 소유하고 동기적으로 갱신하는 값이다. 반면 서버 상태는 애플리케이션이 소유하지 않은, 원격 어딘가에 존재하는 데이터의 스냅샷이다. 이 차이에서 몇 가지 성질이 따라온다. 서버 상태는 내가 모르는 사이에 다른 클라이언트에 의해 바뀔 수 있고, 가져오는 데 비동기 처리와 실패 가능성이 따르며, 시간이 지나면 "오래된(stale)" 상태가 된다.

Redux 같은 도구가 잘 다루는 것은 전자다. 후자를 억지로 같은 방식으로 다루면 위에서 언급한 로딩/에러/캐시 보일러플레이트가 필연적으로 생긴다. TanStack Query는 서버 상태를 별도의 모델로 인정하고, "이 데이터는 지금 신선한가, 오래됐는가", "다시 가져와야 하는가"라는 질문에 기본값을 제공한다.

## 핵심 개념 2: 쿼리 키와 staleTime/gcTime 기반 캐싱

TanStack Query의 캐시는 **쿼리 키(query key)** 를 기준으로 식별된다. 같은 키를 쓰는 `useQuery` 호출은 컴포넌트 위치와 상관없이 같은 캐시 항목을 공유하므로, 여러 컴포넌트가 동일한 데이터를 요청해도 중복 네트워크 요청이 자동으로 합쳐진다. 키는 보통 배열로 구성하며, 뒤쪽 요소가 필터나 파라미터 역할을 한다(예: `["todos", { status: "done" }]`).

캐시 항목의 수명은 두 값으로 조절한다. **staleTime**은 데이터를 "신선하다"고 간주하는 기간으로, 이 시간 안에는 같은 쿼리가 다시 마운트되어도 네트워크 요청 없이 캐시 값을 그대로 쓴다. **gcTime**(과거 이름은 cacheTime)은 쿼리를 아무도 구독하지 않게 된 뒤에도 캐시를 메모리에 남겨두는 기간으로, 이 시간이 지나면 캐시가 가비지 컬렉션된다. 기본값은 staleTime이 0(즉시 stale 취급)이고 gcTime이 5분인데, 실제 값은 라이브러리 버전에 따라 조정될 수 있으므로 프로젝트에 도입할 때는 사용 중인 버전의 문서로 확인하는 편이 안전하다.

## 핵심 개념 3: 뮤테이션과 invalidateQueries를 통한 무효화

데이터를 읽는 쪽은 `useQuery`, 서버 상태를 변경(생성·수정·삭제)하는 쪽은 `useMutation`이 맡는다. 뮤테이션 자체는 캐시를 자동으로 갱신하지 않으므로, 변경이 성공한 뒤 관련된 쿼리를 다시 가져오도록 명시적으로 알려줘야 한다. 이때 쓰는 것이 `queryClient.invalidateQueries`다. 특정 쿼리 키(또는 그 접두사)를 무효화하면, 해당 키를 구독 중인 쿼리들이 stale 상태로 표시되고 활성 상태라면 즉시 다시 요청된다.

이 흐름 덕분에 "할 일 목록을 수정했으니 목록 화면을 새로고침해야 한다"는 로직을 컴포넌트 간 이벤트 전달이나 수동 리듀서 갱신 없이, 뮤테이션의 `onSuccess` 콜백 한 줄로 처리할 수 있다.

## 예제

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// 목록 조회
function TodoList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["todos"],
    queryFn: async () => {
      const res = await fetch("/api/todos");
      if (!res.ok) throw new Error("failed to fetch todos");
      return res.json();
    },
    staleTime: 30_000, // 30초 동안은 신선한 데이터로 간주
  });

  if (isLoading) return <p>로딩 중...</p>;
  if (error) return <p>에러가 발생했습니다.</p>;

  return (
    <ul>
      {data.map((todo: { id: string; title: string }) => (
        <li key={todo.id}>{todo.title}</li>
      ))}
    </ul>
  );
}

// 항목 추가 후 목록 캐시 무효화
function AddTodoForm() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (title: string) =>
      fetch("/api/todos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => {
      // "todos" 키를 구독 중인 쿼리를 다시 가져오도록 무효화
      queryClient.invalidateQueries({ queryKey: ["todos"] });
    },
  });

  return (
    <button onClick={() => mutation.mutate("새 할 일")}>
      추가하기
    </button>
  );
}
```

## 실무 포인트

- **쿼리 키는 의존성 배열처럼 설계한다**: 쿼리 결과가 달라지는 모든 변수(필터, 페이지 번호, 정렬 조건 등)를 키에 포함시켜야 한다. 빠뜨리면 서로 다른 조건의 요청이 같은 캐시 항목을 잘못 공유하게 된다. 반대로 계층 구조(`["todos"]` → `["todos", id]`)로 키를 설계해두면, 상위 키만 무효화해도 하위 키들이 함께 무효화되어 관리가 쉬워진다.
- **낙관적 업데이트는 롤백 경로까지 함께 설계한다**: 응답을 기다리지 않고 캐시를 먼저 낙관적으로 갱신하면 체감 반응 속도는 좋아지지만, 뮤테이션이 실패했을 때 이전 상태로 되돌리는 로직이 없으면 화면과 서버 상태가 어긋난 채로 남는다. `onMutate`에서 이전 캐시 값을 저장해두고, `onError`에서 그 값으로 되돌리는 패턴을 함께 구현해야 안전하다.

## 3줄 요약

- 서버 상태는 클라이언트 상태와 성질이 달라서(비동기, 외부 소유, 시간에 따라 오래됨) 같은 방식으로 관리하면 보일러플레이트가 쌓인다.
- TanStack Query는 쿼리 키로 캐시를 식별하고, staleTime/gcTime으로 데이터의 신선도와 캐시 수명을 관리한다.
- 뮤테이션 이후에는 invalidateQueries로 관련 쿼리 키를 명시적으로 무효화해야 하며, 낙관적 업데이트를 쓸 때는 실패 시 롤백 경로까지 함께 마련해야 한다.

## 참고 자료

- [TanStack Query 공식 문서](https://tanstack.com/query/latest/docs/framework/react/overview)
- [Important Defaults (staleTime/gcTime 기본값)](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)
- [Query Invalidation 가이드](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [Mutations 가이드](https://tanstack.com/query/latest/docs/framework/react/guides/mutations)
- [Optimistic Updates 가이드](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)
