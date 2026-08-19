---
layout: single
title: "CSS로는 안 되는 그 애니메이션 — Web Animations API로 명령형 제어하기"
date: 2026-08-27 12:30:00 +0530
categories: frontend
tags: ["web-animations-api", "javascript", "animation", "performance", "css"]
toc: true
toc_sticky: true
excerpt: "CSS 애니메이션은 선언적이라 깔끔하지만 재생 중 일시정지·역재생·동적 키프레임 같은 제어가 필요해지면 한계를 드러낸다. Web Animations API로 명령형 제어를 붙이는 법을 정리한다."
---

CSS `transition`과 `@keyframes`는 대부분의 UI 애니메이션에 충분하다. 그런데 "사용자가 드래그하는 동안 애니메이션 진행률을 손가락 위치에 맞춰 실시간으로 바꾼다", "여러 요소의 애니메이션을 정확히 동기화한다", "재생 중간에 되감아 역재생한다" 같은 요구가 들어오면 CSS만으로는 버겁다. `requestAnimationFrame`으로 매 프레임 스타일을 직접 계산하는 것도 가능하지만, 이는 메인 스레드를 점유하고 브라우저의 컴포지터 최적화를 포기하는 방식이다.

Web Animations API(WAAPI)는 이 사이의 간극을 메운다. CSS 애니메이션과 동일하게 컴포지터 스레드에서 실행되는 성능을 유지하면서, `Animation` 객체를 통해 재생·일시정지·역재생·속도 조절 같은 명령형 제어를 JavaScript로 할 수 있다. 이 글에서는 WAAPI의 핵심 API와 CSS 애니메이션과의 역할 분담을 정리한다.

## 핵심 개념 1: `element.animate()`와 `Animation` 객체

WAAPI의 진입점은 `Element.prototype.animate(keyframes, options)`다. 키프레임 배열과 지속시간·이징 같은 옵션을 넘기면 `Animation` 객체가 반환되고, 이 객체로 애니메이션을 제어한다.

```javascript
const animation = card.animate(
  [
    { transform: 'translateY(0) scale(1)', opacity: 1 },
    { transform: 'translateY(-20px) scale(1.05)', opacity: 0.8 },
  ],
  { duration: 400, easing: 'ease-out', fill: 'forwards' }
);

animation.pause();          // 즉시 일시정지
animation.playbackRate = -1; // 역재생으로 전환
animation.play();
await animation.finished;   // 애니메이션 완료를 Promise로 대기
```

`fill: 'forwards'`는 CSS의 `animation-fill-mode: forwards`와 동일하게 마지막 키프레임 상태를 유지시킨다. `animation.finished`가 Promise를 반환하므로 애니메이션이 끝난 뒤 다음 로직을 `await`로 이어 붙일 수 있다는 점이 CSS `animationend` 이벤트보다 다루기 쉽다.

## 핵심 개념 2: CSS 애니메이션 vs WAAPI, 역할 분담 기준

| 상황 | 적합한 방식 |
|---|---|
| 단순 호버·트랜지션, 값 고정 | CSS `transition`/`@keyframes` |
| 재생 중 일시정지·역재생·속도 변경 필요 | WAAPI |
| 스크롤 위치·드래그 진행률에 애니메이션을 동기화 | WAAPI (`currentTime` 직접 조작) |
| 여러 요소를 정확히 같은 타이밍으로 동기화 | WAAPI (하나의 타임라인 공유) |
| 서버·상태에 따라 키프레임 자체가 동적으로 바뀜 | WAAPI (JS로 키프레임 생성) |

핵심은 WAAPI도 CSS 애니메이션과 마찬가지로 `transform`·`opacity` 같은 컴포지터 처리 가능한 속성을 쓰는 한 GPU 컴포지터 스레드에서 실행된다는 점이다. 즉 "명령형 제어를 얻는 대가로 성능을 포기하는 것"이 아니라, 동일한 성능 특성 위에 제어 API만 얹는 것에 가깝다. 다만 `width`, `top` 같은 레이아웃에 영향을 주는 속성을 애니메이션하면 CSS든 WAAPI든 똑같이 메인 스레드에서 리플로우가 발생한다.

<img src="/assets/images/posts/2026-08-27-web-animations-api-imperative-control-1.svg" alt="CSS 애니메이션과 Web Animations API가 같은 컴포지터 스레드 실행 경로를 공유하되 WAAPI만 Animation 객체를 통한 재생 제어 계층을 추가로 갖는 구조도" style="width:100%;">

## 예제: 드래그 진행률에 애니메이션 동기화하기

```javascript
const sheet = document.querySelector('.bottom-sheet');
const anim = sheet.animate(
  [{ transform: 'translateY(100%)' }, { transform: 'translateY(0%)' }],
  { duration: 1000, fill: 'both' }
);
anim.pause(); // 드래그로만 제어할 것이므로 자동 재생 정지

let startY = 0;
sheet.addEventListener('pointerdown', (e) => { startY = e.clientY; });
sheet.addEventListener('pointermove', (e) => {
  const dragRatio = Math.min(1, Math.max(0, (startY - e.clientY) / 300));
  anim.currentTime = dragRatio * 1000; // 진행률을 손가락 위치에 직접 매핑
});
sheet.addEventListener('pointerup', () => {
  // 절반 이상 끌었으면 끝까지, 아니면 원위치로 자동 완주
  anim.playbackRate = anim.currentTime > 500 ? 1 : -1;
  anim.play();
});
```

`currentTime`을 직접 대입해 애니메이션 진행률을 입력 이벤트에 실시간으로 묶는 이 패턴은 CSS만으로는 구현할 방법이 없다.

## 실무 포인트

- **`fill` 옵션을 명시적으로 정한다**: 기본값(`none`)은 애니메이션이 끝나면 스타일이 원래대로 되돌아간다. 마지막 상태를 유지하고 싶다면 `forwards`를, 시작 전 상태도 유지하고 싶다면 `both`를 명시해야 예상 밖의 깜빡임을 피할 수 있다.
- **`getAnimations()`로 진행 중인 애니메이션을 관리한다**: `element.getAnimations()`는 그 요소에 걸린 모든 Animation 객체를 반환한다. 새 애니메이션을 걸기 전 기존 것을 `cancel()`하지 않으면 여러 애니메이션이 충돌해 예상치 못한 최종 상태가 나올 수 있다.
- **View Transitions API와는 상호 보완 관계다**: 페이지/DOM 상태 전환 전체를 다룰 때는 View Transitions API가, 개별 요소의 세밀한 재생 제어가 필요할 때는 WAAPI가 적합하다. 실제로 View Transitions는 내부적으로 WAAPI 기반 애니메이션을 생성하므로, `document.startViewTransition()`이 반환한 전환의 각 의사 요소를 WAAPI로 커스터마이징하는 조합도 가능하다.

## 3줄 요약

- WAAPI는 CSS 애니메이션과 같은 컴포지터 스레드 성능을 유지하면서 재생·일시정지·역재생 같은 명령형 제어를 더한다.
- `currentTime`을 직접 조작하면 드래그·스크롤 같은 입력 이벤트에 애니메이션 진행률을 실시간으로 동기화할 수 있다.
- 단순 트랜지션은 CSS로, 동적 제어가 필요한 애니메이션은 WAAPI로 역할을 나누는 것이 유지보수에 유리하다.

## 참고 자료

- [MDN: Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)
- [MDN: Element.animate()](https://developer.mozilla.org/en-US/docs/Web/API/Element/animate)
- [W3C: Web Animations 명세](https://www.w3.org/TR/web-animations-1/)
