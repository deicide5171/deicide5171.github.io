---
layout: single
title: "분석 한 번에 PostGIS 서버를 또 띄워야 할까 — DuckDB Spatial로 끝내는 판단 기준"
date: 2026-10-02 12:45:00 +0530
categories: gis
tags: ["duckdb", "postgis", "geoparquet", "공간분석", "데이터아키텍처"]
toc: true
toc_sticky: true
excerpt: "\"이 지역 GeoParquet 파일 하나만 분석해주세요\"라는 1회성 요청에 매번 PostGIS 서버를 새로 띄우는 건 과하다. 서버 없이 프로세스 안에서 공간 분석을 끝내는 DuckDB Spatial과, 언제 그래도 PostGIS로 승격해야 하는지 판단 기준을 정리했다."
---

## 왜 지금 이 판단이 필요한가

"이번 분기 상권 확장 검토용으로, Overture에서 받은 이 지역 GeoParquet 파일 하나만 빠르게 분석해주세요." 분석가나 기획자에게 이런 요청을 받으면, 그동안 빌더가 쥔 카드는 둘 중 하나였다. PostGIS를 올릴 서버를 새로 띄우고 데이터를 테이블로 임포트하거나, GeoPandas로 파일 전체를 메모리에 올려 느린 반복문을 돌리거나. 둘 다 "파일 하나 잠깐 들여다보는" 일치고는 과하다.

이 전제가 흔들린 이유는 DuckDB의 spatial 확장이 지난 1~2년 사이 빠르게 성숙했기 때문이다. GEOS 위에 구현된 공간 함수 라이브러리와 PROJ 좌표계 변환을 바이너리 하나에 통째로 담아, 서버 프로세스 없이 커맨드 하나로 공간 쿼리를 실행할 수 있다. 게다가 S3에 있는 GeoParquet·COG 파일을 로컬로 내려받지 않고 원격에서 바로 읽어 들이는 기능까지 갖추면서, "서버 기반 공간 데이터베이스가 항상 정답"이라는 전제 자체를 다시 물어야 하는 상황이 됐다.

## 요구사항을 기술 문제로 번역하기

"공간 데이터를 분석해달라"는 말은 실제로는 전혀 다른 두 요구를 뭉뚱그린 표현이다. 하나는 **애플리케이션이 실시간으로 반복해서 던지는 공간 질의**(지도에서 반경 안 매장을 보여줘, 사용자가 특정 구역에 들어오면 알려줘) — 이건 동시 접속·동시 쓰기·낮은 지연을 보장해야 하는 서빙 문제다. 다른 하나는 **분석가가 한 번, 혹은 배치로 돌리는 리포트성 질의**(이 지역 전체 매장 밀도를 구해줘, 분기별 변화를 비교해줘) — 이건 읽기 위주이고 동시성 요구가 거의 없다.

이 둘을 구분하지 않고 둘 다 PostGIS에 몰아넣으면, 분석용으로 쓰는 임시 테이블과 앱이 서빙 중인 운영 테이블이 같은 서버 자원을 두고 경쟁한다. 반대로 서빙용 질의까지 DuckDB로 돌리려 하면, 매번 파일을 스캔하는 구조라 반복 호출에서 영속적인 공간 인덱스의 이점을 누릴 수 없다. 요구사항을 받았을 때 가장 먼저 할 일은 "이게 앱 기능인가, 분석 작업인가"를 가르는 것이다.

## 전체 시스템에서의 위치

<img src="/assets/images/posts/2026-10-02-duckdb-spatial-vs-postgis-tradeoff-1.svg" alt="앱 서빙 경로는 상시 가동 PostGIS 서버가 GiST 인덱스로 동시 접속 질의를 처리하는 반면, 분석 경로는 DuckDB 프로세스가 S3의 GeoParquet·COG 파일을 ETL 없이 직접 읽어 분석한 뒤 프로세스가 종료되면 사라지고 결과만 저장소에 남는 구조를 비교한 다이어그램" style="width:100%;">

서빙 경로는 데이터가 앱의 운영 DB에 상주하고, 상시 가동 중인 PostGIS가 GiST 인덱스로 요청을 빠르게 처리한 뒤 다음 요청을 또 받을 준비를 한다. 분석 경로는 정반대다. DuckDB 프로세스는 S3에 있는 원본 파일을 ETL 없이 그 자리에서 읽고, 질의가 끝나면 프로세스 자체가 사라진다. 결과만 파케이나 CSV로 저장소에 남긴다. 이 비대칭이 핵심이다 — 분석 경로에는 애초에 "상주"라는 개념이 없어도 된다.

## PostGIS vs DuckDB Spatial — 무엇을 기준으로 고를까

