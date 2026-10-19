---
layout: single
title: "\"타일 캐시도 에이전트가 바로 쓰게 해주세요\" — WMTS에서 OGC API - Tiles로 넘어가야 하는가"
date: 2026-10-19 12:45:00 +0530
categories: gis
tags: ["ogc-api-tiles", "wmts", "geoserver", "gwc", "vector-tiles", "migration"]
toc: true
toc_sticky: true
excerpt: "GWC로 운영 중인 WMTS 타일 캐시를 두고 '신규 웹앱·에이전트 도구가 바로 소비할 수 있게 해달라'는 요구가 오면, XML 기반 WMTS를 OGC API - Tiles로 바꿔야 하는지 판단하는 기준과 GeoServer에서의 공존 전략을 정리했다."
---

## 도입

"지도 타일 캐시는 이미 잘 돌아가는데, 신규 웹앱이랑 에이전트 도구에서 바로 가져다 쓸 수 있게 좀 해주세요." GWC(GeoWebCache)로 WMTS 타일을 몇 년째 안정적으로 서빙해온 팀이 자주 듣는 요구다. 문제는 WMTS의 GetCapabilities 응답이 수백 줄짜리 XML이고, 타일 URL을 조립하려면 TileMatrixSet 구조를 먼저 파싱해야 한다는 점이다. 사람이 짠 지도 클라이언트는 이미 그 파싱 로직을 라이브러리 안에 갖고 있지만, 빠르게 프로토타입을 만드는 웹앱이나 좌표·줌레벨만 알고 바로 타일을 요청하고 싶은 에이전트 도구 입장에서는 이 XML 협상 과정 자체가 장벽이다.

이 간극을 메우는 것이 OGC API - Tiles다. WMTS가 하던 일(타일 매트릭스 집합 정의, 타일 URL 템플릿 제공)을 그대로 수행하면서도, 메타데이터를 JSON으로, API 설명을 OpenAPI로 내놓는다. 앞서 OGC API - Features가 WFS를 REST/JSON으로 대체했던 것과 같은 흐름이 타일 쪽에서도 벌어지고 있는 것인데, 둘은 별개의 표준이고 적용 시점·판단 기준도 다르다. GeoServer·MapServer 같은 주요 서버 구현체는 이미 GWC 캐시 하나를 WMTS와 OGC API - Tiles 양쪽으로 동시에 노출할 수 있다는 점은 의사결정의 부담을 크게 줄여준다.

## 핵심 개념: 같은 타일, 두 가지 설명서

| 항목 | WMTS | OGC API - Tiles |
|---|---|---|
| 메타데이터 포맷 | GetCapabilities XML (TileMatrixSet 포함) | JSON `tileMatrixSets`, `tiles.json` |
| 타일 URL 구조 | 매트릭스마다 다른 KVP 또는 REST 템플릿을 XML에서 역산 | `/collections/{id}/tiles/{tileMatrixSet}/{z}/{y}/{x}` 고정 패턴 |
| 벡터 타일 지원 | 확장 스펙으로 가능하지만 서버마다 구현이 제각각 | MVT·GeoJSON을 표준 콘텐츠 협상으로 지원 |
| 캐시 계층과의 관계 | GWC가 WMTS 응답을 직접 캐싱 | 같은 GWC 캐시를 REST 경로로 재노출(별도 캐시가 아님) |
| 발견 가능성 | 클라이언트가 XML 스펙을 미리 알아야 파싱 가능 | OpenAPI 문서를 `/api`에서 바로 제공, curl·fetch로 바로 접근 |

중요한 건 이게 "더 빠른 캐시"가 아니라 "같은 캐시를 더 쉽게 찾아가는 길"이라는 점이다. 타일 생성·보관 성능은 GWC 설정(캐시 영역, 포맷, 만료 정책)이 결정하고, OGC API - Tiles는 그 위에 얹는 발견·요청 레이어일 뿐이다. 그래서 "타일이 느려요"라는 요구에는 이 전환이 답이 되지 않는다 — 그건 이전 글에서 다룬 GWC 캐시 전략과 Control Flow 설정의 영역이다.

<img src="/assets/images/posts/2026-10-19-ogc-api-tiles-wmts-geoserver-migration-1.svg" alt="GeoServer가 같은 GWC 타일 캐시를 WMTS와 OGC API Tiles 두 경로로 동시에 노출하는 구조도" style="width:100%;">

## 트레이드오프: 지금 전환해야 하는가

| 상황 | 권장 |
|---|---|
| 신규 웹앱이 JS로 지도를 직접 그린다 | OGC API - Tiles 추가 — 타일 URL 템플릿을 코드에 바로 하드코딩할 수 있어 XML 파싱이 필요 없다 |
| 에이전트·MCP 도구가 타일을 가져다 분석에 쓴다 | OGC API - Tiles가 유리 — OpenAPI 문서가 있어 에이전트가 스펙을 스스로 읽고 요청을 구성할 수 있다 |
| 기존 데스크톱 GIS(QGIS 구버전 등) 연동 유지 | WMTS 유지 — 구형 클라이언트는 여전히 WMTS 플러그인으로만 타일을 받는다 |
| 타일 응답 속도 자체가 느리다 | 전환과 무관 — GWC 캐시 설정과 Control Flow 튜닝이 먼저다 |

