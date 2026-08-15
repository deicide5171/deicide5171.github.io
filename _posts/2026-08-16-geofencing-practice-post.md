---
layout: single
title: "지오펜싱 제대로 구현하기 — 폴리곤 판정부터 히스테리시스, 배터리 최적화까지"
date: 2026-08-16 14:20:00 +0530
categories: gis
tags: ["지오펜싱", "geofencing", "point-in-polygon", "위치기반서비스", "히스테리시스"]
toc: true
toc_sticky: true
excerpt: "원형 반경만으로는 실제 매장·캠퍼스 경계를 표현할 수 없고, GPS 오차는 경계 근처에서 진입·이탈 이벤트를 반복 발생시킨다 — 폴리곤 판정 알고리즘과 히스테리시스, 배터리 최적화 전략으로 지오펜싱을 실전에 맞게 구현하는 방법을 정리한다."
---

## 왜 지금 지오펜싱인가

매장에 들어서면 오는 쿠폰 알림, 배달 기사가 목적지 근처에 왔을 때 뜨는 "곧 도착" 안내, 집 근처에서 자동으로 켜지는 스마트홈 기기까지 — **지오펜싱(Geofencing)** 은 이미 여러 서비스에서 조용히 동작한다. 특정 영역을 정의하고, 사용자(또는 기기)가 그 영역에 들어오거나 나갈 때 이벤트를 발생시키는 개념이다.

문제는 "특정 영역"을 원형 반경으로 단순화하는 순간 시작된다. 실제 매장·캠퍼스·배달 권역은 원이 아니라 도로와 건물 배치를 따라가는 불규칙한 다각형에 가깝다. 여기에 GPS 오차(도심 협곡에서는 수십 미터까지 벌어지기도 한다고 알려져 있다)가 겹치면, 경계 근처에서 진입·이탈 이벤트가 짧은 간격으로 반복 발생하는 "플리커링" 문제가 생긴다. 이 글은 실내 측위(측위 자체의 정확도 확보)와는 다른 각도에서, **확보된 위치 정보로 경계 이벤트를 어떻게 안정적으로 판정할 것인가**에 집중한다.

<img src="/assets/images/posts/2026-08-16-geofencing-practice-1.svg" alt="지오펜싱 진입·이탈 이벤트 판정 개념도 - 지오펜스 폴리곤 경계, 진입/이탈 확정 버퍼, GPS 측위 경로와 이벤트 확정 지점" style="width:100%;">

## 핵심 개념 1: 점-폴리곤(Point-in-Polygon) 판정

경계가 다각형일 때 "현재 위치가 이 다각형 안에 있는가"를 판정하는 대표적인 방법이 **Ray Casting(레이 캐스팅)** 알고리즘이다. 판정하려는 점에서 임의의 방향(보통 수평)으로 반직선을 그었을 때, 이 반직선이 다각형의 변과 교차하는 횟수가 홀수면 내부, 짝수면 외부로 판정한다.

| 방법 | 원리 | 장점 | 주의점 |
|---|---|---|---|
| Ray Casting | 교차 횟수 홀짝 판정 | 구현 간단, 오목 다각형도 처리 | 정점 통과 엣지 케이스 처리 필요 |
| Winding Number | 감김 횟수 계산 | 자기교차 다각형도 안정적 | 구현 복잡도 높음 |
| Bounding Box 필터 | 사각형으로 1차 제외 | 연산량 절감 | 단독 사용 시 정밀 판정 불가 |

실무에서는 Bounding Box로 후보 폴리곤 수를 먼저 줄인 뒤, 남은 후보에만 Ray Casting을 적용하는 2단계 구조가 흔히 쓰인다. 지오펜스가 수백~수천 개로 늘어날수록 이 사전 필터의 효과가 커진다.

## 핵심 개념 2: 히스테리시스로 경계 떨림 막기

GPS 오차가 섞여 있는 이상, 경계선 하나만으로 즉시 판정하면 사용자가 경계 근처에 머무를 때마다 이벤트가 반복 발생한다. 이를 막는 표준 접근이 제어 이론에서 가져온 **히스테리시스(hysteresis)** 다. 경계선 하나 대신 안쪽 "진입 확정 버퍼"와 바깥쪽 "이탈 확정 버퍼" 두 개를 두고, 각 버퍼를 일정 시간(dwell time) 이상 유지했을 때만 이벤트를 확정한다.

| 판정 방식 | 확정 조건 | 오탐지 위험 | 반응 지연 |
|---|---|---|---|
| 단일 경계선 | 경계 통과 즉시 | 높음(플리커링) | 거의 없음 |
| 버퍼 + dwell time | 버퍼 내 N초 유지 | 낮음 | dwell time만큼 |
| 이동 평균 위치 | 최근 N개 평균 좌표 | 중간 | 평균 윈도우만큼 |

dwell time을 너무 길게 잡으면 진입 알림이 늦어지고, 너무 짧게 잡으면 히스테리시스 효과가 줄어든다. 서비스 성격(즉시성이 중요한 쿠폰 알림인지, 몇 초 지연이 허용되는 도착 알림인지)에 따라 값을 다르게 가져가는 것이 합리적이다.

