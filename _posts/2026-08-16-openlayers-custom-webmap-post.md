---
layout: single
title: "OpenLayers로 나만의 웹 지도 만들기 — 레이어·스타일·인터랙션 직접 다루기"
date: 2026-08-16 12:20:00 +0530
categories: gis
tags: ["openlayers", "webmap", "javascript", "vector-layer", "gis"]
toc: true
toc_sticky: true
excerpt: "특정 지도 서비스 API에 종속되지 않고 타일·벡터·스타일·인터랙션을 코드로 직접 조립하고 싶을 때, OpenLayers의 Map·View·Layer·Source 구조를 이해하면 커스텀 웹 지도를 처음부터 설계할 수 있다."
---

## 왜 지금 OpenLayers인가

Mapbox GL이나 MapLibre가 벡터 타일 스타일링과 3D 표현에서 강점을 보이는 사이, **OpenLayers**는 다른 축에서 자리를 지켜왔다. 특정 타일 제공사나 스타일 스펙에 종속되지 않고, WMS·WMTS·GeoJSON·벡터 타일·래스터 등 이질적인 데이터 소스를 하나의 지도 위에 자유롭게 올릴 수 있는 **범용성**이다. 공공기관 GIS 포털이나 사내 지도 시스템처럼 "여러 부서가 서로 다른 포맷으로 만든 데이터를 한 화면에 합쳐야 하는" 상황에서 OpenLayers가 여전히 우선 검토 대상으로 꼽히는 이유다.

BSD 라이선스 오픈소스라 상용 API 키나 사용량 과금 없이 자체 타일 서버·오픈 데이터와 조합해 쓸 수 있다는 점도 실무에서 자주 선택되는 배경이다. 다만 Mapbox GL 계열보다 학습 곡선이 있는 편인데, 그 이유는 지도를 이루는 객체들의 책임이 명확히 분리되어 있어서다. 이 분리 구조를 먼저 이해하면 이후 커스터마이징이 훨씬 수월해진다.

## 핵심 개념 1: Map · View · Layer · Source의 역할 분담

OpenLayers 지도는 하나의 거대한 컴포넌트가 아니라, 역할이 분리된 객체들의 조합이다.

| 객체 | 책임 | 비유 |
|---|---|---|
| `Map` | DOM에 렌더링, 레이어 목록·상호작용 관리 | 캔버스 그 자체 |
| `View` | 중심좌표·줌 레벨·좌표계(projection) 정의 | 카메라 |
| `Layer` | 화면에 그려질 시각적 단위(타일/벡터 등) | 그림이 그려질 레이어 |
| `Source` | 실제 데이터 공급원(URL, GeoJSON 등) | 데이터 원본 |

`Map`은 `layers` 배열을 아래에서 위 순서로 그리고, 각 `Layer`는 자신의 `Source`에서 데이터를 받아온다. `View`는 어떤 좌표계·확대 수준으로 보여줄지만 결정하고, 실제로 무엇을 그릴지는 전혀 알지 못한다. 이 분리 덕분에 배경 타일 레이어를 교체하거나 벡터 레이어를 추가·제거해도 `View` 설정은 그대로 재사용된다.

<img src="/assets/images/posts/2026-08-16-openlayers-custom-webmap-1.svg" alt="OpenLayers 아키텍처 개념도 - Map, View, Layer, Source, Style, Interaction의 관계" style="width:100%;">

## 핵심 개념 2: 스타일은 함수로 결정된다

`ol.layer.Vector`의 표현은 고정된 색상표가 아니라 **스타일 함수**로 정의하는 것이 일반적이다. 피처(feature)마다 속성값에 따라 다른 `Fill`·`Stroke`·`Icon`을 반환하면, 인구밀도·상태값·카테고리 등 데이터 기반 시각화를 코드 레벨에서 세밀하게 제어할 수 있다. 정적 스타일 객체 하나만 지정하면 모든 피처가 동일하게 그려지고, 함수를 넘기면 피처·해상도(resolution)를 인자로 받아 매 렌더링마다 스타일을 계산한다.

