---
layout: single
title: "View Transitions API로 페이지 전환에 생명 불어넣기"
date: 2026-08-21 13:30:00 +0530
categories: frontend
tags: ["frontend", "view-transitions", "css", "animation", "spa"]
toc: true
toc_sticky: true
excerpt: "SPA 페이지 전환마다 라이브러리에 의존하던 애니메이션을, 브라우저 표준 View Transitions API 하나로 자연스럽게 구현하는 방법을 정리한다."
---

SPA에서 라우트가 바뀔 때 화면이 뚝 끊기지 않고 자연스럽게 넘어가길 바라는 요구는 늘 있었다. 그래서 실무에서는 흔히 Framer Motion이나 react-transition-group 같은 애니메이션 라이브러리를 붙이고, 진입·퇴장 애니메이션을 각 컴포넌트마다 수동으로 정의해왔다. 문제는 이 방식이 번들 크기를 키우고, 컴포넌트 트리 구조와 애니메이션 타이밍을 맞추는 과정에서 코드가 금방 복잡해진다는 점이다. 특히 리스트 아이템이 상세 페이지의 특정 요소로 확대되는 것 같은 "모핑(morphing)" 효과는 라이브러리 없이 직접 구현하기가 까다로웠다.

View Transitions API는 이런 문제를 브라우저 표준 기능으로 해결하려는 시도다. DOM 상태가 바뀌기 전후의 스냅샷을 브라우저가 자동으로 캡처하고, 그 사이를 크로스페이드나 커스텀 애니메이션으로 이어주기 때문에 개발자가 직접 시작 상태와 종료 상태의 좌표를 계산할 필요가 없다. CSS 몇 줄과 자바스크립트 한 줄로 이전에는 라이브러리가 필요했던 효과를 구현할 수 있다는 점이 매력적이다.

이 글에서는 View Transitions API의 동작 원리를 짚어보고, SPA와 MPA 각각에서 어떻게 적용하는지, 그리고 실무에 도입할 때 고려해야 할 브라우저 지원과 접근성 이슈를 정리한다.

## 핵심 개념 1: 전후 스크린샷 기반 크로스페이드/모핑

View Transitions API의 핵심 아이디어는 단순하다. DOM이 바뀌기 직전 화면을 이미지로 캡처하고, DOM이 바뀐 직후 화면도 이미지로 캡처한 다음, 두 이미지를 겹쳐서 CSS 애니메이션으로 전환한다. 기본값은 오래된 화면이 페이드아웃되고 새 화면이 페이드인되는 크로스페이드다.

여기서 중요한 것은 `view-transition-name`이라는 CSS 속성이다. 전환 전후에 같은 이름을 가진 요소가 있으면, 브라우저는 그 요소를 별도의 레이어로 분리해 캡처하고 위치·크기가 다르더라도 부드럽게 보간(interpolate)한다. 예를 들어 목록의 썸네일과 상세 페이지의 큰 이미지에 동일한 `view-transition-name`을 지정하면, 썸네일이 커지면서 상세 이미지로 자연스럽게 모핑되는 효과를 별도의 좌표 계산 코드 없이 얻을 수 있다.

## 핵심 개념 2: document.startViewTransition 기본 사용법

SPA(단일 페이지 애플리케이션)에서는 `document.startViewTransition()` 메서드로 전환을 직접 제어한다. 이 메서드는 DOM을 변경하는 콜백 함수를 인자로 받는다. 브라우저는 콜백이 실행되기 전 현재 화면을 캡처하고, 콜백이 끝난 뒤(및 관련 스타일/레이아웃이 안정된 뒤) 새 화면을 캡처해서 전환을 시작한다.

```js
function navigate(newContent) {
  if (!document.startViewTransition) {
    // 미지원 브라우저는 전환 없이 즉시 DOM 갱신
    updateDOM(newContent);
    return;
  }
  document.startViewTransition(() => {
    updateDOM(newContent);
  });
}
```

`startViewTransition`은 `ViewTransition` 객체를 반환하며, 이 객체의 `ready`, `updateCallbackDone`, `finished` 프로미스를 통해 전환 단계별로 후속 처리를 걸 수 있다. React나 Vue 같은 프레임워크에서는 라우터의 페이지 전환 훅 안에서 상태 업데이트를 이 콜백으로 감싸는 식으로 통합한다.

## 핵심 개념 3: MPA의 @view-transition vs SPA에서의 사용

초기 View Transitions API는 SPA를 위한 same-document 전환만 지원했지만, 이후 여러 문서(document) 간 이동, 즉 전통적인 MPA(멀티페이지 앱)의 페이지 이동에도 확장되었다. MPA에서는 자바스크립트 호출 없이 CSS `@view-transition` 규칙만으로 전환을 켤 수 있다.