## 예제 1: Ray Casting으로 점-폴리곤 판정 (TypeScript)

```typescript
type Point = { lat: number; lng: number };

// Ray Casting 알고리즘: point가 polygon(경도/위도 순서 무관, 일관성만 유지) 내부인지 판정
function isPointInPolygon(point: Point, polygon: Point[]): boolean {
  let inside = false;
  const { lat: x, lng: y } = point;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lat, yi = polygon[i].lng;
    const xj = polygon[j].lat, yj = polygon[j].lng;

    const intersects =
      yi > y !== yj > y &&
      x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;

    if (intersects) inside = !inside;
  }

  return inside;
}
```

좁은 지역이라면 위경도를 평면 좌표처럼 취급해도 무방하지만, 다각형이 넓거나 고위도 지역이라면 지구 곡률로 인한 왜곡을 감안해 투영 좌표계로 변환 후 판정하는 것이 안전하다.

## 예제 2: dwell time 기반 히스테리시스 상태 전이

```typescript
type FenceState = "OUTSIDE" | "ENTERING" | "INSIDE" | "EXITING";

function updateFenceState(
  prev: FenceState,
  inBuffer: { inner: boolean; outer: boolean },
  elapsedMs: number,
  dwellAccumMs: number,
  dwellThresholdMs = 5000
): { state: FenceState; dwellAccumMs: number; fireEvent?: "ENTER" | "EXIT" } {
  if (prev === "OUTSIDE" && inBuffer.inner) {
    const accum = dwellAccumMs + elapsedMs;
    return accum >= dwellThresholdMs
      ? { state: "INSIDE", dwellAccumMs: 0, fireEvent: "ENTER" }
      : { state: "ENTERING", dwellAccumMs: accum };
  }
  if (prev === "INSIDE" && !inBuffer.outer) {
    const accum = dwellAccumMs + elapsedMs;
    return accum >= dwellThresholdMs
      ? { state: "OUTSIDE", dwellAccumMs: 0, fireEvent: "EXIT" }
      : { state: "EXITING", dwellAccumMs: accum };
  }
  return { state: prev, dwellAccumMs: 0 }; // 버퍼 이탈 시 dwell 누적 리셋(튕김 방지)
}
```

## 배터리 최적화: 측위 주기를 어떻게 가져갈 것인가

GPS를 계속 고정밀로 켜두면 배터리 소모가 커진다. 실무에서는 경계와의 대략적 거리에 따라 측위 정밀도·주기를 적응적으로 조절한다. 경계에서 멀 때는 저정밀·저빈도 측위(네트워크 기반 위치 등)로 충분하고, 가까워질수록 GPS 고정밀 측위로 전환해 판정 정확도를 높인다. iOS Core Location, Android GeofencingClient 같은 OS API는 이런 스케줄링을 내부 처리해주지만 **원형 지오펜스만 지원**한다는 제약이 있다. 폴리곤이 필요하면 OS API로 넓은 원형 영역을 1차 트리거로 걸고, 그 안에서만 앱이 폴리곤 판정을 돌리는 하이브리드 구조가 배터리와 정확도를 함께 챙기는 절충안이다.

## 실무 포인트

- **원형 1차 필터 → 폴리곤 정밀 판정**: OS 지오펜싱 API의 저전력 트리거를 활용하고, 폴리곤 판정은 필요할 때만 앱 로직으로 수행한다.
- **dwell time은 서비스 요구사항에 맞춰 조정**: 즉시성이 중요한 알림과 지연이 허용되는 알림은 다른 임계값을 가져가야 한다.
- **다중 지오펜스 겹침 처리 규칙을 미리 정의**: 여러 지오펜스가 겹치는 지점에서 어떤 이벤트를 우선할지(가장 안쪽 영역 우선 등) 사전에 설계한다.
- **경계 좌표에 오차 마진을 반영**: 등록된 폴리곤과 실제 물리적 경계 사이 오차를 감안해 약간 여유를 둔다.

## 3줄 요약

- 지오펜싱은 단순 반경 판정이 아니라 Ray Casting 같은 점-폴리곤 알고리즘으로 불규칙한 경계를 정확히 표현하는 것에서 시작한다.
- GPS 오차로 인한 경계 근처 이벤트 반복(플리커링)은 진입/이탈 버퍼와 dwell time을 둔 히스테리시스 설계로 완화한다.
- 배터리 소모를 줄이려면 OS의 원형 지오펜스 API로 1차 트리거를 걸고, 필요한 순간에만 정밀 폴리곤 판정과 고정밀 측위를 수행하는 하이브리드 구조가 현실적이다.

## 참고 자료

- [Apple Developer — Core Location: Monitoring the User's Proximity to Geographic Regions](https://developer.apple.com/documentation/corelocation/monitoring-the-user-s-proximity-to-geographic-regions)
- [Android Developers — Geofencing](https://developer.android.com/develop/sensors-and-location/location/geofencing)
- [Turf.js — booleanPointInPolygon](https://turfjs.org/docs/api/booleanPointInPolygon)
