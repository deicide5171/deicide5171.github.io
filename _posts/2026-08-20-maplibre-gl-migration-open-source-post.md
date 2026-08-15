---
layout: single
title: "MapLibre GL로 갈아타기 — Mapbox 라이선스 변경 이후의 오픈소스 웹 지도"
date: 2026-08-20 12:20:00 +0530
categories: gis
tags: ["gis", "maplibre", "mapbox-gl", "webgl", "open-source", "web-map"]
toc: true
toc_sticky: true
excerpt: "Mapbox GL JS의 라이선스 정책 변경을 계기로 갈라져 나온 오픈소스 포크 MapLibre GL의 아키텍처와, 기존 Mapbox 기반 코드를 마이그레이션할 때 실무 체크포인트를 정리한다."
---

WebGL 기반 벡터 타일 렌더링 라이브러리의 사실상 표준이었던 Mapbox GL JS는 v2부터 오픈소스(BSD-3) 라이선스를 접고 독점 라이선스로 전환했다. 기존 v1까지는 자유롭게 포크·재배포가 가능했지만, v2 이후로는 Mapbox 계정 토큰 없이는 상용 서비스에 사용할 수 없는 구조로 바뀐 것이다. 지도 UI를 프로덕션에 올려둔 팀 입장에서는 라이브러리 업그레이드가 곧 상용 계약으로 이어지는 셈이라, 이 변화는 단순한 버전업 이슈를 넘어 라이선스 리스크 문제로 받아들여졌다.

이 반발 속에서 등장한 것이 **MapLibre GL**이다. Mapbox GL JS v1의 마지막 오픈소스 커밋을 기반으로 커뮤니티(당시 여러 지도 서비스 업체와 개발자들)가 포크를 만들었고, 이후 별도 조직으로 독립해 BSD 라이선스 아래 개발을 이어가고 있다. 코드베이스의 뿌리가 같기 때문에 API 표면 대부분이 겹치지만, 포크 이후 각자의 방향으로 기능이 갈라지는 지점도 점점 늘고 있다. 이 글에서는 MapLibre의 렌더링 파이프라인 구조를 짚고, Mapbox 기반 코드를 옮길 때 실무에서 확인해야 할 지점을 정리한다.

## 핵심 개념 1: 벡터 타일 렌더링 파이프라인

MapLibre GL은 서버에서 벡터 타일(주로 MVT, Mapbox Vector Tile 포맷)을 받아 브라우저에서 WebGL로 직접 그리는 구조다. 큰 흐름은 타일 요청 → 파싱 → 스타일 적용 → WebGL 렌더링 네 단계로 나눌 수 있다.

<img src="/assets/images/posts/2026-08-20-maplibre-gl-migration-open-source-1.svg" alt="MapLibre GL 벡터 타일 렌더링 파이프라인 - 타일 요청부터 파싱, 스타일 적용, WebGL 렌더링까지의 흐름도" style="width:100%;">

지도 이동·확대 시 현재 화면에 필요한 타일 좌표(z/x/y)를 계산해 서버에 요청하고, 받은 바이너리를 워커 스레드에서 파싱해 지오메트리로 복원한다. 이후 스타일 JSON에 정의된 레이어 순서와 필터·페인트 속성을 적용해 실제로 그릴 정점 데이터를 만들고, 이를 GPU에 넘겨 WebGL로 래스터화한다. 타일 파싱과 지오메트리 타일링(tessellation)을 메인 스레드가 아닌 워커에서 처리하는 것은 Mapbox GL JS 시절부터 이어진 설계이며, MapLibre도 이 구조를 그대로 물려받았다.

## 핵심 개념 2: Mapbox GL과의 API 호환성 수준

MapLibre는 포크 초기 버전에서는 Mapbox GL JS v1과 거의 동일한 API를 유지했다. `Map`, `Marker`, `Popup` 같은 핵심 클래스명과 메서드 시그니처, 스타일 스펙의 큰 틀(레이어 타입, 소스 타입, 표현식 문법)이 공유된다. 덕분에 대부분의 프로젝트는 import 경로와 패키지명만 바꿔도 기본 지도 렌더링은 그대로 동작하는 경우가 많다.

다만 완전히 같은 라이브러리는 아니다. 두 프로젝트는 각자 릴리스 주기와 로드맵을 독립적으로 운영하고 있어서, 시간이 지날수록 세부 API와 성능 최적화 방향이 조금씩 벌어진다. 예를 들어 3D 지형·건물 렌더링이나 특정 표현식 함수처럼 어느 한쪽에만 먼저 들어오는 기능이 생길 수 있고, 반대로 Mapbox 쪽 상용 기능(예: 특정 클라우드 연동 기능)은 MapLibre에 아예 없다. 마이그레이션 전에는 "API가 비슷하다"는 가정만으로 넘어가지 말고, 실제 사용 중인 메서드·표현식이 두 프로젝트 문서에 공통으로 존재하는지 하나씩 확인하는 편이 안전하다.

## 핵심 개념 3: 스타일 스펙과 생태계 분기

