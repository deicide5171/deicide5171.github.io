---
layout: single
title: "React Compiler 1.0, 이제 useMemo는 그만 써도 될까"
date: 2026-08-15 12:00:00 +0900
categories: web-dev
tags: ["react", "react-compiler", "frontend", "performance", "javascript"]
toc: true
toc_sticky: true
excerpt: "React 팀이 공식 배포한 React Compiler가 안정 버전에 접어들며 수동 메모이제이션 시대가 저물고 있다. 동작 원리와 도입 방법, 주의점을 정리한다."
---

## 왜 지금 React Compiler인가

React로 성능 튜닝을 해본 사람이라면 `useMemo`, `useCallback`, `React.memo`를 얼마나 조심스럽게 다뤄야 하는지 안다. 의존성 배열 하나를 빼먹으면 최적화가 무력화되거나, 오히려 오래된 값을 참조하는 버그가 생긴다. 이 수동 메모이제이션은 지난 몇 년간 React 코드베이스에서 가장 반복적이고 실수하기 쉬운 작업이었다.

React 팀은 이 문제를 언어 차원에서 해결하는 대신 컴파일러 차원에서 해결하는 길을 택했다. 빌드 시점에 컴포넌트와 훅의 코드를 분석해 불필요한 재렌더링을 자동으로 막아주는 **React Compiler**가 그 결과물이다. 안정 버전이 나온 이후 Vite, Next.js, Expo 같은 주요 빌드 도구·프레임워크와의 통합이 이어지며 실무 도입 사례가 빠르게 늘고 있다.

수동 최적화가 표준이던 시대에서 "그냥 평범하게 짜도 빠른" 시대로 넘어가는 전환점이라는 점에서, 지금 짚어볼 가치가 있는 주제다.

## React Compiler는 무엇을 자동화하는가

기존에는 개발자가 직접 "이 값은 재계산할 필요 없다", "이 함수는 재생성할 필요 없다"를 판단해서 `useMemo`/`useCallback`으로 표시해야 했다. React Compiler는 이 판단을 컴파일 타임에 정적 분석으로 대신 수행한다.

| 항목 | 기존 방식 | React Compiler 도입 후 |
|---|---|---|
| 메모이제이션 | 개발자가 수동으로 `useMemo`/`useCallback` 작성 | 컴파일러가 자동 삽입 |
| 실수 위험 | 의존성 배열 누락, 과도한 메모이제이션 | 정적 분석 기반이라 누락 없음 |
| 코드 가독성 | 최적화 코드가 로직과 뒤섞임 | 로직만 남아 가독성 향상 |
| 전제 조건 | 없음 | 컴포넌트가 "Rules of React"를 준수해야 함 |

핵심은 컴파일러가 컴포넌트 함수와 훅의 순수성, 데이터 흐름을 분석해서 "이 값은 입력이 바뀌지 않으면 다시 계산할 필요가 없다"는 지점을 스스로 찾아낸다는 점이다. 개발자는 로직만 작성하면 되고, 최적화는 빌드 파이프라인이 맡는다.

단, 전제 조건이 있다. 컴포넌트가 렌더링 중 부수효과를 일으키거나 훅 규칙을 어기면 컴파일러가 최적화를 건너뛰거나 잘못된 가정을 할 수 있다. 그래서 `eslint-plugin-react-hooks`의 컴파일러 연동 린트 규칙을 함께 켜서, 위반 지점을 빌드 전에 잡아내는 것이 권장된다.

## 코드로 보는 차이

기존에는 리스트 필터링처럼 비용이 있는 계산을 이렇게 감쌌다.

```jsx
// Before: 수동 메모이제이션
function ProductList({ products, keyword }) {
  const filtered = useMemo(
    () => products.filter((p) => p.name.includes(keyword)),
    [products, keyword]
  );

  const handleSelect = useCallback(
    (id) => console.log("selected", id),
    []
  );

  return filtered.map((p) => (
    <ProductRow key={p.id} product={p} onSelect={handleSelect} />
  ));
}
```

React Compiler를 적용하면 같은 로직을 최적화 코드 없이 작성해도 컴파일러가 동일한 효과를 자동으로 만들어낸다.

```jsx
// After: React Compiler가 자동 최적화
function ProductList({ products, keyword }) {
  const filtered = products.filter((p) => p.name.includes(keyword));

  const handleSelect = (id) => console.log("selected", id);

  return filtered.map((p) => (
    <ProductRow key={p.id} product={p} onSelect={handleSelect} />
  ));
}
```

빌드 설정은 번들러 플러그인 형태로 추가한다(Vite 예시).

```js
// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [["babel-plugin-react-compiler", {}]],
      },
    }),
  ],
});
```

## 실무 적용 포인트와 주의사항

- **점진 도입이 기본 전제**: 한 번에 전체 코드베이스를 컴파일러 대상으로 돌리기보다, 디렉토리 단위로 opt-in하며 린트 경고를 먼저 해소하는 방식이 안전하다.
- **기존 useMemo/useCallback을 당장 지울 필요는 없다**: 컴파일러는 기존 메모이제이션 코드와 공존 가능하다. 신규 코드부터 자연스러운 스타일로 작성하고, 기존 코드는 점검하며 정리해도 된다.
- **"Rules of React" 준수가 핵심 전제조건**: 렌더링 중 외부 상태를 직접 변경하거나 훅을 조건부로 호출하는 패턴이 있으면 컴파일러 최적화가 제대로 동작하지 않는다. 린트 규칙으로 먼저 검증하자.
- **React Native에도 동일하게 적용된다**: 웹 전용 기능이 아니므로, 모바일 코드베이스에서도 같은 이점을 기대할 수 있다.
- **측정 없이 맹신하지 말 것**: 실제 성능 개선 폭은 컴포넌트 구조와 데이터 크기에 따라 다르다. 도입 전후로 프로파일링해서 실제 효과를 확인하는 습관은 여전히 유효하다.

## 마무리

- React Compiler는 수동 `useMemo`/`useCallback` 없이도 빌드 타임 정적 분석으로 불필요한 재렌더링을 제거해준다.
- 도입 전제조건은 "Rules of React" 준수이며, 관련 린트 규칙으로 위반 지점을 먼저 잡는 것이 안전한 도입 경로다.
- 기존 메모이제이션 코드와 공존 가능하므로 전체 재작성 없이 점진적으로 옮겨갈 수 있다.

## 참고 자료

- [React Compiler 공식 블로그](https://react.dev/blog/2025/10/07/react-compiler-1)
- [React Compiler 문서](https://react.dev/learn/react-compiler)
- [react-compiler-runtime / babel-plugin-react-compiler (GitHub)](https://github.com/facebook/react/tree/main/compiler)
