---
layout: single
title: "무한 스크롤 구현하기 — Intersection Observer vs scroll 이벤트 성능 비교"
date: 2026-09-22 12:30:00 +0530
categories: frontend
tags: ["intersectionobserver", "무한스크롤", "스크롤이벤트", "웹성능", "자바스크립트"]
toc: true
toc_sticky: true
excerpt: "스크롤 이벤트 리스너로 만든 무한 스크롤이 스크롤할 때마다 버벅이는 문제를, Intersection Observer API로 다시 구현해 해결하는 방법과 두 방식의 성능 차이를 정리했다."
---

## 왜 scroll 이벤트로 만든 무한 스크롤이 버벅이나

목록 하단에 도달하면 다음 페이지를 자동으로 불러오는 무한 스크롤은 이제 거의 표준적인 UX 패턴이 됐다. 이 기능을 처음 구현할 때 대부분 `window.addEventListener('scroll', ...)`으로 스크롤 위치를 계속 확인하다가, 사용자의 스크롤 위치가 문서 하단 근처에 도달하면 다음 데이터를 불러오는 방식을 떠올린다. 직관적이고 동작도 하지만, 실제 서비스에 넣고 나면 스크롤할 때마다 화면이 살짝씩 끊기는 느낌을 받는다.

이유는 `scroll` 이벤트가 **초당 수십~수백 번씩 발생**하는 매우 빈번한 이벤트이기 때문이다. 이 이벤트가 발생할 때마다 콜백 함수 안에서 `getBoundingClientRect()`나 `scrollTop`, `offsetHeight` 같은 값을 읽으면, 브라우저는 그 값을 정확히 계산하기 위해 레이아웃을 강제로 다시 계산(reflow)한다. 스크롤이 빈번하게 발생하는 상황에서 매번 레이아웃을 다시 계산하면, 메인 스레드가 그 작업으로 붙잡혀 실제 스크롤 렌더링이 밀리는 현상, 즉 버벅임(jank)이 발생한다.

## 잘못된 접근: 쓰로틀링만으로 버티기

이 문제를 처음 마주치면 흔히 `throttle`이나 `debounce`로 이벤트 처리 빈도를 줄이는 방법을 먼저 시도한다.

```javascript
// 쓰로틀링으로 완화는 되지만 근본 해결은 아니다
let ticking = false;
window.addEventListener('scroll', () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
      if (scrollHeight - scrollTop - clientHeight < 300) {
        loadNextPage();
      }
      ticking = false;
    });
    ticking = true;
  }
});
```

쓰로틀링은 콜백 실행 빈도를 줄여줄 뿐, `scroll` 이벤트 자체가 여전히 매 프레임 발생하고 레이아웃 값을 읽는 로직도 여전히 남아있다는 근본 구조는 바뀌지 않는다. 저사양 기기나 목록 아이템 수가 많아 DOM이 무거워진 페이지에서는 여전히 체감되는 지연이 남는다.

## 올바른 접근: Intersection Observer로 관찰 위임하기

Intersection Observer API는 "특정 요소가 화면(뷰포트)에 들어오는지"를 브라우저가 직접, 비동기적으로 감지하게 위임하는 방식이다. 개발자는 스크롤 위치를 직접 계산하지 않고, 감지하고 싶은 대상 요소 하나만 등록하면 된다.

```javascript
const sentinel = document.querySelector('#load-more-trigger');

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        loadNextPage();
      }
    });
  },
  { root: null, rootMargin: '300px', threshold: 0 }
);

observer.observe(sentinel);
```

목록 맨 아래에 눈에 보이지 않는 `sentinel`(감지용) 요소를 하나 두고, 이 요소가 뷰포트에 들어오는 순간 콜백이 호출되도록 등록한다. `rootMargin: '300px'`을 주면 sentinel이 실제 화면에 닿기 300px 전에 미리 콜백이 실행되므로, 사용자가 스크롤 끝에 닿기 전에 다음 페이지를 미리 불러와 자연스러운 경험을 만들 수 있다.

<img src="/assets/images/posts/2026-09-22-infinite-scroll-intersection-observer-1.svg" alt="scroll 이벤트 방식은 매 프레임 레이아웃을 재계산하고 Intersection Observer 방식은 브라우저 렌더링 엔진이 비동기로 교차 여부만 알려주는 구조를 비교하는 다이어그램" style="width:100%;">

## 두 방식의 핵심 차이

| 항목 | scroll 이벤트 | Intersection Observer |
|---|---|---|
| 실행 빈도 | 스크롤마다 초당 수십~수백 회 | 교차 상태가 바뀔 때만 |
| 레이아웃 계산 | 콜백 안에서 직접 읽어 강제 reflow 유발 | 브라우저가 렌더링 파이프라인 내에서 비동기 처리 |
| 메인 스레드 부담 | 큼 | 작음 |
| 구현 복잡도 | 쓰로틀링·디바운싱 로직 직접 관리 필요 | 옵저버 등록만으로 대부분 해결 |

Intersection Observer는 브라우저 렌더링 엔진 내부에서 교차 여부를 계산하고, 그 결과가 바뀔 때만 메인 스레드의 자바스크립트 콜백을 호출한다. 즉 "관찰"이라는 작업 자체를 메인 스레드 바깥으로 넘긴다는 점이 scroll 이벤트 방식과의 근본적인 차이다.

## 실무 포인트

- **sentinel 요소는 리스트 마지막 항목이 아니라 별도의 빈 요소로 두는 편이 안전하다.** 리스트 아이템 자체를 관찰 대상으로 쓰면 아이템이 교체·재정렬될 때 옵저버 등록이 꼬일 수 있다.
- **로딩 중 중복 요청을 반드시 막아라.** `rootMargin`으로 미리 트리거되는 특성상, 네트워크 응답이 오기 전에 같은 콜백이 다시 호출될 수 있다. 로딩 플래그로 중복 호출을 차단해야 한다.
- **마지막 페이지에 도달하면 옵저버를 반드시 해제하라.** `observer.disconnect()`를 호출하지 않으면 더 이상 필요 없는 감시가 계속 유지되어 메모리 누수로 이어질 수 있다.
- **DOM이 매우 무거운 리스트라면 가상 스크롤(virtualization)과 함께 고려하라.** Intersection Observer가 스크롤 감지 자체는 가볍게 해결해주지만, 화면에 렌더링된 DOM 노드 수 자체가 많으면 별도의 최적화가 필요하다.

## 마무리 요약

- scroll 이벤트로 만든 무한 스크롤은 매 프레임 레이아웃 값을 읽어 reflow를 유발하므로 스크롤이 잦은 페이지에서 버벅임을 일으킨다.
- Intersection Observer는 요소의 뷰포트 교차 여부 감지를 브라우저에 위임해 메인 스레드 부담을 크게 줄인다.
- rootMargin으로 미리 로딩을 트리거하고, 로딩 중복 방지와 옵저버 해제를 함께 처리해야 실전에서 안정적으로 동작한다.

## 참고 자료

- [MDN - Intersection Observer API](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API)
- [web.dev - Intersection Observer v2](https://web.dev/articles/intersectionobserver-v2)
