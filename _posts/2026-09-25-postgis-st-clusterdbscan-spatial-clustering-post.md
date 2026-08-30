---
layout: single
title: "PostGIS ST_ClusterDBSCAN으로 공간 밀집 지역 자동 탐지하기"
date: 2026-09-25 13:20:00 +0530
categories: gis
tags: ["PostGIS", "DBSCAN", "공간클러스터링", "밀집지역분석", "SQL"]
toc: true
toc_sticky: true
excerpt: "마커 수천 개를 화면 줌 레벨에 따라 시각적으로만 묶는 클라이언트 클러스터링과 달리, 실제 좌표 거리와 밀도를 기준으로 상권·사고 다발 지역 같은 진짜 밀집 구역을 DB 쿼리 한 번으로 찾아내는 PostGIS ST_ClusterDBSCAN의 동작 원리를 정리했다."
---

## 왜 지금 ST_ClusterDBSCAN을 다시 봐야 하는가

지도 위에 마커가 수천 개 찍히면 화면이 버벅이는 문제를 마커 클러스터링으로 해결하는 방법은 이미 익숙하다. 그런데 그 클러스터링은 어디까지나 "화면에 겹쳐 보이는 마커를 시각적으로 묶어서 보여주는 것"일 뿐, 줌 레벨을 바꾸면 클러스터 구성 자체가 매번 달라지는 임시적인 그룹핑이다. 반면 실무에서는 "실제로 어느 지역에 배달 요청이 밀집되어 있는가", "사고가 반복적으로 발생하는 구간은 어디인가"처럼 화면과 무관하게 데이터 자체의 공간적 밀집도를 분석해 영구적인 그룹으로 저장해야 하는 요구가 자주 생긴다. 이때 필요한 것이 밀도 기반 클러스터링 알고리즘인 DBSCAN이고, PostGIS는 이를 `ST_ClusterDBSCAN`이라는 윈도우 함수로 SQL 쿼리 한 번에 실행할 수 있게 제공한다.

## 핵심 개념 1 — 거리(eps)와 최소 개수(minpoints)로 정의되는 밀집

DBSCAN(Density-Based Spatial Clustering of Applications with Noise)은 K-Means 같은 알고리즘과 달리 클러스터 개수를 미리 지정할 필요가 없다. 대신 두 개의 파라미터로 "밀집됐다"의 기준을 정의한다. `eps`는 이웃으로 인정할 최대 거리이고, `minpoints`는 어떤 점이 "핵심점(core point)"이 되기 위해 그 반경 안에 있어야 하는 최소 이웃 수다. 어떤 점 주변 `eps` 거리 안에 `minpoints`개 이상의 점이 있으면 그 점을 핵심점으로 표시하고, 핵심점들이 서로 `eps` 거리 안에서 연쇄적으로 이어지면 하나의 클러스터로 병합한다. 어느 클러스터에도 속하지 못한 고립된 점은 노이즈(noise)로 분류되어 클러스터 ID가 NULL로 반환된다. 이 방식의 강점은 클러스터의 모양이 원형이 아니라 도로를 따라 길게 늘어진 형태여도 실제 밀집 구조를 그대로 따라간다는 점이다.

## 핵심 개념 2 — 윈도우 함수로 동작한다: GROUP BY가 아니라 OVER

`ST_ClusterDBSCAN`은 일반적인 집계 함수처럼 `GROUP BY`와 함께 쓰는 것이 아니라, 윈도우 함수로 동작해 `OVER ()` 절과 함께 사용한다. 각 행(포인트)에 대해 그 포인트가 속한 클러스터의 번호(정수, 0부터 시작)를 새로운 컬럼으로 반환하며, 원래 행 개수와 결과 행 개수가 동일하게 유지된다는 것이 특징이다. 이 덕분에 원본 데이터를 그대로 두고 클러스터 ID만 한 컬럼 추가하는 형태로 결과를 받을 수 있어, 이후 `GROUP BY cluster_id`로 클러스터별 통계(중심점, 개수, 면적 등)를 뽑아내는 후속 쿼리와 자연스럽게 이어진다.

