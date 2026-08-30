---
layout: single
title: "웹지도 좌표가 어긋날 때 — EPSG:4326과 3857 혼동 잡는 법"
date: 2026-09-21 13:20:00 +0530
categories: gis
tags: ["epsg4326", "epsg3857", "좌표계", "웹지도", "웹메르카토르"]
toc: true
toc_sticky: true
excerpt: "OpenLayers·Mapbox·MapLibre로 지도를 만들다 마커가 엉뚱한 위치에 찍히거나 지도가 아예 안 보일 때, 가장 흔한 원인인 EPSG:4326과 3857 혼동을 진단하고 고치는 방법을 정리했다."
---

## 왜 이 에러를 거의 모두가 한 번은 겪는가

웹 지도 라이브러리를 처음 다뤄보면 십중팔구 마주치는 증상이 있다. 위경도 좌표를 분명히 정확히 입력했는데 마커가 지도 밖 저 멀리에 찍히거나, 심하면 지도 자체가 회색 화면으로 렌더링되지 않는다. 원인을 추적해보면 거의 항상 두 좌표계를 혼동해서 생긴 문제다.

- **EPSG:4326 (WGS84)**: 위도·경도를 도(degree) 단위로 표현하는 좌표계. GPS, 대부분의 공공 데이터, GeoJSON의 기본 좌표계다. 값의 범위는 경도 -180~180, 위도 -90~90.
- **EPSG:3857 (Web Mercator)**: 구면인 지구를 평면 지도로 투영하기 위해 미터 단위로 변환한 좌표계. Google Maps, OpenStreetMap 타일, 대부분의 웹 지도 라이브러리 내부 렌더링이 이 좌표계를 쓴다.

두 좌표계 모두 "위치를 나타내는 숫자 두 개"라는 겉모습은 같지만, 값의 단위와 범위가 완전히 다르다. 서울시청의 위치는 EPSG:4326으로는 `[126.978, 37.566]`이지만, EPSG:3857로 변환하면 `[14135099, 4518234]`처럼 미터 단위의 훨씬 큰 숫자가 된다. 이 둘을 뒤섞어서 넘기면 마커가 지도 밖으로 날아가거나, 지도 자체가 렌더링되지 않는다.

<img src="/assets/images/posts/2026-09-21-epsg-4326-3857-confusion-fix-1.svg" alt="EPSG:4326은 위경도 도 단위 좌표, EPSG:3857은 미터 단위로 투영된 좌표라는 차이와, 서울시청 좌표가 두 체계에서 각각 어떻게 표현되는지 보여주는 다이어그램" style="width:100%;">

## 잘못된 접근: 라이브러리마다 다른 기본값을 무시하기

라이브러리마다 "API에 넣는 좌표"의 기본 좌표계가 다르다는 점이 혼란을 키운다.

| 라이브러리 | 사용자 입력 API 기본 좌표계 | 내부 렌더링 좌표계 |
|---|---|---|
| Mapbox GL JS / MapLibre GL JS | EPSG:4326 (위경도) | EPSG:3857 |
| Leaflet | EPSG:4326 (위경도) | EPSG:3857 |
| OpenLayers | 명시적으로 지정 필요(기본값 없음) | 뷰(View)에 설정된 투영법 |

Mapbox GL JS나 MapLibre GL JS, Leaflet은 사용자가 마커를 찍을 때 위경도(EPSG:4326)를 그대로 넣으면 라이브러리가 알아서 내부적으로 EPSG:3857로 변환해 그려준다. 그런데 **OpenLayers는 다르다.** OpenLayers는 `Map`의 `View`에 설정된 투영법을 그대로 따르므로, 좌표를 넣을 때 명시적으로 변환하지 않으면 위경도 값을 그대로 미터 좌표로 착각해 렌더링한다. 이게 OpenLayers를 처음 쓰는 사람들이 "마커가 지도 밖에 찍힌다"는 문제를 가장 많이 겪는 이유다.

## 올바른 접근: OpenLayers에서 명시적으로 변환하기

```javascript
import { fromLonLat } from 'ol/proj';

const seoulCityHallLonLat = [126.978, 37.566]; // EPSG:4326
const seoulCityHallMercator = fromLonLat(seoulCityHallLonLat); // EPSG:3857로 변환

const marker = new Feature({
  geometry: new Point(seoulCityHallMercator)
});
```

`fromLonLat()`은 EPSG:4326 좌표를 View의 기본 투영법인 EPSG:3857로 변환해준다. 반대로 지도에서 클릭한 위치를 위경도로 다시 뽑고 싶다면 `toLonLat()`을 쓴다. GeoJSON을 불러올 때도 `readFeatures()`의 `featureProjection` 옵션에 `'EPSG:3857'`을 지정해야, 데이터 안의 위경도가 지도 좌표계로 자동 변환된다.

```javascript
const features = new GeoJSON().readFeatures(geojsonData, {
  featureProjection: 'EPSG:3857'  // 이걸 빠뜨리면 좌표가 어긋난다
});
```

## 실무 포인트

- **국내 공공데이터는 EPSG:5179, 5181 같은 국가 좌표계로 제공되는 경우가 많다.** 이 경우 EPSG:4326으로 착각하고 바로 쓰면 좌표가 한반도 밖으로 튄다. `proj4` 라이브러리로 EPSG 코드에 맞는 변환 정의를 등록한 뒤 변환해야 한다.
- **좌표 순서(위도-경도 vs 경도-위도)도 혼동 원인이다.** GeoJSON 표준은 `[경도, 위도]` 순서지만, 많은 국내 API나 일반 텍스트 표기는 `[위도, 경도]` 순서를 쓴다. 좌표를 넣기 전에 순서를 반드시 확인한다.
- **디버깅할 때는 좌표 값의 자릿수부터 확인하라.** 두 자리대(-180~180) 숫자면 EPSG:4326, 일곱 자리 이상의 큰 숫자면 EPSG:3857일 가능성이 높다. 이 감으로도 원인의 8할은 바로 짚어낼 수 있다.
- **좌표계 변환은 한 곳에서만 처리하도록 통일하라.** 여러 컴포넌트에서 각자 변환을 하다 보면 이중 변환되어 오히려 더 엉뚱한 위치로 튀는 사고가 난다.

## 마무리 요약

- EPSG:4326은 위경도 도 단위, EPSG:3857은 웹 지도 렌더링에 쓰이는 미터 단위 좌표계로, 값의 자릿수부터 확연히 다르다.
- Mapbox GL·MapLibre·Leaflet은 위경도 입력을 자동 변환해주지만, OpenLayers는 `fromLonLat()`/`toLonLat()`으로 명시적 변환이 필요하다.
- 국내 공공데이터의 국가 좌표계, 좌표 순서(위경도 vs 경위도)까지 함께 확인해야 좌표 어긋남 문제를 근본적으로 해결할 수 있다.

## 참고 자료

- [OpenLayers 공식 문서 - ol/proj](https://openlayers.org/en/latest/apidoc/module-ol_proj.html)
- [EPSG.io - 3857](https://epsg.io/3857)
