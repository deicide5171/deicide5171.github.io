---
layout: single
title: "Vite 플러그인 직접 만들어보기"
date: 2026-08-15 22:30:00 +0530
categories: web-dev
tags: ["Vite", "플러그인개발", "Rollup", "빌드도구"]
toc: true
toc_sticky: true
excerpt: "Vite 플러그인 API의 주요 훅과 Rollup 호환성을 살펴보고 간단한 커스텀 변환 플러그인을 직접 만들어본다."
---

## 왜 지금 이 이야기인가

Vite는 이제 단순한 개발 서버를 넘어 대부분의 프런트엔드 프로젝트에서 기본 빌드 도구로 자리잡았다. 프레임워크 스타터, 컴포넌트 라이브러리, 심지어 백엔드 SSR 프로젝트까지 Vite 생태계 위에서 돌아가는 경우가 흔해졌다. 그런데 정작 "Vite 플러그인을 직접 만든다"는 주제는 상대적으로 덜 다뤄지는 편이다. 대부분 기존 플러그인을 가져다 쓰는 데 그치고, 내부 훅 구조까지 들여다볼 기회는 적기 때문이다.

하지만 사내 공통 컴포넌트를 자동 임포트하거나, 특정 파일 포맷을 커스텀 변환하거나, 빌드 시점에 메타데이터를 주입하는 등 조직 특화 요구사항은 결국 직접 플러그인을 작성해야 해결되는 경우가 많다. Vite 플러그인 API는 Rollup 플러그인 인터페이스를 확장한 구조라서, Rollup을 다뤄본 적이 없어도 몇 가지 핵심 훅만 이해하면 충분히 접근 가능하다.

## Vite 플러그인 API의 핵심 훅

| 훅 | 실행 시점 | 용도 |
|---|---|---|
| resolveId | 모듈 경로를 해석할 때 | 가상 모듈 생성, 경로 리다이렉트 |
| load | 모듈 소스 코드를 로드할 때 | 실제 파일이 아닌 콘텐츠를 동적으로 제공 |
| transform | 모듈 소스를 변환할 때 | 코드 변환, 주석 삽입, 커스텀 문법 처리 |
| configureServer | 개발 서버 생성 시 | 커스텀 미들웨어 추가 |
| config / configResolved | 설정 병합/확정 시 | 사용자 설정을 읽거나 수정 |

이 중 resolveId → load → transform은 Rollup의 빌드 파이프라인과 동일한 순서로 동작한다. Vite는 이 파이프라인을 개발 서버(dev server)와 프로덕션 빌드(rollup 기반) 양쪽에서 재사용하기 때문에, 하나의 플러그인이 dev/build 모드 모두에서 일관되게 동작하도록 설계할 수 있다는 게 큰 장점으로 언급된다.

## Rollup 플러그인과의 호환성

Vite 플러그인은 Rollup 플러그인 인터페이스의 상위 집합(superset)이다. 즉, 순수 Rollup 플러그인은 대부분 별도 수정 없이 Vite에서도 동작한다. 다만 Vite 전용 훅(configureServer, transformIndexHtml, handleHotUpdate 등)은 Rollup에는 존재하지 않으므로, 순수 Rollup 환경에서 재사용하려면 해당 훅을 조건부로 무시하도록 작성해야 한다. 반대로 개발 서버 전용 동작(HMR 처리 등)이 필요한 플러그인은 Vite에서만 의미가 있고 프로덕션 빌드(build) 단계에서는 적용되지 않도록 `apply: 'serve'` 또는 `apply: 'build'` 같은 조건을 명시하는 것이 일반적이다.

## 예제

```javascript
// 간단한 커스텀 변환 플러그인: 특정 매크로 문자열을 빌드 시점에 치환
export default function myMacroPlugin(options = {}) {
  const define = options.define || {};

  return {
    name: 'vite-plugin-simple-macro',

    // 특정 조건에서만 적용 (dev/build 모두)
    enforce: 'pre',

    transform(code, id) {
      // .js/.ts 파일에 한해서만 처리
      if (!/\.[jt]sx?$/.test(id)) return null;

      let transformed = code;
      let hasChanged = false;

      for (const [key, value] of Object.entries(define)) {
        const pattern = new RegExp(`__${key}__`, 'g');
        if (pattern.test(transformed)) {
          transformed = transformed.replace(pattern, JSON.stringify(value));
          hasChanged = true;
        }
      }

      if (!hasChanged) return null;

      return {
        code: transformed,
        map: null, // 실제로는 magic-string 등으로 소스맵 생성 권장
      };
    },
  };
}
```

```typescript
// vite.config.ts 에서 사용하는 방법
import { defineConfig } from 'vite';
import myMacroPlugin from './plugins/my-macro-plugin';

export default defineConfig({
  plugins: [
    myMacroPlugin({
      define: {
        BUILD_TIME: new Date().toISOString(),
        APP_VERSION: '1.0.0',
      },
    }),
  ],
});
```

## 실무 포인트와 주의사항

- transform 훅에서 조건 없이 모든 파일을 처리하면 빌드 속도가 크게 느려질 수 있으므로 파일 확장자/경로 필터링을 반드시 넣을 것
- 소스맵(sourcemap)을 누락하면 디버깅 시 원본 코드 위치를 찾기 어려워지므로 실제 배포용 플러그인에서는 magic-string 등으로 정확한 매핑을 생성할 것
- `enforce: 'pre' | 'post'` 옵션으로 다른 플러그인(예: 프레임워크 플러그인)보다 먼저/나중에 실행되도록 순서를 명시적으로 제어할 것
- dev 전용/build 전용 로직은 `apply` 옵션으로 분리해 불필요한 코드 경로 실행을 막을 것

## 3줄 요약

- Vite 플러그인은 resolveId, load, transform 같은 Rollup 호환 훅과 configureServer 같은 Vite 전용 훅으로 구성된다
- Rollup 플러그인 대부분은 Vite에서 그대로 재사용 가능하지만 그 반대는 항상 성립하지는 않는다
- 실무 플러그인 작성 시 파일 필터링, 소스맵, 실행 순서(enforce), 적용 범위(apply)를 신경 써야 한다

## 참고 자료

- [Vite 공식 문서 - Plugin API](https://vite.dev/guide/api-plugin.html)
- [Rollup 공식 문서 - Plugin Development](https://rollupjs.org/plugin-development/)
- [Vite 공식 문서 - Using Plugins](https://vite.dev/guide/using-plugins.html)
