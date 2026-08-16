---
layout: single
title: "타일 서버를 지워버리기 — tippecanoe와 PMTiles로 만드는 정적 벡터 타일 파이프라인"
date: 2026-08-23 14:20:00 +0530
categories: gis
tags: ["gis", "tippecanoe", "pmtiles", "vector-tiles", "maplibre", "serverless"]
toc: true
toc_sticky: true
excerpt: "요청마다 타일을 만드는 서버 대신, 빌드 시점에 tippecanoe로 타일을 미리 굽고 PMTiles 단일 파일로 정적 스토리지에 올려 HTTP Range 요청만으로 서빙하는 파이프라인을 정리한다."
---

웹 지도에 벡터 타일을 서빙하는 방법을 검색하면 대부분 서버를 세우는 이야기부터 나온다. PostGIS에 데이터를 넣고 pg_tileserv나 martin 같은 타일 서버를 붙이거나, 상용 지도 서비스의 타일 API를 구독하는 식이다. 요청이 올 때마다 DB에서 지오메트리를 꺼내 타일을 만드는 이 구조는 데이터가 수시로 바뀔 때는 합리적이지만, 실제 서비스에서 지도에 올리는 데이터의 상당수는 그렇지 않다. 행정경계, 도로망, 건물 폴리곤, 분기마다 갱신되는 통계 데이터처럼 한번 만들면 한동안 그대로인 데이터를 위해 24시간 돌아가는 서버와 DB를 유지하는 것은 낭비에 가깝다.

이 글에서 다루는 대안은 발상을 뒤집는다. 타일을 요청 시점에 만들지 말고, **빌드 시점에 전 줌 레벨을 미리 구워서 정적 파일로 배포**하는 것이다. 사실 "미리 굽기" 자체는 오래된 기법이다. 문제는 결과물이었다. z/x/y 디렉터리 구조로 풀어놓으면 수십만~수백만 개의 작은 파일이 생겨 업로드와 동기화가 고통스럽고, MBTiles로 묶으면 SQLite 파일을 읽어줄 서버가 다시 필요해진다.

이 마지막 퍼즐을 푼 것이 **PMTiles**다. 타일 전체를 단일 파일에 담되, 클라이언트가 HTTP Range 요청으로 필요한 타일 바이트만 읽어갈 수 있게 설계된 포맷이다. 굽는 쪽은 Mapbox에서 시작해 현재 Felt가 관리하는 **tippecanoe**가 사실상 표준 도구다. 두 도구를 이으면 "서버 프로세스가 하나도 없는" 벡터 타일 파이프라인이 완성된다.

## 핵심 개념 1: tippecanoe는 변환기가 아니라 '지도 제작 도구'다

tippecanoe를 GeoJSON을 타일로 바꾸는 단순 변환기로 생각하면 절반만 이해한 것이다. 벡터 타일의 진짜 어려움은 변환이 아니라 **줌 레벨마다 무엇을 버릴지 결정하는 일**이다. 전국 건물 수백만 채를 줌 7 타일에 전부 담으면 타일 하나가 수 MB로 부풀어 렌더링이 불가능해진다. tippecanoe는 이 결정을 자동화한다. 낮은 줌에서는 지오메트리를 단순화하고, 밀집 지역의 피처를 규칙적으로 솎아내고, 작은 폴리곤을 병합해 각 타일을 렌더링 가능한 크기(기본 상한 500KB)로 유지한다.

실무에서 가장 자주 쓰는 옵션 조합은 다음과 같다. `-zg`는 데이터의 밀도를 보고 적절한 최대 줌을 자동 결정하고, `--drop-densest-as-needed`는 타일이 상한을 넘을 때 가장 밀집된 곳부터 피처를 떨어뜨리며, `--extend-zooms-if-still-dropping`은 최대 줌에서도 여전히 피처가 버려지고 있으면 줌을 한 단계 더 늘려 전체 데이터가 보이는 줌을 보장한다. 어떤 옵션이 정답인지는 데이터 성격(포인트인지 폴리곤인지, 균일 분포인지 도심 집중인지)에 따라 달라서, 한 번 굽고 끝이 아니라 결과를 지도에 올려보며 옵션을 조정하는 반복 작업이 필요하다.

