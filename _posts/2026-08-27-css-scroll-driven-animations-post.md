---
layout: single
title: "스크롤이 곧 타임라인이 된다 — CSS Scroll-driven Animations 실무"
date: 2026-08-27 13:30:00 +0530
categories: frontend
tags: ["css", "scroll-driven-animations", "performance", "frontend", "web-animations"]
toc: true
toc_sticky: true
excerpt: "스크롤에 따라 진행률바를 채우거나 요소를 나타나게 하는 효과를 JS 스크롤 리스너로 만들면 자꾸 버벅인다. CSS만으로 스크롤 위치를 애니메이션 타임라인으로 쓰는 법을 정리한다."
---

스크롤 진행률바, 스크롤에 맞춰 나타나는 리빌 애니메이션, 패럴랙스 효과 — 이런 것들을 만들 때 흔히 `scroll` 이벤트 리스너에 `requestAnimationFrame`을 조합해 매 프레임 스크롤 위치를 읽고 스타일을 직접 갱신한다. 이 방식은 동작은 하지만 메인 스레드에서 스크롤 이벤트와 스타일 계산이 계속 오가면서 스크롤 중 프레임 드랍이 발생하기 쉽다.

CSS Scroll-driven Animations는 이 문제를 근본적으로 없앤다. 스크롤 위치 자체를 애니메이션의 "시간"으로 취급해, 브라우저가 컴포지터 스레드에서 애니메이션 진행률을 스크롤 위치에 직접 묶어버린다. JS 이벤트 루프를 거치지 않으므로 메인 스레드가 바빠도 스크롤 애니메이션은 매끄럽게 유지된다. 이 글에서는 이 기능의 핵심 개념과 실무 적용법을 정리한다.

## 핵심 개념 1: 두 가지 타임라인 — `scroll()`과 `view()`

Scroll-driven Animations는 애니메이션의 진행률을 결정하는 타임라인 소스로 두 가지를 제공한다.

**`scroll()`**은 스크롤 컨테이너 전체의 스크롤 진행률(0~100%)을 타임라인으로 쓴다. "페이지를 처음부터 끝까지 스크롤하는 동안 진행률바를 0%에서 100%로 채운다"처럼 컨테이너 전체 기준 애니메이션에 적합하다.

**`view()`**은 특정 요소가 뷰포트(또는 지정한 컨테이너)에 들어오고 나가는 구간 자체를 타임라인으로 쓴다. "이 카드가 화면에 들어올 때 페이드인되고, 화면을 벗어나면 사라진다"처럼 개별 요소의 가시성 기반 애니메이션에 적합하다. 내부적으로 `IntersectionObserver`가 하던 일을 브라우저 네이티브 타임라인으로 대체한 것에 가깝다.

## 핵심 개념 2: JS 방식과의 비교

| 구분 | JS (scroll + rAF) | CSS Scroll-driven Animations |
|---|---|---|
| 실행 스레드 | 메인 스레드 | 컴포지터 스레드 (독립적) |
| 메인 스레드 부하 시 영향 | 프레임 드랍 발생 가능 | 영향받지 않음 |
| 구현 복잡도 | 이벤트 리스너·쓰로틀링 직접 관리 | 선언적 CSS 몇 줄 |
| 브라우저 지원 | 전 브라우저 | 최신 Chromium·Firefox(2024~) 계열, Safari는 부분 지원 |
| 세밀한 로직(조건 분기 등) | 자유롭게 가능 | 제한적(CSS 표현력 안에서만) |

브라우저 지원이 완전하지 않다는 점이 현재 가장 큰 제약이다. `@supports (animation-timeline: scroll())`로 기능 감지 후 폴백을 두거나, 점진적 향상(progressive enhancement)으로 접근해야 한다.

<img src="/assets/images/posts/2026-08-27-css-scroll-driven-animations-1.svg" alt="scroll() 타임라인은 스크롤 컨테이너 전체 진행률을, view() 타임라인은 개별 요소가 뷰포트에 들어오고 나가는 구간을 애니메이션 진행률로 사용하는 구조 비교도" style="width:100%;">

## 예제: 읽기 진행률바와 카드 리빌 애니메이션

```css
/* 1. 페이지 스크롤 진행률바 — scroll() 타임라인 */
@keyframes grow-progress {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}

.progress-bar {
  transform-origin: left;
  animation: grow-progress auto linear;
  animation-timeline: scroll(root); /* 문서 스크롤 전체를 타임라인으로 */
}

/* 2. 카드가 뷰포트에 들어올 때 페이드인 — view() 타임라인 */
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}

.reveal-card {
  animation: fade-in-up auto linear;
  animation-timeline: view();
  animation-range: entry 0% cover 40%; /* 진입 시작부터 40% 지점까지만 진행 */
}
```

`animation-range`로 타임라인 중 어느 구간에서 애니메이션이 진행될지 세밀하게 지정할 수 있다. `entry 0% cover 40%`는 "요소가 뷰포트에 들어오기 시작할 때부터, 뷰포트 40% 지점을 지날 때까지" 애니메이션을 진행시키고 그 이후는 최종 상태를 유지한다.

## 실무 포인트

- **`@supports`로 반드시 폴백을 챙긴다**: Safari 등 미지원 브라우저에서는 `animation-timeline`이 무시되어 `@keyframes`의 시작 상태(예: `opacity: 0`)로 요소가 멈춰 보일 수 있다. `@supports not (animation-timeline: view())`로 감싸 기본 표시 상태를 강제하거나, IntersectionObserver 폴백을 준비해야 한다.
- **`will-change`는 필요할 때만 최소로 쓴다**: 컴포지터 레이어 승격을 유도하려고 무분별하게 `will-change: transform`을 남발하면 오히려 GPU 메모리를 낭비하고 성능이 떨어질 수 있다. Scroll-driven Animations 자체는 이미 컴포지터 처리를 전제하므로 대부분의 경우 추가 지정이 필요 없다.
- **`animation-range`로 튜닝하며 자연스러움을 조정한다**: 기본값(`normal`, 전체 구간)은 종종 너무 빠르거나 느리게 느껴진다. `entry`, `exit`, `cover`, `contain` 키워드 조합으로 애니메이션이 시작·종료되는 지점을 조정해 실제 스크롤 체감과 맞추는 튜닝이 거의 항상 필요하다.

## 3줄 요약

- CSS Scroll-driven Animations는 스크롤 위치를 애니메이션 타임라인으로 삼아 컴포지터 스레드에서 실행되므로 JS 스크롤 리스너보다 매끄럽다.
- `scroll()`은 컨테이너 전체 진행률을, `view()`는 개별 요소의 가시성 구간을 타임라인으로 쓴다는 역할 차이가 있다.
- 브라우저 지원이 아직 완전하지 않으므로 `@supports` 기반 폴백과 `animation-range` 튜닝이 실무 적용의 핵심이다.

## 참고 자료

- [MDN: CSS scroll-driven animations](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations)
- [Chrome for Developers: Scroll-driven animations](https://developer.chrome.com/docs/css-ui/scroll-driven-animations)
- [MDN: animation-timeline](https://developer.mozilla.org/en-US/docs/Web/CSS/animation-timeline)
