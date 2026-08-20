---
layout: single
title: "Leaflet 시작하기 — 가장 가벼운 웹 지도 라이브러리 첫걸음"
date: 2026-09-04 12:20:00 +0530
categories: gis
tags: ["leaflet", "웹지도", "gis입문", "튜토리얼", "지도"]
toc: true
toc_sticky: true
excerpt: "가장 배우기 쉬운 웹 지도 라이브러리 Leaflet으로 지도를 띄우고 마커·팝업을 추가하는 첫걸음을 정리했다."
---

## 왜 처음에는 Leaflet인가

웹 지도를 처음 만든다면 Leaflet이 가장 부담 없는 출발점이다. 파일 크기가 매우 작고(약 40KB), 핵심 API가 단순해서 몇 줄만으로 지도가 뜬다. 오픈소스라 라이선스 걱정도 없고, 부족한 기능은 방대한 플러그인 생태계로 대부분 채울 수 있다.

<img src="/assets/images/posts/2026-09-04-leaflet-getting-started-1.svg" alt="Leaflet이 타일 레이어와 마커·팝업 등의 오버레이 레이어를 겹쳐 지도를 구성하는 레이어 구조를 보여주는 다이어그램" style="width:100%;">

## Leaflet의 레이어 개념

Leaflet 지도는 여러 레이어를 겹쳐서 구성된다.

| 레이어 | 역할 |
|---|---|
| 타일 레이어(TileLayer) | 지도 배경 이미지(OSM 등) |
| 마커(Marker) | 특정 위치를 표시하는 핀 |
| 팝업(Popup) | 마커 클릭 시 뜨는 말풍선 |
| 벡터 레이어 | 선·다각형·원 등 도형 |

## 코드 예제: 지도 띄우고 마커 찍기

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>#map { height: 500px; }</style>
</head>
<body>
  <div id="map"></div>
  <script>
    // 지도 생성 ([위도, 경도], 줌 레벨)
    const map = L.map('map').setView([37.5665, 126.978], 13);

    // 타일 레이어 추가 (배경 지도)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap'
    }).addTo(map);

    // 마커 + 팝업
    L.marker([37.5665, 126.978])
      .addTo(map)
      .bindPopup('서울 시청')
      .openPopup();
  </script>
</body>
</html>
```

Leaflet은 좌표를 `[위도, 경도]` 순서로 받는다. GeoJSON이나 Mapbox 계열이 `[경도, 위도]`를 쓰는 것과 반대라, 두 라이브러리를 함께 쓸 때 순서 혼동이 자주 생긴다.

## 실무 포인트

- **타일 레이어의 `attribution`은 반드시 표시해야 한다.** OpenStreetMap 같은 무료 타일은 출처 표기가 라이선스 조건이므로, 지우면 안 된다.
- **OSM 기본 타일 서버를 대량 트래픽 서비스에 그대로 쓰면 안 된다.** OSM 타일은 커뮤니티 자원이라 상업적 대량 사용에 제약이 있으므로, 트래픽이 많다면 자체 타일 서버나 상용 타일 제공자를 검토해야 한다.
- **마커가 수천 개 이상이면 그대로 찍지 말고 클러스터링을 써야 한다.** `Leaflet.markercluster` 플러그인으로 가까운 마커를 묶으면 성능과 가독성이 모두 좋아진다.

## 마무리 요약

- Leaflet은 가볍고 API가 단순해 웹 지도를 처음 배우기에 가장 적합하다.
- 지도는 타일 레이어(배경) 위에 마커·팝업·벡터 같은 오버레이를 겹쳐 구성한다.
- Leaflet은 `[위도, 경도]` 순서를 쓰며, 타일 출처 표기 유지와 대량 트래픽 시 타일 서버 검토가 실무 포인트다.

## 참고 자료

- [Leaflet 공식 튜토리얼](https://leafletjs.com/examples.html)
- [Leaflet 공식 문서](https://leafletjs.com/reference.html)
