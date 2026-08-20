---
layout: single
title: "GeoJSON이 뭔가요 — 웹 지도에서 가장 많이 쓰는 공간 데이터 포맷 입문"
date: 2026-08-31 14:20:00 +0530
categories: gis
tags: ["geojson", "gis", "입문", "웹지도", "공간데이터"]
toc: true
toc_sticky: true
excerpt: "웹 지도에서 점·선·면 데이터를 주고받을 때 가장 널리 쓰이는 GeoJSON 포맷의 구조를 예제와 함께 처음부터 정리했다."
---

## 왜 하필 GeoJSON인가

지리 정보를 담는 포맷은 Shapefile, KML, GML 등 여러 가지가 있지만, 웹 지도 개발에서는 **GeoJSON**이 사실상 표준이다. 이유는 단순하다. GeoJSON은 그냥 JSON이라서 별도 파서 없이 자바스크립트의 `JSON.parse()`만으로 바로 다룰 수 있고, Leaflet·MapLibre·OpenLayers 등 거의 모든 웹 지도 라이브러리가 기본 지원한다.

## GeoJSON 도형 타입

<img src="/assets/images/posts/2026-08-31-geojson-basics-1.svg" alt="GeoJSON의 대표 지오메트리 타입인 Point, LineString, Polygon의 형태와 좌표 배열 구조를 비교하는 다이어그램" style="width:100%;">

| 타입 | 표현하는 것 | 좌표 구조 |
|---|---|---|
| Point | 하나의 점(예: 매장 위치) | `[경도, 위도]` |
| LineString | 선(예: 도로, 경로) | `[[경도,위도], [경도,위도], ...]` |
| Polygon | 면(예: 행정구역 경계) | `[[[경도,위도], ...]]` (첫 좌표와 마지막 좌표 동일) |

## 코드 예제: 기본 구조

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [126.978, 37.5665]
  },
  "properties": {
    "name": "서울 시청",
    "category": "관공서"
  }
}
```

`Feature`는 지오메트리(위치·형태)와 속성 정보(이름, 카테고리 등)를 함께 담는 기본 단위다. 여러 Feature를 모으면 `FeatureCollection`이 된다.

```json
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature", "geometry": { "type": "Point", "coordinates": [126.978, 37.5665] }, "properties": { "name": "서울 시청" } },
    { "type": "Feature", "geometry": { "type": "Point", "coordinates": [127.027, 37.4979] }, "properties": { "name": "강남역" } }
  ]
}
```

## 실무 포인트

- **좌표 순서는 `[경도, 위도]`다.** 위도·경도 순서로 저장하는 다른 포맷(예: 일부 GPS 기기 로그)과 혼동하면 지도에 엉뚱한 위치가 찍힌다. GeoJSON 스펙(RFC 7946)에 명시된 규칙이므로 예외가 없다.
- **Polygon의 좌표 배열은 첫 점과 마지막 점이 같아야 닫힌 도형으로 인식된다.** 이 조건을 빠뜨리면 일부 라이브러리에서 렌더링 오류가 난다.
- **대용량 GeoJSON(수만 개 이상의 Feature)을 브라우저에 그대로 로드하면 성능이 급격히 나빠진다.** 이 경우 벡터 타일(PBF)로 변환해서 서빙하는 것이 실무 표준이다.

## 마무리 요약

- GeoJSON은 순수 JSON 구조라서 별도 파서 없이 웹에서 바로 다룰 수 있는 공간 데이터 포맷이다.
- Point, LineString, Polygon이 가장 기본이 되는 지오메트리 타입이다.
- 좌표 순서는 항상 `[경도, 위도]`이며, 대용량 데이터는 벡터 타일로 변환해 서빙해야 한다.

## 참고 자료

- [GeoJSON 공식 스펙 (RFC 7946)](https://datatracker.ietf.org/doc/html/rfc7946)
- [geojson.io - 온라인 GeoJSON 편집 도구](https://geojson.io/)
