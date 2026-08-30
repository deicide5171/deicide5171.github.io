---
layout: single
title: "MapLibre GL JS Terrain — 표고 데이터(DEM)로 3D 지형 렌더링하기"
date: 2026-09-24 12:20:00 +0530
categories: gis
tags: ["MapLibre", "Terrain", "DEM", "3D웹지도", "지형렌더링"]
toc: true
toc_sticky: true
excerpt: "평면 벡터 타일 지도에 등고선만으로 표현하던 지형을, MapLibre GL JS의 terrain 소스가 Terrain-RGB 타일을 디코딩해 실제로 높낮이가 있는 3D 메시로 변형하는 원리와 exaggeration·hillshade 설정을 정리했다."
---

## 왜 지금 MapLibre Terrain을 알아야 하는가

등산로 지도, 재난 대응(침수·산사태 시뮬레이션), 드론 비행 경로 계획처럼 지형 자체가 핵심 정보인 서비스에서는 등고선이나 색상 음영만으로 지형을 표현하는 2D 지도가 직관성이 떨어진다. 사용자가 카메라를 기울여 실제로 산과 계곡의 높낮이를 눈으로 확인할 수 있어야 하는 요구가 늘면서, MapLibre GL JS는 `terrain` 소스 타입으로 지형 표고 데이터를 실제 3D 메시로 변형해 렌더링하는 기능을 제공한다. 문제는 이 기능이 단순히 "옵션 하나 켜면 끝"이 아니라, 표고 데이터가 어떤 형식으로 인코딩돼 있고 GPU에서 어떻게 메시로 변환되는지를 이해해야 결과물의 품질과 성능을 제어할 수 있다는 점이다.

## 핵심 개념 1 — Terrain-RGB 타일: 표고 값을 이미지 픽셀로 인코딩하기

지형 표고 데이터를 서버에서 클라이언트로 효율적으로 전송하기 위해, 대부분의 지형 서비스는 표고 값을 일반 PNG 이미지의 RGB 채널에 인코딩한 Terrain-RGB(또는 Mapbox Terrain-RGB와 유사한 포맷) 타일을 쓴다. 각 픽셀의 R, G, B 값을 조합해 하나의 정밀한 고도 값을 복원할 수 있도록 인코딩 공식이 정해져 있다(예: `height = -10000 + (R*256*256 + G*256 + B) * 0.1`). 이 방식의 장점은 기존 타일 서버·CDN 인프라를 그대로 재사용할 수 있다는 것이다 — 지형 데이터가 특수한 포맷이 아니라 "그냥 PNG 이미지"이기 때문에 캐싱이나 배포가 벡터/래스터 타일과 동일하게 다뤄진다.

<img src="/assets/images/posts/2026-09-24-maplibre-terrain-3d-elevation-rendering-1.svg" alt="Terrain-RGB 타일의 픽셀 값이 셰이더에서 고도 값으로 디코딩되고, 이 값이 GPU 메시의 정점 Z좌표로 사용되어 평면 타일이 실제 지형 높낮이를 가진 3D 메시로 변형되는 과정과, exaggeration 값에 따라 지형 굴곡이 과장되는 비교를 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — GPU에서 평면 타일이 3D 메시로 변형되는 과정

MapLibre는 지형 타일을 일반 격자 메시(grid mesh)로 미리 준비해두고, Terrain-RGB 타일에서 디코딩한 고도 값을 이 메시의 각 정점(vertex)의 Z좌표로 대입한다. 이 변형은 버텍스 셰이더 단계에서 GPU가 수행하므로, CPU는 표고 데이터를 미리 지오메트리로 변환하는 무거운 전처리를 할 필요가 없다. 벡터 레이어나 위성 이미지 같은 다른 레이어는 이렇게 변형된 지형 메시 위에 "드레이핑(draping)"되어, 실제 지형 굴곡을 따라 자연스럽게 씌워진다. 카메라 각도를 기울이면(pitch) 이 3D 메시가 실제 원근감을 갖고 렌더링되어 산과 계곡의 입체감이 드러난다.

| 항목 | 설명 |
|---|---|
| Terrain-RGB 타일 | 표고 값을 PNG의 RGB 채널로 인코딩한 래스터 타일 |
| 지형 메시 변형 | 버텍스 셰이더에서 고도 값을 정점 Z좌표로 대입 |
| exaggeration | 실제 고도 대비 시각적 과장 배율 (1.0이 실제 비율) |
| hillshade | 조명 방향을 가정해 경사면에 음영을 넣는 별도 레이어 |

## 예제 — Terrain 소스 설정과 exaggeration 적용

```javascript
map.on('load', () => {
  map.addSource('terrain-dem', {
    type: 'raster-dem',
    tiles: ['https://example.com/terrain-rgb/{z}/{x}/{y}.png'],
    tileSize: 256,
    maxzoom: 14,
  });

  map.setTerrain({
    source: 'terrain-dem',
    exaggeration: 1.5, // 평탄한 지형도 입체감이 드러나도록 과장
  });

  // 경사·방향 기반 음영을 별도 레이어로 추가해 입체감을 보강
  map.addLayer({
    id: 'hillshade',
    type: 'hillshade',
    source: 'terrain-dem',
    paint: { 'hillshade-exaggeration': 0.5 },
  });

  map.easeTo({ pitch: 60, bearing: -20 }); // 카메라를 기울여야 지형이 눈에 보임
});
```

## 실무 포인트

- **`exaggeration`을 지역 특성에 맞게 조정하라.** 평지가 대부분인 지역에서는 기본값(1.0)으로는 지형 굴곡이 거의 안 보이므로 값을 높여야 하지만, 산악 지형에서 과도하게 높이면 오히려 비현실적으로 뾰족해 보인다.
- **지형 타일의 해상도와 maxzoom을 실제 필요 수준으로 제한하라.** 표고 데이터는 대부분 위성 관측 기반이라 특정 줌 레벨 이상에서는 실질적인 해상도 향상이 없는데도 타일 요청만 늘어나는 경우가 있다.
- **모바일 기기에서는 지형 렌더링 성능을 별도로 테스트하라.** 3D 메시 변형과 hillshade 조합은 저사양 GPU에서 프레임 드롭을 유발할 수 있으므로, 필요하다면 기기 성능에 따라 지형 기능을 조건부로 비활성화하는 것도 고려해야 한다.

## 마무리 요약

- MapLibre의 Terrain 기능은 Terrain-RGB 타일에 인코딩된 고도 값을 GPU 버텍스 셰이더 단계에서 메시 정점 Z좌표로 변형해 3D 지형을 만든다.
- 이 방식 덕분에 지형 데이터도 일반 래스터 타일처럼 기존 CDN·캐싱 인프라를 그대로 활용할 수 있다.
- exaggeration과 hillshade 설정을 지역 특성에 맞게 조정해야 지형이 실제보다 밋밋하거나 비현실적으로 과장되는 문제를 피할 수 있다.

## 참고 자료

- [MapLibre GL JS - setTerrain](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/#setterrain)
- [MapLibre GL JS - 3D Terrain example](https://maplibre.org/maplibre-gl-js/docs/examples/3d-terrain/)