## 예제: 배경 타일 + 데이터 기반 벡터 스타일링

```javascript
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import TileLayer from 'ol/layer/Tile.js';
import VectorLayer from 'ol/layer/Vector.js';
import VectorSource from 'ol/source/Vector.js';
import XYZ from 'ol/source/XYZ.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { Fill, Stroke, Style, Circle as CircleStyle } from 'ol/style.js';
import Select from 'ol/interaction/Select.js';

const baseLayer = new TileLayer({
  source: new XYZ({ url: 'https://{a-c}.tile.example.com/{z}/{x}/{y}.png' }),
});

const vectorSource = new VectorSource({
  url: '/data/stations.geojson',
  format: new GeoJSON(),
});

const vectorLayer = new VectorLayer({
  source: vectorSource,
  style: (feature) => {
    const isActive = feature.get('status') === 'active';
    return new Style({
      image: new CircleStyle({
        radius: 6,
        fill: new Fill({ color: isActive ? '#2fa84f' : '#999999' }),
        stroke: new Stroke({ color: '#ffffff', width: 1.5 }),
      }),
    });
  },
});

const map = new Map({
  target: 'map',
  layers: [baseLayer, vectorLayer],
  view: new View({ center: [14135000, 4518000], zoom: 12 }), // EPSG:3857
});

// 클릭 시 피처 선택 하이라이트
map.addInteraction(new Select({ layers: [vectorLayer] }));
```

`View`의 좌표는 기본 좌표계인 `EPSG:3857`(Web Mercator) 기준이라, 위경도(EPSG:4326) 값을 그대로 넣으면 엉뚱한 위치에 지도가 표시된다. `ol/proj`의 `fromLonLat()`으로 변환하거나, `proj4` 라이브러리로 필요한 좌표계를 등록해야 정확히 맞아떨어진다.

## 실무 포인트

- **좌표계 변환은 항상 명시적으로 처리한다.** 서버에서 내려오는 데이터가 EPSG:4326인지 3857인지 먼저 확인하고, `Source`나 `View` 생성 시 `projection` 옵션을 명시한다.
- **벡터 피처가 많아지면 클러스터링을 검토한다.** `ol/source/Cluster`로 근접 피처를 묶지 않으면 수천 개 포인트에서 렌더링 성능이 급격히 떨어진다.
- **인터랙션은 레이어 단위로 범위를 좁힌다.** `Select`·`Modify` 등에 `layers` 옵션을 지정하지 않으면 모든 벡터 레이어가 대상이 되어 의도치 않은 편집이 발생할 수 있다.
- **번들 크기는 개별 모듈 import로 관리한다.** `import Map from 'ol'` 대신 예제처럼 `ol/Map.js` 식 개별 경로로 가져오면 트리 셰이킹이 적용돼 번들에 불필요한 모듈이 포함되지 않는다.

## 3줄 요약

- OpenLayers는 Map·View·Layer·Source의 책임이 분리된 구조라, 배경 타일과 벡터 데이터를 자유롭게 조합하고 교체할 수 있다.
- 벡터 레이어의 표현은 정적 스타일 객체 대신 스타일 함수로 정의하면 피처 속성에 따른 데이터 기반 시각화가 가능하다.
- 실무 도입 시에는 좌표계 명시적 변환, 대량 피처 클러스터링, 인터랙션 대상 레이어 제한을 함께 챙겨야 한다.

## 참고 자료

- [OpenLayers 공식 문서 — Quick Start](https://openlayers.org/doc/quickstart.html)
- [OpenLayers API — ol/layer/Vector](https://openlayers.org/en/latest/apidoc/module-ol_layer_Vector.html)
- [OpenLayers 공식 예제 모음](https://openlayers.org/en/latest/examples/)
