---
layout: single
title: "WFS의 REST 후계자, OGC API - Features로 공간 데이터 서비스 만들기"
date: 2026-08-19 13:20:00 +0530
categories: gis
tags: ["gis", "ogc-api-features", "wfs", "geojson", "rest-api", "spatial-data"]
toc: true
toc_sticky: true
excerpt: "XML·SOAP 기반이라 다루기 번거로웠던 WFS 대신, HTTP GET과 JSON만으로 공간 데이터를 주고받는 OGC API - Features의 리소스 구조와 필터링 방식을 정리한다."
---

## 왜 지금 OGC API - Features인가

공간 데이터를 표준 프로토콜로 서비스하려 할 때 오랫동안 기본값이었던 것은 WFS(Web Feature Service)였다. 문제는 WFS가 XML 요청 파라미터, 네임스페이스, GML 인코딩처럼 웹 개발자에게는 낯선 규약 위에 서 있다는 점이다. REST API와 JSON에 익숙한 프론트엔드·백엔드 개발자 입장에서는 지도 데이터 하나 받아오는 데 별도의 WFS 클라이언트 라이브러리나 XML 파서가 필요했고, 이는 GIS 전문가가 아닌 팀이 공간 데이터를 서비스에 붙이는 데 실질적인 장벽이었다.

OGC(Open Geospatial Consortium)는 이 간극을 메우기 위해 **OGC API** 라는 새로운 표준 계열을 만들었고, 그 첫 결과물이 **OGC API - Features** 다. 리소스를 HTTP GET으로 접근하고 기본 응답 포맷으로 GeoJSON을 쓰며, API 명세 자체를 OpenAPI로 제공한다. WFS가 "지도 서버 전용 프로토콜을 배워야 접근 가능한 데이터"였다면, OGC API - Features는 "curl과 fetch로 바로 찔러볼 수 있는 데이터"에 가깝다. 이전 글에서 다룬 PostGIS 기반 벡터 타일 서빙이 "화면에 그릴 타일"을 내려주는 것이었다면, 이번 표준은 그보다 상위 레이어에서 **개별 피처(feature) 단위의 조회·필터링**을 REST 방식으로 표준화한다는 점에서 다르다.

## 핵심 개념 1: WFS와 무엇이 다른가

| 구분 | WFS (2.0) | OGC API - Features |
|---|---|---|
| 요청 방식 | XML POST 또는 긴 쿼리스트링 GET | 표준 HTTP GET(리소스 경로 기반) |
| 응답 포맷 | GML(기본), 확장으로 GeoJSON | GeoJSON(기본), 다른 포맷도 협상 가능 |
| API 명세 | 별도 스펙 문서 참조 | OpenAPI 문서를 `/api`에서 직접 제공 |
| 탐색 방식 | 클라이언트가 스펙을 미리 알아야 함 | 응답 안 `links`로 다음 요청을 스스로 안내(하이퍼미디어) |
| 학습 곡선 | GIS 전용 지식 필요 | 일반 REST API 감각으로 접근 가능 |

WFS를 완전히 대체한다기보다, 같은 데이터를 훨씬 다루기 쉬운 방식으로 노출하는 대안이 늘어난 것으로 보는 편이 정확하다. 실제로 상당수 서버 구현체는 같은 데이터셋을 WFS와 OGC API - Features 양쪽으로 동시에 제공한다.

## 핵심 개념 2: 리소스 구조

OGC API - Features는 소수의 리소스 경로만으로 전체 API를 구성한다. 진입점인 랜딩 페이지에서 시작해 컬렉션 목록 → 개별 컬렉션 → 피처 목록 → 개별 피처 순으로 내려가는 구조다.

<img src="/assets/images/posts/2026-08-19-ogc-api-features-1.svg" alt="OGC API Features 리소스 구조 - 랜딩 페이지에서 컬렉션, 피처 목록, 개별 피처로 이어지는 계층도" style="width:100%;">

| 경로 | 역할 |
|---|---|
| `GET /` | 랜딩 페이지 — 다른 리소스로 가는 링크 모음 |
| `GET /conformance` | 이 서버가 준수하는 표준 항목 목록 |
| `GET /collections` | 제공하는 데이터셋(레이어) 목록 |
| `GET /collections/{id}` | 특정 컬렉션의 메타데이터(좌표범위, CRS 등) |
| `GET /collections/{id}/items` | 해당 컬렉션의 피처 목록(GeoJSON FeatureCollection) |
| `GET /collections/{id}/items/{featureId}` | 피처 단건 조회 |