## 핵심 개념 2: PMTiles — 단일 파일을 Range 요청으로 읽는다

PMTiles 파일의 내부는 크게 헤더, 디렉터리, 타일 데이터 세 부분으로 구성된다. 디렉터리는 타일 좌표(z/x/y)를 파일 내 오프셋과 길이로 매핑하는 색인이고, 타일들은 힐베르트 곡선 순서로 정렬되어 지리적으로 인접한 타일이 파일 안에서도 가까이 배치된다. 클라이언트는 먼저 파일 앞부분을 Range 요청으로 읽어 헤더와 디렉터리를 확보하고, 이후 화면에 필요한 타일의 오프셋을 계산해 해당 바이트 구간만 요청한다. 서버가 하는 일은 정적 파일의 일부를 잘라 보내주는 것뿐이므로, S3·Cloudflare R2·일반 웹 서버 등 Range를 지원하는 곳이면 어디든 호스팅이 된다.

기존 방식과의 차이를 표로 정리하면 이렇다.

| 구분 | z/x/y 디렉터리 | MBTiles | PMTiles |
|---|---|---|---|
| 파일 개수 | 수십만~수백만 개 | 1개 (SQLite) | 1개 |
| 정적 호스팅 직접 서빙 | 가능하나 업로드·동기화 부담 큼 | 불가 (서버 필요) | 가능 (Range 요청) |
| 배포/갱신 | 파일 단위 동기화 | 파일 교체 + 서버 재시작 | 파일 1개 교체 |
| 서버 프로세스 | 불필요 | 필요 | 불필요 |

## 핵심 개념 3: 소비하는 쪽 — MapLibre와 pmtiles 프로토콜

MapLibre GL JS는 기본적으로 `https://.../{z}/{x}/{y}.pbf` 형태의 URL 템플릿으로 타일을 요청한다. PMTiles를 쓰려면 protomaps가 제공하는 `pmtiles` 자바스크립트 라이브러리로 커스텀 프로토콜을 등록해, `pmtiles://` 스킴의 소스 URL이 내부적으로 Range 요청으로 변환되게 하면 된다. 디렉터리는 클라이언트가 캐싱하므로 지도를 움직일 때마다 색인을 다시 읽지는 않는다. CDN을 앞에 두면 자주 요청되는 바이트 구간이 엣지에 캐싱되어, 사실상 전용 타일 서버와 구분되지 않는 응답 속도가 나온다.

이 구조의 진짜 매력은 운영 비용의 형태가 바뀐다는 점이다. 동적 타일 서버는 트래픽이 없어도 인스턴스와 DB가 상시 비용을 발생시키고, 트래픽이 몰리면 스케일링과 커넥션 풀을 고민해야 한다. 반면 PMTiles는 남는 비용이 스토리지 요금과 전송량뿐이고, 부하 대응은 CDN이 대신한다. 장애 지점도 "정적 파일이 안 내려온다" 하나로 줄어들어, 소규모 팀이 지도 서비스를 유지하는 부담이 크게 낮아진다. 갱신 파이프라인도 단순해서, 원본 데이터가 바뀔 때 CI에서 tippecanoe를 돌려 파일 하나를 교체하는 배치 작업으로 자동화하면 끝이다.

<img src="/assets/images/posts/2026-08-23-tippecanoe-pmtiles-pipeline-1.svg" alt="원본 공간 데이터가 tippecanoe 빌드를 거쳐 PMTiles 단일 파일이 되고, 정적 스토리지에 올라간 뒤 브라우저가 HTTP Range 요청으로 필요한 타일만 읽어가는 파이프라인 구조도" style="width:100%;">

## 예제

