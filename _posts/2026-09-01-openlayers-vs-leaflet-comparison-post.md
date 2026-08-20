---
layout: single
title: "OpenLayers vs Leaflet, 뭘 배워야 할까 — 초보자를 위한 웹 지도 라이브러리 비교"
date: 2026-09-01 12:20:00 +0530
categories: gis
tags: ["openlayers", "leaflet", "웹지도", "gis입문", "비교"]
toc: true
toc_sticky: true
excerpt: "웹 지도 개발을 시작할 때 가장 먼저 고민하게 되는 OpenLayers와 Leaflet 중 무엇을 배워야 할지, 기능과 학습 곡선 기준으로 비교했다."
---

## 왜 이 두 라이브러리가 항상 같이 언급되나

웹 지도 관련 강의나 튜토리얼을 찾아보면 OpenLayers와 Leaflet이 거의 항상 함께 등장한다. 둘 다 오픈소스이고 무료라서 라이선스 걱정 없이 쓸 수 있다는 공통점이 있지만, 설계 철학이 다르기 때문에 프로젝트 성격에 따라 적합한 선택이 달라진다.

## 두 라이브러리 비교

<img src="/assets/images/posts/2026-09-01-openlayers-vs-leaflet-comparison-1.svg" alt="OpenLayers와 Leaflet의 기능 범위와 학습 곡선을 비교하는 다이어그램, Leaflet은 가볍고 간단하며 OpenLayers는 기능이 풍부하지만 상대적으로 복잡함을 보여준다" style="width:100%;">

| 항목 | Leaflet | OpenLayers |
|---|---|---|
| 학습 곡선 | 완만함(핵심 API가 적음) | 상대적으로 가파름(기능이 많음) |
| 파일 크기 | 매우 작음(~40KB) | 상대적으로 큼 |
| 좌표계 지원 | 기본적으로 웹 메르카토르 위주 | 다양한 좌표계·투영법을 기본 지원 |
| 벡터 타일 | 플러그인으로 지원 | 기본 내장 |
| 대표 용도 | 간단한 마커 지도, 대시보드 | 복잡한 GIS 분석 도구, 다중 좌표계 처리 |

## 코드로 보는 체감 난이도 차이

```javascript
// Leaflet: 몇 줄이면 지도가 뜬다
const map = L.map('map').setView([37.5665, 126.978], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
L.marker([37.5665, 126.978]).addTo(map);
```

```javascript
// OpenLayers: 설정할 것이 더 많지만 그만큼 세밀한 제어가 가능하다
const map = new ol.Map({
  target: 'map',
  layers: [new ol.layer.Tile({ source: new ol.source.OSM() })],
  view: new ol.View({
    center: ol.proj.fromLonLat([126.978, 37.5665]),
    zoom: 13,
  }),
});
```

Leaflet은 좌표를 `[위도, 경도]`로 바로 쓰지만, OpenLayers는 좌표계 변환 함수(`ol.proj.fromLonLat`)를 거쳐야 한다는 점에서 이미 설계 철학의 차이가 드러난다.

## 어떤 상황에 무엇을 골라야 할까

```text
1. 마커 몇 개 찍고 팝업만 띄우면 되는 간단한 지도인가?
   → Leaflet. 빠르게 만들고 파일 크기도 작다.

2. 여러 좌표계(UTM, 지역 좌표계 등)를 다뤄야 하는가?
   → OpenLayers. 좌표계 변환이 라이브러리 안에 이미 갖춰져 있다.

3. 공공 GIS 프로젝트나 WMS/WFS 표준 프로토콜을 많이 써야 하는가?
   → OpenLayers. OGC 표준 지원이 훨씬 풍부하다.

4. 처음 웹 지도를 배우는 입장이라 부담 없이 시작하고 싶은가?
   → Leaflet으로 시작해 개념을 익힌 뒤 필요하면 OpenLayers로 넘어가는 것도 좋은 경로다.
```

## 실무 포인트

- **3D 지도나 최신 WebGL 기반 스타일링이 필요하다면 Leaflet도 OpenLayers도 아니라 MapLibre GL JS를 검토하는 것이 낫다.** 이 둘은 2D 래스터/벡터 지도에 강점이 있는 라이브러리다.
- **Leaflet 생태계는 플러그인이 매우 많아서, 기능이 부족하다고 느껴지면 대부분 서드파티 플러그인으로 해결된다.**
- **OpenLayers는 학습 초반 진입장벽이 있지만, 한 번 구조를 이해하면 복잡한 공간 분석 UI를 구현할 때 오히려 더 명확한 구조를 제공한다.**

## 마무리 요약

- Leaflet은 가볍고 배우기 쉬워 간단한 지도에 적합하고, OpenLayers는 기능이 풍부해 복잡한 GIS 요구사항에 적합하다.
- 여러 좌표계나 OGC 표준(WMS/WFS)을 다뤄야 한다면 OpenLayers가 유리하다.
- 3D나 최신 WebGL 스타일링이 필요하면 이 둘이 아니라 MapLibre GL JS를 검토해야 한다.

## 참고 자료

- [Leaflet 공식 문서](https://leafletjs.com/reference.html)
- [OpenLayers 공식 문서](https://openlayers.org/doc/)
