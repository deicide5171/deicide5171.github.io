---
layout: single
title: "INP(Interaction to Next Paint) — 새로운 Core Web Vitals 지표 최적화하기"
date: 2026-09-24 13:30:00 +0530
categories: frontend
tags: ["INP", "CoreWebVitals", "웹성능", "FID", "메인스레드"]
toc: true
toc_sticky: true
excerpt: "FID를 대체한 Core Web Vitals 지표 INP가 클릭 한 번이 아니라 사용자와의 모든 상호작용을 측정 대상으로 삼으면서 최적화 접근이 어떻게 달라져야 하는지, 메인 스레드 점유를 줄이는 실질적인 기법을 정리했다."
---

## 왜 지금 INP를 다시 봐야 하는가

FID(First Input Delay)는 오랫동안 사용자 상호작용 응답성을 측정하는 Core Web Vitals 지표였지만, 근본적인 한계가 있었다. FID는 사용자의 "첫 번째" 입력에 대한 지연시간만 측정했고, 그마저도 입력 이벤트가 처리되기 시작하는 시점까지만 쟀지 실제로 화면이 갱신되는 시점까지는 포함하지 않았다. 즉 페이지 로드 초반에 한 번만 반응이 빨랐다면 이후 상호작용이 아무리 버벅여도 FID 점수에는 잡히지 않는 구조적 맹점이 있었다. INP는 페이지 생애주기 전체에서 발생하는 모든(혹은 대표적인) 상호작용의 응답 시간을 측정하고, 그중 가장 느린 상호작용(또는 근사치)을 대표값으로 사용함으로써 이 맹점을 해소한다.

## 핵심 개념 1 — INP가 측정하는 세 구간

INP는 하나의 상호작용을 입력 지연(input delay), 처리 시간(processing time), 표시 지연(presentation delay) 세 구간의 합으로 측정한다. 입력 지연은 사용자가 클릭이나 키 입력을 한 시점부터 이벤트 핸들러가 실행되기 시작하는 시점까지, 처리 시간은 이벤트 핸들러 실행에 걸리는 시간, 표시 지연은 핸들러 실행이 끝난 뒤 실제로 다음 프레임이 화면에 그려지기까지의 시간이다. 세 구간 중 어느 것이 병목인지에 따라 최적화 방향이 완전히 달라지므로, 단순히 "INP가 나쁘다"는 결과만 보고 대응하면 엉뚱한 곳을 고치게 된다.

## 핵심 개념 2 — 메인 스레드 점유가 세 구간 모두에 영향을 준다

세 구간이 개념적으로는 분리돼 있지만, 실무에서 INP를 악화시키는 가장 흔한 원인은 결국 메인 스레드가 장시간 다른 작업(Long Task)으로 점유돼 있는 것이다. 입력 지연은 메인 스레드가 다른 스크립트를 실행 중이라 이벤트 핸들러 자체가 큐에서 대기하기 때문에 늘어나고, 표시 지연 역시 렌더링 작업이 메인 스레드에서 밀려나면 늘어난다. 따라서 INP 개선의 핵심은 각 상호작용 핸들러 자체를 최적화하는 것뿐 아니라, 상호작용과 무관한 곳에서 메인 스레드를 오래 점유하는 코드(대량 리스트 렌더링, 무거운 상태 계산, 서드파티 스크립트)를 찾아 분산시키는 것이다.

| 구간 | 주요 원인 | 대응 |
|---|---|---|
| 입력 지연 | 메인 스레드가 다른 Long Task로 점유 | 작업을 작은 단위로 쪼개기(yield) |
| 처리 시간 | 핸들러 자체의 무거운 동기 로직 | 불필요한 리렌더링·계산 제거 |
| 표시 지연 | 큰 DOM 변경, 레이아웃 스래싱 | DOM 변경 최소화, `content-visibility` 활용 |

## 예제 — 긴 작업을 yield로 쪼개기

```javascript
function processLargeList(items) {
  let i = 0;
  function chunk(deadline) {
    while (i < items.length && (deadline.timeRemaining() > 0 || i % 50 === 0)) {
      renderItem(items[i]);
      i++;
    }
    if (i < items.length) {
      // 남은 작업이 있으면 다음 유휴 시점으로 양보
      if ('scheduler' in window && 'yield' in window.scheduler) {
        window.scheduler.yield().then(() => chunk({ timeRemaining: () => 5 }));
      } else {
        requestIdleCallback(chunk);
      }
    }
  }
  requestIdleCallback(chunk);
}
```

`scheduler.yield()`는 실행 중인 작업을 명시적으로 양보해 브라우저가 대기 중인 사용자 입력을 먼저 처리할 기회를 준다. 이를 지원하지 않는 브라우저에서는 `requestIdleCallback`이나 `setTimeout(fn, 0)`으로 유사하게 작업을 쪼갤 수 있다.

## 실무 포인트

- **Chrome DevTools의 Performance 패널에서 "Interactions" 트랙을 직접 확인하라.** INP 값만 보고 끝내지 말고, 실제로 어느 상호작용에서 입력/처리/표시 중 어느 구간이 늘어났는지 트레이스로 확인해야 정확한 원인을 찾을 수 있다.
- **서드파티 스크립트의 실행 시점을 상호작용이 몰리는 구간과 분리하라.** 광고나 분석 스크립트가 페이지 초기 로드 직후 한꺼번에 실행되면서 메인 스레드를 점유하면, 이 시점의 사용자 상호작용 INP가 크게 튈 수 있다.
- **React나 Vue 같은 프레임워크에서는 상태 업데이트 배치와 렌더링 범위를 좁혀라.** 하나의 클릭으로 큰 트리 전체가 리렌더링되도록 상태를 설계하면 처리 시간 구간이 불필요하게 길어진다.

## 마무리 요약

- INP는 첫 입력만 측정하던 FID의 한계를 넘어, 페이지 생애주기 전체의 대표적인 상호작용 응답성을 측정하는 지표다.
- 입력 지연·처리 시간·표시 지연 세 구간 중 어디가 병목인지 구분해야 올바른 최적화 방향을 잡을 수 있다.
- 메인 스레드를 오래 점유하는 Long Task를 찾아 작업을 잘게 쪼개고 양보(yield)하는 것이 INP 개선의 핵심 기법이다.

## 참고 자료

- [web.dev - Interaction to Next Paint (INP)](https://web.dev/articles/inp)
- [Chrome for Developers - Optimize INP](https://web.dev/articles/optimize-inp)
