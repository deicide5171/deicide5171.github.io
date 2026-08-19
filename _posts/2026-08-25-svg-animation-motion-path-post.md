---
layout: single
title: "곡선을 따라 움직이는 UI — SVG 애니메이션과 CSS Motion Path 실무"
date: 2026-08-25 13:30:00 +0530
categories: frontend
tags: ["svg", "motion-path", "css-animation", "web-animations-api", "frontend"]
toc: true
toc_sticky: true
excerpt: "SMIL이 사실상 종료 수순에 들어간 지금, SVG 도형을 곡선 경로를 따라 움직이는 애니메이션을 CSS offset-path와 Web Animations API로 구현하는 방법과 성능 고려사항을 정리한다."
---

버튼 클릭 시 아이콘이 직선이 아니라 살짝 휘어진 곡선을 그리며 장바구니로 날아가는 연출, 지도 위에서 경로를 따라 움직이는 마커, 온보딩 화면에서 점이 경로를 그리며 다음 스텝으로 이동하는 인터랙션 — 이런 "경로를 따라 움직이는" 애니메이션은 흔히 SVG의 `<animateMotion>`(SMIL 애니메이션)으로 구현됐다. 그런데 SMIL은 브라우저 벤더들 사이에서 오랫동안 "새 기능 추가는 중단하고 유지보수만 한다"는 입장이 이어져 왔고, 최신 명세는 이 역할을 CSS의 **motion path**(`offset-path`) 기능으로 넘기는 방향으로 정리되고 있다.

이 글에서는 경로를 따라 움직이는 애니메이션을 최신 표준인 CSS `offset-path`로 구현하는 방법, SVG `<path>`와의 연동, 그리고 Web Animations API로 이를 프로그래밍적으로 제어하는 패턴을 정리한다.

## 핵심 개념 1: offset-path — 임의의 경로를 움직임의 궤적으로

CSS Motion Path 스펙의 핵심은 `offset-path` 속성이다. 이 속성에 SVG `path()` 함수로 곡선을 지정하면, 해당 요소는 그 경로를 따라 이동할 수 있는 궤적을 갖게 된다. 실제 이동은 `offset-distance`(경로상 진행률, 0%~100%)를 애니메이션시켜 구현하고, `offset-rotate`로 요소가 경로의 접선 방향을 따라 자연스럽게 회전하도록 만들 수 있다.

기존 SMIL의 `<animateMotion>`은 SVG 요소에만 적용 가능했지만, `offset-path`는 CSS 속성이므로 일반 HTML 요소(`div`, `img` 등)에도 그대로 쓸 수 있다는 점이 실무에서 특히 유용하다. 아이콘이 카드 사이를 곡선을 그리며 이동하는 UI를 SVG로 감싸지 않고도 순수 CSS로 구현할 수 있다는 뜻이다.

## 핵심 개념 2: SVG path와 CSS motion path의 좌표계 차이

SVG `<path>`의 `d` 속성 좌표는 SVG 문서 자체의 좌표계(viewBox 기준)를 따르지만, CSS `offset-path: path(...)`에 넣는 경로 좌표는 해당 요소가 속한 CSS 박스의 좌표계를 기준으로 해석된다. 두 좌표계가 다르다는 것을 모르고 SVG에서 그린 경로의 좌표를 그대로 CSS에 복붙하면 요소가 엉뚱한 위치로 튀는 경우가 흔하다. 실무에서는 SVG 편집 도구(피그마, 일러스트레이터, 또는 브라우저 개발자 도구)에서 뽑은 path 좌표를 CSS 요소의 실제 렌더링 좌표계에 맞춰 오프셋을 조정하는 과정이 거의 항상 필요하다.

| 구분 | SMIL `<animateMotion>` | CSS `offset-path` |
|---|---|---|
| 적용 대상 | SVG 요소만 | HTML/SVG 요소 모두 |
| 표준 상태 | 신규 개발 중단, 유지보수만 | 활발히 개발 중인 표준 |
| 애니메이션 제어 | SVG 속성(begin, dur 등) | CSS 애니메이션/트랜지션, JS WAAPI |
| 접선 방향 자동 회전 | rotate="auto" | offset-rotate: auto |
| 브라우저 개발자 도구 지원 | 제한적 | 크롬 등에서 시각적 편집 지원 |

