---
layout: single
title: "PostGIS 설치하고 첫 공간 쿼리 날려보기"
date: 2026-09-01 13:20:00 +0530
categories: gis
tags: ["postgis", "postgresql", "공간쿼리", "gis입문", "튜토리얼"]
toc: true
toc_sticky: true
excerpt: "PostgreSQL에 PostGIS 확장을 설치하고, 두 지점 사이의 거리를 구하는 첫 공간 쿼리까지 실행해보는 입문 가이드."
---

## 왜 일반 SQL로는 공간 데이터를 다루기 어려운가

두 지점 사이의 거리를 구하거나 "이 폴리곤 안에 있는 점을 모두 찾아라" 같은 질의는 일반 SQL의 산술 연산만으로는 정확히 계산하기 어렵다. 지구가 평면이 아니라 타원체이기 때문에 단순 피타고라스 계산으로는 오차가 생기고, 폴리곤 포함 여부 같은 연산은 애초에 표준 SQL에 없는 개념이다. **PostGIS**는 PostgreSQL에 공간 데이터 타입과 연산을 추가해주는 확장(extension)으로, GIS 분야에서 사실상 표준으로 쓰인다.

## geometry vs geography, 거리 계산이 달라지는 이유

<img src="/assets/images/posts/2026-09-01-postgis-first-spatial-query-1.svg" alt="PostGIS의 geometry 타입은 평면 좌표로 계산해 오차가 생기지만 geography 타입은 지구 곡률을 반영해 정확한 미터 단위 거리를 계산하는 차이를 보여주는 다이어그램" style="width:100%;">

## 설치와 활성화

```sql
-- PostgreSQL 데이터베이스에 접속한 뒤 확장 활성화
CREATE EXTENSION postgis;

-- 설치 확인
SELECT PostGIS_Version();
```

우분투 계열이라면 `sudo apt install postgis postgresql-16-postgis-3`처럼 OS 패키지를 먼저 설치해야 `CREATE EXTENSION`이 성공한다. 관리형 클라우드 DB(RDS, Cloud SQL 등)는 대부분 PostGIS를 옵션으로 이미 제공한다.

## 공간 테이블 만들고 데이터 넣기

```sql
CREATE TABLE places (
    id serial PRIMARY KEY,
    name text,
    geom geometry(Point, 4326)  -- 4326 = WGS84 위경도 좌표계
);

INSERT INTO places (name, geom) VALUES
    ('서울 시청', ST_SetSRID(ST_MakePoint(126.978, 37.5665), 4326)),
    ('강남역', ST_SetSRID(ST_MakePoint(127.027, 37.4979), 4326));
```

`ST_MakePoint(경도, 위도)`로 점을 만들고, `ST_SetSRID`로 좌표계(SRID)를 지정한다. `4326`은 위경도 좌표계를 나타내는 코드로 GPS 좌표를 다룰 때 가장 흔히 쓰인다.

## 첫 공간 쿼리: 두 지점 사이 거리 구하기

```sql
SELECT
    a.name, b.name,
    ST_Distance(a.geom::geography, b.geom::geography) AS distance_meters
FROM places a, places b
WHERE a.name = '서울 시청' AND b.name = '강남역';
```

`::geography`로 형변환하는 것이 중요하다. `geometry` 타입 그대로 계산하면 평면 좌표 기준 거리(단위가 부정확)가 나오지만, `geography`로 변환하면 지구 곡률을 고려한 실제 미터 단위 거리가 나온다.

## 실무 포인트

- **`geometry`와 `geography` 타입을 헷갈리면 거리·면적 계산 결과가 크게 틀어진다.** 정확한 실측 거리가 필요하면 `geography`, 복잡한 공간 연산과 성능이 중요하면 `geometry`를 쓰는 것이 일반적인 구분이다.
- **공간 인덱스(GiST)를 만들지 않으면 데이터가 많아질수록 공간 쿼리가 급격히 느려진다.** `CREATE INDEX idx_places_geom ON places USING GIST (geom);`을 반드시 함께 만들어야 한다.
- **좌표계(SRID)를 명시하지 않거나 다른 SRID의 데이터를 섞어서 계산하면 결과가 조용히 틀리게 나온다.** 에러 없이 틀린 값이 나오는 경우가 많아 특히 주의해야 한다.

## 마무리 요약

- PostGIS는 PostgreSQL에 공간 데이터 타입과 연산을 추가하는 확장으로, `CREATE EXTENSION postgis`로 활성화한다.
- 실제 거리를 구할 때는 `geometry`가 아니라 `::geography`로 형변환해야 지구 곡률을 반영한 정확한 미터 단위 값이 나온다.
- 공간 인덱스(GiST)를 만들지 않으면 데이터가 늘어날수록 쿼리 성능이 급격히 나빠진다.

## 참고 자료

- [PostGIS 공식 문서](https://postgis.net/documentation/)
- [PostGIS 공식 문서 - ST_Distance](https://postgis.net/docs/ST_Distance.html)
