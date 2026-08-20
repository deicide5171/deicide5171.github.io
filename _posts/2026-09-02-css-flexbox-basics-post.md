---
layout: single
title: "CSS Flexbox 기초 — justify-content와 align-items 헷갈리지 않기"
date: 2026-09-02 12:30:00 +0530
categories: frontend
tags: ["css", "flexbox", "레이아웃", "입문", "프론트엔드기초"]
toc: true
toc_sticky: true
excerpt: "CSS Flexbox를 배울 때 가장 헷갈리는 justify-content와 align-items의 차이를, 축(axis) 개념으로 명확하게 정리했다."
---

## 왜 이 두 속성이 항상 헷갈리는가

Flexbox를 처음 배우면 "가로 정렬은 justify-content인가 align-items인가"를 매번 검색하게 된다. 이 둘을 헷갈리는 근본 원인은 **주축(main axis)과 교차축(cross axis)** 개념을 모르고 "가로/세로"로만 외우려 하기 때문이다. Flexbox는 방향이 고정되어 있지 않아서, `flex-direction`이 바뀌면 가로/세로 의미도 함께 바뀐다.

## 핵심 개념: 주축과 교차축

| 속성 | 어느 축을 정렬하나 | 기본값(row) 기준 |
|---|---|---|
| `justify-content` | 주축(main axis) 정렬 | 가로 방향 정렬 |
| `align-items` | 교차축(cross axis) 정렬 | 세로 방향 정렬 |
| `flex-direction: row` | 주축 = 가로 | justify-content가 가로를 담당 |
| `flex-direction: column` | 주축 = 세로 | justify-content가 세로를 담당 |

`flex-direction`이 `row`일 때는 주축이 가로라서 `justify-content`가 가로 정렬을, `align-items`가 세로 정렬을 맡는다. 하지만 `column`으로 바꾸면 주축이 세로로 바뀌면서 두 속성의 실제 정렬 방향도 서로 뒤바뀐다.

## 코드 예제: 정중앙 정렬

```css
.container {
  display: flex;
  justify-content: center; /* 주축(기본은 가로) 방향 가운데 정렬 */
  align-items: center;     /* 교차축(기본은 세로) 방향 가운데 정렬 */
  height: 300px;
}
```

이 두 줄만 있으면 컨테이너 안의 요소를 가로·세로 정중앙에 배치할 수 있다. Flexbox 이전에는 정중앙 정렬을 위해 `position: absolute`와 `transform`을 조합하는 등 번거로운 방법을 써야 했다.

## flex-direction을 바꾸면 생기는 변화

```css
/* row(기본값): justify-content가 가로, align-items가 세로 */
.row-container {
  display: flex;
  flex-direction: row;
  justify-content: space-between; /* 가로로 양 끝 정렬 */
}

/* column: justify-content가 세로, align-items가 가로 */
.column-container {
  display: flex;
  flex-direction: column;
  justify-content: space-between; /* 이제는 세로로 양 끝 정렬! */
}
```

같은 `justify-content: space-between`이라도 `flex-direction`에 따라 실제로 적용되는 방향이 완전히 달라진다는 것이 초보자가 가장 자주 놓치는 부분이다.

## 실무 포인트

- **"justify는 주축, align은 교차축"이라는 규칙만 외우면 flex-direction이 바뀌어도 헷갈리지 않는다.** 가로/세로로 암기하지 말고 축 개념으로 이해하는 것이 근본적인 해결책이다.
- **자식 요소 개별 정렬이 필요하면 `align-self`를 쓴다.** `align-items`는 컨테이너 안의 모든 자식에게 적용되지만, 특정 자식만 다르게 정렬하고 싶을 때는 그 자식에 `align-self`를 지정한다.
- **`gap` 속성을 쓰면 자식 요소 사이 간격을 마진 계산 없이 간단히 줄 수 있다.** 예전에는 마지막 요소의 마진을 따로 제거하는 트릭이 필요했지만 `gap`으로 훨씬 깔끔해졌다.

## 마무리 요약

- justify-content는 주축을, align-items는 교차축을 정렬한다는 것이 핵심 규칙이다.
- flex-direction이 row에서 column으로 바뀌면 두 속성이 담당하는 실제 방향도 서로 바뀐다.
- 가로/세로로 암기하지 말고 축 개념으로 이해하면 Flexbox 레이아웃을 훨씬 수월하게 다룰 수 있다.

## 참고 자료

- [MDN - Flexbox 기본 개념](https://developer.mozilla.org/ko/docs/Web/CSS/CSS_flexible_box_layout/Basic_concepts_of_flexbox)
- [CSS-Tricks - A Complete Guide to Flexbox](https://css-tricks.com/snippets/css/a-guide-to-flexbox/)