```css
@view-transition {
  navigation: auto;
}
```

이 규칙을 페이지에 선언하면, 같은 출처(origin) 내에서 링크를 클릭해 다른 문서로 이동할 때도 브라우저가 자동으로 전후 스크린샷을 캡처해 전환을 적용한다. SPA에서는 개발자가 `startViewTransition`으로 전환 시점을 코드로 제어해야 하지만, MPA에서는 선언적으로 켜기만 하면 되는 대신 전환 시점이나 콜백 개입은 제한적이다. 즉 SPA는 세밀한 제어가 필요할 때, MPA용 cross-document 전환은 페이지 이동 자체에 최소한의 애니메이션만 얹고 싶을 때 적합하다.

## 예제

목록에서 상세 화면으로 전환하며 특정 요소를 모핑시키는 예제다. 목록의 카드와 상세 페이지의 헤더 이미지에 같은 `view-transition-name`을 부여한다.

```css
/* 목록의 카드 이미지와 상세 페이지의 헤더 이미지에 각각 지정 */
.card-thumb {
  view-transition-name: hero-image;
}

/* 기본 크로스페이드 대신 커스텀 애니메이션을 지정하고 싶을 때 */
::view-transition-old(hero-image),
::view-transition-new(hero-image) {
  animation-duration: 0.4s;
  animation-timing-function: ease-in-out;
}

/* prefers-reduced-motion 사용자는 전환을 사실상 순간 전환으로 축소 */
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
  }
}
```

```js
async function goToDetail(id) {
  if (!document.startViewTransition) {
    renderDetail(id);
    return;
  }
  const transition = document.startViewTransition(() => renderDetail(id));
  try {
    await transition.finished;
  } catch (e) {
    // 전환이 중간에 취소되는 경우(빠른 연속 네비게이션 등) 대비
    console.warn("view transition interrupted", e);
  }
}
```

`view-transition-name`은 같은 시점에 화면에 두 개 이상 중복되면 오류가 발생하므로, 리스트처럼 동일 요소가 여러 개 반복되는 UI에서는 각 항목에 고유한 이름(예: `hero-image-${id}`)을 부여해야 한다.

## 실무 포인트

브라우저 지원 현황은 계속 바뀌는 영역이므로 도입 전에 반드시 최신 상태를 caniuse.com이나 MDN에서 직접 확인하는 것이 안전하다. 다만 이 API를 지원하지 않는 브라우저에서 호출하면 에러가 나는 것이 아니라 `document.startViewTransition`이 아예 존재하지 않으므로, 위 예제처럼 `if (!document.startViewTransition)` 분기로 감싸 폴백 경로(즉시 DOM 갱신)를 마련해두면 미지원 환경에서도 기능 자체는 그대로 동작한다. 즉 이 API는 "있으면 화면이 더 매끄러워지는" 점진적 향상(progressive enhancement) 방식으로 설계하는 것이 적절하다.

접근성 측면에서는 `prefers-reduced-motion` 미디어 쿼리를 반드시 함께 고려해야 한다. 전정기관 문제로 움직임에 민감한 사용자를 위해 OS 설정에서 모션 감소를 켠 경우, `::view-transition-*` 의사 요소들의 `animation-duration`을 극단적으로 짧게 재정의해 전환 효과를 사실상 순간 전환으로 만들어주는 것이 권장된다. 또한 전환 애니메이션이 스크린 리더 사용자에게 불필요한 레이아웃 변화로 인식되지 않도록, 포커스 이동이나 라이브 리전 안내 같은 기존 접근성 처리와 별개로 다뤄야 한다.

## 3줄 요약

- View Transitions API는 DOM 변경 전후 화면을 브라우저가 자동으로 캡처해, `view-transition-name`으로 지정한 요소를 좌표 계산 없이 크로스페이드/모핑 전환시켜준다.
- SPA는 `document.startViewTransition()`으로 전환을 코드로 제어하고, MPA는 CSS `@view-transition` 규칙만으로 문서 간 이동에 전환을 선언적으로 적용할 수 있다.
- 지원 여부는 `document.startViewTransition` 존재 여부로 분기해 폴백을 준비하고, `prefers-reduced-motion` 사용자를 위해 애니메이션 지속 시간을 짧게 재정의하는 것이 실무에서 중요하다.

## 참고 자료

- [MDN - View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API)
- [MDN - Document: startViewTransition() method](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition)
- [MDN - @view-transition](https://developer.mozilla.org/en-US/docs/Web/CSS/@view-transition)
- [Chrome for Developers - Same-document view transitions](https://developer.chrome.com/docs/web-platform/view-transitions/same-document)
- [Chrome for Developers - Cross-document view transitions](https://developer.chrome.com/docs/web-platform/view-transitions/cross-document)
