---
layout: single
title: "래스터도 결국 테이블 안에 — PostGIS raster 타입과 ST_Value, 벡터 변환 실무"
date: 2026-08-29 13:20:00 +0530
categories: gis
tags: ["postgis", "raster", "st_value", "gis", "spatial-database", "vector-raster-conversion"]
toc: true
toc_sticky: true
excerpt: "PostGIS의 raster 타입으로 DEM·위성영상을 DB 안에서 직접 질의하는 방법과, ST_Value로 픽셀값을 읽고 ST_DumpAsPolygons/ST_AsRaster로 벡터-래스터를 상호 변환하는 실무를 정리한다."
---

래스터 데이터(DEM, 위성영상, 격자형 기후 데이터)를 다루다 보면 결국 벡터 데이터(포인트, 폴리곤)와 함께 질의해야 하는 순간이 온다. "이 지점의 고도는 얼마인가", "이 행정구역 안의 평균 식생지수는 얼마인가" 같은 질문은 래스터와 벡터를 같은 질의 안에서 엮어야 답할 수 있다. 파일 기반으로 GDAL 커맨드라인을 여러 단계 거쳐 처리할 수도 있지만, PostGIS의 `raster` 타입을 쓰면 이 작업을 SQL 한 번으로, 심지어 벡터 테이블과 조인해서 처리할 수 있다.

이 글은 GDAL 기반 래스터 대수(map algebra)나 데이터큐브 같은 대용량 처리 파이프라인이 아니라, **PostGIS 안에서 래스터를 벡터와 함께 다루는 실무 질의 패턴**에 초점을 맞춘다. 구체적으로는 특정 지점의 픽셀값을 읽는 `ST_Value`, 폴리곤 내부 통계를 구하는 존별 통계, 그리고 래스터와 벡터를 서로 변환하는 `ST_DumpAsPolygons`/`ST_AsRaster`를 다룬다.

## 핵심 개념 1: PostGIS raster 타입의 구조

PostGIS는 `raster`라는 컬럼 타입으로 격자 데이터를 테이블 안에 저장한다. 하나의 raster 값은 내부적으로 여러 개의 **타일(tile)**로 나뉘어 저장되는 것이 일반적인데, 이는 큰 래스터 하나를 통째로 한 행에 담으면 조회·인덱싱이 비효율적이기 때문이다. `raster2pgsql` 유틸리티로 GeoTIFF 같은 파일을 불러올 때 `-t` 옵션으로 타일 크기(예: `256x256`)를 지정하면, 원본 이미지가 여러 행으로 쪼개져 저장되고 각 타일마다 공간 인덱스(GiST)가 걸린다.

```bash
# GeoTIFF를 PostGIS raster 테이블로 적재 (256x256 타일, SRID 4326)
raster2pgsql -s 4326 -t 256x256 -I -C elevation.tif public.dem_tiles | psql -d gisdb
```

이렇게 타일 단위로 저장하면, 특정 지점이나 영역을 조회할 때 공간 인덱스로 관련된 타일만 골라내 필요한 부분만 계산할 수 있어 전체 래스터를 매번 읽지 않아도 된다.

## 핵심 개념 2: ST_Value로 지점의 픽셀값을 읽는다

가장 흔한 질의는 "이 좌표의 값이 무엇인가"이다. `ST_Value`는 포인트 지오메트리가 걸리는 픽셀의 값을 반환한다.

```sql
-- 특정 지점(경도 127.05, 위도 37.5)의 고도값을 DEM 래스터에서 조회
SELECT ST_Value(rast, pt.geom) AS elevation
FROM dem_tiles
JOIN (SELECT ST_SetSRID(ST_MakePoint(127.05, 37.5), 4326) AS geom) AS pt
  ON ST_Intersects(rast, pt.geom)
WHERE ST_BandIsNoData(rast, 1) IS NOT TRUE;  -- NoData 픽셀은 제외
```

`ST_Intersects(rast, pt.geom)`는 공간 인덱스를 타서 후보 타일을 빠르게 좁혀주는 역할을 한다. 여러 개의 포인트에 대해 한꺼번에 값을 뽑고 싶다면, 포인트 테이블과 래스터 테이블을 조인하는 형태로 그대로 확장하면 된다. 이 패턴은 관측소 좌표 목록에 해당하는 기후 격자값을 한 번에 매칭하는 등의 작업에 자주 쓰인다.

## 핵심 개념 3: 존별 통계와 벡터-래스터 상호 변환

폴리곤 안의 평균·합계 같은 통계가 필요하다면 `ST_SummaryStats`를 폴리곤으로 자른(clip) 래스터에 적용한다.

```sql
-- 행정구역 폴리곤 안의 평균 고도 계산 (ST_Clip으로 폴리곤 범위만 잘라낸 뒤 통계)
SELECT d.name,
       (ST_SummaryStats(ST_Clip(r.rast, b.geom))).mean AS avg_elevation
FROM boundaries b
JOIN dem_tiles r ON ST_Intersects(r.rast, b.geom)
JOIN districts d ON d.id = b.district_id;
```

