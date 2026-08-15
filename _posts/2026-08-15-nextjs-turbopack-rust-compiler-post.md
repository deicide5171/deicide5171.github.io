---
layout: single
title: "Next.js 16.3, Turbopack과 Rust 기반 React Compiler는 어디까지 왔나"
date: 2026-08-15 14:30:00 +0530
categories: web-dev
tags: ["nextjs", "turbopack", "react-compiler", "rust", "frontend", "vite"]
toc: true
toc_sticky: true
excerpt: "Next.js 16.3 계열 업데이트에서 Turbopack 메모리 관리와 Rust 기반 React Compiler 지원이 어떻게 달라졌는지, 마이그레이션 체크리스트와 함께 정리한다."
---

## 왜 지금 Next.js 16.3인가

Next.js는 13번대부터 Turbopack을 실험적으로 얹기 시작해, 15번대에서 `next dev --turbo`를 기본값에 가깝게 끌어올렸고, 16번대에 들어서면서 빌드 파이프라인 전반을 Rust 툴체인으로 옮기는 작업을 이어가고 있다. 16.3 계열은 새 기능을 왕창 얹는 릴리스라기보다, 그동안 Turbopack으로 전환하며 쌓인 메모리·캐시·HMR 관련 이슈를 다듬는 성격이 강하다.

특히 대규모 모노레포나 컴포넌트 수가 많은 프로젝트에서 `next dev` 프로세스가 시간이 지날수록 메모리를 계속 점유하는 문제, 그리고 재시작할 때마다 캐시가 날아가 처음부터 컴파일하는 문제는 실무에서 체감이 컸던 부분이다. 16.3.1 등 후속 패치 릴리스들은 이런 세부 안정성 이슈를 잡는 데 집중되어 있다고 알려져 있다.

또 하나 눈에 띄는 변화는 React Compiler를 Babel 기반이 아니라 Rust 네이티브 구현으로 지원하는 흐름이다. 빌드 도구 자체가 Rust로 재작성되는 큰 그림 안에서, 컴파일러 통합도 같은 방향으로 맞춰지고 있는 셈이다. 이번 글에서는 이 변화들을 실무 관점에서 정리한다.

## 16.3의 핵심 변화 정리

| 영역 | 이전 방식 | 16.3 계열에서의 변화 |
|---|---|---|
| Turbopack 메모리 관리 | 장시간 dev 서버 구동 시 메모리 사용량이 계속 누적되는 경향 | 사용하지 않는 캐시 항목을 정리하는 eviction 로직 강화 |
| 빌드 캐시 | dev 서버 재시작 시 캐시가 초기화되는 경우가 잦음 | 디스크 기반 영속 캐시로 재시작 후에도 캐시 재사용 시도 |
| React Compiler 연동 | Babel 플러그인 경유 (`babel-plugin-react-compiler`) | Rust 네이티브 구현 경로 지원, 트랜스파일 오버헤드 감소 지향 |
| 모듈 탐색 방식 | 정적 import 위주 | Vite 생태계와 호환되는 `import.meta.glob` 스타일 지원 |
| next/image | 기존 최적화 파이프라인 | 캐시·리사이징 관련 세부 개선 (패치 릴리스 단위로 지속 반영) |

이 중 실무 임팩트가 가장 큰 것은 역시 **Turbopack 메모리 eviction**과 **영속 빌드 캐시** 두 가지다. 둘 다 신규 기능이라기보다는 "느껴지던 불편함을 줄이는" 성격이라, 별도 설정 변경 없이 업그레이드만으로 체감 개선을 기대할 수 있는 부분으로 보인다. 다만 정확한 개선 폭은 프로젝트 규모와 캐시 히트율에 따라 달라질 수 있어, 수치로 단정하기보다는 직접 프로파일링해보는 편이 안전하다.

## Rust 기반 React Compiler 지원

기존에는 React Compiler를 쓰려면 Babel 플러그인(`babel-plugin-react-compiler`)을 거쳐야 했다. Babel 기반 트랜스파일은 AST 순회와 변환 과정에서 빌드 시간에 영향을 주는데, Turbopack이 Rust로 전환되면서 이 컴파일러 단계도 Rust 네이티브 경로로 처리할 수 있게 하는 방향이 이번 업데이트에서 함께 다뤄지고 있다.

