---
layout: single
title: "전 세계 건물·도로·POI를 내 지도에 — Overture Maps 도입 판단과 파이프라인"
date: 2026-09-28 12:45:00 +0530
categories: gis
tags: ["overture", "geoparquet", "pmtiles", "duckdb", "공간데이터"]
toc: true
toc_sticky: true
excerpt: "\"지도에 전국 매장과 건물이 다 나오게 해주세요\"라는 요구사항 앞에서 Overture Maps는 매력적인 선택지다. 다만 8,150만 개 POI를 받아오는 일과 그것을 서비스 지도에 띄우는 일은 완전히 다른 작업이다. 데이터 도입 판단 기준과 GeoParquet에서 PMTiles까지의 파이프라인, 그리고 스키마 v2.0.0이 남긴 교훈을 정리했다."
---

## "지도에 전국 매장이 다 나오게 해주세요"

기획 회의에서 자주 나오는 요구사항이다. "경쟁사 지도에는 건물 이름이랑 가게가 다 뜨는데 우리 지도는 회색 덩어리만 나와요." 이 말은 기술적으로 두 개의 전혀 다른 문제로 번역된다. 하나는 **어디서 그 데이터를 구할 것인가**, 다른 하나는 **수천만 건을 어떻게 지도 위에 띄울 것인가**다. 앞의 문제만 풀고 뒤를 못 풀면 "데이터는 있는데 지도가 안 열리는" 상태가 된다.

Overture Maps는 앞의 문제에 대한 2026년 시점의 가장 현실적인 답 중 하나다. Amazon·Meta·Microsoft·TomTom이 함께 만든 재단이 OSM을 포함한 여러 출처를 통합·정제해 개방 라이선스로 배포한다. 2026-09-23.0 릴리스 기준으로 장소(POI) 8,150만 건, 건물 25.3억 동, 주소 4.74억 건 규모다. 직전 릴리스에서 장소가 7,360만에서 10.6% 늘었을 만큼 갱신도 활발하다.

## Overture가 주는 것, 그리고 주지 않는 것

도입 판단에서 가장 중요한 건 **이게 데이터 배포판이지 API 서비스가 아니라는 점**이다. Overture는 S3와 Azure에 GeoParquet 파일 묶음을 올려둘 뿐이다. 지오코딩 엔드포인트도, 타일 서버도, SLA도 없다. 타일 서버와 갱신 파이프라인은 전부 도입하는 쪽이 짓는다. 이 지점을 흐리면 "무료 데이터니까 싸다"는 판단이 운영 비용에서 뒤집힌다.

대신 상용 API가 잘 안 주는 두 가지를 준다. 첫째, **데이터를 손에 쥔다**. 오프라인 처리, 대량 공간 조인, 자체 필터링이 호출 수 제한 없이 가능하다. 둘째, **GERS ID**라는 안정적인 전역 식별자가 붙어 있어 릴리스가 바뀌어도 같은 객체를 추적하고 자체 DB와 조인할 수 있다.

| 선택지 | 초기 비용 | 운영 부담 | 커스터마이징 | 적합한 경우 |
|---|---|---|---|---|
| 상용 지도 API | 낮음 | 낮음 | 거의 불가 | 호출량이 적고 빠르게 붙여야 할 때 |
| OSM 직접 가공 | 중간 | 높음 | 완전 자유 | 특정 지역·특정 태그만 깊게 쓸 때 |
| Overture | 중간 | 중간 | 자유 | 전 세계 범위가 필요하고 데이터를 직접 다뤄야 할 때 |

## 전체 파이프라인에서의 위치

<img src="/assets/images/posts/2026-09-28-overture-maps-data-adoption-pipeline-1.svg" alt="S3의 Overture GeoParquet에서 DuckDB로 bbox·타입 필터링을 거쳐 GeoJSONSeq를 추출하고 tippecanoe로 PMTiles를 구워 오브젝트 스토리지와 CDN을 통해 MapLibre에 서빙하는 파이프라인, 그리고 GERS ID로 자체 DB와 조인하는 경로를 함께 보여주는 구조도" style="width:100%;">

핵심은 **원본 데이터를 그대로 서비스에 붙이지 않는다**는 것이다. Overture GeoParquet은 분석용 저장 포맷이지 렌더링용 포맷이 아니다. 지도에 띄우려면 필요한 영역·필요한 타입만 뽑아 타일로 굽는 단계가 반드시 들어간다. 이 중간 단계를 생략하려다 실패하는 팀이 많다.

