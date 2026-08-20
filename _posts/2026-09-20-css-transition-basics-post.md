---
layout: single
title: "CSS 트랜지션이 뭔가요 — 부드러운 상태 변화 만들기"
date: 2026-09-20 13:30:00 +0530
categories: frontend
tags: ["css", "transition", "애니메이션", "인터랙션", "입문"]
toc: true
toc_sticky: true
excerpt: "hover 등 상태가 바뀔 때 값이 부드럽게 변하도록 하는 CSS transition의 기본 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "버튼 색이 순간적으로 딱 바뀌어 어색하다"

`:hover`로 색을 바꾸면 값이 순식간에 튀어 딱딱해 보인다. **CSS 트랜지션(transition)**은 이런 값 변화가 **정해진 시간에 걸쳐 부드럽게** 이어지도록 해준다. 자바스크립트 없이 간단한 인터랙션을 만드는 기본 도구다.

## 기본 사용법

```css
.button {
  background: #03c75a;
  transition: background 0.3s ease;  /* 배경색을 0.3초에 걸쳐 */
}
.button:hover {
  background: #02a94c;               /* 부드럽게 변함 */
}
```

`transition: 속성 시간 이징` 형태다. 상태가 바뀔 때(hover, 클래스 토글 등) 그 속성이 지정 시간 동안 서서히 변한다.

## 자주 쓰는 값

| 부분 | 의미 | 예 |
|---|---|---|
| property | 어떤 속성을 | background, transform, opacity |
| duration | 얼마 동안 | 0.3s, 200ms |
| timing | 변화 곡선 | ease, linear, ease-in-out |

## 실무 포인트

- **transform·opacity를 애니메이션하라.** 이 둘은 레이아웃을 다시 계산하지 않아 부드럽고 성능이 좋다. `width`·`top` 같은 값은 렌더링 부담이 크다.
- **`all`은 남발하지 마라.** `transition: all`은 모든 속성을 대상으로 해 의도치 않은 변화까지 애니메이션되고 성능도 나빠진다. 대상 속성을 명시한다.
- **여러 속성은 콤마로.** `transition: background 0.3s, transform 0.2s`처럼 나눠 지정할 수 있다.

## 마무리 요약

- CSS 트랜지션은 상태가 바뀔 때 값이 지정 시간에 걸쳐 부드럽게 변하게 한다.
- `속성 시간 이징` 형태로 쓰며, hover·클래스 토글 등과 함께 쓴다.
- 성능을 위해 transform·opacity를 쓰고, `all` 남발과 무거운 속성은 피한다.

## 참고 자료

- [MDN - CSS transitions](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_transitions/Using_CSS_transitions)
