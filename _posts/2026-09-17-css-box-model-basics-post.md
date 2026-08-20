---
layout: single
title: "CSS 박스 모델이 뭔가요 — margin, padding, border의 관계"
date: 2026-09-17 13:30:00 +0530
categories: frontend
tags: ["css", "박스모델", "margin", "padding", "입문"]
toc: true
toc_sticky: true
excerpt: "모든 HTML 요소가 사각형 박스로 그려지는 원리와 margin·padding·border·content의 관계를 처음 배우는 사람 기준으로 정리했다."
---

## 요소는 모두 사각형 박스다

CSS에서 모든 HTML 요소는 **사각형 박스**로 그려진다. 이 박스는 안쪽부터 **내용(content) → 안쪽 여백(padding) → 테두리(border) → 바깥 여백(margin)**의 층으로 이뤄진다. 이 구조를 **박스 모델(box model)**이라 한다. 레이아웃이 뜻대로 안 될 때 대부분 이 관계를 이해하면 풀린다.

## 네 층

| 영역 | 설명 |
|---|---|
| content | 실제 내용(글자·이미지) |
| padding | 내용과 테두리 사이 안쪽 여백 |
| border | 테두리 선 |
| margin | 다른 요소와의 바깥 여백 |

## 크기 계산 (box-sizing)

```text
기본(content-box):
  width는 내용만! padding·border는 별도로 더해짐
  width:100 + padding:20 + border:2 = 실제 124px

border-box:
  width에 padding·border 포함
  width:100이면 실제로도 100px (안에서 나눠 씀)
-> 대부분 box-sizing: border-box 를 권장
```

## 실무 포인트

- **`box-sizing: border-box`를 기본으로.** content-box는 width에 padding·border가 안 포함돼 크기 계산이 헷갈린다. 보통 전역으로 `* { box-sizing: border-box }`를 걸어 "width가 곧 실제 너비"가 되게 한다.
- **margin은 바깥, padding은 안쪽.** 배경색은 padding까지 칠해지고 margin에는 안 칠해진다. 요소 안쪽 간격은 padding, 요소 사이 간격은 margin이다.
- **margin 겹침(collapse)에 주의.** 위아래로 인접한 두 요소의 세로 margin은 합쳐지지 않고 큰 값 하나로 겹쳐진다. 간격이 예상과 다르면 이 현상을 의심한다.

## 마무리 요약

- 박스 모델은 모든 요소가 content→padding→border→margin 층으로 된 사각형 박스라는 개념이다.
- `box-sizing: border-box`를 쓰면 width에 padding·border가 포함돼 크기 계산이 직관적이다.
- padding은 안쪽·margin은 바깥 여백이며, 세로 margin 겹침 현상에 주의한다.

## 참고 자료

- [MDN - 박스 모델](https://developer.mozilla.org/ko/docs/Learn/CSS/Building_blocks/The_box_model)
