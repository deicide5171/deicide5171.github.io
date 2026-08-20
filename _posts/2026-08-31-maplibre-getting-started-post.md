---
layout: single
title: "MapLibre GL JS 시작하기 — 설치부터 첫 지도 띄우기까지"
date: 2026-08-31 12:20:00 +0530
categories: gis
tags: ["maplibre", "웹지도", "gis", "입문", "튜토리얼"]
toc: true
toc_sticky: true
excerpt: "오픈소스 웹 지도 라이브러리 MapLibre GL JS를 npm 설치부터 첫 지도 렌더링까지, 처음 시작하는 사람 기준으로 정리했다."
---

## 왜 지금 MapLibre인가

Mapbox GL JS가 v2부터 상용 라이선스로 전환되면서, 오픈소스 라이선스를 유지하는 포크인 MapLibre GL JS가 사실상 웹 지도 라이브러리의 무료 표준이 됐다. API가 Mapbox GL JS와 거의 동일해서 기존 Mapbox 자료를 참고하면서 학습해도 무방하다는 점도 진입장벽을 낮춘다.

## MapLibre 렌더링 구조

<img src="/assets/images/posts/2026-08-31-maplibre-getting-started-1.svg" alt="MapLibre GL JS가 벡터 타일 서버에서 타일을 받아 WebGL로 브라우저 화면에 렌더링하는 흐름을 보여주는 구조도" style="width:100%;">

## 핵심 개념 3가지

| 개념 | 설명 |
|---|---|
| Style Spec | 레이어·색상·라벨을 정의하는 JSON 명세 (Mapbox Style Spec 호환) |
| Vector Tile | 좌표 데이터를 타일 단위로 나눈 바이너리 포맷(PBF), 클라이언트에서 스타일링 |
| Source / Layer | Source는 데이터 출처, Layer는 그 데이터를 어떻게 그릴지 정의 |

## 코드 예제: 첫 지도 띄우기

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet" />
  <style>#map { width: 100%; height: 500px; }</style>
</head>
<body>
  <div id="map"></div>
  <script>
    const map = new maplibregl.Map({
      container: 'map',
      style: 'https://demotiles.maplibre.org/style.json', // 무료 데모 스타일
      center: [126.978, 37.5665], // 서울 시청 [경도, 위도]
      zoom: 10,
    });
    map.addControl(new maplibregl.NavigationControl());
  </script>
</body>
</html>
```

이 코드만으로 확대·축소·회전이 되는 벡터 지도가 뜬다. `center`는 `[위도, 경도]`가 아니라 `[경도, 위도]` 순서라는 점이 처음 쓰는 사람이 가장 많이 헷갈리는 부분이다.

## 실무 포인트

- **데모 스타일은 실서비스에 쓸 수 없다.** 실제 서비스에서는 자체 벡터 타일 서버(PostGIS + pg_tileserv, 또는 tippecanoe로 만든 PMTiles)를 붙여야 한다.
- **npm으로 설치할 경우** `npm install maplibre-gl` 후 `import maplibregl from 'maplibre-gl'`로 불러오면 번들러 환경에서도 동일하게 동작한다.
- **Mapbox 튜토리얼을 참고할 때는 `mapboxgl`을 `maplibregl`로, 액세스 토큰 관련 코드를 제거**하면 대부분 그대로 동작한다. 단, Mapbox 전용 스타일 URL(`mapbox://styles/...`)은 MapLibre에서 쓸 수 없다.

## 마무리 요약

- MapLibre GL JS는 Mapbox GL JS의 오픈소스 포크로 API가 거의 동일하다.
- `center` 좌표는 `[경도, 위도]` 순서임을 기억해야 한다.
- 실서비스에서는 데모 스타일 대신 자체 벡터 타일 서버를 준비해야 한다.

## 참고 자료

- [MapLibre GL JS 공식 문서](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre GitHub](https://github.com/maplibre/maplibre-gl-js)
