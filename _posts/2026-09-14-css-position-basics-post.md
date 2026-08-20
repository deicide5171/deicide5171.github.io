---
layout: single
title: "CSS position이 뭔가요 — relative, absolute 헷갈림 정리"
date: 2026-09-14 12:30:00 +0530
categories: frontend
tags: ["css", "position", "레이아웃", "웹", "입문"]
toc: true
toc_sticky: true
excerpt: "요소의 위치를 정하는 CSS position 속성(static·relative·absolute·fixed·sticky)의 차이를 처음 배우는 사람 기준으로 정리했다."
---

## 요소를 원하는 위치에 두고 싶은데 안 된다

`top`, `left`로 요소를 옮기려는데 꿈쩍도 안 하는 경험이 흔하다. 이는 **position** 속성 때문이다. position은 요소가 **어떤 기준으로 배치되고, top/left 같은 위치 값이 먹히는지**를 정한다.

## position 값

| 값 | 설명 |
|---|---|
| static | 기본값. 문서 흐름대로(위치값 무시) |
| relative | 원래 자리 기준으로 이동 |
| absolute | 가장 가까운 위치 지정 조상 기준 |
| fixed | 화면(뷰포트) 기준 고정 |
| sticky | 스크롤하다 특정 지점에서 고정 |

## 핵심 관계

```text
absolute 요소는 "가장 가까운 position이 static이 아닌 조상"을 기준으로 배치된다.
-> 부모를 기준으로 삼고 싶으면
   부모에 position: relative 를 주고
   자식에 position: absolute 를 준다 (아주 흔한 패턴)
```

## 실무 포인트

- **static에는 위치값이 안 먹는다.** `top`/`left`가 안 통하면 십중팔구 position이 기본값(static)이다. `relative`나 `absolute`를 먼저 지정해야 위치 값이 적용된다.
- **relative 부모 + absolute 자식 패턴.** 배지·툴팁·닫기 버튼을 특정 요소 위에 겹쳐 놓을 때, 부모에 `relative`, 자식에 `absolute`를 주는 것이 정석이다. 이러면 자식이 부모 기준으로 정확히 배치된다.
- **fixed·sticky는 헤더에 유용.** 스크롤해도 항상 보이는 상단바는 `fixed`, 특정 위치까지 스크롤되면 붙는 메뉴는 `sticky`를 쓴다. sticky는 부모 영역을 벗어나면 다시 흐른다는 점을 기억한다.

## 마무리 요약

- position은 요소의 배치 기준과 위치 값(top/left) 적용 여부를 정한다.
- static(기본)엔 위치값이 안 먹고, relative(원래 자리)·absolute(조상 기준)·fixed(화면)·sticky(스크롤 고정)가 있다.
- "relative 부모 + absolute 자식"이 겹치기 배치의 정석 패턴이다.

## 참고 자료

- [MDN - position](https://developer.mozilla.org/ko/docs/Web/CSS/position)
