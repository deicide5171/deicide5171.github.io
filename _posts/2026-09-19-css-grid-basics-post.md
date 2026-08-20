---
layout: single
title: "CSS Grid가 뭔가요 — 2차원 레이아웃 시작하기"
date: 2026-09-19 12:30:00 +0530
categories: frontend
tags: ["css", "grid", "레이아웃", "그리드", "입문"]
toc: true
toc_sticky: true
excerpt: "행과 열을 동시에 다루는 2차원 레이아웃 도구 CSS Grid의 기본 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "카드들을 격자로 딱 맞게 배치하고 싶다"

이미지 갤러리나 대시보드처럼 행과 열이 모두 있는 배치는 Flexbox만으로는 번거롭다. **CSS Grid**는 행과 열을 동시에 정의하는 **2차원 레이아웃** 도구라, 이런 격자 배치에 잘 맞는다.

## 기본 사용법

```css
.container {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;  /* 3등분 열 */
  gap: 16px;                            /* 칸 사이 간격 */
}
```

`fr`은 남은 공간을 비율로 나누는 단위다. `1fr 1fr 1fr`은 세 열을 똑같이 나눈다. `repeat(3, 1fr)`로 줄여 쓸 수도 있다.

## 자주 쓰는 속성

| 속성 | 하는 일 |
|---|---|
| grid-template-columns | 열의 개수·너비 정의 |
| grid-template-rows | 행의 개수·높이 정의 |
| gap | 칸 사이 간격 |
| grid-column / grid-row | 특정 아이템이 차지할 칸 범위 |

## 반응형 격자

```css
.container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
```

`auto-fill` + `minmax`를 쓰면, 화면 폭에 맞춰 한 줄에 들어가는 카드 수가 자동으로 바뀐다. 미디어 쿼리 없이도 반응형 격자가 된다.

## 실무 포인트

- **2차원은 Grid, 1차원은 Flexbox.** 행·열을 모두 다루는 페이지 레이아웃은 Grid, 한 줄 안에서의 정렬·간격은 Flexbox가 편하다.
- **`fr`과 `gap`을 먼저 익혀라.** 이 둘만으로 대부분의 균등 격자를 만들 수 있다.
- **`minmax`로 찌그러짐 방지.** 최소 너비를 정하면 좁은 화면에서 칸이 너무 작아지는 것을 막는다.

## 마무리 요약

- CSS Grid는 행과 열을 동시에 정의하는 2차원 레이아웃 도구다.
- `grid-template-columns`, `fr`, `gap`으로 균등 격자를 쉽게 만든다.
- `auto-fill` + `minmax`로 미디어 쿼리 없이 반응형 격자를 구현한다.

## 참고 자료

- [MDN - CSS Grid Layout](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout)