래스터를 벡터로 바꾸는 방향은 `ST_DumpAsPolygons`가 담당한다. 같은 값을 가진 인접 픽셀들을 하나의 폴리곤으로 묶어(연결 요소 단위) 벡터화하는데, 토지피복 분류 결과처럼 "같은 클래스 값을 가진 영역을 폴리곤으로 뽑아내고 싶을 때" 쓰인다.

```sql
-- 토지피복 래스터(클래스 값 정수)를 클래스별 폴리곤으로 변환
SELECT (gv).val AS landcover_class, (gv).geom AS boundary
FROM (
  SELECT ST_DumpAsPolygons(rast, 1) AS gv
  FROM landcover_tiles
) sub;
```

반대로 벡터를 래스터로 굽는(rasterize) 방향은 `ST_AsRaster`가 맡는다. 폴리곤 레이어를 특정 해상도의 격자로 변환할 때, 예를 들어 벡터 형태의 존(zone) 구획을 다른 래스터 분석과 같은 해상도로 맞춰야 할 때 쓰인다.

```sql
-- 폴리곤을 30m 해상도 래스터로 변환 (분석용 격자와 해상도를 맞출 때)
SELECT ST_AsRaster(geom, 30.0, 30.0, '8BUI', zone_id) AS zone_raster
FROM zone_polygons;
```

<img src="/assets/images/posts/2026-08-29-postgis-raster-type-practice-1.svg" alt="PostGIS raster 타입은 타일 단위로 저장되고, ST_Value로 지점 조회, ST_SummaryStats로 폴리곤 존 통계, ST_DumpAsPolygons로 래스터에서 벡터로, ST_AsRaster로 벡터에서 래스터로 변환하는 흐름" style="width:100%;">

## 핵심 비교: 주요 함수와 용도

| 함수 | 입력 → 출력 | 대표 용도 |
|---|---|---|
| `ST_Value` | 래스터 + 포인트 → 픽셀값 | 특정 지점의 관측값 조회 |
| `ST_SummaryStats` | 래스터(+ 폴리곤으로 Clip) → 통계 | 존별 평균·합계·표준편차 |
| `ST_DumpAsPolygons` | 래스터 → 폴리곤 집합 | 분류 결과의 벡터화 |
| `ST_AsRaster` | 벡터 → 래스터 | 벡터 구역을 분석용 격자로 변환 |
| `ST_Clip` | 래스터 + 폴리곤 → 잘린 래스터 | 통계·연산 전 관심 영역만 추출 |

## 실무 포인트

- **NoData 처리를 빠뜨리지 않는다**: DEM이나 위성영상에는 관측 결손 영역이 NoData 값으로 표시된다. `ST_Value`나 `ST_SummaryStats` 결과에 NoData가 섞이면 평균값이 왜곡되므로, `ST_BandIsNoData`로 걸러내거나 통계 함수의 `exclude_nodata_value` 옵션을 명시적으로 확인한다.
- **out-of-db 래스터 옵션을 검토한다**: `raster2pgsql -R` 옵션으로 실제 픽셀 데이터를 DB 밖의 파일로 두고 메타데이터만 DB에 저장하는 방식도 가능하다. 매우 큰 래스터를 다룰 때 DB 용량 부담을 줄일 수 있지만, 파일 경로 관리와 백업 전략을 별도로 챙겨야 한다는 트레이드오프가 있다.
- **타일 크기는 조회 패턴에 맞춰 정한다**: 타일이 너무 크면 작은 영역 조회에도 불필요하게 큰 데이터를 읽고, 너무 작으면 타일 수가 많아져 메타데이터 오버헤드와 조인 비용이 늘어난다. 일반적으로 100~256픽셀 사각형이 무난한 시작점으로 언급되지만, 실제 조회 패턴(포인트 조회 위주인지 넓은 영역 통계 위주인지)에 따라 벤치마크로 조정하는 것이 안전하다.

## 3줄 요약

- PostGIS의 raster 타입은 격자 데이터를 타일 단위로 테이블에 저장해, 벡터 데이터와 같은 SQL 안에서 함께 질의할 수 있게 한다.
- `ST_Value`로 지점의 픽셀값을, `ST_SummaryStats`+`ST_Clip`으로 폴리곤 존별 통계를 구하는 것이 가장 흔한 실무 질의 패턴이다.
- `ST_DumpAsPolygons`는 래스터를 벡터로, `ST_AsRaster`는 벡터를 래스터로 변환해, 두 데이터 모델 사이를 필요에 따라 오갈 수 있게 해준다.

## 참고 자료

- [PostGIS 공식 문서: Raster Reference](https://postgis.net/docs/RT_reference.html)
- [PostGIS 공식 문서: raster2pgsql](https://postgis.net/docs/using_raster_dataman.html)
- [PostGIS 공식 문서: ST_SummaryStats](https://postgis.net/docs/RT_ST_SummaryStats.html)
