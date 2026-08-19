---
layout: single
title: "FID가 사라진 자리에 INP가 왔다 — Core Web Vitals 응답성 최적화 실전"
date: 2026-08-26 12:30:00 +0530
categories: frontend
tags: ["frontend", "core-web-vitals", "inp", "performance", "javascript", "web-vitals"]
toc: true
toc_sticky: true
excerpt: "Core Web Vitals의 응답성 지표가 FID에서 INP로 완전히 교체된 뒤, 실제로 무엇을 측정하고 어떤 코드 패턴이 INP를 악화시키는지, 그리고 어떻게 줄이는지 정리한다."
---

Core Web Vitals의 세 지표 중 응답성을 담당하던 FID(First Input Delay)는 이제 완전히 퇴역했고, 그 자리를 INP(Interaction to Next Paint)가 대체했다. 두 지표의 차이는 단순한 이름 교체가 아니다. FID는 "첫 입력이 처리되기까지의 지연"만 쟀지만, INP는 페이지 생애주기 전체에 걸쳐 발생하는 모든 상호작용(클릭, 탭, 키보드 입력) 중 가장 느렸던 것을 기준으로 삼는다. 즉 첫 클릭은 빨랐지만 스크롤 후 나온 드롭다운을 열 때 500ms가 걸린다면, FID로는 잡히지 않았을 그 지연이 INP에서는 그대로 점수에 반영된다.

이 차이 때문에 "FID는 좋았는데 INP 도입 후 점수가 나빠졌다"는 사이트가 많았다. 특히 SPA처럼 페이지 전환 없이 오래 머무는 애플리케이션일수록 상호작용 총량이 많아 INP가 나쁘게 잡히기 쉽다. 이 글에서는 INP가 실제로 측정하는 세 구간과, 각 구간에서 흔히 발생하는 코드 패턴별 최적화 방법을 정리한다.

## 핵심 개념 1: INP는 세 구간의 합이다

INP는 사용자가 상호작용을 시작한 시점부터 다음 프레임이 화면에 그려지기까지의 시간을 측정하며, 이 시간은 세 구간으로 나뉜다.

| 구간 | 내용 | 흔한 지연 원인 |
|---|---|---|
| Input Delay | 이벤트 발생 후 핸들러 실행 시작까지 대기 | 메인 스레드가 다른 긴 작업(long task)으로 점유됨 |
| Processing Time | 이벤트 핸들러 실행 자체 | 핸들러 안에서 무거운 동기 연산, 불필요한 리렌더 |
| Presentation Delay | 핸들러 종료 후 브라우저가 다음 프레임을 그리기까지 | 큰 DOM 변경, 레이아웃 스래싱, 무거운 CSS |

이 중 실무에서 가장 흔히 문제가 되는 것은 Input Delay다. 메인 스레드가 50ms 이상 걸리는 "긴 작업(long task)"으로 막혀 있으면, 그 작업이 끝날 때까지 사용자의 클릭 이벤트 핸들러 자체가 시작되지 못한다. 이 긴 작업은 대개 초기 로드 시점의 대용량 JS 파싱·실행, 또는 상호작용 중 실행되는 무거운 상태 업데이트에서 나온다.

## 핵심 개념 2: 긴 작업을 쪼개는 것이 첫 번째 해법이다

메인 스레드를 막는 긴 작업을 발견했다면, 가장 효과적인 대응은 그 작업을 작은 단위로 쪼개 브라우저가 중간에 입력을 처리할 틈을 주는 것이다. `scheduler.yield()`(최신 브라우저)나 `setTimeout(fn, 0)`으로 작업을 다음 태스크로 미루는 방식이 대표적이다. React 18 이상에서는 `startTransition`으로 긴급하지 않은 렌더링을 낮은 우선순위로 미룰 수 있다.

```javascript
// 나쁜 예: 대량의 리스트를 한 번에 동기 렌더링해 긴 작업을 만든다
function handleSearch(query) {
  const filtered = hugeList.filter(item => item.name.includes(query));
  setResults(filtered); // 렌더링까지 한 번에 동기 처리
}

// 개선: 무거운 렌더 결과를 낮은 우선순위로 표시
import { startTransition } from 'react';

function handleSearch(query) {
  // 입력창 자체는 즉시 업데이트(긴급) — setSearchInput은 별도 상태
  setSearchInput(query);

  startTransition(() => {
    // 검색 결과 리스트 갱신은 긴급하지 않으므로 낮은 우선순위로 스케줄링
    const filtered = hugeList.filter(item => item.name.includes(query));
    setResults(filtered);
  });
}
```

`startTransition`으로 감싼 업데이트는 더 급한 입력(타이핑 계속하기 등)이 들어오면 중단·재시작될 수 있어, 사용자가 입력하는 동안 메인 스레드가 결과 렌더링에 발이 묶이지 않는다.

## 실무 포인트

- **이벤트 핸들러 안의 동기 연산을 의심한다**: `onClick` 핸들러 안에서 대량 배열 정렬, JSON 파싱, 동기 API 호출 등이 실행되면 Processing Time이 그대로 늘어난다. 가능하면 계산을 웹 워커로 옮기거나, 결과를 미리 계산해 캐시해 둔다.
- **서드파티 스크립트의 이벤트 리스너를 점검한다**: 광고·분석 스크립트가 전역 `click` 리스너를 걸어두고 무거운 로직을 실행하면, 내가 작성한 코드와 무관하게 INP가 나빠진다. Chrome DevTools의 Performance 패널에서 Long Task 발생 지점의 콜스택을 확인해 원인 스크립트를 특정한다.
- **측정은 필드 데이터(CrUX, RUM)를 우선한다**: 로컬 개발 환경에서 빠르게 동작하는 상호작용도 저사양 기기·혼잡한 네트워크의 실제 사용자에게는 느릴 수 있다. Chrome UX Report나 자체 RUM(Real User Monitoring)으로 실제 분포를 확인하지 않고 랩(lab) 환경 수치만 보고 최적화를 마쳤다고 판단하면 안 된다.

## 3줄 요약

- INP는 FID와 달리 페이지 생애주기 전체의 모든 상호작용 중 가장 느렸던 것을 기준으로 삼아, SPA에서 특히 나빠지기 쉽다.
- INP는 Input Delay·Processing Time·Presentation Delay 세 구간의 합이며, 실무에서는 메인 스레드를 막는 긴 작업이 Input Delay를 키우는 경우가 가장 흔하다.
- 긴 작업을 `startTransition`이나 스케줄링 API로 쪼개고, 서드파티 스크립트의 영향을 점검하며, 필드 데이터로 실제 사용자 체감을 확인해야 한다.

## 참고 자료

- [web.dev: Interaction to Next Paint (INP)](https://web.dev/articles/inp)
- [web.dev: Optimize INP](https://web.dev/articles/optimize-inp)
- [React 공식 문서: startTransition](https://react.dev/reference/react/startTransition)
