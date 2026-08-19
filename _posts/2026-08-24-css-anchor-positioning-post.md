---
layout: single
title: "팝오버 위치 계산, JS 없이 CSS로 — CSS Anchor Positioning 실전"
date: 2026-08-24 12:30:00 +0530
categories: frontend
tags: ["css", "anchor-positioning", "popover", "tooltip", "floating-ui", "web-platform"]
toc: true
toc_sticky: true
excerpt: "툴팁·드롭다운 위치 계산을 위해 Floating UI 같은 JS 라이브러리에 의존해온 문제를, 브라우저 네이티브 CSS Anchor Positioning API가 어떻게 대체하는지 정리한다."
---

드롭다운 메뉴가 화면 오른쪽 끝에서 잘리지 않게, 툴팁이 뷰포트를 벗어나면 반대편으로 뒤집히게 — 이런 "앵커 요소를 기준으로 다른 요소의 위치를 계산하는" 로직은 지금까지 거의 전부 JavaScript의 몫이었다. Floating UI(구 Popper.js)가 사실상 업계 표준으로 자리 잡은 이유도, 브라우저 뷰포트 충돌 감지와 위치 재계산을 순수 CSS로는 할 수 없었기 때문이다.

CSS Anchor Positioning API는 이 문제를 플랫폼 레벨로 끌어올린다. 임의의 요소를 앵커로 지정하고, 다른 요소를 그 앵커에 상대적으로 배치하며, 공간이 부족하면 자동으로 대체 위치로 전환하는 것까지 CSS만으로 표현할 수 있다. 이 글에서는 핵심 문법과 JS 라이브러리 대비 실무 적용 지점을 정리한다.

## 핵심 개념 1: anchor-name과 anchor()로 위치 연결하기

앵커가 될 요소에 `anchor-name`을 부여하고, 위치를 잡을 요소에서 `position-anchor`로 참조한 뒤 `anchor()` 함수로 좌표를 계산한다.

```css
.trigger-button {
  anchor-name: --my-anchor;
}

.tooltip {
  position: fixed; /* 또는 absolute */
  position-anchor: --my-anchor;

  /* 앵커의 아래쪽 가장자리에 top을 맞춘다 */
  top: anchor(--my-anchor bottom);
  left: anchor(--my-anchor left);
}
```

`anchor()`는 앵커 요소의 `top`/`bottom`/`left`/`right`/`center` 같은 가장자리 값을 가져와 현재 요소의 좌표 프로퍼티에 대입한다. 기존에는 JS로 `getBoundingClientRect()`를 호출해 픽셀 값을 계산했던 작업을, 브라우저 레이아웃 엔진이 리페인트 없이 직접 처리한다는 점이 핵심 차이다.

## 핵심 개념 2: position-try-fallbacks — 충돌 시 자동 전환

Anchor Positioning의 진짜 가치는 공간 부족 시 자동 대체(fallback) 처리에 있다. `position-try-fallbacks`에 대체 위치 목록을 지정하면, 브라우저가 뷰포트 충돌을 감지해 순서대로 시도한다.

```css
.tooltip {
  position: fixed;
  position-anchor: --my-anchor;
  top: anchor(--my-anchor bottom);
  left: anchor(--my-anchor left);

  /* 아래쪽 공간이 부족하면 위쪽으로, 그래도 부족하면 오른쪽으로 */
  position-try-fallbacks: flip-block, flip-inline, --custom-fallback;
}

@position-try --custom-fallback {
  top: anchor(--my-anchor top);
  left: anchor(--my-anchor right);
}
```

`flip-block`/`flip-inline` 같은 내장 키워드 외에 `@position-try`로 완전히 커스텀한 대체 위치 세트를 정의할 수도 있다.

## 핵심 개념 3: 기존 JS 라이브러리 방식과의 비교

| 구분 | Floating UI/Popper (JS) | CSS Anchor Positioning |
|---|---|---|
| 위치 계산 주체 | JS가 매 프레임 재계산 | 브라우저 레이아웃 엔진 |
| 스크롤/리사이즈 대응 | 이벤트 리스너 + 재계산 | 네이티브 반응(리페인트 불필요) |
| 번들 크기 | Floating UI ~5-10KB | 0 (플랫폼 기능) |
| 충돌 감지·자동 전환 | 라이브러리 로직 | `position-try-fallbacks` |
| 브라우저 지원 | 전 브라우저 | 제한적(Chromium 계열 우선 도입) |
| `popover` 속성과 결합 | 별도 라이브러리 필요 | 네이티브 `popover` API와 자연스럽게 결합 |

가장 큰 실무 이점은 성능이다. JS 기반 위치 계산은 스크롤·리사이즈마다 레이아웃을 강제로 다시 읽어(`getBoundingClientRect`) 재계산하는 비용이 들지만, 네이티브 Anchor Positioning은 브라우저 내부 레이아웃 파이프라인에 통합돼 있어 이 왕복이 없다.

## 실무 포인트

- **브라우저 지원 범위를 먼저 확인하고 점진적 향상으로 설계한다**: 아직 모든 브라우저가 지원하는 것은 아니므로, `@supports (anchor-name: --a)` 피처 쿼리로 미지원 브라우저에서는 Floating UI 폴백을 유지하는 이중 경로가 현실적이다.
- **네이티브 `popover` 속성과 함께 쓸 때 진가가 나온다**: `popovertarget` 속성으로 연결된 팝오버는 최상위 레이어(top layer)에 렌더링되어 `z-index` 전쟁과 `overflow: hidden` 클리핑 문제에서 자유로운데, 여기에 Anchor Positioning을 결합하면 JS 없이 완전한 팝오버 컴포넌트를 만들 수 있다.
- **anchor-name은 전역 스코프라는 점을 주의한다**: 같은 이름을 여러 요소에 재사용하면 마지막에 매칭된 것이 적용되는 등 예상과 다른 동작이 나올 수 있어, 컴포넌트별로 고유한 커스텀 프로퍼티 이름 규칙을 정해두는 것이 안전하다.

## 3줄 요약

- CSS Anchor Positioning은 `anchor-name`/`anchor()`로 임의 요소를 기준점 삼아 다른 요소를 배치하는 기능을 플랫폼 레벨로 제공한다.
- `position-try-fallbacks`가 뷰포트 충돌을 감지해 대체 위치로 자동 전환해주어, Floating UI 같은 JS 라이브러리의 핵심 기능을 대체한다.
- 브라우저 지원이 아직 제한적이므로 `@supports` 기반 점진적 향상 전략과, 네이티브 `popover` API와의 조합을 함께 설계하는 것이 실무 적용의 핵심이다.

## 참고 자료

- [MDN: CSS anchor positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_anchor_positioning)
- [MDN: anchor() 함수](https://developer.mozilla.org/en-US/docs/Web/CSS/anchor)
- [Chrome for Developers: Anchor positioning API](https://developer.chrome.com/docs/css-ui/anchor-positioning-api)
- [Floating UI 공식 문서](https://floating-ui.com/docs/getting-started)
