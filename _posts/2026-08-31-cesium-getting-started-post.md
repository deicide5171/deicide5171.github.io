---
layout: single
title: "Cesium 시작하기 — 3D 지구본 띄우고 카메라 다루기"
date: 2026-08-31 13:20:00 +0530
categories: gis
tags: ["cesium", "3d지도", "웹지도", "gis", "입문"]
toc: true
toc_sticky: true
excerpt: "3D 지구본 렌더링 라이브러리 Cesium을 npm으로 설치해 첫 화면을 띄우고, 카메라 이동과 엔티티 추가까지 따라 하는 입문 가이드."
---

## 왜 지금 Cesium인가

2D 웹 지도 라이브러리(Leaflet, OpenLayers 등)로는 지형 고도, 3D 건물, 위성 궤도 같은 데이터를 표현하기 어렵다. Cesium은 처음부터 **WGS84 타원체 위에서의 3D 렌더링**을 전제로 설계된 오픈소스 라이브러리라, 디지털 트윈이나 항공·위성 데이터 시각화에서 사실상 표준처럼 쓰인다. 다만 2D 지도보다 개념이 하나 더 있어서 처음 접하면 어디서부터 손대야 할지 막막할 수 있다.

## 2D 지도와 3D 지구본의 좌표 개념 차이

<img src="/assets/images/posts/2026-08-31-cesium-getting-started-1.svg" alt="2D 평면 좌표계와 Cesium이 사용하는 WGS84 타원체 기반 3차원 Cartesian 좌표계, 그리고 위치·방향·시야각을 갖는 3D 카메라 개념을 비교하는 다이어그램" style="width:100%;">

## 2D 지도 라이브러리와의 차이

| 항목 | Leaflet/OpenLayers | Cesium |
|---|---|---|
| 좌표 표현 | 평면 좌표(투영법 적용) | 지구 타원체 위 3차원 좌표(Cartesian3) |
| 카메라 | 팬/줌 중심 | 위치+방향+시야각을 가진 3D 카메라 |
| 지형 | 기본 미지원(플러그인 필요) | Cesium World Terrain 내장 지원 |
| 대표 데이터 포맷 | GeoJSON, WMS/WMTS | 3D Tiles, CZML, KML |

## 코드 예제: 첫 지구본 띄우기

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <style>#cesiumContainer { width: 100%; height: 500px; }</style>
</head>
<body>
  <div id="cesiumContainer"></div>
  <script>
    Cesium.Ion.defaultAccessToken = 'YOUR_ION_ACCESS_TOKEN'; // ion.cesium.com에서 무료 발급
    const viewer = new Cesium.Viewer('cesiumContainer', {
      terrain: Cesium.Terrain.fromWorldTerrain(),
    });

    // 카메라를 서울 상공으로 이동
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(126.978, 37.5665, 15000),
    });
  </script>
</body>
</html>
```

`Cartesian3.fromDegrees(경도, 위도, 고도)`로 좌표를 지정하는 점이 2D 라이브러리와 가장 다른 부분이다. 지형까지 렌더링하려면 무료 Ion 계정에서 액세스 토큰을 발급받아야 한다.

## 엔티티 추가하기

```javascript
viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(126.978, 37.5665),
  point: { pixelSize: 12, color: Cesium.Color.RED },
  label: { text: '서울 시청', font: '14px sans-serif' },
});
```

`viewer.entities.add()`로 점, 라벨, 폴리곤, 3D 모델 등을 지도 위에 올릴 수 있다. 시간에 따라 위치가 바뀌는 엔티티(위성, 항공기 등)는 CZML 포맷으로 정의하는 것이 일반적이다.

## 실무 포인트

- **Ion 액세스 토큰 없이도 라이브러리는 동작하지만, World Terrain이나 위성 영상 베이스맵은 Ion 서비스를 거치므로 토큰이 필요하다.** 무료 티어로도 개인 프로젝트는 충분히 커버된다.
- **대용량 3D 모델은 반드시 3D Tiles로 변환해서 로드해야 한다.** 원본 3D 모델 포맷을 그대로 올리면 브라우저가 감당하지 못한다.
- **`flyTo`의 `duration`을 지정하지 않으면 카메라 이동 속도가 거리에 비례해 자동 계산된다.** 짧은 이동에서도 예상보다 느리게 느껴진다면 `duration` 값을 직접 지정하자.

## 마무리 요약

- Cesium은 좌표를 `Cartesian3.fromDegrees(경도, 위도, 고도)`로 다루는 3D 전용 지도 라이브러리다.
- World Terrain과 위성 베이스맵을 쓰려면 Cesium Ion의 무료 액세스 토큰이 필요하다.
- 대용량 3D 모델은 3D Tiles로 변환해야 브라우저에서 안정적으로 렌더링된다.

## 참고 자료

- [Cesium 공식 문서](https://cesium.com/learn/cesiumjs-learn/)
- [Cesium Sandcastle 예제 모음](https://sandcastle.cesium.com/)
