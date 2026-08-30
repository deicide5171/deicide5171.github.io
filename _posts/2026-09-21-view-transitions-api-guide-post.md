---
layout: single
title: "View Transitions API로 부드러운 페이지 전환 만들기"
date: 2026-09-21 13:30:00 +0530
categories: frontend
tags: ["viewtransitions", "페이지전환애니메이션", "웹표준", "spa", "css애니메이션"]
toc: true
toc_sticky: true
excerpt: "네이티브 앱 같은 부드러운 화면 전환을 위해 복잡한 애니메이션 라이브러리를 붙이기 전에, 브라우저 표준 View Transitions API로 얼마나 간단히 구현할 수 있는지 정리했다."
---

## 왜 지금 이 API를 알아야 하나

SPA(Single Page Application)에서 페이지를 전환할 때 화면이 "뚝" 하고 바뀌는 것과, 이전 화면 요소가 자연스럽게 다음 화면 요소로 이어지며 바뀌는 것은 사용자 체감이 크게 다르다. 네이티브 모바일 앱에서는 이런 전환이 기본이지만, 웹에서는 오랫동안 Framer Motion이나 GSAP 같은 자바스크립트 애니메이션 라이브러리를 직접 붙이거나, 요소 위치를 수동으로 계산해 트랜지션을 흉내내는 방식이 유일한 선택지였다.

**View Transitions API**는 이 작업을 브라우저가 대신 처리하게 해준다. 핵심 아이디어는 단순하다. DOM이 바뀌기 전 상태를 스냅샷으로 찍고, 바뀐 후 상태도 스냅샷으로 찍은 다음, 브라우저가 그 둘 사이를 자동으로 크로스페이드(또는 커스텀 애니메이션)로 이어준다.

## 기본 사용법

```javascript
function updateDOM() {
  document.querySelector('#content').innerHTML = newContent;
}

if (document.startViewTransition) {
  document.startViewTransition(() => updateDOM());
} else {
  updateDOM(); // API 미지원 브라우저는 그냥 즉시 반영
}
```

`document.startViewTransition()`에 DOM을 갱신하는 콜백을 넘기면, 브라우저가 변경 전후 스크린샷을 자동으로 찍어 기본 크로스페이드 애니메이션을 적용한다. 이 정도만으로도 아무 애니메이션이 없던 페이지가 부드럽게 전환되는 것을 바로 체감할 수 있다.

## 잘못된 접근: 요소 위치를 직접 계산하는 수동 트랜지션

View Transitions API 이전에는 "요소가 A 위치에서 B 위치로 이동하는 것처럼 보이게 하려면" `getBoundingClientRect()`로 시작·끝 좌표를 각각 구하고, `transform`으로 시작 위치에 배치한 뒤 `requestAnimationFrame`으로 실제 위치까지 애니메이션시키는 FLIP(First-Last-Invert-Play) 기법을 직접 구현해야 했다.

```javascript
// FLIP 기법 예시 (수동 구현의 복잡함)
const first = element.getBoundingClientRect();
updateDOM();
const last = element.getBoundingClientRect();
const deltaX = first.left - last.left;
const deltaY = first.top - last.top;
element.animate([
  { transform: `translate(${deltaX}px, ${deltaY}px)` },
  { transform: 'none' }
], { duration: 300, easing: 'ease-out' });
```

이 방식은 동작은 하지만 요소마다 좌표 계산 로직을 반복해야 하고, 레이아웃이 복잡해질수록 계산이 틀어지기 쉽다. 특히 페이지 전체가 바뀌는 라우트 전환에는 이 방식을 적용하기가 사실상 불가능에 가까웠다.

## 특정 요소만 이어지게 하기 (Named Transitions)

```css
.hero-image {
  view-transition-name: hero;
}
```

같은 `view-transition-name`을 가진 요소가 전환 전후에 모두 존재하면, 브라우저가 그 요소만 따로 골라 위치와 크기가 자연스럽게 이어지는(morphing) 애니메이션을 적용한다. 상품 목록의 썸네일이 상세 페이지의 큰 이미지로 이어지는 것 같은 효과를 CSS 한 줄과 이름 매칭만으로 구현할 수 있다. 커스텀 애니메이션이 필요하면 `::view-transition-old()`, `::view-transition-new()` 의사 요소에 원하는 CSS 애니메이션을 직접 지정한다.

## 실무 포인트

- **점진적 향상(progressive enhancement)으로 접근하라.** `document.startViewTransition`이 없는 브라우저에서는 그냥 즉시 DOM을 갱신하도록 분기하면 되므로, 지원하지 않는 환경에서도 기능 자체가 깨지지 않는다.
- **다중 페이지 앱(MPA)에서도 쓸 수 있다.** Cross-document View Transitions는 SPA뿐 아니라 실제로 새 HTML 문서를 로드하는 전통적인 다중 페이지 사이트에서도 페이지 간 전환 애니메이션을 지원한다. `@view-transition { navigation: auto; }`를 CSS에 선언하면 활성화된다.
- **`view-transition-name`은 페이지에서 유일해야 한다.** 같은 이름을 가진 요소가 전환 시점에 두 개 이상 동시에 존재하면 브라우저가 에러를 내며 트랜지션을 건너뛴다. 리스트 아이템처럼 여러 개가 반복되는 요소에 이름을 붙일 때는 각 아이템에 고유 ID를 조합해 이름을 동적으로 생성해야 한다.
- **reduced motion 설정을 존중하라.** 사용자가 OS에서 모션 감소를 켜뒀다면 `@media (prefers-reduced-motion: reduce)`로 트랜지션 지속시간을 0에 가깝게 줄이거나 생략하는 것이 접근성 측면에서 바람직하다.

## 마무리 요약

- View Transitions API는 DOM 변경 전후 스냅샷을 브라우저가 자동으로 이어줘, 별도 라이브러리 없이 부드러운 화면 전환을 구현하게 해준다.
- `view-transition-name`으로 특정 요소만 지정하면 상품 썸네일이 상세 이미지로 확대되는 것 같은 정교한 전환도 CSS만으로 만들 수 있다.
- 미지원 브라우저 폴백과 reduced motion 대응을 함께 챙겨야 실무에 안전하게 도입할 수 있다.

## 참고 자료

- [MDN - View Transition API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)
- [Chrome for Developers - Smooth transitions with the View Transition API](https://developer.chrome.com/docs/web-platform/view-transitions)
