---
layout: single
title: "Shapefile의 대안, GeoParquet은 얼마나 왔나"
date: 2026-08-15 17:20:00 +0530
categories: gis
tags: ["geoparquet", "shapefile", "공간데이터", "클라우드네이티브", "parquet"]
toc: true
toc_sticky: true
excerpt: "Shapefile의 오래된 한계를 짚어보고, 이를 대체하려는 클라우드 네이티브 공간 데이터 포맷 GeoParquet의 장점과 도입 시 고려사항을 정리했다."
---

## 왜 지금 GeoParquet인가

GIS 실무에서 Shapefile은 여전히 가장 널리 쓰이는 포맷이다. 하지만 이 포맷은 1990년대에 설계된 구조를 거의 그대로 유지하고 있어서, 최근 몇 년 사이 늘어난 대용량 위성·항공 데이터, 클라우드 기반 분석 파이프라인과는 잘 맞지 않는 지점이 계속 드러나고 있다. 파일 하나가 아니라 `.shp`, `.shx`, `.dbf` 등 여러 파일로 나뉘어야 동작하고, 속성 필드 이름이 10자로 제한되며, 대용량 데이터를 부분만 읽어오기 어렵다는 문제는 오래전부터 지적되어 왔다.

이런 배경에서 최근 몇 년간 공간 데이터 커뮤니티가 주목해온 것이 GeoParquet이다. 컬럼 기반 저장 포맷인 Apache Parquet에 지리공간 메타데이터 규격을 얹은 것으로, Overture Maps나 여러 오픈 지도 데이터셋이 배포 포맷으로 채택하면서 실무 도입 사례가 늘고 있는 것으로 보인다. Shapefile을 완전히 대체했다고 단정하기는 아직 이르지만, 대용량·클라우드 환경에서는 확실히 대안으로 자리잡아가는 흐름이다.

이 글에서는 Shapefile의 한계를 정리하고, GeoParquet과 클라우드 네이티브 공간 데이터 포맷 전반의 장점, 그리고 실무에 도입할 때 고려할 점을 살펴본다.

## Shapefile의 구조적 한계

Shapefile은 하나의 데이터셋을 표현하는 데 여러 개의 개별 파일이 필요하다. 지오메트리를 담는 `.shp`, 인덱스인 `.shx`, 속성 테이블인 `.dbf`가 기본이고, 좌표계 정보(`.prj`)까지 포함하면 파일 관리가 번거로워진다. 파일 중 하나라도 누락되거나 손상되면 데이터셋 전체를 열 수 없다는 점도 실무에서 자주 겪는 문제다.

또한 속성 필드 이름이 최대 10자로 제한되고, 하나의 지오메트리 타입만 담을 수 있으며, 2GB 남짓에서 실질적인 크기 제약이 나타난다는 점도 잘 알려진 한계다. 무엇보다 클라우드 오브젝트 스토리지(S3, GCS 등)에 올려두고 필요한 부분만 골라 읽는 방식의 접근에는 애초에 적합하지 않게 설계되어 있다.

## GeoParquet과 클라우드 네이티브 공간 데이터

GeoParquet은 Parquet의 컬럼 기반 저장 구조를 그대로 활용하면서, 지오메트리 컬럼을 WKB(Well-Known Binary)로 인코딩하고 좌표계·바운딩박스 등의 메타데이터를 파일 스키마에 함께 기록하는 규격이다. 컬럼 단위로 저장되기 때문에 속성 몇 개만 필요한 경우 해당 컬럼만 읽어올 수 있고, Parquet 자체가 제공하는 압축·통계 정보를 통해 불필요한 행 그룹을 건너뛰는 최적화도 가능하다.

여기에 더해 클라우드 최적화 흐름에서는 파일 내부에 미리 공간 인덱스(예: Hilbert curve 정렬)를 두거나, HTTP Range 요청으로 파일의 일부만 내려받는 방식(클라우드 최적화 포맷, COG의 벡터 버전 격)이 함께 논의되고 있다. 아직 이 부분은 표준화가 활발히 진행 중인 영역이라, 도구별로 지원 수준에 차이가 있다는 점은 감안할 필요가 있다.

