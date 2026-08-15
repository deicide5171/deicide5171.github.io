---
layout: single
title: "공간 분석 입문 — 버퍼, 오버레이, 근접 분석"
date: 2026-08-15 20:20:00 +0530
categories: gis
tags: ["GIS", "PostGIS", "공간분석", "QGIS"]
toc: true
toc_sticky: true
excerpt: "GIS에서 가장 기본이 되는 버퍼, 오버레이, 근접 분석의 개념과 PostGIS 활용법을 정리한다."
---

## 왜 공간 분석 기초를 다시 짚는가

지도 데이터를 다루는 서비스가 늘어나면서 "점, 선, 면 데이터를 어떻게 겹쳐보고 거리를 계산하는가"에 대한 수요도 함께 늘고 있는 것으로 보인다. 좌표계 변환이나 타일 서빙 같은 인프라적인 주제와 달리, 공간 분석은 실제로 "이 지역에서 반경 500m 안에 있는 시설은 몇 개인가", "두 구역이 겹치는 면적은 얼마인가" 같은 비즈니스 질문에 직접 답을 주는 영역이다. 이번 글에서는 GIS 공간 분석의 가장 기본이 되는 세 가지 연산, 버퍼(buffer)·오버레이(overlay)·근접(proximity) 분석을 PostGIS 예제와 함께 정리한다.

## 핵심 개념 세 가지

| 분석 유형 | 정의 | 대표 활용 사례 |
|---|---|---|
| 버퍼 분석 | 특정 지점/선/면으로부터 일정 거리만큼 영역을 확장해 새로운 폴리곤을 생성 | 상권 반경 분석, 위험구역 설정, 소음 영향권 산정 |
| 오버레이 분석 | 두 개 이상의 레이어를 겹쳐 교집합/합집합/차집합 연산 수행 | 용도지역과 하천구역의 중첩 확인, 배달 구역 통합 |
| 근접 분석 | 특정 지점에서 가장 가까운 객체를 찾거나 거리 기준으로 순위를 매김 (k-NN) | 최근접 매장 찾기, 배차 최적화, 응급실 접근성 분석 |

세 연산은 서로 조합해서 쓰는 경우가 많다. 예를 들어 특정 지점 반경 1km 버퍼를 만든 뒤, 그 안에 포함된 상업지구 폴리곤과 오버레이해 교집합 면적을 구하고, 그 안에서 가장 가까운 지하철역을 근접 분석으로 찾는 식이다.

## PostGIS 함수 예제

```sql
-- 버퍼 분석: 특정 지점에서 반경 500m 영역 생성 (좌표계는 미터 단위 투영좌표계 가정)
SELECT
    id,
    ST_Buffer(geom, 500) AS buffer_geom
FROM stores
WHERE id = 1;

-- 오버레이 분석: 상권 버퍼와 용도지역 폴리곤의 교집합
SELECT
    z.zone_name,
    ST_Area(ST_Intersection(b.buffer_geom, z.geom)) AS overlap_area
FROM store_buffers b
JOIN zoning z
    ON ST_Intersects(b.buffer_geom, z.geom);

-- 근접 분석: 특정 지점에서 가장 가까운 지하철역 5곳 (k-NN, <-> 연산자 활용)
SELECT
    station_name,
    geom <-> ST_SetSRID(ST_MakePoint(127.0276, 37.4979), 4326) AS distance
FROM subway_stations
ORDER BY geom <-> ST_SetSRID(ST_MakePoint(127.0276, 37.4979), 4326)
LIMIT 5;
```

`<->` 연산자는 PostGIS에서 KNN(최근접 이웃) 검색을 위한 인덱스 지원 거리 연산자로, GiST 인덱스가 걸려 있으면 전체 테이블 스캔 없이 빠르게 근접 객체를 찾을 수 있는 것으로 알려져 있다. 정확한 거리 단위(미터 등)를 얻으려면 지리좌표계(SRID 4326)보다 투영좌표계로 변환한 뒤 연산하는 것이 일반적이다.

## QGIS에서의 실무 활용

PostGIS가 서버 사이드에서 대량 데이터를 처리하는 데 강점이 있다면, QGIS는 분석 결과를 시각적으로 검증하고 반복적으로 탐색하는 데 유용하다. QGIS의 "Buffer", "Intersection", "Nearest Neighbour Analysis" 같은 프로세싱 도구는 위 SQL 연산과 개념적으로 동일한 작업을 GUI로 제공하며, 프로세싱 모델러(Processing Modeler)를 이용하면 여러 분석 단계를 하나의 재사용 가능한 워크플로우로 묶을 수 있다.

## 실무 포인트와 주의사항

- 버퍼 거리 계산은 좌표계에 따라 결과가 크게 달라진다. 위경도(4326) 좌표계에서 바로 `ST_Buffer`를 쓰면 단위가 도(degree)가 되어 의도한 거리와 다를 수 있으므로, 지역에 맞는 투영좌표계로 변환 후 연산하는 것이 안전하다.
- 오버레이 연산은 폴리곤 개수와 정점 수가 많아질수록 연산 비용이 급격히 늘어난다. 대량 데이터에서는 공간 인덱스(GiST)와 `ST_Intersects` 사전 필터링을 함께 사용하는 것이 일반적이다.
- 근접 분석에서 "가장 가까운 것"이 항상 "실제로 갈 수 있는 가장 빠른 경로"를 의미하지는 않는다. 직선거리 기반 근접 분석과 도로망 기반 라우팅 분석은 다른 결과를 낼 수 있다.
- 분석 결과를 검증할 때는 QGIS 같은 도구로 시각화해 눈으로 한 번 확인하는 과정을 거치는 것이 실수를 줄이는 데 도움이 된다.

## 3줄 요약

- 버퍼·오버레이·근접 분석은 GIS 공간 분석의 가장 기본이 되는 세 축이다.
- PostGIS는 ST_Buffer, ST_Intersection, `<->` 연산자 등으로 이 분석들을 SQL 안에서 수행할 수 있게 해준다.
- 좌표계 선택과 공간 인덱스 활용이 정확도와 성능 모두에 큰 영향을 준다.

## 참고 자료

- [ST_Buffer - PostGIS Documentation](https://postgis.net/docs/ST_Buffer.html)
- [ST_Intersection - PostGIS Documentation](https://postgis.net/docs/ST_Intersection.html)
- [KNN 연산자 - PostGIS Documentation](https://postgis.net/docs/geometry_distance_knn.html)
- [QGIS Documentation](https://docs.qgis.org/latest/en/docs/)
