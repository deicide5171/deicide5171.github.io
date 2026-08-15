---
layout: single
title: "Signals의 시대 — Vue·Solid·Angular가 반응성을 다시 설계한 이유"
date: 2026-08-18 12:30:00 +0530
categories: frontend
tags: ["signals", "reactivity", "vue", "solidjs", "angular"]
toc: true
toc_sticky: true
excerpt: "리렌더링 최적화 대신 세밀한 의존성 추적으로 방향을 튼 Signals 패러다임을 Vue, Solid, Angular 세 프레임워크의 구현 방식으로 비교해 정리한다."
---

## 왜 지금 Signals인가

React 진영이 오래도록 "컴포넌트를 다시 실행하고 Virtual DOM을 diff해서 최소 변경분만 반영한다"는 모델을 다듬어온 사이, 다른 프레임워크들은 아예 다른 길을 택했다. **Signals**는 상태 값을 변수가 아니라 "구독 가능한 컨테이너"로 다루고, 그 값을 실제로 읽은 코드(계산식·이펙트·DOM 바인딩)만 자동으로 다시 실행시키는 세밀한(fine-grained) 반응성 모델이다. 컴포넌트 함수 전체를 다시 실행할 필요 자체가 없어진다.

SolidJS가 이 개념을 프레임워크 차원에서 대중화한 이후, Vue 3의 반응성 코어(`ref`/`reactive`)가 사실상 동일한 원리로 재구성됐고, Angular도 최근 메이저 버전들에서 `signal()`을 1급 API로 승격시키며 Zone.js 의존을 줄이는 방향으로 옮겨가고 있다. 여기에 더해 TC39에는 프레임워크 간 Signals 구현을 표준화하려는 제안(Signals proposal)이 초기 단계로 논의되고 있어, "각 프레임워크가 결국 같은 문제를 각자 풀고 있다"는 인식이 커지는 중이다. 정확한 채택 시점이나 표준화 일정은 아직 확정된 바 없으므로 단정하기보다는, 세 프레임워크가 실제로 이 문제를 어떻게 풀었는지 구현 차이에 집중해 살펴본다.

## 핵심 개념 1: Virtual DOM diffing과 무엇이 다른가

기존 모델은 상태가 바뀌면 "이 상태를 쓰는 컴포넌트 트리 전체를 다시 렌더링 → 이전 트리와 비교(diff) → 실제 DOM에 패치"하는 흐름을 탄다. Signals 모델은 이 중간 단계를 건너뛴다. 상태(Signal)를 읽는 지점 각각이 의존성 그래프의 노드로 등록되고, 값이 바뀌면 그래프를 타고 실제로 영향받는 노드만 갱신된다.

<img src="/assets/images/posts/2026-08-18-signals-paradigm-comparison-1.svg" alt="Virtual DOM 재조정 방식과 Signals 세밀 반응성 방식의 업데이트 경로 비교 다이어그램" style="width:100%;">

## 핵심 개념 2: 세 프레임워크의 구현 비교

이름과 API는 다르지만, 세 프레임워크 모두 "값 컨테이너 + 파생 계산 + 부수효과"라는 동일한 3단 구조를 공유한다.

| 프레임워크 | 핵심 API | 의존성 추적 방식 | 렌더링/변경 감지 모델 |
|---|---|---|---|
| Vue 3 | `ref()` / `reactive()` / `computed()` | Proxy로 getter·setter를 가로채 자동 추적 | 컴파일러가 정적 분석으로 리렌더 범위를 좁혀 최적화 |
| SolidJS | `createSignal()` / `createMemo()` / `createEffect()` | 함수 호출(getter) 시점에 실행 컨텍스트가 자동 구독 | Virtual DOM 없음 — 컴파일 시점에 실제 DOM 갱신 코드로 변환 |
| Angular | `signal()` / `computed()` / `effect()` | getter 호출 기반 추적, RxJS Observable과 상호운용 계층 제공 | Zone.js 없이 동작하는 방향으로 점진 전환 중 |

