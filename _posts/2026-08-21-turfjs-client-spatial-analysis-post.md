---
layout: single
title: "브라우저에서 끝내는 공간 분석 — Turf.js로 버퍼·교차·거리 계산하기"
date: 2026-08-21 13:20:00 +0530
categories: gis
tags: ["turf.js", "javascript", "geojson", "웹지도", "공간연산"]
toc: true
toc_sticky: true
excerpt: "PostGIS나 별도 공간 분석 서버 없이도, 브라우저에서 Turf.js로 버퍼·교차·거리 계산을 직접 수행해 지도 인터랙션에 즉시 반영하는 방법을 정리한다."
---

## 왜 지금 클라이언트 공간 연산인가

"반경 500m 안에 있는 매장은?", "이 배달 구역과 저 배달 구역이 겹치는가?" 같은 질문에 답하려면 보통 PostGIS 같은 공간 DB에 쿼리를 던지거나 별도의 공간 분석 API를 호출해야 한다고 생각하기 쉽다. 하지만 사용자가 지도 위에서 마커를 드래그하거나 반경 슬라이더를 움직일 때마다 서버 왕복이 발생하면, 그 지연만큼 지도 조작감이 떨어진다. 실시간성이 중요한 인터랙션이라면 연산을 아예 클라이언트로 가져오는 편이 낫다.

**Turf.js**는 GeoJSON을 입력·출력으로 삼는 순수 JavaScript 공간 연산 라이브러리다. 서버나 네이티브 바인딩 없이 브라우저에서 바로 동작하기 때문에, OpenLayers·MapLibre·Leaflet 같은 웹 지도 라이브러리와 함께 쓰면 사용자가 그린 도형이나 실시간 좌표를 그 자리에서 분석해 지도에 바로 그려낼 수 있다. 서버 사이드 GIS 분석(PostGIS 등)이 대용량·정밀 배치 작업에 강하다면, Turf.js는 소규모 데이터에 대한 즉각적인 클라이언트 반응성에 강하다.

## 핵심 개념 1: Turf.js가 다루는 것과 다루지 않는 것

| 구분 | Turf.js (클라이언트) | PostGIS (서버) |
|---|---|---|
| 입출력 형식 | GeoJSON 객체 | 공간 컬럼(geometry/geography) |
| 실행 위치 | 브라우저(사용자 기기) | DB 서버 |
| 강점 | 지연 없는 즉시 반응, 인터랙션 연동 | 대용량 데이터, 공간 인덱스 기반 대규모 질의 |
| 적합한 규모 | 화면에 보이는 수십~수백 개 피처 | 수만~수억 건의 영속 데이터 |
| 대표 연산 | buffer, intersect, distance, area, nearestPoint | ST_Buffer, ST_Intersection, ST_Distance, GiST 인덱스 |

두 도구는 경쟁 관계가 아니라 역할이 다르다. 서버에서 대량 데이터를 미리 걸러 GeoJSON으로 내려보내고, 그 이후 사용자 조작에 따라 달라지는 세부 연산은 Turf.js가 클라이언트에서 담당하는 조합이 흔하다.

## 핵심 개념 2: 대표 연산 세 가지

<img src="/assets/images/posts/2026-08-21-turfjs-client-spatial-analysis-1.svg" alt="Turf.js 브라우저 공간 연산 흐름도 - GeoJSON 입력이 buffer, intersect, distance 연산을 거쳐 결과 GeoJSON으로 지도에 렌더링되는 과정" style="width:100%;">

- **buffer**: 점·선·면 주변에 지정한 거리만큼 영역을 확장한 폴리곤을 생성한다. 반경 상권 분석, 위험구역 표시에 쓰인다.
- **intersect / union / difference**: 두 폴리곤을 겹쳐 교집합·합집합·차집합을 구한다. 배달 구역 중첩 확인, 관할 구역 병합에 쓰인다.
- **distance / nearestPoint**: 두 지점 사이 거리를 구하거나, 여러 후보 중 가장 가까운 지점을 찾는다. 최근접 매장 탐색에 쓰인다.

