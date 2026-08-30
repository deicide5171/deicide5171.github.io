---
layout: single
title: "MapLibre GL JS에서 커스텀 마커 아이콘 쓰기 — addImage 흔한 실수"
date: 2026-09-21 12:20:00 +0530
categories: gis
tags: ["maplibre", "커스텀마커", "addimage", "심볼레이어", "웹지도"]
toc: true
toc_sticky: true
excerpt: "MapLibre GL JS에서 기본 원형 대신 브랜드 아이콘으로 마커를 표시하려 할 때, 이미지가 안 보이거나 렌더링 타이밍 에러가 나는 이유를 addImage API 기준으로 정리했다."
---

## 왜 기본 마커로는 부족한가

MapLibre GL JS로 원형 circle 레이어를 그리면 빠르고 간단하지만, 실제 서비스에서는 카테고리별로 다른 아이콘(음식점, 주유소, 병원 등)을 지도에 표시해야 하는 경우가 훨씬 많다. `new maplibregl.Marker()`로 DOM 기반 마커를 개별 생성할 수도 있지만, 앞선 글에서 다뤘듯 포인트 수가 많아지면 DOM 마커는 성능 문제를 일으킨다. 대량의 커스텀 아이콘을 성능 저하 없이 표시하려면 GeoJSON 소스 + `symbol` 레이어 + 이미지 스프라이트 조합이 정석이다.

## 잘못된 접근: 이미지를 바로 스타일에 참조하기

처음 시도하는 방법은 이렇다.

```javascript
map.addLayer({
  id: 'poi',
  type: 'symbol',
  source: 'poi-source',
  layout: {
    'icon-image': 'restaurant-icon'  // 아직 등록 안 된 이미지 이름
  }
});
```

이렇게 하면 브라우저 콘솔에 `Image "restaurant-icon" could not be loaded` 같은 경고가 뜨거나, 최악의 경우 아무 에러 없이 그냥 아이콘이 안 보인다. MapLibre GL JS의 스타일 시스템은 CSS의 `background-image`처럼 파일 경로를 직접 참조하는 방식이 아니라, **먼저 `map.addImage()`로 이미지를 스타일의 스프라이트 시트에 등록해야만 `icon-image`에서 그 이름으로 참조할 수 있다.** 이 등록 절차를 빠뜨리는 것이 가장 흔한 첫 실수다.

<img src="/assets/images/posts/2026-09-21-maplibre-marker-icon-addimage-1.svg" alt="loadImage로 이미지를 비동기로 불러온 뒤 addImage로 스프라이트에 등록하고, 그 다음에야 symbol 레이어의 icon-image에서 참조할 수 있는 순서를 보여주는 다이어그램" style="width:100%;">

## 올바른 접근: loadImage로 로드하고 addImage로 등록

```javascript
map.loadImage('/assets/icons/restaurant.png', (error, image) => {
  if (error) throw error;
  if (!map.hasImage('restaurant-icon')) {
    map.addImage('restaurant-icon', image);
  }

  map.addLayer({
    id: 'poi',
    type: 'symbol',
    source: 'poi-source',
    layout: {
      'icon-image': 'restaurant-icon',
      'icon-size': 0.5,
      'icon-allow-overlap': true
    }
  });
});
```

핵심은 **이미지 로딩이 비동기**라는 점이다. `loadImage()`의 콜백(혹은 Promise) 안에서 `addImage()`를 호출하고, 그 이후에 레이어를 추가하거나 스타일을 갱신해야 한다. 레이어 정의를 이미지 로딩보다 먼저 실행하면, 아직 등록되지 않은 이미지 이름을 참조하는 순간이 생겨 렌더링이 실패한다.

## 두 번째 흔한 실수: 스타일 리로드 시 이미지가 사라짐

```javascript
map.setStyle('mapbox://styles/new-style');
// 이후 poi 레이어를 다시 추가하려 하면 addImage 에러
```

`setStyle()`로 스타일을 완전히 교체하면, 이전 스타일에 등록해둔 이미지들도 함께 사라진다. 스타일이 바뀐 뒤 같은 커스텀 아이콘을 다시 쓰려면 `style.load` 이벤트를 기다렸다가 `addImage()`를 다시 호출해야 한다.

```javascript
map.on('style.load', () => {
  map.loadImage('/assets/icons/restaurant.png', (error, image) => {
    if (error) throw error;
    if (!map.hasImage('restaurant-icon')) {
      map.addImage('restaurant-icon', image);
    }
  });
});
```

이 이벤트 리스너를 놓치면, 스타일 전환 기능(예: 다크모드/라이트모드 지도 스타일 토글)을 넣었을 때 전환 직후 커스텀 아이콘이 전부 사라지는 버그로 이어진다.

## SDF 아이콘으로 색상 동적 변경하기

```javascript
map.loadImage('/assets/icons/pin-sdf.png', (error, image) => {
  map.addImage('pin-icon', image, { sdf: true });

  map.addLayer({
    id: 'poi',
    type: 'symbol',
    layout: { 'icon-image': 'pin-icon' },
    paint: { 'icon-color': ['match', ['get', 'category'], 'food', '#e74c3c', '#3498db'] }
  });
});
```

`sdf: true` 옵션으로 등록한 이미지(단색 실루엣 형태로 준비된 SDF 이미지)는 `icon-color` 속성으로 런타임에 색을 바꿀 수 있다. 카테고리별로 아이콘 이미지 파일을 여러 개 준비하지 않고도, 하나의 실루엣 이미지로 색상만 데이터에 따라 다르게 표현할 수 있어 이미지 자산 관리가 훨씬 단순해진다.

## 실무 포인트

- **`hasImage()`로 중복 등록을 방지하라.** 같은 이름으로 `addImage()`를 두 번 호출하면 에러가 나므로, 조건 검사를 습관화한다.
- **아이콘이 많다면 스프라이트를 미리 빌드하라.** 개별 이미지를 하나씩 `loadImage()`로 불러오는 대신, Mapbox의 `spritezero` 같은 도구로 스프라이트 시트를 미리 만들어두면 네트워크 요청 수를 줄일 수 있다.
- **HiDPI(레티나) 디스플레이 대응을 잊지 마라.** `addImage()`의 세 번째 인자로 `pixelRatio: 2`를 지정하지 않으면 고해상도 화면에서 아이콘이 흐릿하게 보인다.
- **`icon-allow-overlap`과 `icon-ignore-placement`를 상황에 맞게 조정하라.** 기본값은 아이콘끼리 겹치면 자동으로 숨기므로, 밀집된 POI 지역에서 아이콘이 뜻하지 않게 사라지는 경우 이 옵션부터 점검한다.

## 마무리 요약

- MapLibre GL JS에서 커스텀 아이콘을 쓰려면 `icon-image`에서 참조하기 전에 반드시 `addImage()`로 스프라이트에 먼저 등록해야 한다.
- 이미지 로딩은 비동기이므로 콜백 순서를 지키지 않으면 렌더링이 조용히 실패하고, 스타일을 통째로 교체하면 등록된 이미지도 함께 사라진다.
- SDF 이미지와 `icon-color`를 조합하면 카테고리별 이미지 파일 없이도 색상만 다르게 표현할 수 있다.

## 참고 자료

- [MapLibre GL JS 공식 문서 - addImage](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/#addimage)
- [MapLibre GL JS 공식 예제 - Add an icon to the map](https://maplibre.org/maplibre-gl-js/docs/examples/add-image/)
