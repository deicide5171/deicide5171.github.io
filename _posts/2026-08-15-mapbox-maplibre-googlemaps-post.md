---
layout: single
title: "Mapbox, MapLibre, 구글 맵 — 지도 API는 뭘 골라야 할까"
date: 2026-08-15 16:20:00 +0530
categories: gis
tags: ["mapbox", "maplibre", "google-maps", "vector-tile", "gis"]
toc: true
toc_sticky: true
excerpt: "Mapbox GL JS, MapLibre GL JS, Google Maps Platform의 라이선스·비용·커스터마이징 자유도를 비교하고 프로젝트 상황별 선택 기준을 정리했다."
---

## 왜 지금 지도 API 선택이 고민거리인가

웹이든 앱이든 지도 기능을 붙이려는 순간 가장 먼저 마주치는 질문은 "어떤 지도 API를 쓸 것인가"다. 몇 년 전만 해도 선택지가 단순했지만, 2020년 Mapbox GL JS가 오픈소스 라이선스(BSD-3)를 상용 라이선스로 전환하면서 판이 크게 바뀌었다. 그 직후 마지막 오픈소스 버전을 포크한 MapLibre GL JS가 등장했고, 지금은 커뮤니티 주도로 활발히 유지보수되는 독립적인 프로젝트로 자리 잡았다.

여기에 오랫동안 범용 지도의 대명사였던 Google Maps Platform까지 더해지면 선택지는 세 갈래로 나뉜다. 문제는 세 제품이 겉보기엔 비슷해 보여도 라이선스 구조, 비용 모델, 커스터마이징 자유도가 근본적으로 다르다는 점이다. 스타트업 MVP와 대규모 커머셜 서비스, 사내 툴이 요구하는 조건이 전혀 다르기 때문에 "어떤 게 제일 좋냐"가 아니라 "우리 프로젝트에 뭐가 맞냐"를 물어야 한다.

이 글에서는 세 지도 API의 구조적 차이를 정리하고, 실제 선택 시 고려해야 할 기준을 살펴본다. 구체적인 가격표는 변동이 잦으므로 이 글에서는 상대적인 비용 구조만 다루고, 정확한 금액은 공식 가격 정책 확인이 필요하다.

## 핵심 비교: 라이선스·커스터마이징·생태계

세 제품 모두 벡터 타일 기반 렌더링을 지원하지만, 접근 방식은 다르다. Mapbox GL JS는 상용 SDK로 스타일 커스터마이징 도구(Mapbox Studio)와 데이터 파이프라인이 강력하다. MapLibre GL JS는 Mapbox GL JS v1 계열 코드를 포크한 오픈소스(BSD-2 계열) 프로젝트로, 타일 소스를 자유롭게 조합할 수 있는 대신 상용 지도 데이터·지오코딩 같은 부가 서비스는 별도로 구해야 한다. Google Maps Platform은 자체 SDK와 방대한 POI(관심 지점) 데이터가 강점이지만, 벡터 타일 스타일링 자유도는 상대적으로 제한적이다.

| 항목 | Mapbox GL JS | MapLibre GL JS | Google Maps Platform |
|---|---|---|---|
| 라이선스 | 상용(무료 티어 포함) | 오픈소스(BSD 계열) | 상용 API |
| 비용 구조 | 사용량 기반, 공식 가격 정책 확인 필요 | 라이브러리 자체는 무료, 타일 서버 비용 별도 | 사용량 기반, 공식 가격 정책 확인 필요 |
| 스타일 커스터마이징 | 매우 자유로움(Studio 지원) | 자유로움(타일 소스 직접 구성) | 제한적(스타일 옵션 위주) |
| POI/지오코딩 데이터 | 자체 제공 | 없음(외부 연동 필요) | 매우 풍부 |
| 벤더 종속 | 있음 | 낮음(자체 인프라 구성 가능) | 있음 |

## 코드로 보는 초기화 차이

Mapbox GL JS와 MapLibre GL JS는 API가 거의 동일해 마이그레이션 부담이 적다.

```javascript
// MapLibre GL JS - 지도 초기화 (오픈소스 타일 서버 연동)
import maplibregl from 'maplibre-gl';

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json',
  center: [126.9780, 37.5665], // 서울
  zoom: 10
});

map.addControl(new maplibregl.NavigationControl());
```

```javascript
// Google Maps JavaScript API - 지도 초기화
function initMap() {
  new google.maps.Map(document.getElementById("map"), {
    center: { lat: 37.5665, lng: 126.9780 },
    zoom: 10,
    mapId: "YOUR_MAP_ID" // 벡터 지도 스타일 적용 시 필요
  });
}
```

## 실무 포인트와 주의사항

가장 먼저 확인할 것은 예상 트래픽과 데이터 요구사항이다. 커스텀 디자인 지도(다크 모드, 브랜드 컬러 반영 등)가 핵심 요구사항이면 Mapbox나 MapLibre가 유리하고, POI 검색·리뷰·길찾기 데이터의 정확도가 중요하면 Google Maps Platform이 앞선다. MapLibre는 라이선스 비용이 없는 대신 타일 서버(예: OpenMapTiles, 자체 PostGIS 파이프라인)를 직접 구축하거나 관리형 서비스를 별도 계약해야 하므로, 총소유비용(TCO)을 라이브러리 비용만으로 판단하면 안 된다.

벤더 종속성도 고려 대상이다. 상용 API는 약관·가격 정책이 사업자 사정에 따라 바뀔 수 있으므로, 장기 서비스라면 마이그레이션 경로(예: Mapbox 스타일을 MapLibre로 이전 가능한지)를 미리 점검해두는 편이 안전하다. 또한 세 서비스 모두 API 키 노출, 도메인 제한 설정, 사용량 알림 설정을 초기에 해두지 않으면 예상치 못한 과금으로 이어질 수 있다.

## 3줄 요약

- Mapbox GL JS는 상용이지만 스타일 커스터마이징과 데이터 파이프라인이 강력하다.
- MapLibre GL JS는 무료 오픈소스지만 타일 인프라를 직접 준비해야 하는 대신 벤더 종속을 낮출 수 있다.
- Google Maps Platform은 POI·길찾기 데이터가 강하지만 벡터 스타일링 자유도는 상대적으로 낮으며, 세 제품 모두 정확한 비용은 공식 가격 정책 확인이 필요하다.

## 참고 자료

- [Mapbox GL JS 공식 문서](https://docs.mapbox.com/mapbox-gl-js/guides/)
- [MapLibre GL JS 공식 문서](https://maplibre.org/maplibre-gl-js/docs/)
- [Google Maps Platform 공식 문서](https://developers.google.com/maps/documentation)
- [MapLibre 프로젝트 배경 설명(MapLibre 공식 블로그)](https://maplibre.org/news/)
