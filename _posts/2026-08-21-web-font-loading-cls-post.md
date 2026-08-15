---
layout: single
title: "웹폰트 로딩과 CLS — font-display와 size-adjust로 레이아웃 흔들림 잡기"
date: 2026-08-21 12:30:00 +0530
categories: frontend
tags: ["font-display", "size-adjust", "웹폰트최적화", "cls", "웹폰트"]
toc: true
toc_sticky: true
excerpt: "커스텀 웹폰트가 늦게 도착할 때 텍스트 박스 크기가 바뀌며 생기는 CLS를, font-display 전략과 size-adjust 계열 폰트 메트릭 오버라이드로 잡는 방법을 정리한다."
---

## 왜 지금 폰트 로딩을 다시 봐야 하는가

Core Web Vitals 최적화 글에서는 보통 이미지·광고 슬롯의 `width`/`height`나 `aspect-ratio` 지정을 CLS(Cumulative Layout Shift) 해법으로 꼽는다. 그런데 실제 필드 데이터를 뜯어보면 CLS의 상당 부분이 이미지가 아니라 **커스텀 웹폰트가 늦게 로드되면서 글자 박스 크기가 바뀌는 순간**에서 발생한다. 폴백 시스템 폰트로 먼저 그린 텍스트가 웹폰트로 교체되는 순간, 글자 폭·줄바꿈 위치·문단 높이가 달라지고 그 아래 콘텐츠가 밀린다.

이 문제는 이미지처럼 `width`/`height`를 미리 지정하는 방식으로는 해결되지 않는다. 텍스트 박스의 크기는 폰트의 메트릭(글자 폭, 상단/하단 여백)에 좌우되기 때문에, 폰트 자체의 로딩 전략과 메트릭 조정이 필요하다. 이 글에서는 `font-display`의 각 값이 실제로 무엇을 하는지, 그리고 최근 브라우저가 지원하는 `size-adjust` 계열 `@font-face` 디스크립터로 폴백 폰트와 웹폰트의 박스 크기를 미리 맞추는 방법을 정리한다.

## 핵심 개념 1: FOIT·FOUT·FOFT — 폰트가 늦게 도착할 때 브라우저의 선택지

웹폰트가 아직 도착하지 않은 짧은 시간 동안 브라우저가 텍스트를 어떻게 그릴지는 세 가지 갈래로 나뉜다.

| 전략 | 의미 | 사용자 체감 | CLS 영향 |
|---|---|---|---|
| FOIT (Flash of Invisible Text) | 폰트 도착 전까지 텍스트를 아예 안 그림 | 텍스트가 안 보이는 공백 구간 발생 | 스왑 시점에 발생(단, 텍스트 자체가 늦게 나타남) |
| FOUT (Flash of Unstyled Text) | 폴백 폰트로 즉시 그린 뒤 웹폰트로 교체 | 텍스트는 바로 보이지만 폰트가 바뀌는 깜빡임 | 폴백-웹폰트 박스 크기 차이만큼 발생 가능 |
| FOFT (Flash of Faux Text) | 웹폰트의 굵기·스타일 없는 축약 버전을 먼저 쓰고 이후 전체 교체 | FOUT과 유사하되 스타일 전환 단계가 추가 | FOUT과 동일한 원인으로 발생 가능 |

세 전략 모두 "폰트가 바뀌는 순간"이 존재하는 한 CLS 위험은 남아 있다. 결국 관건은 그 전환 시점의 박스 크기 차이를 얼마나 줄이느냐다.

## 핵심 개념 2: font-display 값별 동작

`@font-face`의 `font-display` 속성은 폰트 로딩 중 브라우저가 텍스트를 어떻게 처리할지 지정한다.

| 값 | 블록 구간(텍스트 숨김) | 스왑 구간(폴백→웹폰트 교체 허용) | 특징 |
|---|---|---|---|
| `auto` | 브라우저 기본 정책 따름 | 브라우저 기본 정책 따름 | 브라우저마다 동작이 다를 수 있어 명시적 지정 권장 |
| `block` | 짧게 존재(대체로 수백 ms 이내) | 매우 김(사실상 무제한에 가까움) | 아이콘 폰트처럼 폰트가 없으면 의미가 깨지는 경우에 적합, FOIT 유발 |
| `swap` | 사실상 없음(0에 가까움) | 매우 김 | 즉시 텍스트 표시, FOUT 유발 — 가장 흔히 쓰이는 값 |
| `fallback` | 매우 짧음 | 짧음(일정 시간 후 폰트가 안 오면 폴백 유지) | 텍스트 노출과 안정성의 절충 |
| `optional` | 매우 짧음 | 거의 없음(네트워크 상황에 따라 웹폰트를 아예 포기) | 느린 네트워크에서 CLS를 가장 적극적으로 회피 |

수치는 브라우저·스펙 버전에 따라 조정될 수 있어 정확한 구간 길이는 단정하지 않는다. 다만 방향성은 명확하다. `block`은 텍스트를 늦게라도 원래 폰트로 보여주는 데, `optional`은 애초에 흔들림 자체를 없애는 데 무게를 둔다. 본문 텍스트처럼 CLS에 민감한 영역은 `swap`이나 `optional`이, 브랜드 아이덴티티가 중요한 헤드라인 정도만 `block`이 적합한 경우가 많다.

## 핵심 개념 3: size-adjust로 폴백과 웹폰트의 박스 크기 맞추기