건물 폴리곤 GeoJSON을 PMTiles로 굽는 명령이다. 최근 버전의 tippecanoe는 `-o` 확장자만 `.pmtiles`로 주면 PMTiles를 직접 출력한다.

```bash
tippecanoe -o buildings.pmtiles \
  -l buildings \
  -n "서울 건물 폴리곤" \
  -zg \
  --drop-densest-as-needed \
  --extend-zooms-if-still-dropping \
  --force \
  buildings.geojson

# 결과 확인 후 정적 스토리지에 업로드 (예: S3)
aws s3 cp buildings.pmtiles s3://my-tiles-bucket/buildings.pmtiles
```

브라우저 쪽에서는 프로토콜 등록 한 번이면 일반 벡터 소스처럼 쓸 수 있다.

```javascript
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  center: [126.978, 37.566],
  zoom: 11,
  style: {
    version: 8,
    sources: {
      buildings: {
        type: "vector",
        url: "pmtiles://https://tiles.example.com/buildings.pmtiles",
      },
    },
    layers: [
      {
        id: "buildings-fill",
        type: "fill",
        source: "buildings",
        "source-layer": "buildings",
        paint: { "fill-color": "#4a78a8", "fill-opacity": 0.6 },
      },
    ],
  },
});
```

## 실무 포인트와 흔한 함정

**함정 1: maxzoom을 무작정 올리는 것.** "확대해도 선명해야 하니까"라며 최대 줌을 18~20으로 굽는 경우가 있는데, 줌이 한 단계 오를 때마다 타일 수는 4배가 되므로 파일 크기와 빌드 시간이 폭증한다. 벡터 타일은 래스터와 달리 **오버줌(overzoom)**이 가능하다. 최대 줌 타일의 좌표 데이터를 렌더러가 그대로 확대해 그리므로, 대부분의 데이터는 줌 14~15까지만 굽고 그 이상은 렌더러에 맡기는 것이 옳다.

**함정 2: 중간 프록시의 자동 압축.** 타일 데이터는 이미 내부적으로 gzip 압축되어 있는데, CDN이나 웹 서버가 파일 전체에 압축을 다시 걸면(Content-Encoding 적용) Range 요청의 바이트 오프셋이 원본과 어긋나 타일이 깨진다. PMTiles는 반드시 **압축 변환 없이(identity)** 서빙해야 하고, CDN 설정에서 해당 경로의 자동 압축을 꺼야 한다. 브라우저에서 직접 읽는다면 CORS 설정에 `Range` 헤더 허용도 필요하다.

**언제 쓰지 말아야 하나.** 갱신은 파일 전체 재빌드·교체이므로, 데이터가 분 단위로 바뀌는 실시간 위치 데이터나 사용자 권한에 따라 보여줄 피처가 달라지는 요구사항에는 맞지 않는다. 그런 경우는 PostGIS 기반 동적 타일 서버가 여전히 정답이다. 반대로 "주기적 배치로 갱신되는 데이터 + 불특정 다수에게 동일한 지도"라면, 운영 비용과 장애 지점 측면에서 PMTiles 쪽이 압도적으로 유리하다.

## 마무리 요약

- tippecanoe는 줌별 단순화·피처 드로핑을 자동화해 원본 공간 데이터를 렌더링 가능한 벡터 타일로 구워주는 빌드 도구다.
- PMTiles는 전체 타일을 단일 파일에 담고 HTTP Range 요청으로 필요한 부분만 읽게 해, 타일 서버 없이 정적 스토리지 + CDN만으로 서빙을 완성한다.
- 배치 갱신 데이터에는 최적이지만, 실시간 갱신·사용자별 필터링이 필요하면 동적 타일 서버를 선택해야 한다.

## 참고 자료

- tippecanoe 공식 저장소: <https://github.com/felt/tippecanoe>
- PMTiles 명세와 문서: <https://docs.protomaps.com/pmtiles/>
- PMTiles 라이브러리 저장소: <https://github.com/protomaps/PMTiles>
- MapLibre GL JS 문서: <https://maplibre.org/maplibre-gl-js/docs/>
