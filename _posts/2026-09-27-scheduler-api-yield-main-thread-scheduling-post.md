---
layout: single
title: "Scheduler API 딥다이브 — scheduler.yield()로 메인 스레드 블로킹을 직접 제어하기"
date: 2026-09-27 12:30:00 +0530
categories: frontend
tags: ["SchedulerAPI", "메인스레드", "성능최적화", "INP", "브라우저내부"]
toc: true
toc_sticky: true
excerpt: "setTimeout(fn, 0)으로 메인 스레드를 양보하던 오래된 관행을 대체하는 네이티브 Scheduler API의 우선순위 큐 모델과 scheduler.yield()의 동작 원리, React 18+ 스케줄러와의 관계를 정리했다."
---

## 왜 지금 Scheduler API를 봐야 하는가

Core Web Vitals에 INP(Interaction to Next Paint)가 도입되면서, 무거운 JS 작업이 메인 스레드를 오래 점유해 사용자 입력 응답이 늦어지는 문제가 성능 최적화의 핵심 지표가 됐다. 오랫동안 개발자들은 긴 작업을 잘게 쪼개 메인 스레드를 양보하기 위해 `setTimeout(fn, 0)`이나 `requestAnimationFrame` 같은 편법을 써왔다. 문제는 이 API들이 애초에 스케줄링을 위해 설계되지 않았다는 점이다. `setTimeout`은 최소 지연 시간 클램핑, 타이머 우선순위 부재 같은 부작용이 있고, 브라우저의 실제 렌더링 파이프라인과 협조하지 않는다. Scheduler API는 이 문제를 해결하기 위해 브라우저가 네이티브로 제공하는 우선순위 기반 작업 스케줄링 인터페이스다.

## 핵심 개념 1 — postTask와 우선순위 큐

Scheduler API의 핵심은 `scheduler.postTask(callback, options)`로, 콜백을 우선순위와 함께 큐에 등록한다. 우선순위는 세 단계로 나뉜다: `user-blocking`(클릭 응답처럼 즉시 처리해야 하는 작업), `user-visible`(기본값, 화면에 보이지만 즉각적이지 않아도 되는 작업), `background`(분석 로깅처럼 지연되어도 무방한 작업). 브라우저는 이 우선순위를 참고해 렌더링과 입력 처리 사이에서 어떤 작업을 먼저 실행할지 스스로 판단한다. `setTimeout`과 달리 브라우저의 내부 렌더링 스케줄러와 같은 이벤트 루프 메커니즘을 공유하므로, 우선순위가 실제로 의미 있게 반영된다.

## 핵심 개념 2 — scheduler.yield()로 긴 작업 쪼개기

`scheduler.yield()`는 현재 실행 중인 작업이 스스로 "지금 잠깐 메인 스레드를 양보하겠다"고 선언하는 API다. 기존 방식인 `setTimeout(fn, 0)`으로 작업을 쪼개면 콜백이 매크로태스크 큐 맨 뒤로 밀려나 대기 시간이 예측 불가능했지만, `scheduler.yield()`는 브라우저가 입력 이벤트나 렌더링처럼 더 급한 작업이 있는지 확인한 뒤, 없다면 거의 지연 없이 원래 작업을 이어서 실행한다. 또한 `yield()`가 반환하는 Promise는 원래 작업과 같은 우선순위 컨텍스트를 유지하므로, 작업을 쪼개도 우선순위 정보가 유실되지 않는다는 점이 `setTimeout`과의 결정적 차이다.

| 방식 | 우선순위 지정 | 대기 시간 예측 가능성 | 렌더링 파이프라인과의 협조 |
|---|---|---|---|
| `setTimeout(fn, 0)` | 불가능 | 낮음(4ms 클램핑, 큐 밀림) | 없음 |
| `requestIdleCallback` | 유휴 시간만 | 매우 낮음(호출 보장 안 됨) | 부분적 |
| `scheduler.postTask` | 3단계 우선순위 | 높음 | 있음 |
| `scheduler.yield` | 현재 작업 우선순위 유지 | 높음 | 있음 |

## 코드 예제 — 긴 목록 렌더링을 청크로 분할하기

```javascript
async function processLargeList(items) {
  for (let i = 0; i < items.length; i++) {
    renderItem(items[i]);

    // 50개마다 메인 스레드를 양보해 입력 이벤트가 끼어들 틈을 준다
    if (i % 50 === 0) {
      if ('scheduler' in window && 'yield' in scheduler) {
        await scheduler.yield();
      } else {
        // 폴백: 지원하지 않는 브라우저용
        await new Promise((r) => setTimeout(r, 0));
      }
    }
  }
}

// 사용자 클릭 직후 실행해야 하는 작업은 높은 우선순위로 등록
scheduler.postTask(() => updateUI(), { priority: 'user-blocking' });
```

## 실무 포인트

- **React의 자체 스케줄러와 개념적으로 유사하다.** React 18+의 concurrent 모드는 자체 스케줄러 패키지로 유사한 우선순위 기반 작업 분할을 구현해왔는데, 네이티브 Scheduler API가 성숙하면 이 내부 구현이 점진적으로 표준 API 위로 이전될 가능성이 크다. React가 아닌 vanilla JS나 다른 프레임워크에서도 동일한 이점을 직접 누릴 수 있다는 점이 의미가 크다.
- **브라우저 지원 여부를 반드시 확인하라.** `scheduler.postTask`는 Chromium 계열에서 먼저 안정화됐고, `scheduler.yield()`는 상대적으로 최신 기능이라 지원 범위가 더 좁다. 항상 폴백 경로(`setTimeout` 또는 `MessageChannel`)를 함께 구현해야 한다.
- **우선순위 남용에 주의하라.** 모든 작업을 `user-blocking`으로 등록하면 우선순위 큐가 무의미해진다. 실제로 사용자 입력에 직접 반응하는 작업에만 최상위 우선순위를 부여하고, 나머지는 기본값이나 `background`로 두는 것이 스케줄러의 이점을 살리는 길이다.

## 마무리 요약

- Scheduler API는 `setTimeout` 편법을 대체하는 네이티브 우선순위 기반 작업 스케줄링으로, 브라우저의 렌더링 파이프라인과 직접 협조한다.
- `scheduler.postTask`는 3단계 우선순위로 작업을 예약하고, `scheduler.yield()`는 긴 작업을 우선순위를 유지한 채 쪼개 입력 응답성을 지킨다.
- INP 최적화를 위해 긴 동기 작업을 청크 단위로 나눌 때는 `setTimeout(fn, 0)` 대신 이 API를 우선 고려하되, 브라우저 지원 범위에 맞는 폴백을 반드시 갖춰야 한다.

## 참고 자료

- [MDN — Prioritized Task Scheduling API](https://developer.mozilla.org/en-US/docs/Web/API/Prioritized_Task_Scheduling_API)
- [web.dev — Optimize INP with Scheduler API](https://web.dev/articles/optimize-inp)
- [Chrome for Developers — scheduler.yield() 설명](https://developer.chrome.com/docs/web-platform/scheduler-yield-origin-trial)
