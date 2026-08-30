---
layout: single
title: "MapLibre GL JS로 3D 건물 표현하기 — fill-extrusion 첫 설정과 흔한 실수"
date: 2026-09-22 13:20:00 +0530
categories: gis
tags: ["maplibre", "fillextrusion", "3d건물", "벡터타일", "웹지도라이브러리"]
toc: true
toc_sticky: true
excerpt: "평면 지도에 건물 층수 데이터를 넣었는데 아무리 설정해도 입체감이 안 생기는 문제를, MapLibre GL JS의 fill-extrusion 레이어 타입과 높이 표현식으로 해결하는 방법을 정리했다."
---

## 왜 fill 레이어로는 3D 건물이 안 만들어지나

벡터 타일에 건물 폴리곤과 층수 정보가 담겨 있으니, 그냥 `fill` 레이어에 색만 입히면 3D처럼 보일 것이라고 기대하기 쉽다. 하지만 `fill` 레이어는 어디까지나 폴리곤을 평면에 색으로 채우는 2D 렌더링 방식이라, 층수 데이터를 아무리 스타일에 연결해도 입체감이 생기지 않는다. MapLibre GL JS에서 건물을 실제로 "세워서" 보여주려면 `fill`이 아니라 별도의 레이어 타입인 **`fill-extrusion`** 을 써야 한다.

`fill-extrusion`은 2D 폴리곤의 각 변을 수직으로 밀어 올려(압출·extrude) 3D 입체 형태로 렌더링하는 전용 레이어 타입이다. 지도가 3D 시점(pitch)으로 기울어져 있을 때만 이 입체감이 눈에 보이므로, 평면 시점 그대로 두고 fill-extrusion을 적용하면 "분명 설정했는데 아무 변화가 없다"고 오해하기 쉽다.

## 첫 설정: 지도에 pitch를 주고 fill-extrusion 레이어 추가하기

```javascript
const map = new maplibregl.Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json',
  center: [126.978, 37.5665],
  zoom: 15,
  pitch: 60,   // 시점을 기울여야 입체감이 보인다
  bearing: -20,
});

map.on('load', () => {
  map.addLayer({
    id: 'buildings-3d',
    type: 'fill-extrusion',
    source: 'openmaptiles',
    'source-layer': 'building',
    paint: {
      'fill-extrusion-color': '#aab8c2',
      'fill-extrusion-height': ['get', 'render_height'],
      'fill-extrusion-base': ['get', 'render_min_height'],
      'fill-extrusion-opacity': 0.85,
    },
  });
});
```

`pitch: 60`처럼 지도를 충분히 기울이지 않으면 위에서 내려다보는 시점이라 건물이 세워져 있어도 눈으로는 그냥 평면 도형처럼 보인다. 처음 fill-extrusion을 시도했는데 "아무 효과가 없다"고 느끼는 경우 대부분 이 pitch 설정을 빼먹었기 때문이다.

## 흔한 실수: 높이 데이터가 없는데 고정값만 주기

`fill-extrusion-height`에 벡터 타일 속성값(`render_height` 등)이 아니라 고정 숫자를 주면, 모든 건물이 똑같은 높이로 뭉뚱그려져 도시의 실제 스카이라인을 전혀 반영하지 못한다.

```javascript
// 잘못된 예: 모든 건물이 30m로 똑같이 표시됨
'fill-extrusion-height': 30,

// 올바른 예: 타일 속성에 담긴 실제 층수/높이 정보를 표현식으로 참조
'fill-extrusion-height': ['get', 'render_height'],
```

사용하는 벡터 타일 소스(OpenMapTiles, Mapbox Streets 등)마다 높이 관련 속성명이 다를 수 있으므로, 스타일을 작성하기 전에 반드시 해당 타일 소스의 스키마 문서에서 실제 속성명을 확인해야 한다. 속성명이 다르면 `['get', '없는속성']`은 `undefined`를 반환하고, 결과적으로 모든 건물이 높이 0으로 렌더링되어 다시 평면처럼 보이게 된다.

<img src="/assets/images/posts/2026-09-22-maplibre-fill-extrusion-3d-buildings-1.svg" alt="fill 레이어는 폴리곤을 평면으로 채우고 fill-extrusion 레이어는 render_height 속성값만큼 폴리곤을 수직으로 압출해 입체 건물을 만드는 과정을 비교하는 다이어그램" style="width:100%;">

## fill-extrusion-base로 지하층·경사지 건물 처리하기

`fill-extrusion-base`는 압출을 시작하는 바닥 높이를 지정한다. 기본값 0이면 모든 건물이 지면(고도 0)에서부터 솟아오른다고 가정하는데, 실제로는 경사진 지형에 건물이 있거나 지하 주차장처럼 지면 아래로 파인 구조가 있는 경우 이 값을 조정해 더 사실적인 표현이 가능하다.

| 속성 | 역할 | 흔한 실수 |
|---|---|---|
| `fill-extrusion-height` | 건물 꼭대기 높이 | 고정값 사용으로 스카이라인이 평평해짐 |
| `fill-extrusion-base` | 압출 시작 높이(바닥) | 기본값 0을 그대로 둬서 경사지 표현이 부자연스러움 |
| `fill-extrusion-opacity` | 투명도 | 1.0으로 두면 건물 뒤편 도로·라벨이 완전히 가려짐 |

## 실무 포인트

- **줌 레벨에 따라 fill-extrusion 표시 여부를 조절하라.** 도시 전체를 줌아웃한 상태에서 수만 개의 건물을 모두 압출하면 렌더링 부하가 커진다. `minzoom` 설정으로 일정 줌 레벨 이상에서만 3D 건물을 표시하는 것이 일반적이다.
- **라이트 설정(`light`)으로 입체감을 더 살릴 수 있다.** MapLibre 스타일의 `light` 속성으로 광원의 방향과 강도를 조정하면 건물 면마다 음영이 달라져 실제로 훨씬 입체적으로 보인다.
- **성능이 중요하다면 3D Tiles나 별도 3D 렌더링 라이브러리(Cesium, deck.gl)를 함께 검토하라.** fill-extrusion은 간단한 도시 스카이라인 표현에는 충분하지만, 건물 외벽 텍스처나 매우 정밀한 3D 모델까지 필요하다면 별도의 3D 전용 파이프라인이 더 적합하다.

## 마무리 요약

- 평면 지도에 건물을 입체로 세우려면 `fill` 레이어가 아니라 `fill-extrusion` 레이어 타입을 써야 하고, 지도의 `pitch`를 함께 기울여야 눈으로 입체감을 확인할 수 있다.
- 높이 값은 고정 숫자가 아니라 벡터 타일 속성(`render_height` 등)을 표현식으로 참조해야 실제 도시 스카이라인을 반영할 수 있다.
- 사용하는 타일 소스마다 높이 속성명이 다르므로, 스타일 작성 전 타일 스키마 문서 확인이 필수다.

## 참고 자료

- [MapLibre GL JS 공식 문서 - fill-extrusion](https://maplibre.org/maplibre-style-spec/layers/#fill-extrusion)
- [OpenMapTiles 스키마 - building](https://openmaptiles.org/schema/#building)