전면 교체가 아니라 "GWC 설정은 그대로 두고 OGC API - Tiles 엔드포인트만 추가로 켠다"가 리스크가 가장 낮은 선택이다. WMTS를 꺼야 할 이유가 아직 없고, 반대로 신규 클라이언트·에이전트를 위해 OGC API - Tiles를 켜지 않을 이유도 없다.

## 실무 진행 순서

1. **GWC가 OGC API - Tiles를 지원하는 버전인지 확인한다.** GeoServer는 최신 버전에서 GWC 캐시를 OGC API - Tiles 모듈로도 노출하는 옵션을 제공한다. 별도 캐시를 새로 만드는 게 아니라 기존 캐시 설정을 그대로 재사용하는지 먼저 확인한다.
2. **TileMatrixSet 정의를 점검한다.** WMTS에서 쓰던 격자 체계(보통 EPSG:3857 기반 GoogleMapsCompatible)가 OGC API - Tiles 쪽 JSON 정의와 1:1로 매핑되는지 확인한다. 여기서 어긋나면 줌레벨별 타일이 다른 영역을 가리키는 버그가 난다.
3. **벡터 타일 포맷을 결정한다.** 래스터 타일만 쓰던 레이어를 이 기회에 MVT로도 열지 판단한다. 콘텐츠 협상(`Accept` 헤더)으로 같은 엔드포인트에서 포맷을 나눠 받을 수 있다.
4. **신규 소비자부터 전환한다.** 내부 웹앱, 에이전트 도구 연동 건부터 OGC API - Tiles 경로를 쓰게 하고, 기존 WMTS 연동은 건드리지 않는다.
5. **OpenAPI 문서를 사내 포털에 연결한다.** 자동 생성되는 스펙 문서를 그대로 노출하면, 새 통합을 시도하는 팀이 GWC 설정을 몰라도 타일 요청 방법을 스스로 찾을 수 있다.

예제(OGC API - Tiles 메타데이터와 타일 요청):

```text
GET /geoserver/ogc/tiles/v1/collections/topp:states/tiles

{
  "tileMatrixSetLinks": [
    { "tileMatrixSet": "WebMercatorQuad",
      "tileMatrixSetURI": ".../tileMatrixSets/WebMercatorQuad" }
  ],
  "links": [
    { "rel": "item", "href": ".../tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}?f=mvt" }
  ]
}

GET /geoserver/ogc/tiles/v1/collections/topp:states/tiles/WebMercatorQuad/8/103/221?f=mvt
```

## 실무 포인트

- WMTS의 `TileMatrix` 축 순서(행·열)와 OGC API - Tiles의 경로 파라미터 순서가 서버 구현체마다 미묘하게 다르게 매핑될 수 있다. 마이그레이션 직후 특정 줌레벨에서만 타일이 어긋난다면 이 매핑부터 의심한다.
- 캐시는 하나지만 노출 경로가 둘이 되면, 캐시 무효화(purge) 작업을 할 때 두 경로 모두에 반영되는지 반드시 확인해야 한다. GWC REST API로 purge했는데 OGC API - Tiles 쪽 응답은 그대로인 경우가 실제로 보고된다.
- 벡터 타일로 처음 전환할 때는 스타일링 책임이 서버에서 클라이언트로 넘어간다는 점을 팀에 미리 공유해야 한다. 래스터 타일은 서버가 색을 다 입혀서 주지만, MVT는 좌표만 주고 스타일은 클라이언트 라이브러리(MapLibre 등)가 맡는다.

## 마무리

- OGC API - Tiles는 WMTS 캐시 자체를 더 빠르게 만드는 게 아니라, 같은 캐시를 더 쉽게 찾고 요청하게 해주는 발견·요청 레이어다.
- 타일 성능 문제는 GWC 캐시 전략의 영역이고, 클라이언트·에이전트 접근성 문제는 OGC API - Tiles의 영역이다 — 둘을 혼동하면 엉뚱한 곳을 고치게 된다.
- WMTS를 끄지 않고 같은 GWC 캐시 위에 OGC API - Tiles 경로를 추가로 켜는 것이 가장 리스크가 낮은 도입 순서다.

## 참고 자료

- [OGC API - Tiles Standard](https://ogcapi.ogc.org/tiles/)
- [GeoServer OGC API 모듈 문서](https://docs.geoserver.org/latest/en/user/services/ogcapi/index.html)
- [GeoWebCache 공식 문서](https://www.geowebcache.org/docs/current/)
