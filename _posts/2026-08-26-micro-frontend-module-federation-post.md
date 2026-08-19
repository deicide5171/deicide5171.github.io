---
layout: single
title: "한 팀의 배포가 다른 팀의 화면을 깨뜨릴 때 — 마이크로 프런트엔드와 Module Federation"
date: 2026-08-26 13:30:00 +0530
categories: frontend
tags: ["frontend", "micro-frontend", "module-federation", "webpack", "vite", "architecture"]
toc: true
toc_sticky: true
excerpt: "여러 팀이 하나의 프런트엔드 코드베이스를 공유하다 배포가 서로를 막는 상황을, Module Federation으로 런타임에 독립 배포되는 마이크로 프런트엔드로 분리하는 실전 구성을 정리한다."
---

백엔드를 마이크로서비스로 쪼갠 조직에서도 프런트엔드는 여전히 하나의 거대한 SPA로 남아있는 경우가 흔하다. 팀은 여러 개인데 배포할 프런트엔드 저장소는 하나이므로, A팀이 배포를 준비하는 동안 B팀의 변경사항이 같은 빌드에 섞여 들어가고, 한 팀의 버그가 전체 애플리케이션의 배포를 막는다. 백엔드에서 이미 겪었던 "모놀리스가 조직 확장을 막는다"는 문제가 프런트엔드에서 그대로 재현되는 것이다.

마이크로 프런트엔드는 이 문제를 프런트엔드 애플리케이션을 여러 개의 독립 배포 단위로 쪼개는 방식으로 접근한다. 여러 구현 방식이 있지만, 그중 Webpack 5(및 Vite의 대응 플러그인)가 제공하는 **Module Federation**은 런타임에 서로 다른 출처에서 빌드된 JS 번들을 동적으로 로드해 하나의 애플리케이션처럼 조합하는 방식으로 가장 널리 쓰인다. 이 글에서는 Module Federation의 핵심 개념과, 실무에서 이 구조를 도입할 때 마주치는 트레이드오프를 정리한다.

## 핵심 개념 1: 호스트와 리모트, 그리고 공유 의존성

Module Federation은 애플리케이션을 **호스트(host)**와 **리모트(remote)**로 나눈다. 호스트는 사용자가 처음 접속하는 셸 애플리케이션이고, 리모트는 호스트가 런타임에 동적으로 불러오는 독립 배포된 모듈이다. 각 리모트는 자신만의 저장소, 빌드 파이프라인, 배포 주기를 가지며, 호스트는 리모트의 소스 코드를 빌드 시점에 알 필요 없이 URL만으로 참조한다.

| 개념 | 역할 |
|---|---|
| 호스트(host) | 셸 애플리케이션, 여러 리모트를 조합해 화면을 구성 |
| 리모트(remote) | 독립적으로 빌드·배포되는 기능 단위(예: 결제 위젯, 상품 상세) |
| `exposes` | 리모트가 외부에 공개하는 모듈 목록 |
| `remotes` | 호스트가 참조할 리모트의 진입점 URL |
| `shared` | React, React-DOM처럼 중복 로드를 피할 공통 의존성 |

`shared` 설정이 실무에서 가장 까다로운 부분이다. 호스트와 모든 리모트가 React를 각자 번들에 포함하면 사용자는 같은 라이브러리를 여러 번 다운로드하게 되고, 버전이 다르면 하나의 페이지에 React 인스턴스가 두 개 존재해 훅 관련 오류가 발생한다. `shared`로 지정하면 런타임에 이미 로드된 버전을 재사용하되, 버전 충돌 시의 동작(singleton 강제 여부, 버전 범위)을 명시적으로 정해야 한다.

## 예제: 호스트와 리모트의 Webpack 설정

```javascript
// remote(상품-상세 팀)의 webpack.config.js
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'productDetail',
      filename: 'remoteEntry.js',
      exposes: {
        './ProductDetail': './src/ProductDetail.jsx',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
      },
    }),
  ],
};
```

```javascript
// host(셸 애플리케이션)의 webpack.config.js
new ModuleFederationPlugin({
  name: 'shell',
  remotes: {
    // 리모트 팀이 배포한 빌드의 URL — 호스트는 이 팀의 소스를 몰라도 된다
    productDetail: 'productDetail@https://cdn.example.com/product-detail/remoteEntry.js',
  },
  shared: {
    react: { singleton: true, requiredVersion: '^18.0.0' },
    'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
  },
});
```

```javascript
// host 코드에서 리모트 모듈을 동적으로 불러와 사용
import { lazy, Suspense } from 'react';

const ProductDetail = lazy(() => import('productDetail/ProductDetail'));

function ProductPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <ProductDetail />
    </Suspense>
  );
}
```

`productDetail` 팀이 자신의 저장소에서 독립적으로 빌드·배포해 `remoteEntry.js`를 CDN에 올리면, 호스트는 재배포 없이 다음 페이지 요청부터 최신 버전을 자동으로 불러온다. 이것이 마이크로 프런트엔드가 해결하려는 핵심 문제 — 팀 간 배포 독립성 — 이다.

## 실무 포인트

- **공유 의존성 버전 정책을 조직 차원에서 정한다**: 팀마다 React 버전이 제각각이면 `singleton: true`로 강제해도 버전 범위를 벗어나는 리모트가 로드에 실패하거나 경고를 낸다. 메이저 버전 업그레이드는 모든 리모트 팀이 조율된 일정으로 진행해야 하며, 이 조율 비용이 마이크로 프런트엔드 도입의 숨은 비용이다.
- **런타임 통합은 성능 비용을 수반한다**: 여러 리모트를 동적으로 로드하는 구조는 번들 하나를 미리 최적화해 서빙하는 단일 SPA보다 초기 로드에 네트워크 왕복이 늘어난다. 리모트 로딩을 라우트 단위로 지연시키고, 핵심 경로의 리모트는 프리페치하는 전략이 필요하다.
- **팀 경계와 화면 경계를 일치시킨다**: 마이크로 프런트엔드는 조직 구조(Conway의 법칙)를 반영한 분리여야 효과가 있다. 화면 하나에 여러 팀의 리모트가 촘촘히 얽혀 있으면 오히려 통합 테스트와 디버깅이 단일 SPA보다 복잡해진다. 팀 소유 경계가 명확한 기능 단위(체크아웃, 상품 상세 등)부터 분리하는 것이 안전하다.

## 3줄 요약

- 여러 팀이 하나의 프런트엔드 저장소를 공유하면 배포가 서로를 막는 병목이 생기며, 마이크로 프런트엔드는 이를 독립 배포 단위로 쪼개 해결한다.
- Module Federation은 호스트가 런타임에 리모트의 번들을 동적으로 불러오는 방식이며, `shared` 설정으로 React 같은 공통 의존성의 중복 로드와 버전 충돌을 관리해야 한다.
- 공유 의존성 버전 조율, 런타임 로딩 성능, 팀-화면 경계 일치라는 세 가지 트레이드오프를 감안하지 않으면 도입 효과보다 복잡도 증가가 더 클 수 있다.

## 참고 자료

- [Webpack 공식 문서: Module Federation](https://webpack.js.org/concepts/module-federation/)
- [Module Federation 공식 사이트: Module Federation 2.0](https://module-federation.io/)
- [Martin Fowler: Micro Frontends](https://martinfowler.com/articles/micro-frontends.html)