설정 자체는 크게 복잡하지 않다. `next.config`에서 실험적 플래그로 컴파일러를 켜는 기존 방식은 유지되되, 내부적으로 Turbopack이 이를 처리하는 경로가 바뀌는 쪽에 가깝다.

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    reactCompiler: true,
  },
};

export default nextConfig;
```

Vite 호환 `import.meta.glob` 지원도 함께 언급되는 변화다. 여러 파일을 패턴 매칭으로 한 번에 불러오는 패턴은 Vite 생태계에서 익숙한 방식인데, Turbopack이 이를 지원하면서 Vite에서 Next.js로(또는 그 반대로) 옮겨오는 프로젝트의 마이그레이션 장벽이 다소 낮아질 것으로 보인다.

```ts
// Vite 스타일 glob import 예시 (라우트/모듈 자동 등록 등에 사용)
const modules = import.meta.glob("./pages/**/*.tsx");

for (const path in modules) {
  console.log(path); // 예: "./pages/about.tsx"
}
```

## 실무 포인트와 마이그레이션 체크리스트

- **먼저 dev 서버로만 검증**: Turbopack 메모리 관리 개선은 `next dev` 환경에서 체감 효과가 크므로, 프로덕션 빌드보다 로컬 개발 워크플로에서 먼저 변화를 확인하는 것이 좋다.
- **캐시 디렉토리 용량 모니터링**: 영속 빌드 캐시가 디스크에 쌓이는 구조이므로, CI 환경이나 컨테이너 이미지 빌드에서는 캐시 디렉토리 크기와 정리 정책을 함께 점검해야 한다.
- **React Compiler를 이미 쓰고 있다면 회귀 테스트 우선**: Babel 경로에서 Rust 네이티브 경로로 내부 처리 방식이 바뀌는 지점이므로, 컴파일러가 적용되는 컴포넌트들의 렌더링 결과·성능을 업그레이드 전후로 비교해보는 것이 안전하다.
- **패치 버전 고정 후 단계적 업그레이드**: 16.3 계열은 마이너 내 패치 릴리스(16.3.x)가 이어지는 시기이므로, 프로덕션 브랜치는 특정 패치 버전에 고정하고 개발 브랜치에서 먼저 최신 패치를 검증하는 방식이 무난하다.
- **커스텀 webpack 설정 의존도 재확인**: Turbopack으로의 전환이 계속 진행 중인 만큼, 커스텀 webpack 플러그인이나 loader에 강하게 의존하는 프로젝트는 Turbopack 전환 로드맵과의 호환 여부를 별도로 확인할 필요가 있다.
- **구체적 수치는 직접 측정**: 공식 발표에서 언급되는 메모리 절감률이나 빌드 시간 단축 폭은 벤치마크 환경에 따라 달라질 수 있으므로, 각자의 프로젝트에서 업그레이드 전후 지표를 직접 재보는 것을 권장한다.

## 3줄 요약

- Next.js 16.3 계열은 Turbopack의 메모리 eviction과 영속 빌드 캐시로 dev 서버 안정성을 다듬는 데 초점을 둔 업데이트다.
- React Compiler를 Rust 네이티브 경로로 지원하고 Vite 호환 `import.meta.glob`을 도입해, 빌드 성능과 생태계 호환성을 함께 넓히려 하고 있다.
- 실무에서는 캐시 디렉토리 관리, 패치 버전 고정, React Compiler 회귀 테스트를 체크리스트 삼아 단계적으로 업그레이드하는 것이 안전하다.

## 참고 자료

- [Next.js 공식 블로그](https://nextjs.org/blog)
- [Next.js Releases (GitHub)](https://github.com/vercel/next.js/releases)
- [Turbopack 공식 문서](https://nextjs.org/docs/app/api-reference/turbopack)
- [React Compiler 문서](https://react.dev/learn/react-compiler)
