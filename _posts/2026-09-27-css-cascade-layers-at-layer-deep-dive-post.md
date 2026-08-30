---
layout: single
title: "CSS Cascade Layers(@layer) 딥다이브 — 명시도 전쟁을 구조적으로 끝내는 법"
date: 2026-09-27 13:30:00 +0530
categories: frontend
tags: ["CSS", "CascadeLayers", "atlayer", "명시도", "CSS아키텍처"]
toc: true
toc_sticky: true
excerpt: "!important와 점점 더 구체적인 셀렉터를 쌓아가며 명시도 전쟁을 벌이던 방식을, CSS Cascade Layers는 규칙을 명시적인 우선순위 레이어로 나눠 구조적으로 해결한다. 캐스케이드 알고리즘에서 @layer가 실제로 개입하는 지점을 정리했다."
---

## 왜 명시도만으로는 한계가 오는가

디자인 시스템, 서드파티 컴포넌트 라이브러리, 유틸리티 클래스(Tailwind 등), 팀의 커스텀 스타일이 한 프로젝트에 뒤섞이면 필연적으로 명시도 전쟁이 벌어진다. 라이브러리의 기본 스타일을 덮어쓰려고 셀렉터를 더 구체적으로 쓰거나 `!important`를 붙이면, 그 다음에 그걸 다시 덮어써야 하는 팀원은 한 단계 더 강한 셀렉터를 써야 한다. 이 악순환은 CSS 파일이 커질수록 유지보수를 불가능에 가깝게 만든다. CSS Cascade Layers는 이 문제의 근본 원인, 즉 "어떤 스타일이 이겨야 하는지"를 셀렉터의 구체성이 아니라 **명시적으로 선언한 레이어 순서**로 결정하게 해준다.

## 핵심 개념 1 — 캐스케이드 알고리즘에서 레이어가 개입하는 위치

CSS의 캐스케이드는 여러 단계를 거쳐 어떤 선언이 이길지 결정한다. 단순화하면 origin(사용자 에이전트/사용자/저작자 스타일)과 importance(`!important` 여부) → **레이어 순서** → 명시도(specificity) → 소스 코드 순서(나중에 온 것이 이김) 순으로 우선순위가 매겨진다. 중요한 것은 레이어 순서가 명시도보다 **먼저** 개입한다는 점이다. 즉 나중에 선언된 레이어 안의 규칙은, 설령 그 안의 셀렉터가 `.a`처럼 명시도가 낮아도, 먼저 선언된 레이어 안에 있는 `#id .very .specific .selector`보다 항상 이긴다. 명시도 비교는 오직 **같은 레이어 안에서만** 의미를 갖는다. 이것이 레이어가 "명시도 전쟁을 끝낸다"고 표현되는 이유다.

## 핵심 개념 2 — 레이어가 없는 스타일은 항상 가장 강하다

주의할 점 하나는 `@layer`로 감싸지 않은 일반 CSS 규칙(unlayered style)이 **모든 레이어보다 우선한다**는 것이다. 레이어는 "이 스타일들을 서로 비교할 때의 순서"를 정의하는 것이고, 레이어에 속하지 않은 규칙은 캐스케이드에서 가장 마지막(가장 강한) 지점에 위치한다. 그래서 실무 패턴은 서드파티 라이브러리와 리셋을 낮은 우선순위 레이어에 넣고, 팀의 컴포넌트 스타일은 그보다 높은 레이어에 두며, 정말 예외적으로 무조건 이겨야 하는 유틸리티(예: `.hidden { display: none !important; }` 없이도 항상 이겨야 하는 규칙)는 레이어 밖에 그대로 두는 것이다.

| 우선순위(낮음→높음) | 대상 |
|---|---|
| 1. 낮은 우선순위 레이어 | 서드파티 라이브러리, CSS 리셋 |
| 2. 높은 우선순위 레이어 | 팀의 컴포넌트/디자인 시스템 스타일 |
| 3. 레이어에 속하지 않은 규칙(unlayered) | 항상 최우선 — 신중하게 사용 |
| (모든 경우 예외) `!important` | 레이어 순서를 역전시킴(단, 레이어 간 importance는 순서가 반대로 적용) |

## 코드 예제 — 레이어 선언과 순서 제어

```css
/* 레이어 순서를 먼저 명시적으로 선언 — 이후 실제 내용이 어느 순서로 로드되든
   이 선언 순서(reset -> library -> components -> utilities)가 우선순위를 결정한다 */
@layer reset, library, components, utilities;

@layer reset {
  * { margin: 0; padding: 0; box-sizing: border-box; }
}

@layer library {
  .btn { background: gray; padding: 8px 16px; }
}

@layer components {
  /* 명시도가 .btn과 같은 클래스 선택자여도, 더 높은 레이어이므로 항상 이긴다 */
  .btn { background: var(--brand-color); border-radius: 8px; }
}

/* 외부 라이브러리 CSS를 통째로 낮은 레이어로 강제 편입시킬 수도 있다 */
@import url("third-party.css") layer(library);
```

## 실무 포인트

- **레이어 순서는 선언 시점이 아니라 첫 등장 순서로 고정된다.** `@layer reset, library, components;`처럼 이름만 먼저 나열해 순서를 명시적으로 확정해두면, 실제 스타일 내용이 파일 어디에 흩어져 있든 안전하게 그 순서를 유지한다. 이 선언을 빠뜨리면 각 레이어의 순서는 CSS에서 처음 등장한 순서로 암묵적으로 결정되어 예측이 어려워진다.
- **`!important`와 결합하면 순서가 역전된다.** 레이어 안에서 `!important`를 쓰면, 일반 선언과 반대로 **먼저 선언된 레이어의 `!important`가 나중 레이어보다 우선**한다. 레이어와 `!important`를 섞어 쓸수록 예측이 어려워지므로 가급적 피하는 것이 좋다.
- **브라우저 지원을 확인하고 점진적으로 도입하라.** 모던 브라우저는 대부분 지원하지만, 레거시 지원이 필요한 프로젝트라면 `@supports (background: paint(x))`처럼 폴백 전략 없이 통째로 마이그레이션하는 것은 위험하다. 새로 작성하는 컴포넌트부터 레이어를 적용하는 점진적 도입이 현실적이다.

## 마무리 요약

- Cascade Layers는 명시도보다 먼저 개입하는 레이어 순서를 도입해, 셀렉터 구체성 경쟁 없이도 어떤 스타일이 이길지 명시적으로 통제할 수 있게 한다.
- 레이어에 속하지 않은 일반 규칙은 모든 레이어보다 강하므로, 서드파티/리셋을 낮은 레이어에 격리하고 팀 스타일을 그 위 레이어에 두는 구조가 표준 패턴이다.
- `@layer` 이름만 먼저 선언해 순서를 고정하고, `!important`와의 역전 규칙을 이해한 뒤 점진적으로 도입하는 것이 안전하다.

## 참고 자료

- [MDN — CSS Cascade Layers](https://developer.mozilla.org/en-US/docs/Web/CSS/@layer)
- [web.dev — The Future of CSS: Cascade Layers](https://web.dev/articles/css-cascade-layers)