| 항목 | 클라이언트 마커 클러스터링 | PostGIS ST_ClusterDBSCAN |
|---|---|---|
| 판단 기준 | 화면 픽셀 거리(줌 레벨 의존) | 실제 좌표 거리(eps)와 밀도 |
| 결과의 영속성 | 렌더링 시점마다 재계산, 저장 안 함 | 쿼리 결과로 영구 저장·분석 가능 |
| 클러스터 모양 | 원형에 가까움(픽셀 그룹) | 데이터 분포를 따라 임의 형태 |
| 노이즈 처리 | 없음(모든 점이 어딘가에 속함) | 밀집도 미달 점은 노이즈로 명시적 분리 |

## 예제 — 배달 요청 밀집 구역 탐지와 클러스터별 통계

```sql
-- eps=500m(SRID가 미터 단위 투영좌표계라고 가정), 반경 안 최소 5개 이상이면 클러스터
SELECT
    id,
    geom,
    ST_ClusterDBSCAN(geom, eps := 500, minpoints := 5) OVER () AS cluster_id
FROM delivery_requests;

-- 클러스터별 통계 뽑기 (노이즈로 분류된 NULL은 제외)
WITH clustered AS (
    SELECT
        geom,
        ST_ClusterDBSCAN(geom, eps := 500, minpoints := 5) OVER () AS cluster_id
    FROM delivery_requests
)
SELECT
    cluster_id,
    COUNT(*) AS point_count,
    ST_Centroid(ST_Collect(geom)) AS cluster_center,
    ST_ConvexHull(ST_Collect(geom)) AS cluster_boundary
FROM clustered
WHERE cluster_id IS NOT NULL
GROUP BY cluster_id
ORDER BY point_count DESC;
```

<img src="/assets/images/posts/2026-09-25-postgis-st-clusterdbscan-spatial-clustering-1.svg" alt="원본 포인트 집합에 eps 반경과 minpoints 기준을 적용해 서로 가까운 점들이 클러스터 0, 클러스터 1로 묶이고 고립된 점은 노이즈로 분류되는 DBSCAN의 동작을, 화면 줌 레벨에 따라 임시로만 묶는 클라이언트 마커 클러스터링과 비교해 보여주는 다이어그램" style="width:100%;">

## 실무 포인트

- **`eps` 단위는 사용 중인 SRID의 단위를 그대로 따른다.** EPSG:4326(위경도, 도 단위)로 계산하면 `eps=500`이 500도가 되어버리는 흔한 실수가 생긴다. 미터 단위로 거리를 지정하려면 EPSG:3857 같은 투영좌표계로 `ST_Transform` 해둔 geometry 컬럼을 써야 한다.
- **`minpoints`를 너무 작게 잡으면(예: 2) 노이즈 필터링 효과가 거의 사라진다.** 우연히 가까운 점 두 개도 클러스터로 잡히므로, 실제로 의미 있는 "밀집"이라 부를 만한 최소 개수를 도메인 지식에 맞춰 정해야 한다.
- **대용량 테이블에서는 사전에 공간 인덱스(GiST)가 걸려 있어야 실행 계획이 합리적으로 나온다.** `ST_ClusterDBSCAN` 자체는 인덱스를 직접 활용하는 함수는 아니지만, 대상 데이터를 좁히는 `WHERE ST_Intersects(...)` 같은 조건과 함께 쓸 때는 공간 인덱스 유무가 전체 쿼리 성능에 큰 영향을 준다.

## 마무리 요약

- ST_ClusterDBSCAN은 화면 표시용 임시 그룹핑이 아니라, `eps`(거리)와 `minpoints`(최소 이웃 수)로 정의된 실제 밀도 기준의 클러스터를 SQL 한 번으로 계산해준다.
- 클러스터에 속하지 못한 고립점은 노이즈(NULL)로 명시적으로 분류되며, 클러스터 모양은 원형에 국한되지 않고 실제 데이터 분포를 따라간다.
- 윈도우 함수로 동작해 원본 행에 클러스터 ID 컬럼만 추가하므로, 이후 GROUP BY로 클러스터별 중심점·경계·개수 같은 통계를 자연스럽게 이어서 뽑을 수 있다.

## 참고 자료

- [PostGIS 공식 문서 - ST_ClusterDBSCAN](https://postgis.net/docs/ST_ClusterDBSCAN.html)
- [PostGIS 공식 문서 - Clustering Functions Overview](https://postgis.net/docs/reference.html#Clustering_Functions)
