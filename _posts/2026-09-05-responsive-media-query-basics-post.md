---
layout: single
title: "반응형 웹 기초 — 미디어 쿼리와 모바일 퍼스트"
date: 2026-09-05 13:30:00 +0530
categories: frontend
tags: ["반응형웹", "미디어쿼리", "css", "모바일퍼스트", "입문"]
toc: true
toc_sticky: true
excerpt: "화면 크기에 따라 레이아웃이 바뀌는 반응형 웹의 핵심인 미디어 쿼리와 모바일 퍼스트 접근을 처음 배우는 사람 기준으로 정리했다."
---

## 하나의 페이지로 PC와 모바일을 모두

같은 웹 페이지가 PC에서는 넓게, 모바일에서는 좁게 잘 보이려면 화면 크기에 따라 레이아웃이 바뀌어야 한다. **반응형 웹(Responsive Web)**은 하나의 HTML/CSS로 다양한 화면 크기에 대응하는 방식이며, 그 핵심 도구가 **미디어 쿼리(media query)**다.

## 미디어 쿼리 기본 문법

```css
/* 기본 스타일 (모든 화면) */
.container { display: flex; }

/* 화면 폭이 768px 이하일 때만 적용 */
@media (max-width: 768px) {
  .container {
    flex-direction: column; /* 모바일에서는 세로로 쌓기 */
  }
}
```

`@media (조건) { ... }` 안의 스타일은 그 조건(화면 폭 등)이 맞을 때만 적용된다. 위 예제는 화면이 좁아지면 가로 배치를 세로 배치로 바꾼다.

## 모바일 퍼스트 vs 데스크톱 퍼스트

| 접근 | 방식 | 미디어 쿼리 |
|---|---|---|
| 모바일 퍼스트 | 모바일 기본 스타일 → 넓어지면 확장 | `min-width` 사용 |
| 데스크톱 퍼스트 | PC 기본 스타일 → 좁아지면 축소 | `max-width` 사용 |

```css
/* 모바일 퍼스트: 기본은 모바일, 넓어지면 데스크톱 스타일 추가 */
.menu { flex-direction: column; } /* 기본: 모바일 */

@media (min-width: 768px) {
  .menu { flex-direction: row; } /* 넓어지면 가로로 */
}
```

최근에는 **모바일 퍼스트**가 권장된다. 모바일 사용자가 많고, 작은 화면에서 시작해 확장하는 것이 스타일 관리가 더 깔끔하기 때문이다.

## 반응형의 필수 준비물

```html
<!-- 이 태그가 없으면 모바일에서 반응형이 제대로 안 먹는다 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

이 viewport 메타 태그는 "화면 폭을 실제 기기 폭에 맞춰라"는 지시다. 이게 없으면 모바일 브라우저가 PC 화면을 축소해서 보여줘, 미디어 쿼리가 의도대로 동작하지 않는다.

## 실무 포인트

- **px 대신 상대 단위(rem, %, vw)를 활용하라.** 고정 px로만 짜면 다양한 화면에 유연하게 대응하기 어렵다. 폰트는 `rem`, 너비는 `%`나 `max-width`를 섞어 쓰면 훨씬 부드럽게 반응한다.
- **미디어 쿼리 없이도 되는 것은 미디어 쿼리 없이 하라.** Flexbox의 `flex-wrap`, CSS Grid의 `auto-fit`, `clamp()` 함수 등을 쓰면 브레이크포인트를 잘게 나누지 않고도 유연한 레이아웃을 만들 수 있다.
- **실제 기기나 브라우저 개발자 도구의 반응형 모드로 확인하라.** 코드만 보고 판단하지 말고, 여러 화면 폭에서 실제로 어떻게 보이는지 눈으로 확인하는 것이 필수다.

## 마무리 요약

- 반응형 웹은 하나의 HTML/CSS로 다양한 화면 크기에 대응하며, 핵심 도구는 미디어 쿼리다.
- 모바일 퍼스트(min-width)로 작은 화면부터 확장하는 방식이 최근 권장된다.
- viewport 메타 태그는 반응형의 필수 전제이며, 상대 단위와 Flexbox/Grid를 함께 쓰면 더 유연해진다.

## 참고 자료

- [MDN - 미디어 쿼리](https://developer.mozilla.org/ko/docs/Web/CSS/CSS_media_queries/Using_media_queries)
- [MDN - 반응형 디자인](https://developer.mozilla.org/ko/docs/Learn/CSS/CSS_layout/Responsive_Design)