## 핵심 개념 3: Web Animations API로 프로그래밍적 제어

CSS 애니메이션만으로는 "사용자 스크롤 진행률에 따라 경로 진행률을 맞춘다"거나 "다른 비동기 이벤트에 맞춰 애니메이션을 일시정지·재개한다" 같은 동적 제어가 번거롭다. 이런 경우 Web Animations API(WAAPI)로 `offset-distance`를 직접 키프레임 애니메이션으로 제어하면, JavaScript에서 `animation.currentTime`이나 `animation.playbackRate`를 조작해 임의의 진행률로 애니메이션을 동기화할 수 있다.

## 예제: CSS Motion Path + WAAPI로 곡선 이동 구현

```html
<svg width="0" height="0" style="position:absolute;">
  <!-- 실제로 그리지는 않고 경로 정의만 재사용하기 위한 숨김 SVG -->
  <path id="flight-path" d="M 20 200 C 120 20, 280 20, 380 200" />
</svg>

<div class="icon" id="cart-icon">🛒</div>
```

```css
.icon {
  offset-path: path("M 20 200 C 120 20, 280 20, 380 200");
  offset-rotate: auto; /* 경로 접선 방향으로 자동 회전 */
  offset-distance: 0%;
}
```

```javascript
const icon = document.getElementById('cart-icon');

// Web Animations API로 경로 진행률을 애니메이션
const animation = icon.animate(
  [{ offsetDistance: '0%' }, { offsetDistance: '100%' }],
  { duration: 800, easing: 'ease-in-out', fill: 'forwards' }
);

// 예: 다른 애니메이션이 끝난 뒤 이어서 재생하도록 동기화
otherAnimation.finished.then(() => animation.play());

// 예: 스크롤 진행률에 맞춰 경로 진행률을 수동으로 매핑
window.addEventListener('scroll', () => {
  const progress = getScrollProgress(); // 0~1
  animation.currentTime = progress * animation.effect.getTiming().duration;
});
```

## 실무 포인트

- **브라우저 지원 범위를 반드시 확인한다**: `offset-path`와 `offset-rotate`는 최신 주요 브라우저에서 대부분 지원되지만, 레거시 브라우저 지원이 필요한 프로젝트라면 폴리필이나 SMIL 폴백 경로를 함께 준비해야 한다. `@supports (offset-path: path("M0 0"))`로 기능 감지 후 폴백을 분기하는 패턴이 안전하다.
- **경로가 복잡할수록 GPU 가속 여부를 확인한다**: `offset-distance`만 애니메이션시키는 경우 브라우저가 합성(compositing) 단계에서 처리해 부드럽지만, `offset-path` 자체를 매 프레임 바꾸면 레이아웃·페인트가 다시 발생해 성능이 급격히 나빠질 수 있다. 경로 자체는 고정하고 진행률만 애니메이션하는 것이 원칙이다.
- **접근성 고려를 빠뜨리지 않는다**: 의미 없는 장식용 모션이라면 `prefers-reduced-motion` 미디어 쿼리로 모션 민감 사용자에게는 애니메이션을 생략하거나 즉시 종료 상태로 보여주는 대체 스타일을 반드시 제공해야 한다.

## 3줄 요약

- SMIL `<animateMotion>`은 유지보수 단계에 머물러 있고, 경로를 따라 움직이는 애니메이션의 최신 표준은 CSS `offset-path`다.
- SVG 좌표계와 CSS 박스 좌표계가 다르므로 경로 좌표를 그대로 복사하면 위치가 어긋나기 쉽고, 이를 반드시 확인해야 한다.
- 동적 제어가 필요하면 Web Animations API로 `offset-distance`를 직접 조작하고, 성능을 위해 경로 자체보다 진행률만 애니메이션하는 것이 원칙이다.

## 참고 자료

- [MDN 웹 문서: CSS Motion Path](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_motion_path)
- [MDN 웹 문서: Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)
- [W3C 명세: Motion Path Level 1](https://www.w3.org/TR/motion-path-1/)