| 기준 | PostGIS (상시 서버) | DuckDB Spatial (임베디드) |
|---|---|---|
| 운영 모델 | 서버 프로세스 상시 가동 | 프로세스 내 라이브러리, 서버 불필요 |
| 동시 쓰기·트랜잭션 | ACID 트랜잭션, 동시 쓰기 지원 | 읽기 중심, 동시 쓰기 안전성 약함 |
| 데이터 소스 | 로컬 테이블로 임포트 필요 | S3의 GeoParquet·COG·Shapefile 원격 직접 쿼리 |
| 반복 질의 성능 | GiST 영속 인덱스로 빠름 | 매 쿼리 스캔 기반, 반복 서빙엔 불리 |
| 적합한 경우 | 앱이 실시간으로 던지는 공간 질의, geofencing | 분석가의 1회성·배치 리포트, ETL 파이프라인 중간 단계 |

가장 흔한 함정은 "DuckDB가 빠르니 운영 DB도 교체하자"는 성급한 결론이다. DuckDB spatial은 매 쿼리마다 필요한 범위를 스캔하는 구조이므로, 같은 반경 검색을 초당 수백 번 반복해야 하는 서빙 워크로드에는 맞지 않는다. 반대로 "이미 PostGIS가 있으니 분석도 거기서 하자"는 것도 함정이다. 분석가가 매번 새 테이블을 만들고 지우는 작업을 운영 DB에서 반복하면 그 자체로 운영 부담이자 사고 위험이다.

## 실제 프로젝트 진행 순서

1. **요청이 앱 기능인지 분석 작업인지부터 구분한다.** "이 화면에서 매번 써야 한다"면 서빙, "이번 한 번 결과만 필요하다"면 분석이다.
2. **분석이라면 DuckDB부터 시도한다.** 별도 설치 없이 `pip install duckdb` 후 `INSTALL spatial; LOAD spatial;`만으로 바로 쿼리를 실행할 수 있다.
3. **원본이 S3의 GeoParquet·COG라면 ETL을 생략한다.** 파일을 로컬로 내려받거나 테이블로 적재하지 않고 원격 경로를 그대로 쿼리에 바인딩한다.
4. **같은 질의가 반복적으로, 동시에, 낮은 지연으로 필요해지면 그때 PostGIS로 승격을 검토한다.** "분석"이 "기능"으로 바뀌는 순간이 바로 이 지점이다.
5. **승격할 때는 DuckDB에서 검증한 쿼리 로직을 거의 그대로 포팅한다.** 두 시스템 모두 GEOS 기반이라 ST_Distance, ST_Within 같은 함수명과 의미가 대부분 겹친다.

```sql
INSTALL spatial;
LOAD spatial;

-- S3의 GeoParquet을 내려받지 않고 바로 쿼리
SELECT name, ST_AsText(geometry) AS geom
FROM read_parquet('s3://overture-maps/release/places/*.parquet')
WHERE ST_Within(
  geometry,
  ST_GeomFromText('POLYGON((127.0 37.5, 127.1 37.5, 127.1 37.6, 127.0 37.6, 127.0 37.5))')
)
LIMIT 100;
```

## 실무 포인트

**DuckDB의 공간 인덱스는 비영속적이다.** 세션이 끝나면 인덱스도 함께 사라지므로, 같은 파일을 반복 분석할 계획이라면 매번 인덱스를 다시 만드는 비용을 감안해야 한다. 이 비용이 누적되기 시작하면 PostGIS 승격 신호로 봐도 좋다.

**좌표계 변환이 기본 내장돼 있다.** PROJ 데이터베이스를 통째로 바이너리에 포함하고 있어 별도 설치 없이 `ST_Transform`으로 좌표계를 바꿀 수 있다. 분석 환경을 빠르게 세팅할 때 이 점이 특히 유리하다.

**운영 DB의 대체재가 아니다.** 동시 쓰기 트랜잭션 보장이 약하므로, 앱이 사용자 데이터를 실시간으로 쓰고 읽는 경로에 DuckDB를 끼워 넣는 선택은 피해야 한다. 분석과 서빙의 경계를 명확히 유지하는 것이 이 판단의 핵심이다.

## 마무리

- "공간 데이터를 분석해달라"는 요청은 먼저 앱 서빙 문제인지 1회성 분석 문제인지부터 구분해야 한다.
- 분석이라면 서버를 새로 띄우기 전에 DuckDB Spatial로 S3의 GeoParquet·COG를 직접 쿼리하는 쪽이 더 빠르고 가볍다.
- 같은 질의가 반복·동시·저지연 요구로 바뀌는 순간이 PostGIS 승격 시점이며, 이때 쿼리 로직은 거의 그대로 포팅할 수 있다.

## 참고 자료

- [DuckDB Spatial Extension — 공식 문서](https://duckdb.org/docs/current/core_extensions/spatial/overview.html)
- [PostGIS meets DuckDB: Crunchy Bridge for Analytics goes Spatial](https://www.crunchydata.com/blog/postgis-meets-duckdb-crunchy-bridge-for-analytics-goes-spatial)
- [DuckDB is probably the most important geospatial software of the decade](https://simonwillison.net/2025/May/4/duckdb-is-probably-the-most-important-geospatial-software-of-the/)
