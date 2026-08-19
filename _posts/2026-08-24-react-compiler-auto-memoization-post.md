---
layout: single
title: "useMemo를 그만 써도 될까 — React Compiler 자동 메모이제이션 실전"
date: 2026-08-24 13:30:00 +0530
categories: frontend
tags: ["react", "react-compiler", "memoization", "usememo", "usecallback", "performance"]
toc: true
toc_sticky: true
excerpt: "리렌더링 최적화를 위해 useMemo/useCallback을 수동으로 흩뿌려야 했던 문제를, 빌드 타임에 메모이제이션을 자동 삽입하는 React Compiler가 어떻게 대체하는지 실무 적용 관점에서 정리한다."
---

React에서 불필요한 리렌더링을 막으려면 `useMemo`, `useCallback`, `React.memo`를 적재적소에 손으로 붙여야 했다. 문제는 이 작업이 반복적이고 실수하기 쉽다는 것이다. 의존성 배열을 하나 빠뜨리면 stale closure 버그가 생기고, 반대로 최적화가 필요 없는 곳까지 습관적으로 감싸면 코드만 지저분해지고 오히려 메모리·비교 비용이 늘어난다.

React Compiler(구 React Forget)는 이 문제를 컴파일 타임으로 옮긴다. 컴포넌트와 훅의 코드를 정적으로 분석해, 어디에 메모이제이션이 필요한지 판단하고 빌드 시점에 자동으로 삽입한다. 개발자는 원칙적으로 `useMemo`/`useCallback`을 손으로 쓸 필요가 없어진다. 이 글에서는 동작 원리, 전제 조건, 그리고 도입 시 실무에서 마주치는 지점을 정리한다.

## 핵심 개념 1: 무엇이 자동화되는가

React Compiler는 컴포넌트 함수와 커스텀 훅의 코드를 분석해, 각 값이 이전 렌더링과 비교해 실제로 바뀌었는지 추적하는 코드를 자동 생성한다. 개념적으로는 아래와 같은 변환이 빌드 시점에 일어난다.

```jsx
// 개발자가 작성하는 코드 — 메모이제이션 훅이 전혀 없다
function ProductList({ items, category }) {
  const filtered = items.filter(item => item.category === category);
  const handleClick = (id) => console.log('clicked', id);

  return filtered.map(item => (
    <ProductCard key={item.id} item={item} onClick={handleClick} />
  ));
}
```

```jsx
// React Compiler가 빌드 시점에 생성하는 것과 개념적으로 동일한 코드
function ProductList({ items, category }) {
  const $ = useMemoCache(3);
  let filtered;
  if ($[0] !== items || $[1] !== category) {
    filtered = items.filter(item => item.category === category);
    $[0] = items; $[1] = category; $[2] = filtered;
  } else {
    filtered = $[2];
  }
  // handleClick도 동일한 방식으로 자동 메모이제이션됨
  // ...
}
```

핵심은 개발자가 의존성 배열을 신경 쓸 필요가 없어진다는 것이다. 컴파일러가 데이터 흐름을 분석해 무엇이 실제로 바뀌었는지 정확히 추적하므로, 사람이 의존성 배열을 빠뜨려서 생기는 stale closure 버그 자체가 사라진다.

## 핵심 개념 2: 전제 조건 — Rules of Hooks 준수가 필수

React Compiler는 마법이 아니라 정적 분석이다. 코드가 React의 규칙(훅은 최상위에서만 호출, 조건문 안에서 호출 금지, 순수 함수로 렌더링)을 지킨다는 전제 위에서 안전하게 최적화를 적용한다. 규칙을 위반하는 코드가 있으면 컴파일러는 해당 컴포넌트에 대한 최적화를 건너뛰고(bail out) 원래 동작대로 둔다.

`eslint-plugin-react-compiler`는 이 규칙 위반을 빌드 전에 잡아주는 역할을 한다. 컴파일러가 자동으로 최적화를 포기하는 상황을 사전에 알려주므로, 마이그레이션 과정에서 이 린트를 먼저 통과시키는 것이 중요한 첫 단계다.

## 핵심 개념 3: 수동 메모이제이션 vs 컴파일러 기반

| 구분 | 수동 useMemo/useCallback | React Compiler |
|---|---|---|
| 적용 주체 | 개발자가 판단해 직접 삽입 | 컴파일러가 정적 분석으로 자동 삽입 |
| 실수 가능성 | 의존성 배열 누락, 과도/과소 적용 | 규칙 준수 시 컴파일러가 일관되게 적용 |
| 코드 가독성 | 최적화 코드가 로직과 뒤섞임 | 로직만 작성, 최적화는 빌드 결과물에 존재 |
| 세밀한 제어 | 특정 값만 선택적으로 최적화 가능 | 컴파일러 판단에 위임(수동 오버라이드 가능) |
| 점진적 도입 | 필요 없음(기존 방식 그대로) | 디렉터리/컴포넌트 단위 opt-in 가능 |

## 실무 포인트

- **전면 전환보다 점진적 도입이 안전하다**: `babel-plugin-react-compiler` 설정에서 특정 디렉터리만 대상으로 지정하거나, 파일 상단에 `"use no memo"` 지시어로 개별 컴포넌트를 제외할 수 있다. 레거시 코드베이스에서는 신규 컴포넌트부터 적용하고 점차 넓혀가는 전략이 안전하다.
- **컴파일러가 만능은 아니다**: 여전히 프로파일링은 필요하다. 컴파일러는 "리렌더링 자체를 막는" 최적화를 자동화할 뿐, 알고리즘적으로 비효율적인 렌더 로직(예: 렌더 중 무거운 동기 계산)까지 고쳐주지는 않는다. React DevTools Profiler로 실제 병목을 확인하는 습관은 여전히 유효하다.
- **테스트에서 실제 렌더링 횟수를 검증하던 코드는 재점검이 필요하다**: 컴파일러 적용 전후로 리렌더링 발생 시점이 달라질 수 있어, "N번 렌더링됐는지"를 단정하는 테스트가 깨질 수 있다. 렌더링 횟수보다는 최종 결과와 부수효과 검증에 집중하는 테스트 스타일로 옮겨가는 것이 장기적으로 안전하다.

## 3줄 요약

- React Compiler는 컴포넌트 코드를 정적 분석해 `useMemo`/`useCallback`을 빌드 타임에 자동 삽입해, 의존성 배열 실수로 인한 버그 가능성을 구조적으로 없앤다.
- 이 최적화는 Rules of Hooks를 지키는 코드에만 안전하게 적용되므로 `eslint-plugin-react-compiler`로 규칙 위반을 먼저 걸러내는 것이 마이그레이션의 첫 단계다.
- 컴파일러 도입은 점진적으로(디렉터리/컴포넌트 단위 opt-in) 진행하고, 렌더링 횟수 자체보다는 실제 성능 프로파일링과 최종 동작 검증에 집중하는 것이 안전하다.

## 참고 자료

- [React 공식 문서: React Compiler](https://react.dev/learn/react-compiler)
- [React 공식 블로그: React Compiler 소개](https://react.dev/blog/2024/02/15/react-labs-what-we-have-been-working-on-february-2024)
- [eslint-plugin-react-compiler GitHub 저장소](https://github.com/facebook/react/tree/main/packages/eslint-plugin-react-compiler)
