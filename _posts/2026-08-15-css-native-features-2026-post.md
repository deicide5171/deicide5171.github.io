---
layout: single
title: "2026년, JS 없이 CSS만으로 되는 것들 — Container Queries, :has(), Anchor Positioning"
date: 2026-08-15 11:30:00 +0530
categories: frontend
tags: ["css", "frontend", "container-queries", "anchor-positioning", "web-performance"]
toc: true
toc_sticky: true
excerpt: "React Compiler와 시그널이 프레임워크 쪽 자동화를 밀어붙이는 동안, CSS 자체도 컨테이너 쿼리·:has()·앵커 포지셔닝으로 예전엔 JS가 필요했던 문제들을 흡수하고 있다. 2026년 기준 실전 활용법을 정리한다."
---

## 왜 지금 CSS 네이티브 기능인가

React Compiler가 메모이제이션을 컴파일 타임으로 넘기고, 시그널 기반 반응성이 프레임워크 경계를 넘나드는 것처럼, 프런트엔드는 지난 몇 년간 "런타임 JS가 하던 일을 어떻게 더 앞단으로 옮길까"를 계속 고민해왔다. 같은 흐름이 CSS에서도 일어나고 있다. 부모 요소를 선택하는 셀렉터, 컴포넌트 크기 기준 반응형, 팝업 위치 계산까지 — 몇 년 전만 해도 JS 라이브러리 없이는 불가능하다고 여겨지던 것들이 이제 순수 CSS만으로 된다.

이 변화가 중요한 이유는 단순히 "코드 몇 줄이 줄어든다"가 아니다. **레이아웃·위치 계산을 브라우저 엔진이 직접 처리하면 JS 번들 크기와 실행 비용이 줄고, 리플로우 타이밍도 브라우저가 최적화한 값을 그대로 쓸 수 있다.** Interaction to Next Paint 같은 지표가 중요해질수록 이런 네이티브 기능의 가치가 커진다.

## 핵심 개념 1: Container Queries — 화면이 아니라 컴포넌트 기준 반응형

기존 미디어 쿼리는 뷰포트(화면) 크기만 기준으로 삼는다. 그래서 같은 카드 컴포넌트를 사이드바에 넣을 때와 본문 영역에 넣을 때 서로 다른 스타일을 적용하려면 컴포넌트 바깥에서 클래스를 갈아 끼우는 수밖에 없었다. **컨테이너 쿼리**는 컴포넌트를 감싼 컨테이너 자체의 너비를 기준으로 스타일을 바꾼다.

<img src="/assets/images/posts/2026-08-15-css-native-features-2026-1.svg" alt="같은 카드 컴포넌트가 컨테이너 너비에 따라 세로 배치와 가로 배치로 전환되는 개념도" style="width:100%;">

```css
.card-container {
  container-type: inline-size;
  container-name: card;
}

.card {
  display: flex;
  flex-direction: column;
}

@container card (min-width: 401px) {
  .card {
    flex-direction: row; /* 넓은 컨테이너에서는 가로 배치 */
  }
}
```

같은 `.card` 컴포넌트가 어디에 배치되든 자기 자신의 실제 너비만 보고 레이아웃을 결정하므로, 디자인 시스템 컴포넌트를 여러 위치에 재사용할 때 특히 유용하다.

## 핵심 개념 2: `:has()` — 드디어 생긴 "부모 선택자"

CSS는 오랫동안 "자식 상태를 보고 부모 스타일을 바꾸는" 셀렉터가 없었다. `:has()`는 이 공백을 메운다.

```css
/* 이미지가 있는 카드에만 그림자 적용 */
.card:has(img) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 유효성 검사 실패한 입력이 있는 폼에 경고 테두리 */
form:has(input:invalid) {
  border: 1px solid #e05252;
}

/* 다음 형제가 아니라 "체크된 라디오 다음의 특정 요소" 스타일링 */
.radio-group:has(input:checked + .label-extra) .detail-panel {
  display: block;
}
```

이전에는 이런 조건을 처리하려면 JS로 자식 요소 상태를 감시해 부모에 클래스를 붙였다 뗐다 해야 했다. `:has()`는 이 로직을 선언적 CSS로 옮긴다.

## 핵심 개념 3: CSS Anchor Positioning — 툴팁·팝오버 위치 계산을 JS 없이

드롭다운, 툴팁, 팝오버의 위치를 트리거 요소 기준으로 계산하는 것은 대표적으로 JS 라이브러리(Floating UI 등)에 의존해온 영역이다. **CSS Anchor Positioning**은 `anchor-name`과 `position-anchor`, `anchor()` 함수로 이 계산을 CSS 레벨에서 처리한다.

```css
.trigger-button {
  anchor-name: --my-anchor;
}

.tooltip {
  position: absolute;
  position-anchor: --my-anchor;
  top: anchor(bottom); /* 트리거 요소 바로 아래 */
  left: anchor(center); /* 가로 중앙 정렬 */
  margin-top: 8px;
}
```

## JS 솔루션 vs CSS 네이티브 기능 비교

| 요구사항 | 기존 JS 솔루션 | CSS 네이티브 기능 |
|---|---|---|
| 컴포넌트 크기 기준 반응형 | ResizeObserver + 클래스 토글 | Container Queries |
| 자식 상태 기반 부모 스타일링 | JS로 클래스 추가/제거 | `:has()` |
| 툴팁/팝오버 위치 계산 | Floating UI, Popper.js | Anchor Positioning |

## 실무 포인트

- **브라우저 지원 범위를 먼저 확인한다**: Container Queries와 `:has()`는 주요 브라우저에 안정적으로 자리 잡았지만, Anchor Positioning은 상대적으로 늦게 표준화된 기능이라 대상 사용자층의 브라우저 버전을 확인해야 한다.
- **점진적 향상(progressive enhancement)으로 접근한다**: `@supports`로 네이티브 기능 지원 여부를 검사하고, 미지원 브라우저에는 기존 JS 라이브러리를 폴백으로 유지하는 것이 안전하다.
- **`:has()`는 성능을 함께 고려한다**: 셀렉터 평가 비용이 일반 셀렉터보다 크므로, 문서 전체를 훑는 광범위한 셀렉터보다는 범위를 좁힌 셀렉터로 사용하는 것이 좋다.
- **디자인 시스템 컴포넌트부터 컨테이너 쿼리로 전환한다**: 여러 컨텍스트에서 재사용되는 카드·리스트 아이템류 컴포넌트가 컨테이너 쿼리 도입 효과가 가장 크다.

## 3줄 요약

- Container Queries는 화면이 아니라 컴포넌트를 감싼 컨테이너의 너비 기준으로 스타일을 바꿔 재사용 가능한 반응형 컴포넌트를 만든다.
- `:has()`는 자식 상태를 보고 부모 스타일을 바꾸는 오랜 공백을 메워 JS로 하던 클래스 토글 로직을 선언적 CSS로 옮긴다.
- Anchor Positioning은 툴팁·팝오버 위치 계산을 CSS 레벨로 가져오지만, 상대적으로 늦게 표준화된 만큼 브라우저 지원 범위와 폴백 전략을 함께 챙겨야 한다.

## 참고 자료

- [MDN — CSS Container Queries](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries)
- [MDN — `:has()` pseudo-class](https://developer.mozilla.org/en-US/docs/Web/CSS/:has)
- [MDN — CSS Anchor Positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_anchor_positioning)
