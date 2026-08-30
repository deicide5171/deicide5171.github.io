---
layout: single
title: "deck.gl TripsLayer로 이동 경로 시간 애니메이션 만들기"
date: 2026-09-24 12:20:00 +0530
categories: gis
tags: ["deckgl", "TripsLayer", "경로애니메이션", "GPU셰이더", "3D웹지도"]
toc: true
toc_sticky: true
excerpt: "차량 수천 대의 이동 경로를 시간에 따라 지도 위에서 움직이는 것처럼 보여주려 할 때, 매 프레임 좌표를 다시 계산해 CPU 병목에 빠지는 대신 deck.gl TripsLayer가 GPU 셰이더에서 직접 경로를 클리핑하는 원리를 정리했다."
---

## 왜 지금 TripsLayer를 알아야 하는가

배달 차량, 항공기, 선박처럼 시간에 따라 위치가 바뀌는 궤적 데이터를 지도 위에서 "실제로 움직이는 것처럼" 보여줘야 하는 요구는 물류·교통 대시보드에서 흔하다. 순진하게 구현하면 매 애니메이션 프레임마다 "현재 시각까지 지나온 좌표만 골라서 새로운 배열을 만들고, 그 배열을 다시 렌더링 레이어에 통째로 넘기는" 방식을 쓰게 되는데, 이 방식은 궤적 개수가 수백 개를 넘어가는 순간 매 프레임 자바스크립트에서 배열을 다시 계산하는 비용 자체가 프레임 드롭의 원인이 된다. deck.gl의 `TripsLayer`는 이 문제를 "좌표 재계산을 프레임마다 반복하지 않는다"는 접근으로 해결한다.

## 핵심 개념 1 — 전체 경로와 타임스탬프를 한 번만 GPU에 올린다

`TripsLayer`는 각 궤적의 전체 좌표 배열과, 각 좌표에 대응하는 타임스탬프 배열을 GPU 버퍼에 딱 한 번 업로드한다. 이후 애니메이션이 진행되는 동안 자바스크립트가 하는 일은 오직 하나, `currentTime`이라는 숫자 하나(uniform 변수)를 매 프레임 갱신해 셰이더에 전달하는 것뿐이다. 실제로 "이 시점까지 지나온 구간이 어디까지인가"를 판단하고 그 구간만 그리는 작업은 GPU의 정점 셰이더가 각 정점의 타임스탬프와 `currentTime`을 비교해 직접 수행한다. 즉 좌표 배열 자체는 애니메이션 내내 단 한 번도 다시 계산되거나 재전송되지 않는다.

<img src="/assets/images/posts/2026-09-24-deckgl-tripslayer-animated-path-rendering-1.svg" alt="원본 trip 데이터가 좌표와 타임스탬프 배열로 GPU에 한 번 업로드되고, currentTime 유니폼 값만 매 프레임 갱신되어 셰이더가 지나온 구간과 아직 지나지 않은 구간을 GPU에서 직접 클리핑하는 TripsLayer의 동작 원리를, 매 프레임 좌표를 재계산하는 일반적인 방식과 비교해 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — trailLength로 궤적의 "꼬리" 길이를 제어한다

단순히 지나온 지점까지 선을 다 그리면 화면이 지나온 경로로 뒤덮여 어디가 실제 "현재 위치"인지 알아보기 어려워진다. `TripsLayer`는 `trailLength` 파라미터로 현재 시각으로부터 얼마 이전까지의 구간만 꼬리로 그릴지 지정할 수 있다. `currentTime`에서 `trailLength`를 뺀 시점 이전의 구간은 투명 처리되거나 그려지지 않고, 그 사이 구간만 궤적으로 표시되며 보통 꼬리 끝(현재 위치)에 가까울수록 불투명하게, 멀수록 투명하게 그라디언트를 주어 이동 방향과 속도감을 시각적으로 표현한다.

| 파라미터 | 역할 |
|---|---|
| `getPath` | 각 궤적의 좌표 배열을 반환하는 접근자 |
| `getTimestamps` | 각 좌표에 대응하는 시각(초 단위 등) 배열 반환 |
| `currentTime` | 현재 애니메이션 재생 시각 (매 프레임 갱신) |
| `trailLength` | 현재 시각으로부터 얼마나 이전까지를 꼬리로 그릴지 |

## 예제 — TripsLayer로 차량 궤적 애니메이션 구성

```javascript
import { TripsLayer } from '@deck.gl/geo-layers';

const tripsLayer = new TripsLayer({
  id: 'vehicle-trips',
  data: vehicleTrips, // [{ path: [[lng,lat], ...], timestamps: [0, 12, 25, ...] }, ...]
  getPath: (d) => d.path,
  getTimestamps: (d) => d.timestamps,
  getColor: [30, 144, 255],
  opacity: 0.8,
  widthMinPixels: 3,
  trailLength: 60, // 최근 60초 구간만 꼬리로 표시
  currentTime: 0,   // 애니메이션 루프에서 매 프레임 갱신
});

let time = 0;
function animate() {
  time = (time + 1) % maxTimestamp;
  deckOverlay.setProps({
    layers: [tripsLayer.clone({ currentTime: time })],
  });
  requestAnimationFrame(animate);
}
animate();
```

`currentTime`만 갱신해 레이어를 다시 만들면, 실제 좌표·타임스탬프 데이터는 매번 다시 전송되지 않고 GPU에 이미 올라간 버퍼를 그대로 재사용한다.

## 실무 포인트

- **타임스탬프의 시작 기준을 궤적마다 통일하라.** 서로 다른 차량의 궤적이 실제 시각(예: 하루 중 초 단위)을 기준으로 되어 있어야 여러 궤적이 같은 `currentTime`에서 상대적으로 올바른 위치에 놓인다. 상대 시간(각 궤적의 출발을 0으로)으로 두면 모든 차량이 동시에 출발하는 것처럼 보이는 실수를 하기 쉽다.
- **대량의 궤적을 다룰 때는 `getPath`, `getTimestamps` 접근자 함수 자체의 비용에 주의하라.** 데이터가 이미 배열 형태라면 접근자를 단순 필드 참조로 유지해, 매 렌더마다 불필요한 변환 연산이 발생하지 않도록 해야 한다.
- **실시간 데이터를 다룬다면 `currentTime`을 실제 시각(Date.now() 기반)과 동기화할지, 배속 재생할지 정책을 먼저 정하라.** 라이브 트래킹과 과거 궤적 리플레이는 시간 매핑 방식이 달라야 한다.

## 마무리 요약

- TripsLayer는 전체 경로와 타임스탬프를 GPU에 한 번만 업로드하고, 애니메이션 진행은 `currentTime` 값 하나만 갱신하는 방식으로 CPU 재계산 병목을 없앤다.
- 실제 구간 선택과 렌더링은 GPU 셰이더가 각 정점의 타임스탬프를 `currentTime`과 비교해 직접 수행한다.
- `trailLength`로 궤적의 꼬리 길이를 조절하면 대량의 이동 경로를 겹치지 않게, 현재 위치를 명확히 드러내며 시각화할 수 있다.

## 참고 자료

- [deck.gl - TripsLayer](https://deck.gl/docs/api-reference/geo-layers/trips-layer)
- [deck.gl - Animations](https://deck.gl/docs/developer-guide/animations-and-transitions)
