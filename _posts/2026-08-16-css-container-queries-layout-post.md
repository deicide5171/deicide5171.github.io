---
layout: single
title: "컨테이너 쿼리로 완성하는 진짜 컴포넌트 반응형 레이아웃"
date: 2026-08-16 13:30:00 +0530
categories: frontend
tags: ["css", "container-queries", "frontend", "responsive-design", "layout"]
toc: true
toc_sticky: true
excerpt: "미디어 쿼리로는 풀리지 않던 '같은 컴포넌트, 다른 위치' 문제를 컨테이너 쿼리와 컨테이너 쿼리 유닛으로 실제 카드 컴포넌트에 적용해 끝까지 구현해본다."
---

## 왜 지금 컨테이너 쿼리를 제대로 파야 하는가

디자인 시스템 기반 개발이 보편화되면서 "카드 하나"를 사이드바에도, 본문 그리드에도, 모달 안에도 그대로 재사용하는 일이 당연해졌다. 문제는 미디어 쿼리가 오직 뷰포트 폭만 본다는 점이다. 같은 카드 컴포넌트라도 좁은 사이드바에 들어갔는지 넓은 본문 컬럼에 들어갔는지는 뷰포트 기준으로는 알 방법이 없다. 그래서 실무에서는 오랫동안 `ResizeObserver`로 컴포넌트 크기를 감시하고 JS로 클래스를 토글하는 우회가 표준처럼 쓰였다.

Container Queries는 이 문제를 CSS 레벨에서 해결한다. 주요 브라우저의 지원이 안정화되면서 최근에는 shadcn/ui, Primer 계열을 비롯한 여러 컴포넌트 라이브러리와 디자인 시스템이 컨테이너 쿼리를 실제 컴포넌트 반응형 전략으로 채택하는 사례가 늘고 있고, `@container style()` 같은 스타일 쿼리도 후속 논의가 진행 중이다(다만 확정 스펙·지원 일정은 아직 유동적이므로 도입 전 반드시 최신 브라우저 호환성을 직접 확인해야 한다). 이번 글은 개념 나열이 아니라, 카드 컴포넌트 하나를 처음부터 끝까지 컨테이너 쿼리로 구현하는 데 집중한다.

## 핵심 개념 1: container-type — 컨테이너를 선언하는 세 가지 방법

컨테이너 쿼리를 쓰려면 먼저 부모 요소를 "컨테이너"로 선언해야 한다. 이때 `container-type` 값에 따라 어떤 축을 쿼리할 수 있는지, 그리고 어떤 부작용이 생기는지가 달라진다.

| 값 | 쿼리 가능 축 | 대표 부작용 |
|---|---|---|
| `inline-size` | 인라인 방향(보통 너비)만 | layout·style containment 발생, 자식 margin이 부모 밖으로 collapse 안 됨 |
| `size` | 너비·높이 모두 | 컨테이너 높이가 자식 콘텐츠에 의존하면 순환 참조로 무시됨(명시적 높이 필요) |
| `normal` | 쿼리 불가(기본값) | 없음 — 컨테이너로 동작하지 않음 |

실무에서는 대부분 `inline-size`만으로 충분하다. `size`는 높이까지 반응시켜야 하는 특수한 경우(예: 정사각형 그리드 셀)에만 쓰고, 컨테이너 자체에 고정 높이나 `aspect-ratio`를 지정해 순환 참조를 피해야 한다.

## 핵심 개념 2: 컨테이너 쿼리 유닛 — 폭이 아니라 "내부 비율"로 스케일링

컨테이너 쿼리와 함께 등장한 `cqw`, `cqh`, `cqi`, `cqb`, `cqmin`, `cqmax` 유닛은 뷰포트 단위(`vw`, `vh`)의 컨테이너 버전이다. 미디어 쿼리 breakpoint마다 값을 다시 지정하는 대신, 컨테이너 크기에 비례해 폰트·패딩이 자동으로 스케일된다.

| 유닛 | 기준 |
|---|---|
| `cqw` / `cqi` | 컨테이너의 인라인 크기(보통 너비)의 1% |
| `cqh` / `cqb` | 컨테이너의 블록 크기(보통 높이)의 1% |
| `cqmin` | `cqi`, `cqb` 중 작은 값 |
| `cqmax` | `cqi`, `cqb` 중 큰 값 |

