---
layout: single
title: "MapLibre GL JS 마커가 너무 많을 때 — Supercluster로 클러스터링하기"
date: 2026-09-21 12:20:00 +0530
categories: gis
tags: ["maplibre", "supercluster", "마커클러스터링", "웹지도", "geojson"]
toc: true
toc_sticky: true
excerpt: "MapLibre GL JS에서 수천 개의 포인트 마커를 그대로 찍으면 렌더링이 느려지고 지도가 뒤덮이는 문제를, GeoJSON 소스의 내장 클러스터링 옵션으로 해결하는 방법을 정리했다."
---

## 왜 마커가 많아지면 문제가 생기나

매장 위치, 부동산 매물, IoT 센서 좌표처럼 포인트 데이터가 수천 개를 넘어가는 지도를 MapLibre GL JS로 만들다 보면 두 가지 문제가 동시에 온다. 첫째는 성능이다. 개별 DOM 마커(`new maplibregl.Marker()`)를 수천 개 찍으면 브라우저가 그 개수만큼 DOM 노드를 관리해야 해서 팬·줌마다 버벅인다. 둘째는 가독성이다. 마커가 서로 겹쳐 화면이 온통 점으로 뒤덮이면, 정작 사용자가 보고 싶은 "이 동네에 매물이 몇 개 있는지"라는 정보를 오히려 읽을 수 없게 된다.

이 두 문제를 동시에 해결하는 표준적인 방법이 **마커 클러스터링**이다. 줌 레벨이 낮을 때는 가까운 포인트들을 하나의 원(클러스터)으로 묶어 숫자만 표시하고, 줌 레벨을 올리면 클러스터가 점점 개별 포인트로 풀리는 방식이다.

## 잘못된 접근: 직접 거리 계산으로 그룹핑

클러스터링을 처음 구현할 때 흔히 시도하는 방법은 화면에 보이는 모든 포인트 쌍의 거리를 직접 계산해 가까운 것끼리 묶는 것이다.

```javascript
// 비효율적인 접근: O(n^2) 비교
points.forEach(p1 => {
  points.forEach(p2 => {
    if (distance(p1, p2) < threshold) { /* 그룹핑 */ }
  });
});
```

포인트 수가 적을 때는 동작하지만, 수천 개로 늘어나면 이 방식은 팬·줌 이벤트마다 다시 계산되면서 프레임 드랍이 눈에 띄게 발생한다. 또한 "줌 레벨에 따라 클러스터 반경을 어떻게 조정할지"까지 직접 구현하려면 로직이 급격히 복잡해진다.

## 올바른 접근: GeoJSON 소스의 내장 클러스터링

<img src="/assets/images/posts/2026-09-21-maplibre-marker-clustering-1.svg" alt="줌 레벨이 낮을 때는 가까운 포인트들이 하나의 클러스터 원으로 뭉치고, 줌 레벨을 올리면 클러스터가 점점 개별 포인트로 풀리는 과정을 보여주는 다이어그램" style="width:100%;">

MapLibre GL JS는 GeoJSON 소스에 `cluster: true`만 지정하면 내부적으로 Supercluster 라이브러리를 사용해 이 작업을 처리해준다.

```javascript
map.addSource('points', {
  type: 'geojson',
  data: 'points.geojson',
  cluster: true,
  clusterMaxZoom: 14,   // 이 줌 레벨 이상에서는 클러스터링 안 함
  clusterRadius: 50     // 클러스터로 묶을 픽셀 반경
});

map.addLayer({
  id: 'clusters',
  type: 'circle',
  source: 'points',
  filter: ['has', 'point_count'],
  paint: {
    'circle-color': ['step', ['get', 'point_count'], '#51bbd6', 100, '#f1f075', 750, '#f28cb1'],
    'circle-radius': ['step', ['get', 'point_count'], 20, 100, 30, 750, 40]
  }
});

map.addLayer({
  id: 'cluster-count',
  type: 'symbol',
  source: 'points',
  filter: ['has', 'point_count'],
  layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 }
});

map.addLayer({
  id: 'unclustered-point',
  type: 'circle',
  source: 'points',
  filter: ['!', ['has', 'point_count']],
  paint: { 'circle-color': '#11b4da', 'circle-radius': 6 }
});
```

핵심은 세 개의 레이어를 나눠 그리는 것이다. `point_count` 속성이 있는 피처는 클러스터(원+숫자), 없는 피처는 개별 포인트로 필터링해 각각 다른 스타일을 적용한다. Supercluster는 내부적으로 KD-tree 기반 공간 인덱스를 미리 구축해두기 때문에, 줌 레벨이 바뀔 때마다 O(n²) 재계산 없이 빠르게 클러스터를 다시 계산한다.

## 클러스터 클릭 시 확대(zoom to expand) 처리

```javascript
map.on('click', 'clusters', async (e) => {
  const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] });
  const clusterId = features[0].properties.cluster_id;
  const zoom = await map.getSource('points').getClusterExpansionZoom(clusterId);
  map.easeTo({ center: features[0].geometry.coordinates, zoom });
});
```

클러스터 원을 클릭하면 그 클러스터가 풀리는 최소 줌 레벨로 자동 확대하는 UX가 사용자 경험을 크게 개선한다. 이 처리를 빠뜨리면 사용자가 클러스터를 눌러도 아무 반응이 없어 답답함을 느낀다.

## 실무 포인트

- **데이터가 수만 개를 넘으면 클라이언트 클러스터링만으로는 부족하다.** 이 경우 서버 사이드에서 미리 타일링(벡터 타일)하거나, Tippecanoe로 PMTiles를 생성해 애초에 줌 레벨별로 필요한 데이터만 내려주는 구조를 검토해야 한다.
- **`clusterProperties` 옵션으로 클러스터 안 평균값·합계를 계산할 수 있다.** 예를 들어 매물 클러스터에 "평균 가격"을 표시하고 싶다면 `clusterProperties: { avg_price: ['+', ['get', 'price']] }` 형태로 집계식을 정의한다.
- **원본 데이터가 자주 갱신된다면 `setData()`로 소스를 갈아끼우되, 불필요하게 자주 호출하지 마라.** 매번 전체 GeoJSON을 다시 파싱하고 클러스터 인덱스를 재구축하므로 비용이 크다.

## 마무리 요약

- 포인트가 많아지면 성능과 가독성 문제가 동시에 오며, 표준 해법은 클러스터링이다.
- MapLibre GL JS는 GeoJSON 소스에 `cluster: true`만 지정하면 Supercluster 기반 클러스터링을 자동으로 처리한다.
- 클러스터 클릭 시 확대 UX와 데이터 규모에 따른 서버 사이드 타일링 전환까지 함께 고려해야 완성도 있는 지도가 된다.

## 참고 자료

- [MapLibre GL JS 공식 문서 - Create and style clusters](https://maplibre.org/maplibre-gl-js/docs/examples/cluster/)
- [Supercluster GitHub](https://github.com/mapbox/supercluster)