세 API 모두 "값을 읽으면 자동으로 구독되고, 값을 바꾸면 구독자만 갱신된다"는 동일한 계약을 지킨다. 차이는 그 추적을 컴파일 타임에 정적으로 최적화하느냐(Vue, Solid), 런타임 그래프에 더 의존하느냐, 그리고 기존 아키텍처(Angular의 Zone.js, RxJS)와 어떻게 공존시키느냐에 있다.

## 예제: 같은 카운터, 세 가지 반응성

```javascript
// SolidJS — Signal, 파생값(Memo), 부수효과(Effect)
import { createSignal, createMemo, createEffect } from "solid-js";

function Counter() {
  const [count, setCount] = createSignal(0);
  const doubled = createMemo(() => count() * 2); // count()를 호출해야 구독됨

  createEffect(() => {
    console.log(`count=${count()}, doubled=${doubled()}`);
  });

  return (
    <button onClick={() => setCount((c) => c + 1)}>
      {count()} (x2 = {doubled()})
    </button>
  );
}
```

```typescript
// Angular — 동일한 로직을 signal/computed로 표현
import { Component, signal, computed, effect } from "@angular/core";

@Component({
  selector: "app-counter",
  standalone: true,
  template: `<button (click)="increment()">{{ count() }} (x2 = {{ doubled() }})</button>`,
})
export class CounterComponent {
  count = signal(0);
  doubled = computed(() => this.count() * 2);

  constructor() {
    effect(() => console.log(`count=${this.count()}, doubled=${this.doubled()}`));
  }

  increment() {
    this.count.update((c) => c + 1);
  }
}
```

두 코드는 프레임워크만 다를 뿐 구조가 거의 동일하다. `count()`처럼 값을 **호출해서 읽는 순간** 의존성이 등록되고, `computed`/`createMemo`는 캐시된 파생값을, `effect`는 부수효과를 담당한다. Vue의 `ref.value` 역시 같은 계약을 `.value` 접근자로 표현할 뿐이다.

## 실무 포인트

- **템플릿/JSX 밖에서 값을 읽을 때 구독이 깨지지 않는지 확인한다.** 구조 분해나 값 복사로 getter 호출을 건너뛰면 추적이 끊겨 갱신이 누락된다.
- **Angular는 기존 Zone.js·RxJS 기반 코드와의 점진적 마이그레이션 전략이 필요하다.** signal과 Observable을 상호 변환하는 유틸리티를 프로젝트 초기에 팀 컨벤션으로 정해두는 편이 안전하다.
- **과도하게 세분화된 Signal은 오히려 관리 비용을 늘린다.** 모든 필드를 개별 Signal로 쪼개기보다, 의미 있는 단위로 묶고 필요한 곳에서만 `computed`로 파생시키는 편이 낫다.
- **SSR·하이드레이션 환경에서는 프레임워크별 초기화 타이밍 차이를 반드시 검증한다.** 서버에서 계산된 값과 클라이언트 Signal 초기값이 어긋나면 하이드레이션 불일치가 발생할 수 있다.

## 3줄 요약

- Signals는 컴포넌트 전체 재실행 대신, 값을 실제로 읽은 지점만 자동 구독해 갱신하는 세밀한 반응성 모델이다.
- Vue의 `ref`, Solid의 `createSignal`, Angular의 `signal`은 API 이름은 다르지만 "값 컨테이너 + computed + effect"라는 동일한 3단 구조를 공유한다.
- 표준화(TC39 Signals proposal)는 아직 초기 논의 단계이므로, 지금은 각 프레임워크 문서 기준으로 구현 차이와 마이그레이션 전략을 개별적으로 확인해야 한다.

## 참고 자료

- [Vue.js — Reactivity Fundamentals](https://vuejs.org/guide/essentials/reactivity-fundamentals.html)
- [SolidJS Docs — Signals](https://docs.solidjs.com/concepts/signals)
- [Angular — Signals Guide](https://angular.dev/guide/signals)
- [TC39 Signals Proposal (GitHub)](https://github.com/tc39/proposal-signals)