<img src="/assets/images/posts/2026-08-16-css-container-queries-layout-1.svg" alt="미디어 쿼리는 뷰포트 폭만 보고 같은 카드를 그대로 유지하지만, 컨테이너 쿼리는 카드를 감싼 컨테이너 폭에 따라 세로형과 가로형으로 각각 바뀌는 것을 비교한 개념도" style="width:100%;">

## 핵심 예제: 카드 컴포넌트를 컨테이너 쿼리로 완성하기

아래는 하나의 `.card` 컴포넌트를 정의해 좁은 컨테이너에서는 세로 스택, 넓은 컨테이너에서는 가로 배치로 전환하고, 내부 요소 크기까지 컨테이너 비율로 스케일링하는 전체 예제다.

```css
/* 1) 카드를 감쌀 요소를 컨테이너로 선언 */
.card-slot {
  container-type: inline-size;
  container-name: card;
}

/* 2) 기본(좁은 컨테이너) 레이아웃: 세로 스택 */
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e2e5e9;
}

.card__thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
}

.card__title {
  font-size: clamp(14px, 5cqi, 20px); /* 컨테이너 폭 비례, 상하한 clamp */
}

/* 3) 컨테이너 폭이 일정 크기를 넘으면 가로 배치로 전환 */
@container card (min-width: 420px) {
  .card {
    flex-direction: row;
    align-items: center;
  }

  .card__thumb {
    width: 35%;
    aspect-ratio: 1 / 1;
  }
}

/* 4) 컨테이너가 아주 넓을 때는 여백까지 비례 확장 */
@container card (min-width: 640px) {
  .card {
    padding: 3cqw;
    gap: 3cqw;
  }
}
```

`.card` 자체가 아니라 `.card-slot`이라는 감싸는 요소에 `container-type`을 건다는 점이 핵심이다. 요소는 자기 자신의 크기를 스스로 쿼리할 수 없고, 반드시 조상 컨테이너의 크기를 기준으로 쿼리한다. `container-name: card`로 이름을 지정해두면 중첩된 컨테이너 사이에서도 `@container card (...)`처럼 어떤 컨테이너를 기준으로 삼는지 명시할 수 있어, 여러 겹의 컨테이너가 있는 실제 페이지에서 의도치 않은 컨테이너에 걸리는 실수를 막을 수 있다.

## 실무 포인트

- **`container-type: inline-size`는 새로운 containment 컨텍스트를 만든다.** 내부적으로 `contain: layout style` 이 함께 적용되어, 자식의 margin이 컨테이너 바깥으로 collapse되지 않는 등 레이아웃이 미묘하게 달라질 수 있다. 기존 스타일에 컨테이너를 추가할 때는 이 영향을 반드시 확인한다.
- **요소 자기 자신에는 쿼리를 걸 수 없다.** `.card`에 `container-type`과 `@container` 조건을 동시에 걸면 동작하지 않는다. 감싸는 부모(`.card-slot`)에 컨테이너를 선언하고, 자식(`.card`)에서 쿼리하는 구조를 지킨다.
- **이름 없는 컨테이너는 가장 가까운 조상을 자동으로 매칭한다.** 컴포넌트를 중첩해서 쓰는 디자인 시스템일수록 `container-name`을 명시해 의도한 컨테이너에만 스타일이 걸리도록 한다.
- **점진적 도입은 `@supports (container-type: inline-size)`로 감싼다.** 구형 환경 대상 서비스라면 미디어 쿼리 기반 기본 레이아웃을 먼저 정의하고, 컨테이너 쿼리를 지원 브라우저에 한해 덮어쓰는 방식이 안전하다.

## 3줄 요약

- 컨테이너 쿼리는 컴포넌트를 감싼 조상 요소를 `container-type`으로 선언하고, 그 조상의 크기를 기준으로 자식 스타일을 바꾸는 방식이다.
- `cqw`/`cqi`/`cqb` 같은 컨테이너 쿼리 유닛을 쓰면 breakpoint별로 값을 다시 쓰지 않고도 컨테이너 크기에 비례해 폰트·여백이 자동으로 스케일된다.
- `container-type: inline-size`가 만드는 containment 부작용과 이름 없는 컨테이너의 자동 매칭 문제를 미리 알고 `container-name`으로 명시하는 것이 실전 도입의 핵심이다.

## 참고 자료

- [MDN — CSS Container Queries](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries)
- [MDN — CSS Container Query Units](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries#container_query_length_units)
- [web.dev — New responsive design with container queries](https://web.dev/articles/cq-stable)