Turf.js는 이 연산들을 각각 독립된 함수(`turf.buffer`, `turf.intersect`, `turf.distance` 등)로 제공하며, 모든 함수는 GeoJSON을 받아 GeoJSON을 반환하므로 지도 라이브러리의 소스 데이터로 바로 연결할 수 있다.

## 예제: 반경 버퍼와 교차 여부 판단

```javascript
import * as turf from '@turf/turf';

// 1) 특정 지점 기준 500m 반경 버퍼 생성
const store = turf.point([127.0276, 37.4979]); // [경도, 위도]
const serviceArea = turf.buffer(store, 0.5, { units: 'kilometers' });

// 2) 사용자가 그린 배달 구역 폴리곤과 겹치는지 확인
const deliveryZone = turf.polygon([[
  [127.020, 37.495],
  [127.035, 37.495],
  [127.035, 37.503],
  [127.020, 37.503],
  [127.020, 37.495],
]]);

const overlap = turf.intersect(
  turf.featureCollection([serviceArea, deliveryZone])
);

if (overlap) {
  console.log('겹치는 영역 존재 — 지도에 강조 표시');
  map.getSource('overlap-layer').setData(overlap);
} else {
  console.log('겹치는 영역 없음');
}

// 3) 사용자 위치에서 가장 가까운 매장 찾기
const userLocation = turf.point([127.030, 37.498]);
const stores = turf.featureCollection([store /* , ...다른 매장들 */]);
const nearest = turf.nearestPoint(userLocation, stores);
const km = turf.distance(userLocation, nearest, { units: 'kilometers' });
console.log(`가장 가까운 매장까지 ${km.toFixed(2)}km`);
```

이 코드는 서버 호출 없이 지도 위 이벤트 핸들러 안에서 즉시 실행할 수 있다. 사용자가 반경 슬라이더를 움직이면 `turf.buffer`를 다시 호출해 결과 GeoJSON을 지도 소스에 갱신하는 식으로, 프레임마다 자연스럽게 반응하는 UI를 만들 수 있다.

## 실무 포인트

- **좌표계는 항상 위경도(EPSG:4326) 기준**이다. Turf.js 함수 대부분은 지구 곡률을 고려한 대권 거리(great-circle distance) 계산을 내부적으로 처리하므로, 미터법 투영좌표로 미리 변환할 필요가 없다.
- **대용량 폴리곤 연산은 메인 스레드를 막을 수 있다.** 좌표점이 많은 복잡한 폴리곤에 `intersect`나 `buffer`를 반복 호출하면 프레임 드랍이 발생할 수 있으니, 필요하면 Web Worker로 연산을 분리하는 것을 검토한다.
- **정밀도가 중요한 통계·집계는 서버에서.** Turf.js의 계산 결과는 UI 즉시성에는 충분하지만, 법적·회계적으로 정확해야 하는 면적·거리 값은 PostGIS 등 서버 사이드 계산과 교차 검증하는 편이 안전하다.
- **번들 크기 관리**: `@turf/turf` 전체를 가져오면 번들이 커지므로, 실제 사용하는 연산만 `@turf/buffer`, `@turf/distance`처럼 개별 패키지로 임포트하면 트리쉐이킹에 유리하다.

## 3줄 요약

- Turf.js는 GeoJSON을 입출력으로 쓰는 순수 JS 공간 연산 라이브러리로, 서버 왕복 없이 브라우저에서 buffer·intersect·distance 같은 연산을 즉시 수행한다.
- 대용량·영속 데이터의 정밀 분석은 PostGIS 같은 서버 사이드 도구가, 화면 위 실시간 인터랙션은 Turf.js가 맡는 역할 분담이 자연스럽다.
- 좌표계는 위경도 기준으로 그대로 쓰면 되지만, 무거운 연산은 Web Worker 분리와 개별 패키지 임포트로 성능·번들 크기를 관리해야 한다.

## 참고 자료

- [Turf.js 공식 문서](https://turfjs.org/)
- [Turf.js GitHub Repository](https://github.com/Turfjs/turf)
- [GeoJSON 명세 (RFC 7946)](https://datatracker.ietf.org/doc/html/rfc7946)
