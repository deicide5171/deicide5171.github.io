---
layout: single
title: "PostGIS 하나로 벡터 타일 서버 만들기 — pg_tileserv 실전 정리"
date: 2026-08-15 12:20:00 +0530
categories: gis
tags: ["gis", "postgis", "vector-tile", "spatial-database", "webmap"]
toc: true
toc_sticky: true
excerpt: "PostGIS 테이블을 별도 ETL 없이 바로 웹 지도 타일로 서빙하는 pg_tileserv의 동작 원리와 설정, 실무에서 주의할 성능 포인트를 정리한다."
---

## 왜 지금 PostGIS 타일 서빙인가

웹 지도에 대용량 공간 데이터를 올릴 때 흔한 파이프라인은 "DB에서 데이터를 뽑아 → 별도 배치로 타일을 미리 구워서 → 정적 파일로 서빙"하는 방식이었다. 이 방식은 빠르지만, 데이터가 바뀔 때마다 다시 구워야 한다는 단점이 있다. 실시간성이 중요한 서비스(배차 현황, 실시간 재고, 사용자 신고 지도)에는 잘 맞지 않는다.

**PostGIS**는 이미 많은 팀이 공간 데이터 저장소로 쓰고 있는 오픈소스 확장이다. 여기에 **pg_tileserv** 같은 경량 타일 서버를 앞단에 붙이면, 지오메트리 컬럼이 있는 테이블을 별도 ETL 없이 그대로 **벡터 타일(MVT, Mapbox Vector Tile)** 레이어로 자동 노출할 수 있다. DB에 INSERT/UPDATE가 일어나는 즉시 지도에 반영되는 구조를 훨씬 적은 인프라로 구현할 수 있는 셈이다.

여기에 최근 PostGIS 진영에서는 H3 육각 인덱싱, 3D 지오메트리 지원처럼 공간 분석 기능이 계속 확장되고 있어, "저장소 + 분석 + 서빙"을 한 데이터베이스 안에서 처리하는 흐름이 점점 자연스러워지고 있다.

## 기존 방식 vs PostGIS 직접 서빙

| 항목 | 사전 타일링(배치) | PostGIS + pg_tileserv |
|---|---|---|
| 최신성 | 배치 주기만큼 지연 | DB 반영 즉시 |
| 인프라 | 타일 생성 파이프라인 + 정적 파일 스토리지 | DB + 경량 서버 하나 |
| 대용량 정적 데이터 | 유리(캐싱, CDN 배포 쉬움) | 매 요청 쿼리 부하 발생 |
| 필터링·동적 쿼리 | 어려움(사전 계산된 결과만) | SQL 함수로 자유롭게 조건 추가 가능 |

정적 지도(행정구역 경계, 국가 지도)는 사전 타일링이 여전히 유리하다. 반면 자주 바뀌고 조회 조건이 다양한 데이터(주문 위치, 실시간 센서)는 PostGIS 직접 서빙이 더 잘 맞는다.

## 동작 원리: 지오메트리 컬럼 하나로 타일 레이어가 되는 과정

1. 테이블에 `geometry` 타입 컬럼과 공간 인덱스(GiST)가 있으면 pg_tileserv가 이를 자동 인식해 타일 레이어로 등록한다.
2. 지도 클라이언트가 `/layer/{z}/{x}/{y}.pbf` 형태로 특정 타일 좌표를 요청한다.
3. pg_tileserv는 해당 타일의 경계 박스(bbox)를 계산해 `ST_AsMVT` 함수로 그 범위 안의 지오메트리만 SQL로 조회한다.
4. 결과를 MVT 바이너리로 인코딩해 응답한다 — 클라이언트는 이를 Mapbox GL JS, MapLibre 같은 라이브러리로 렌더링한다.

핵심은 "전체 지도를 미리 만들지 않고, 화면에 보이는 범위만 그때그때 SQL로 잘라 준다"는 점이다.

## 예제: PostGIS 함수 레이어로 커스텀 타일 만들기

단순 테이블 노출을 넘어, 조건이 있는 동적 레이어는 SQL 함수로 만든다.

```sql
CREATE OR REPLACE FUNCTION public.active_reports(
    z integer, x integer, y integer
) RETURNS bytea AS $$
    SELECT ST_AsMVT(tile, 'active_reports', 4096, 'geom') FROM (
        SELECT
            id,
            title,
            ST_AsMVTGeom(
                geom,
                ST_TileEnvelope(z, x, y),
                4096, 64, true
            ) AS geom
        FROM reports
        WHERE status = 'active'
          AND geom && ST_TileEnvelope(z, x, y)
    ) AS tile;
$$ LANGUAGE SQL STABLE;
```

`geom && ST_TileEnvelope(z, x, y)`는 GiST 공간 인덱스를 타는 bbox 필터로, 전체 테이블을 스캔하지 않고 해당 타일 범위와 겹치는 행만 빠르게 골라낸다. pg_tileserv는 이 함수를 자동 감지해 `status='active'`인 신고 데이터만 담은 레이어로 노출한다.

## 실무 포인트

- **공간 인덱스는 선택이 아니라 필수다**: `geom` 컬럼에 `CREATE INDEX ... USING GIST (geom)`이 없으면 타일 요청마다 전체 테이블 스캔이 발생해 응답이 급격히 느려진다.
- **저줌 레벨에서는 단순화(simplify)한다**: 국가 단위로 축소된 지도에서까지 원본 정밀도의 폴리곤을 보낼 필요는 없다. `ST_AsMVTGeom`의 톨러런스와 `ST_Simplify`를 줌 레벨에 맞게 조절한다.
- **캐싱을 앞단에 둔다**: 자주 조회되는 저줌 타일은 리버스 프록시나 CDN 캐시를 앞에 둬 DB 부하를 줄인다. 실시간성이 중요한 고줌 레벨만 캐시 TTL을 짧게 가져간다.
- **함수 기반 레이어의 파라미터를 검증한다**: 사용자 입력을 SQL 함수 인자로 그대로 넘기는 경우 SQL 인젝션 방지를 위해 파라미터 바인딩과 화이트리스트 검증을 거친다.

## 3줄 요약

- PostGIS + pg_tileserv 조합은 별도 ETL 없이 DB 테이블을 실시간 벡터 타일로 노출할 수 있게 해준다.
- 내부적으로는 요청받은 타일의 bbox만 `ST_AsMVT`로 잘라 SQL로 조회하는 방식이라, GiST 공간 인덱스가 성능을 좌우한다.
- 정적·대용량 지도는 여전히 사전 타일링이 유리하며, 자주 바뀌는 동적 데이터에 PostGIS 직접 서빙을 선택적으로 적용하는 것이 현실적인 전략이다.

## 참고 자료

- [PostGIS 공식 문서](https://postgis.net/docs/)
- [pg_tileserv (Crunchy Data)](https://github.com/CrunchyData/pg_tileserv)
- [Mapbox Vector Tile Specification](https://github.com/mapbox/vector-tile-spec)
