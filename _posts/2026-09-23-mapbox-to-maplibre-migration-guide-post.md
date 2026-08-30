---
layout: single
title: "Mapbox GL JS에서 MapLibre GL JS로 마이그레이션하기 — 코드 변경 포인트와 흔한 에러"
date: 2026-09-23 12:20:00 +0530
categories: gis
tags: ["mapbox", "maplibre", "웹지도라이브러리", "마이그레이션", "벡터타일"]
toc: true
toc_sticky: true
excerpt: "Mapbox GL JS로 만든 지도를 오픈소스 MapLibre GL JS로 옮기려 할 때 그대로 npm 패키지만 바꾸면 발생하는 accessToken 에러와 스타일 URL 문제를 실제 코드 변경 포인트 중심으로 정리했다."
---

## 왜 지금 MapLibre로 옮기는 팀이 많은가

Mapbox GL JS는 v2부터 독점 라이선스로 전환되며 사용량 기반 과금이 커졌고, 이 시점을 기점으로 v1의 마지막 오픈소스 코드를 포크해 커뮤니티가 이어받은 것이 MapLibre GL JS다. 지도 렌더링 API 자체는 거의 동일하게 유지되고 있어 "그냥 패키지 이름만 바꾸면 되지 않을까" 하고 시작했다가, 곳곳에서 미묘하게 다른 부분과 마주치며 마이그레이션이 예상보다 오래 걸리는 경우가 많다.

이 글은 실제로 Mapbox GL JS 코드베이스를 MapLibre GL JS로 옮길 때 구체적으로 무엇을 바꿔야 하는지, 그리고 바꾼 뒤 마주치기 쉬운 에러를 중심으로 정리한다.

## 핵심 개념 1 — accessToken이 아니라 스타일 URL 자체가 문제다

가장 먼저 부딪히는 것은 Mapbox 전용 인증 토큰이다. Mapbox GL JS는 `mapboxgl.accessToken`에 발급받은 토큰을 넣어야 지도 스타일과 타일을 불러올 수 있었는데, MapLibre GL JS에는 이 토큰 개념 자체가 없다. 문제는 단순히 이 한 줄을 지운다고 끝나지 않는다는 점이다 — 대부분 `style: 'mapbox://styles/mapbox/streets-v12'`처럼 Mapbox가 호스팅하는 스타일 URL을 그대로 쓰고 있었을 텐데, 이 `mapbox://` 프로토콜과 스타일 자체가 Mapbox 서비스에 종속돼 있으므로 MapLibre로 옮긴다는 것은 결국 **스타일 소스 자체를 다른 곳(OpenMapTiles, MapTiler, 자체 호스팅 타일 서버 등)으로 바꿔야 한다**는 뜻이다.

<img src="/assets/images/posts/2026-09-23-mapbox-to-maplibre-migration-guide-1.svg" alt="Mapbox GL JS 코드에서 accessToken과 mapbox:// 스타일 URL을 제거하고 MapLibre GL JS 패키지와 오픈 타일 소스 기반 style.json으로 교체하는 마이그레이션 과정을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — API 표면은 거의 같지만 완전히 같지는 않다

`Map`, `addLayer`, `addSource`, `Marker`, `Popup` 같은 핵심 API는 MapLibre가 Mapbox v1 시점의 API를 그대로 이어받았기 때문에 거의 동일하게 동작한다. 하지만 Mapbox가 v2 이후에 자체적으로 추가한 최신 기능(예: 특정 3D 지형 확장, RTL 텍스트 플러그인 자동 로딩 방식, 텔레메트리 관련 내부 훅)은 MapLibre에 없거나 다른 방식으로 구현돼 있다. 이런 기능을 쓰고 있었다면 코드 수정 없이 패키지만 바꿔서는 조용히 동작하지 않거나 콘솔에 알 수 없는 에러가 뜬다.

## 예제 — 최소 마이그레이션 코드 비교

```javascript
// Before: Mapbox GL JS
import mapboxgl from 'mapbox-gl';
mapboxgl.accessToken = 'pk.eyJ1...';

const map = new mapboxgl.Map({
  container: 'map',
  style: 'mapbox://styles/mapbox/streets-v12',
  center: [126.978, 37.5665],
  zoom: 12,
});
```