모든 응답에는 `links` 필드가 포함되어 `self`, `next`, `alternate` 같은 관계를 명시한다. 클라이언트는 URL 구조를 미리 외울 필요 없이 이 링크를 따라가기만 하면 되는데, 이는 REST의 HATEOAS 원칙을 공간 데이터 API에 그대로 적용한 것이다.

## 핵심 개념 3: 필터링과 페이지네이션

`items` 엔드포인트는 쿼리 파라미터로 필터링을 지원한다. `bbox`로 사각형 범위를, `datetime`으로 시간 범위를, `limit`으로 한 번에 받을 개수를 지정한다. 대용량 컬렉션은 커서 대신 `links`의 `next` URL을 따라가는 방식으로 페이지네이션을 처리하므로, 클라이언트가 오프셋 값을 직접 계산할 필요가 없다. 더 복잡한 속성 기반 조건(예: 특정 필드 값 비교, 논리 연산 조합)은 별도 확장 표준인 CQL2(Common Query Language) 필터링으로 다루는데, 이는 코어 표준과 분리된 선택적 확장이라 서버마다 지원 여부가 다르다.

## 예제: REST 요청과 응답

```bash
# 서울 인근 bbox 안의 건물 피처를 최대 10개, 최신 5개 필드만 조회
curl "https://example.com/ogcapi/collections/buildings/items?bbox=126.9,37.5,127.1,37.6&limit=10"
```

```json
{
  "type": "FeatureCollection",
  "numberMatched": 4821,
  "numberReturned": 10,
  "links": [
    { "rel": "self", "href": "https://example.com/ogcapi/collections/buildings/items?bbox=126.9,37.5,127.1,37.6&limit=10" },
    { "rel": "next", "href": "https://example.com/ogcapi/collections/buildings/items?bbox=126.9,37.5,127.1,37.6&limit=10&offset=10" }
  ],
  "features": [
    {
      "type": "Feature",
      "id": "b-10293",
      "geometry": { "type": "Polygon", "coordinates": [[[126.978, 37.566], [126.980, 37.566], [126.980, 37.568], [126.978, 37.566]]] },
      "properties": { "name": "예시 빌딩", "floors": 12, "use": "commercial" }
    }
  ]
}
```

`numberMatched`는 조건에 맞는 전체 피처 수, `numberReturned`는 이번 응답에 실제로 담긴 개수다. 클라이언트는 `links`의 `next` 항목만 따라가면 다음 페이지를 얻을 수 있어, 오프셋 계산 로직을 직접 짤 필요가 없다.

## 실무 포인트

- **CRS 기본값 확인이 먼저다**: 코어 표준의 기본 좌표계는 WGS84 경위도이며, 다른 좌표계로 받으려면 서버가 별도 확장(CRS 협상)을 지원하는지부터 확인해야 한다. 모든 구현체가 같은 확장 집합을 지원하지는 않는다.
- **`/conformance`로 지원 범위를 먼저 점검한다**: 필터링, 정렬, CRS 확장 등은 서버 구현체마다 지원 여부가 갈리므로, 실제 요청을 짜기 전에 이 엔드포인트로 무엇이 되고 안 되는지 확인하는 편이 시행착오를 줄인다.
- **대용량 피처는 `limit`을 보수적으로 잡는다**: 지오메트리가 복잡한 폴리곤을 다량 포함한 응답은 페이로드가 커질 수 있어, 초기 개발 단계에서는 작은 `limit`으로 응답 크기와 지연을 먼저 확인하는 것이 안전하다.
- **서버 구현체 선택지가 여러 개다**: pygeoapi, GeoServer, ldproxy 등 오픈소스 구현체가 이미 이 표준을 지원하므로, 처음부터 직접 구현하기보다 기존 구현체 위에 데이터를 얹는 방식을 먼저 검토할 만하다.

## 3줄 요약

- OGC API - Features는 XML 기반 WFS 대신 HTTP GET과 GeoJSON만으로 공간 데이터를 주고받는 REST 스타일 표준이다.
- 랜딩 페이지 → 컬렉션 → 피처 목록 → 개별 피처로 이어지는 소수의 리소스 경로와, 응답에 포함된 `links`를 따라가는 하이퍼미디어 방식이 핵심이다.
- 실무 도입 시에는 `/conformance`로 서버의 실제 지원 범위(CRS, 필터링)를 먼저 확인하고, 대용량 응답은 `limit`과 페이지네이션으로 제어해야 한다.

## 참고 자료

- [OGC API - Features 공식 표준 문서](https://ogcapi.ogc.org/features/)
- [OGC 공식 사이트 — OGC API 개요](https://www.ogc.org/publications/standard/ogcapi-features/)
- [pygeoapi 공식 문서](https://docs.pygeoapi.io/)