`font-display: swap`을 쓰면 텍스트는 즉시 보이지만, 폴백 폰트와 웹폰트의 글자 폭·줄 높이가 다르면 교체 시점에 그 차이만큼 레이아웃이 밀린다. 이 차이를 줄이는 최근 접근이 `@font-face`의 메트릭 오버라이드 디스크립터다.

- `size-adjust`: 폰트 전체의 스케일을 조정해 폴백 폰트와 평균 글자 폭을 비슷하게 맞춘다.
- `ascent-override` / `descent-override` / `line-gap-override`: 폰트의 상단·하단 여백, 줄 간격을 강제로 지정해 줄 높이 차이를 줄인다.

이 값들은 폰트 파일을 열어 직접 계산하기보다, Fontaine이나 Capsize 같은 도구로 두 폰트(웹폰트와 대체할 시스템 폰트)의 메트릭 차이를 분석해 자동 산출하는 방식이 실무에서 자리 잡고 있다. Next.js의 `next/font`나 Nuxt의 폰트 모듈처럼 프레임워크가 빌드 시점에 이 메트릭 매칭을 자동으로 해주는 흐름도 늘고 있어, 직접 손으로 튜닝하지 않아도 되는 경우가 많아졌다.

## 예제 1: 폴백 폰트 메트릭 오버라이드

```css
/* 실제 서비스에서 쓸 웹폰트 */
@font-face {
  font-family: "BrandSans";
  src: url("/fonts/brand-sans.woff2") format("woff2");
  font-display: swap;
  font-weight: 400 700;
}

/* 시스템 폰트를 웹폰트와 비슷한 박스 크기로 맞춘 대체 정의 */
@font-face {
  font-family: "BrandSans Fallback";
  src: local("Arial");
  size-adjust: 104%;        /* 웹폰트 대비 평균 글자 폭 차이 보정 */
  ascent-override: 92%;
  descent-override: 24%;
  line-gap-override: 0%;
}

body {
  font-family: "BrandSans", "BrandSans Fallback", sans-serif;
}
```

`size-adjust`와 `ascent-override` 등의 수치는 실제 두 폰트를 비교 측정해서 산출해야 하는 값으로, 위 수치는 개념을 보여주기 위한 예시일 뿐 그대로 복사해 쓸 수치가 아니다. 서비스에 적용할 때는 Fontaine 같은 도구로 자신의 웹폰트·폴백 폰트 조합에 맞는 값을 계산하는 과정이 필요하다.

## 예제 2: 우선순위 있는 프리로드

```html
<head>
  <!-- LCP 텍스트에 쓰이는 폰트만 선별적으로 프리로드 -->
  <link
    rel="preload"
    href="/fonts/brand-sans.woff2"
    as="font"
    type="font/woff2"
    crossorigin
  >
</head>
```

폰트를 무조건 프리로드하면 오히려 다른 핵심 리소스(LCP 이미지, 초기 JS 번들)와 대역폭을 다투게 될 수 있다. 화면 최상단에서 바로 보이는 텍스트에 쓰이는 폰트 파일 한두 개만 선별적으로 프리로드하는 편이 안전하다.

## 실무 포인트

- **본문 텍스트는 `swap`이나 `optional`, 장식성 폰트는 `block`처럼 용도별로 `font-display` 값을 구분한다.** 모든 폰트에 같은 값을 일괄 적용하면 어느 한쪽에서 손해를 본다.
- **`size-adjust` 계열 값은 도구로 산출하고, 폰트 파일이 바뀔 때마다 재계산한다.** 웹폰트 버전이 바뀌면 메트릭도 바뀌므로 수치를 고정해두면 시간이 지나며 다시 어긋날 수 있다.
- **가변 폰트(variable font) 도입을 검토한다.** 굵기별로 별도 파일을 받는 대신 하나의 가변 폰트 파일로 여러 굵기를 커버하면, 스왑이 일어나는 횟수 자체를 줄일 수 있다.
- **서드파티 폰트 CDN 대신 자체 호스팅(self-hosting)을 우선 고려한다.** 외부 도메인 연결(DNS·TLS 핸드셰이크) 비용이 사라지고, 프리로드·캐시 정책을 직접 통제할 수 있다.
- **CLS는 필드 데이터(실제 사용자 CrUX)로 검증한다.** 로컬 환경은 캐시가 자주 남아있어 폰트 스왑 자체가 재현되지 않는 경우가 많다.

## 3줄 요약

- 웹폰트로 인한 CLS는 이미지와 달리 `width`/`height` 지정만으로는 막을 수 없고, 폴백-웹폰트 간 박스 크기 차이 자체를 줄여야 한다.
- `font-display`는 값에 따라 텍스트를 숨기는 시간과 스왑 허용 구간이 다르며, 콘텐츠 성격에 맞춰 `swap`/`optional`/`block`을 구분해 적용하는 것이 핵심이다.
- `size-adjust`, `ascent-override` 등 메트릭 오버라이드 디스크립터로 폴백 폰트의 박스 크기를 웹폰트에 맞추면 스왑 시점의 레이아웃 이동을 크게 줄일 수 있다.

## 참고 자료

- [font-display — MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display)
- [size-adjust — MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/size-adjust)
- [Best practices for fonts — web.dev](https://web.dev/articles/font-best-practices)
- [Optimizing Web Fonts — Chrome for Developers](https://developer.chrome.com/docs/lighthouse/performance/font-display)
