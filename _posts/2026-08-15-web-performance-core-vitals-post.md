---
layout: single
title: "웹 성능 최적화 실전 — Core Web Vitals 2026"
date: 2026-08-15 23:30:00 +0530
categories: web-dev
tags: ["CoreWebVitals", "웹성능최적화", "Lighthouse", "LCP"]
toc: true
toc_sticky: true
excerpt: "LCP·INP·CLS 세 지표를 중심으로 Core Web Vitals를 측정하는 도구와 실전 최적화 기법을 정리한다."
---

## 왜 지금 이 이야기인가

검색 노출과 사용자 경험 모두에 영향을 주는 Core Web Vitals는 몇 년째 프론트엔드 성능 최적화의 기준점 역할을 하고 있다. 특히 2024년에 FID(First Input Delay)가 INP(Interaction to Next Paint)로 교체된 이후, "첫 입력 반응 속도"뿐 아니라 "페이지 생애 전체에 걸친 상호작용 반응성"을 측정하게 되면서 최적화해야 할 지점도 달라졌다. 2026년 현재 이 세 지표(LCP, INP, CLS)는 여전히 Core Web Vitals의 핵심으로 유지되고 있는 것으로 보인다.

문제는 많은 팀이 "Lighthouse 점수를 90점 이상으로 맞춘다"는 식의 표면적 목표에만 집중하다가, 실제 사용자 환경(필드 데이터)과 실험실 환경(랩 데이터)의 차이를 놓치는 경우가 많다는 점이다. 이 글에서는 세 핵심 지표, 측정 도구의 차이, 그리고 실전에서 바로 적용할 수 있는 최적화 기법을 정리한다.

## Core Web Vitals 핵심 지표

| 지표 | 의미 | 좋음 기준(권장) |
|---|---|---|
| LCP (Largest Contentful Paint) | 화면에서 가장 큰 콘텐츠 요소가 렌더링되는 시점 | 2.5초 이하 |
| INP (Interaction to Next Paint) | 사용자 상호작용부터 다음 화면 갱신까지 걸리는 시간(페이지 전체 상호작용 기준) | 200ms 이하 |
| CLS (Cumulative Layout Shift) | 예기치 않은 레이아웃 이동의 누적 정도 | 0.1 이하 |

이 기준값은 Google이 공개한 권장치를 따른 것으로, 실제 순위 반영 방식이나 가중치는 시기에 따라 조정될 수 있어 공식 문서를 주기적으로 확인하는 것이 안전하다.

## 측정 도구: 랩 데이터 vs 필드 데이터

| 도구 | 데이터 성격 | 특징 |
|---|---|---|
| Lighthouse | 랩(Lab) 데이터 | 로컬/CI에서 시뮬레이션 환경으로 즉시 측정 가능, 네트워크·기기 조건은 고정값 |
| PageSpeed Insights | 랩 + 필드 데이터 | Lighthouse 결과와 함께 실제 사용자 CrUX 데이터를 같이 보여줌 |
| CrUX (Chrome UX Report) | 필드(Field) 데이터 | 실제 크롬 사용자들의 익명화된 성능 데이터를 집계 |

랩 데이터는 재현 가능하고 디버깅에 유용하지만 실제 사용자 환경(느린 네트워크, 저사양 기기 등)을 완전히 반영하지 못한다. 반대로 필드 데이터는 실제 사용자 경험을 보여주지만 "왜 느린지"를 바로 알려주지 않는다. 따라서 두 데이터를 함께 봐야 정확한 진단이 가능하다.

## 실전 최적화 기법

- **이미지 최적화**: 다음 세대 포맷(WebP, AVIF) 사용, 반응형 이미지(`srcset`), `loading="lazy"`로 뷰포트 밖 이미지 지연 로딩.
- **LCP 요소 프리로드**: 가장 큰 콘텐츠 요소가 이미지나 폰트라면 `<link rel="preload">`로 우선순위를 높인다.
- **코드 스플리팅**: 라우트/컴포넌트 단위로 번들을 쪼개 초기 JS 실행 비용을 줄여 INP 개선에 기여한다.
- **레이아웃 이동 방지**: 이미지/광고 슬롯에 명시적 width/height 또는 `aspect-ratio`를 지정해 CLS를 줄인다.
- **긴 태스크 분할**: 메인 스레드를 오래 점유하는 JS 작업을 `requestIdleCallback`이나 작은 단위로 쪼개 INP를 개선한다.

## 예제

이미지 지연 로딩과 LCP 이미지 프리로드 예시:

```html
<head>
  <link rel="preload" as="image" href="/hero.avif" fetchpriority="high">
</head>
<body>
  <img src="/hero.avif" alt="히어로 이미지" width="1200" height="600">
  <img src="/below-fold.jpg" alt="아래쪽 이미지" loading="lazy" width="800" height="400">
</body>
```

레이아웃 이동을 방지하기 위한 CSS 예시:

```css
.thumbnail {
  aspect-ratio: 16 / 9;
  width: 100%;
  height: auto;
}
```

## 실무 포인트와 주의사항

- Lighthouse 점수만 보고 최적화를 끝냈다고 판단하지 말고, 실제 CrUX 필드 데이터로 검증해야 한다.
- 지표 개선 작업은 상위 25% 사용자 기준이 아니라 75번째 백분위수 등 실제 평가 기준에 맞춰 목표를 잡아야 한다.
- 서드파티 스크립트(광고, 분석 도구 등)가 INP와 LCP를 크게 악화시키는 경우가 많으므로 우선 점검 대상에 포함해야 한다.
- 성능 예산(performance budget)을 CI에 넣어 회귀를 자동으로 감지하는 체계를 만드는 것이 장기적으로 효과적이다.

## 3줄 요약

- Core Web Vitals는 LCP, INP, CLS 세 지표로 구성되며 각각 로딩·반응성·시각적 안정성을 나타낸다.
- Lighthouse는 랩 데이터, CrUX는 필드 데이터를 제공하므로 두 데이터를 함께 봐야 정확히 진단할 수 있다.
- 이미지 최적화, 코드 스플리팅, 프리로드, 레이아웃 이동 방지가 실전에서 바로 적용 가능한 핵심 기법이다.

## 참고 자료

- [Web Vitals — web.dev](https://web.dev/articles/vitals)
- [Lighthouse 공식 문서 — Chrome for Developers](https://developer.chrome.com/docs/lighthouse/overview)
- [Chrome UX Report(CrUX) 공식 문서](https://developer.chrome.com/docs/crux)