가장 큰 실무적 이점은 Spark, DuckDB, Pandas/GeoPandas, BigQuery 등 이미 Parquet을 지원하는 빅데이터 분석 도구 생태계에 별도 변환 없이 자연스럽게 올라탈 수 있다는 점이다.

### Shapefile vs GeoParquet 비교

| 항목 | Shapefile | GeoParquet |
|---|---|---|
| 파일 구성 | 여러 파일(.shp/.shx/.dbf 등) | 단일 파일 |
| 속성 필드명 길이 | 최대 10자 제한 | 제한 없음(Parquet 스키마 따름) |
| 저장 방식 | 행 기반 | 컬럼 기반 |
| 부분 읽기 | 어려움 | 컬럼·행 그룹 단위로 용이 |
| 압축 | 제한적 | Parquet 압축 활용(대체로 효율적) |
| 빅데이터 도구 연동 | 별도 변환 필요한 경우가 많음 | Spark·DuckDB 등과 친화적 |
| 생태계 성숙도 | 매우 오래되고 광범위 | 성장 중, 도구별 지원 편차 존재 |

## 코드로 보는 GeoParquet 다루기

GeoPandas를 사용하면 Shapefile과 거의 동일한 방식으로 GeoParquet을 읽고 쓸 수 있다.

```python
import geopandas as gpd

# Shapefile 읽기
gdf = gpd.read_file("parcels.shp")

# GeoParquet으로 저장
gdf.to_parquet("parcels.parquet")

# GeoParquet 다시 읽기
gdf2 = gpd.read_parquet("parcels.parquet")
print(gdf2.crs)
print(gdf2.head())
```

DuckDB의 spatial 확장을 쓰면 파일 전체를 메모리에 올리지 않고도 조건에 맞는 행만 골라 조회할 수 있다.

```python
import duckdb

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")

result = con.execute("""
    SELECT name, geometry
    FROM read_parquet('s3://my-bucket/parcels.parquet')
    WHERE area_sqm > 1000
""").fetchdf()
```

## 실무 도입 시 고려사항

- **도구 호환성 우선 확인**: 사내에서 쓰는 GIS 소프트웨어(QGIS, ArcGIS 등)의 GeoParquet 지원 버전을 먼저 확인하는 것이 안전하다. 최신 버전에서는 대체로 지원하지만, 구버전에서는 플러그인이나 변환 단계가 필요할 수 있다.
- **좌표계 메타데이터 검증**: 변환 과정에서 CRS 정보가 누락되거나 잘못 기록되는 경우가 있으므로, 변환 직후 반드시 좌표계를 확인하는 습관이 필요하다.
- **점진적 전환**: 기존 Shapefile 자산을 한 번에 모두 바꾸기보다는, 신규 대용량 데이터셋이나 클라우드 파이프라인부터 GeoParquet을 적용해보고 범위를 넓히는 방식이 리스크가 적다.
- **표준 버전 확인**: GeoParquet 스펙 자체가 아직 발전 중이므로, 데이터를 주고받는 상대방과 스펙 버전을 맞추는 절차가 필요하다.

## 3줄 요약

- Shapefile은 파일 분산, 필드명 제한, 대용량 처리 비효율 등 오래된 구조적 한계를 가지고 있다.
- GeoParquet은 컬럼 기반 저장과 Parquet 생태계 호환성을 바탕으로 클라우드·빅데이터 환경에 더 적합한 대안으로 떠오르고 있다.
- 다만 표준과 도구 지원이 계속 발전 중인 단계이므로, 도구 호환성 확인과 점진적 전환이 안전한 접근이다.

## 참고 자료

- [GeoParquet 공식 스펙 저장소](https://github.com/opengeospatial/geoparquet)
- [Apache Parquet 공식 문서](https://parquet.apache.org/docs/)
- [GeoPandas 공식 문서](https://geopandas.org/)
- [DuckDB Spatial Extension 문서](https://duckdb.org/docs/extensions/spatial)
- [Overture Maps Foundation](https://overturemaps.org/)
