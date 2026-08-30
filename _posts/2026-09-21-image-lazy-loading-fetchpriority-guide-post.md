---
layout: single
title: "이미지 lazy loading만으로 충분할까 — fetchpriority와 함께 쓰는 법"
date: 2026-09-21 13:30:00 +0530
categories: frontend
tags: ["lazyloading", "fetchpriority", "웹성능", "corewebvitals", "lcp최적화"]
toc: true
toc_sticky: true
excerpt: "모든 이미지에 loading=lazy를 붙였더니 오히려 LCP 점수가 떨어지는 이유와, fetchpriority 속성으로 히어로 이미지 로딩을 우선시켜 실제 체감 속도를 개선하는 방법을 정리했다."
---

## 왜 lazy loading을 다 붙였는데 점수가 떨어지나

이미지 로딩 최적화를 처음 접하면 "화면 밖 이미지는 늦게 불러오면 되니까 `loading="lazy"`를 모든 `<img>`에 붙이자"는 결론에 쉽게 도달한다. 실제로 많은 이미지가 있는 페이지에서 스크롤 하단의 이미지들에는 이 방식이 초기 로딩 시간을 확실히 줄여준다. 그런데 페이지 최상단, 스크롤 없이 바로 보이는 히어로 이미지(hero image)에까지 `loading="lazy"`를 붙이면 오히려 역효과가 난다.

`loading="lazy"`는 브라우저가 "이 이미지는 뷰포트 안에 들어올 때까지 로딩을 미뤄도 된다"고 해석하게 만든다. 그런데 히어로 이미지는 처음부터 뷰포트 안에 있으므로, 이 속성이 붙어 있어도 즉시 로딩을 시작하긴 한다. 문제는 브라우저가 이 이미지를 "당장 중요한 리소스"로 우선순위를 높게 매기지 않는다는 점이다. Core Web Vitals의 **LCP(Largest Contentful Paint)** 지표는 대개 이 히어로 이미지가 화면에 그려지는 시점을 기준으로 측정되는데, 우선순위가 낮게 잡히면 다른 스크립트나 CSS 요청과 경쟁하느라 LCP가 오히려 늦어진다.

## 잘못된 접근: 모든 이미지에 같은 속성을 일괄 적용

```html
<!-- 모든 이미지에 무조건 lazy 적용 -->
<img src="hero-banner.jpg" loading="lazy" alt="메인 배너">
<img src="product-1.jpg" loading="lazy" alt="상품1">
<img src="product-2.jpg" loading="lazy" alt="상품2">
```

이렇게 일괄 적용하면 스크롤 하단 이미지는 이득을 보지만, 정작 사용자가 페이지에 진입하자마자 보게 되는 히어로 이미지의 로딩 우선순위가 낮아져 첫 화면이 그려지는 체감 속도가 늦어진다. "이미지는 다 늦게 불러오는 게 좋다"는 단순화가 낳는 전형적인 함정이다.

## 올바른 접근: 뷰포트 안/밖을 구분해서 다르게 처리한다

```html
<!-- 뷰포트 안(above the fold) 히어로 이미지 -->
<img src="hero-banner.jpg"
     fetchpriority="high"
     loading="eager"
     alt="메인 배너">

<!-- 스크롤 하단(below the fold) 상품 이미지 -->
<img src="product-1.jpg"
     loading="lazy"
     alt="상품1">
```

핵심 원칙은 단순하다. **처음부터 보이는 이미지는 최대한 빨리, 스크롤해야 보이는 이미지는 늦게 불러오게 한다.** `fetchpriority="high"`는 브라우저의 리소스 로딩 우선순위 큐에서 이 이미지를 앞자리로 올려, 같은 시점에 요청되는 다른 리소스보다 먼저 다운로드되게 한다. `loading="eager"`(기본값)와 함께 쓰면 지연 없이 즉시 요청을 시작하면서도 우선순위까지 높게 유지된다.

## 세 가지 속성의 역할 정리

| 속성 | 역할 | 히어로 이미지 | 하단 이미지 |
|---|---|---|---|
| `loading` | 로딩 시점(즉시 vs 뷰포트 진입 시) | `eager` 또는 생략 | `lazy` |
| `fetchpriority` | 같은 시점 요청 중 우선순위 | `high` | `low` 또는 생략 |
| `decoding` | 이미지 디코딩을 렌더링과 동기/비동기로 | `sync` 고려 | `async` |

세 속성은 서로 다른 축을 조정한다는 점이 중요하다. `loading`은 "언제 요청을 시작할지", `fetchpriority`는 "동시에 여러 요청이 있을 때 어떤 걸 먼저 처리할지"를 결정한다. 히어로 이미지에 `loading="lazy"`를 실수로 남겨두면 `fetchpriority="high"`를 함께 줘도 애초에 로딩 시작 자체가 지연될 수 있으므로 두 속성을 함께 점검해야 한다.

## 실무 포인트

- **LCP 후보 이미지를 사전에 `<link rel="preload">`로 예고하는 방법도 함께 검토하라.** `fetchpriority="high"`가 요청 우선순위를 높이는 것이라면, `preload`는 아예 HTML 파싱 초기 단계에서 리소스 존재를 브라우저에 미리 알려 더 이른 시점에 다운로드를 시작하게 한다. 두 기법은 함께 쓸 수 있다.
- **`fetchpriority`를 남용하지 마라.** 페이지의 모든 이미지에 `high`를 붙이면 우선순위 큐 자체가 무의미해진다. 진짜 LCP 후보가 되는 이미지 1~2개에만 적용하는 것이 원칙이다.
- **CSS `background-image`로 넣은 히어로 이미지는 이 속성들의 혜택을 받지 못한다.** `<img>` 태그로 마크업해야 `loading`, `fetchpriority` 속성을 브라우저가 인식하고 우선순위 조정에 반영한다.
- **실제 개선 여부는 Lighthouse나 CrUX 데이터로 검증하라.** 속성을 붙였다고 항상 개선되는 것은 아니며, 네트워크 환경과 다른 리소스 경쟁 상황에 따라 효과가 달라질 수 있다.

## 마무리 요약

- `loading="lazy"`를 히어로 이미지에까지 일괄 적용하면 LCP가 오히려 늦어질 수 있다.
- 뷰포트 안 이미지는 `fetchpriority="high"` + `loading="eager"`, 뷰포트 밖 이미지는 `loading="lazy"`로 구분해서 처리하는 것이 원칙이다.
- `preload`와의 조합, `background-image` 방식의 한계, Lighthouse 검증까지 함께 챙겨야 실제 체감 속도 개선으로 이어진다.

## 참고 자료

- [MDN - fetchpriority](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/fetchpriority)
- [web.dev - Optimize LCP](https://web.dev/articles/optimize-lcp)