지도 스타일(배경색, 도로 색상, 라벨 폰트 등)을 정의하는 스타일 스펙 JSON도 포크 시점 기준으로는 동일했지만, 이후 각자 확장이 붙었다. 특히 **글꼴(fonts)과 스프라이트(sprite) 리소스**는 라이선스 문제와 직결되는 부분이다. Mapbox가 제공하는 기본 스타일·타일 서비스(Mapbox Streets 등)는 Mapbox 계정과 토큰이 필요하므로, MapLibre로 전환할 때는 타일 서버와 스타일 자체도 OpenMapTiles, Protomaps, MapTiler 같은 별도 오픈 소스/오픈 데이터 제공자로 바꿔야 하는 경우가 대부분이다. 즉 라이브러리만 바꾸고 스타일·타일 출처는 그대로 Mapbox 서비스를 참조하면 라이선스 전환의 의미가 퇴색되므로, 마이그레이션 범위를 라이브러리+타일 소스+스타일까지 함께 검토해야 한다.

또한 React 바인딩(react-map-gl), 클러스터링 플러그인, 드로잉 툴 같은 주변 생태계 라이브러리도 일부는 Mapbox 전용으로 만들어졌던 것들이라, MapLibre를 명시적으로 지원하는지 별도로 확인이 필요하다.

## 예제

MapLibre GL 초기화는 Mapbox GL JS와 거의 동일한 형태를 갖는다.

```js
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json', // MapLibre 데모 스타일(오픈 데이터 기반)
  center: [126.9780, 37.5665], // 서울
  zoom: 10
});

map.addControl(new maplibregl.NavigationControl());
```

기존 Mapbox GL JS 코드를 마이그레이션할 때는 보통 import 경로와 accessToken 설정, 스타일 URL을 함께 바꾼다.

```diff
- import mapboxgl from 'mapbox-gl';
- import 'mapbox-gl/dist/mapbox-gl.css';
+ import maplibregl from 'maplibre-gl';
+ import 'maplibre-gl/dist/maplibre-gl.css';

- mapboxgl.accessToken = 'pk.xxxxxxxx'; // Mapbox 토큰 불필요해짐
- const map = new mapboxgl.Map({
+ const map = new maplibregl.Map({
    container: 'map',
-   style: 'mapbox://styles/mapbox/streets-v12',
+   style: 'https://api.maptiler.com/maps/streets/style.json?key=YOUR_KEY', // 오픈 소스 타일 제공자로 교체
    center: [126.9780, 37.5665],
    zoom: 10
  });
```

## 실무 포인트

- **마이그레이션 체크리스트를 라이브러리 교체에만 국한하지 않는다**: 패키지명(`mapbox-gl` → `maplibre-gl`)과 import 문 변경은 시작일 뿐이고, `style` URL이 여전히 `mapbox://` 프로토콜을 참조하고 있지 않은지, accessToken 관련 코드가 남아있지 않은지 전체 코드베이스를 검색해 확인해야 한다.
- **사용 중인 표현식·레이어 타입을 MapLibre 스타일 스펙 문서와 대조한다**: 두 프로젝트가 분기된 이후 추가된 기능은 서로 없을 수 있으므로, 특히 3D 지형이나 최신 표현식 함수를 쓰고 있다면 마이그레이션 전에 지원 여부부터 확인한다.
- **플러그인·바인딩 생태계를 개별 검증한다**: React/Vue 바인딩, 클러스터링, 드로잉 도구 등 서드파티 라이브러리가 MapLibre를 공식 지원하는지, 혹은 커뮤니티 포크가 있는지 하나씩 점검한다.
- **타일·스타일 데이터 출처도 함께 교체 대상으로 본다**: 라이선스 전환의 실익을 보려면 Mapbox 타일 서비스 의존도 함께 정리해야 하며, OpenMapTiles·Protomaps·MapTiler 등 대체 제공자의 요금제·데이터 범위를 사전에 비교해 둔다.
- **전환 후 회귀 테스트는 실제 화면 단위로 진행한다**: 스타일 렌더링 결과나 인터랙션(클릭, 호버, 클러스터링) 동작은 API 문서만으로 완전히 예측하기 어려우므로, 주요 화면을 직접 띄워 시각적으로 비교하는 과정을 거치는 편이 안전하다.

## 3줄 요약

- Mapbox GL JS가 v2부터 독점 라이선스로 전환하면서, v1 마지막 오픈소스 코드를 기반으로 한 커뮤니티 포크 MapLibre GL이 등장했다.
- 포크 초기에는 API와 스타일 스펙이 거의 동일했지만 이후 각자 로드맵이 갈라지면서, 특정 표현식·기능은 한쪽에만 존재할 수 있다.
- 마이그레이션은 라이브러리 교체뿐 아니라 타일·스타일 데이터 출처, 서드파티 플러그인 호환성까지 함께 점검해야 완결된다.

## 참고 자료

- [MapLibre GL JS 공식 문서](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre 공식 사이트](https://maplibre.org/)
- [MapLibre GL JS GitHub 저장소](https://github.com/maplibre/maplibre-gl-js)