## DuckDB로 필요한 만큼만 뽑아내기

전체 릴리스는 수 테라바이트다. 그런데 전부 받을 필요가 없다. GeoParquet은 컬럼 단위로 읽히고 파일에 bbox 컬럼이 들어 있어서, 원격 S3의 파일을 그 자리에서 질의해 필요한 행만 내려받을 수 있다.

```sql
INSTALL spatial; LOAD spatial;
SET s3_region='us-west-2';

COPY (
  SELECT id, names.primary AS name,
         taxonomy.primary AS category,
         geometry
  FROM read_parquet(
    's3://overturemaps-us-west-2/release/2026-09-23.0/theme=places/type=place/*',
    hive_partitioning=1)
  WHERE bbox.xmin BETWEEN 126.7 AND 127.2   -- 서울 근방
    AND bbox.ymin BETWEEN 37.4  AND 37.7
) TO 'seoul-places.geojsonseq'
  WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq');
```

이렇게 뽑은 GeoJSONSeq를 tippecanoe에 넘겨 PMTiles 한 파일로 굽고, 오브젝트 스토리지에 올려 HTTP Range 요청으로 서빙하면 타일 서버 없이도 지도가 뜬다.

```bash
tippecanoe -o seoul-places.pmtiles \
  -zg --drop-densest-as-needed \
  -l places seoul-places.geojsonseq
```

## 스키마 v2.0.0이 남긴 교훈 — 갱신은 계약이다

2026-09-23 릴리스는 스키마 v2.0.0을 함께 올리면서 places 테마의 `categories` 속성을 **삭제했다**. 오랫동안 deprecated 상태였다가 실제로 빠진 것이고, 대신 `taxonomy`(primary·hierarchy·alternates)와 `basic_category`를 쓴다. 예전 쿼리를 그대로 돌리던 파이프라인은 이 릴리스에서 조용히 깨진다.

여기서 배울 점은 Overture만의 문제가 아니다. **외부 개방 데이터를 도입한다는 것은 남이 정한 스키마 변경 일정을 내 배포 일정에 들이는 것**이다. 그래서 도입 시점에 세 가지를 못 박아 두는 편이 낫다. 릴리스 버전을 코드가 아니라 설정으로 관리할 것, 릴리스 고정(pin) 없이 `latest`를 바라보지 말 것, 그리고 갱신을 수동 작업이 아니라 스키마 검증이 포함된 배치로 만들어 둘 것.

## 실무 포인트

**한국 데이터는 반드시 표본 검증부터 한다.** 전 세계 커버리지가 곧 모든 지역의 동일한 품질을 뜻하지는 않는다. 서비스 대상 지역 몇 곳을 뽑아 실제 상호·주소와 대조해 보고 도입 여부를 정한다.

**라이선스는 테마별로 다르다.** 출처에 따라 ODbL 계열 조건이 따라붙는 데이터가 섞여 있으므로, 상용 서비스라면 쓰려는 테마의 출처 표기 의무를 먼저 확인한다.

**갱신 주기를 서비스 요구와 맞춘다.** 월 단위 릴리스는 신규 매장 반영이 느릴 수 있다. 실시간성이 중요한 도메인이라면 Overture를 배경 레이어로 두고 자체 수집 데이터를 위에 얹는 이중 구조가 현실적이다.

## 정리

- Overture는 API가 아니라 **데이터 배포판**이다. 타일 서버와 갱신 파이프라인은 도입하는 쪽이 짓는다는 전제로 비용을 계산한다.
- GeoParquet 원본을 그대로 쓰지 말고 DuckDB로 범위·타입을 좁힌 뒤 PMTiles로 구워 서빙한다.
- 스키마 v2.0.0의 `categories` 삭제처럼, 외부 데이터 도입은 **남의 릴리스 일정을 내 파이프라인에 들이는 일**이다. 버전 고정과 스키마 검증을 처음부터 넣어 둔다.

## 참고 자료

- [Overture Maps — 2026-09-23 릴리스 노트](https://docs.overturemaps.org/blog/2026/09/23/release-notes/)
- [Overture Maps — DuckDB로 데이터 가져오기](https://docs.overturemaps.org/getting-data/duckdb/)
- [Overture Maps — Places 가이드](https://docs.overturemaps.org/guides/places/)
- [PMTiles](https://docs.protomaps.com/pmtiles/)