```javascript
// After: MapLibre GL JS
import maplibregl from 'maplibre-gl';
// accessToken 설정 자체가 필요 없음

const map = new maplibregl.Map({
  container: 'map',
  // mapbox:// 대신 실제 style.json을 호스팅하는 URL을 직접 지정
  style: 'https://api.maptiler.com/maps/streets-v2/style.json?key=YOUR_KEY',
  center: [126.978, 37.5665],
  zoom: 12,
});
```

패키지 임포트 이름을 바꾸고, accessToken 줄을 지우고, style URL을 실제 접근 가능한 style.json 경로로 바꾸는 것이 핵심 3단계다. 여기서 style.json은 MapTiler 같은 상용 타일 서비스를 쓰거나, OpenMapTiles로 직접 타일을 만들어 자체 호스팅할 수도 있다.

## 마이그레이션 시 흔한 에러

| 에러/증상 | 원인 | 해결 |
|---|---|---|
| `Style is not done loading` | style URL이 mapbox:// 그대로 남아있음 | 실제 접근 가능한 style.json URL로 교체 |
| RTL(아랍어 등) 텍스트가 깨짐 | RTL 텍스트 플러그인 자동 로딩 방식 차이 | `setRTLTextPlugin`을 MapLibre 문서 방식대로 수동 등록 |
| 특정 3D 지형 API 호출 시 undefined 에러 | Mapbox 전용 확장 API 사용 | MapLibre가 지원하는 동등 기능으로 대체하거나 제거 |
| 빌드는 되는데 지도가 회색으로만 나옴 | CSS 파일 임포트 경로가 여전히 mapbox-gl/dist/... | maplibre-gl 패키지의 CSS 경로로 교체 |

특히 CSS 임포트를 놓치는 실수가 의외로 잦다. `import 'mapbox-gl/dist/mapbox-gl.css'`를 그대로 남겨두면 JS 코드는 MapLibre로 바뀌었어도 컨트롤 버튼 스타일이 깨지거나 팝업 위치가 어긋나는 등 시각적 문제가 생긴다. `import 'maplibre-gl/dist/maplibre-gl.css'`로 함께 바꿔야 한다.

## 실무 포인트

- **패키지 교체 전에 사용 중인 Mapbox 전용 기능 목록부터 뽑아라.** 코드 전체에서 `mapboxgl`, `mapbox://`, Mapbox 전용 API 호출을 먼저 검색해 마이그레이션 범위를 가늠한 뒤 작업하면 예상치 못한 기능 누락을 줄일 수 있다.
- **타입스크립트를 쓴다면 타입 정의도 함께 바꿔야 한다.** `@types/mapbox-gl` 대신 MapLibre는 자체 타입을 내장하고 있으므로 타입 패키지도 정리해야 빌드 에러가 안 남는다.
- **테스트는 실제 배포 도메인에서 한 번 더 하라.** 타일 서버나 스타일 호스팅에 CORS나 리퍼러 제한이 걸려 있는 경우, 로컬에서는 잘 되다가 운영 도메인에서만 타일이 안 뜨는 경우가 있다.

## 마무리 요약

- MapLibre GL JS로 옮긴다는 것은 API 교체보다 실질적으로는 Mapbox가 호스팅하던 스타일과 타일을 다른 소스로 바꾸는 작업에 가깝다.
- 핵심 API는 거의 동일하지만 Mapbox v2 이후 추가된 전용 기능은 지원되지 않을 수 있으니 사용 중인 기능을 먼저 점검해야 한다.
- CSS 임포트 경로, RTL 텍스트 플러그인 등록 방식처럼 눈에 잘 안 띄는 부분에서 조용히 깨지는 경우가 많으므로 시각적 확인까지 마쳐야 마이그레이션이 끝난다.

## 참고 자료

- [MapLibre GL JS 공식 문서](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre - Mapbox에서 마이그레이션하기](https://maplibre.org/maplibre-gl-js/docs/guides/migrate-from-mapbox/)
