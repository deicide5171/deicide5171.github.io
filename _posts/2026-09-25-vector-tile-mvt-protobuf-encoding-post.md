---
layout: single
title: "벡터 타일(MVT) 포맷 뜯어보기 — Protobuf 인코딩과 좌표 압축 원리"
date: 2026-09-25 12:20:00 +0530
categories: gis
tags: ["MVT", "VectorTile", "Protobuf", "타일링", "MapLibre"]
toc: true
toc_sticky: true
excerpt: "MapLibre나 Mapbox GL이 .pbf 확장자의 타일을 받아 어떻게 도로·건물·라벨을 그려내는지, Mapbox Vector Tile(MVT) 스펙이 GeoJSON과 달리 딕셔너리 인코딩과 정수 델타 좌표로 타일 하나를 수십 배 작게 만드는 내부 구조를 정리했다."
---

## 왜 지금 MVT 포맷을 다시 봐야 하는가

MapLibre GL JS나 Mapbox GL JS로 지도를 만들 때, 대부분의 실무자는 `source-layer`와 표현식(expression)으로 스타일을 입히는 방법까지는 잘 알지만 정작 서버가 내려주는 `.pbf` 파일 안에 무엇이 들어있는지는 블랙박스로 취급한다. 그런데 타일 서버를 직접 운영하거나(예: `tippecanoe`, `Martin`, `pg_tileserv`), 백엔드에서 PostGIS 데이터를 벡터 타일로 직접 인코딩해야 하는 상황이 되면, MVT(Mapbox Vector Tile) 스펙의 내부 구조를 모르고는 왜 타일이 이렇게 작은지, 왜 줌 레벨마다 좌표 정밀도가 다른지, 왜 속성값이 특정 방식으로만 필터링 가능한지 이해할 수 없다. MVT는 GeoJSON을 그대로 압축한 것이 아니라, 애초에 "타일 하나 안에서 최대한 반복을 줄인다"는 설계 철학으로 처음부터 다시 만들어진 바이너리 포맷이다.

## 핵심 개념 1 — 계층 구조: Tile → Layer → Feature

MVT 파일 하나는 Google Protocol Buffers로 직렬화된 `Tile` 메시지다. 이 안에 여러 개의 `Layer`가 들어가는데, 흔히 보는 "도로", "건물", "라벨" 같은 레이어 구분이 바로 이 Layer 단위다. 각 Layer는 `extent`라는 값을 갖는데, 이는 그 레이어 안의 모든 좌표가 표현되는 로컬 좌표계의 크기(보통 4096)를 의미한다. 즉 MVT의 좌표는 위경도나 미터 단위의 절대 좌표가 아니라, 타일 하나를 4096×4096 크기의 로컬 그리드로 놓고 그 안에서의 정수 좌표로 표현된다. 이 덕분에 하나의 좌표값이 float64가 아니라 작은 정수로 충분히 표현되며, 줌 레벨이 달라져도 같은 인코딩 규칙을 재사용할 수 있다.

## 핵심 개념 2 — 딕셔너리 인코딩과 지오메트리 명령어

Feature마다 속성을 어떻게 저장하는지가 MVT와 GeoJSON의 가장 큰 차이다. GeoJSON은 각 feature의 `properties` 객체에 `"highway": "primary"`처럼 키와 값을 문자열 그대로 매번 반복해서 담는다. 도로 100개가 전부 "primary" 타입이라면 그 문자열이 100번 중복 저장된다. MVT는 Layer 단위로 `keys[]`와 `values[]`라는 전역 딕셔너리를 한 번만 만들어두고, 각 Feature의 `tags`에는 그 딕셔너리를 가리키는 정수 인덱스 쌍만 저장한다. 지오메트리도 마찬가지로 압축적이다. 좌표를 하나하나 절대값으로 저장하는 대신, MoveTo·LineTo·ClosePath 같은 드로잉 명령어와 함께 "이전 점으로부터 얼마나 이동했는가"라는 상대 델타값을 zigzag+varint 방식으로 인코딩한다. 인접한 점들은 대체로 가까이 있으므로 델타값이 작아, 가변 길이 정수 인코딩에서 훨씬 적은 바이트를 차지한다.

| 항목 | GeoJSON | MVT |
|---|---|---|
| 인코딩 방식 | 텍스트(JSON) | 바이너리(Protobuf) |
| 좌표 표현 | 절대 좌표(위경도, float) | 타일 로컬 정수 + 이전 점 대비 델타 |
| 속성 저장 | feature마다 키·값 문자열 반복 | Layer 딕셔너리 + 인덱스 참조 |
| 지오메트리 | 좌표 배열 그대로 | 명령어(MoveTo/LineTo) + 델타 정수열 |
| 용도 | 범용 교환 포맷 | 타일 전송 전용 최적화 포맷 |

## 예제 — MVT 디코딩 결과 확인하기

```bash
# mapbox/vector-tile-js 또는 mapbox/tippecanoe의 tile-join 등으로 pbf를 JSON으로 변환
npm install -g @mapbox/vt2geojson
vt2geojson --pbf tile_14_14133_6482.pbf --layer roads > roads.geojson

# 또는 protoc으로 직접 스키마 기반 디코딩
protoc --decode=vector_tile.Tile vector_tile.proto < tile_14_14133_6482.pbf
```

```javascript
// vector-tile-js로 런타임에 직접 파싱하는 예
import { VectorTile } from '@mapbox/vector-tile';
import Protobuf from 'pbf';

const tile = new VectorTile(new Protobuf(pbfBuffer));
const roadsLayer = tile.layers['roads'];
for (let i = 0; i < roadsLayer.length; i++) {
  const feature = roadsLayer.feature(i);
  console.log(feature.properties, feature.loadGeometry()); // 로컬 좌표(0~4096)로 반환됨
}
```

<img src="/assets/images/posts/2026-09-25-vector-tile-mvt-protobuf-encoding-1.svg" alt="MVT 타일 메시지 안에 여러 Layer가 들어있고, 각 Layer는 keys와 values 딕셔너리를 한 번만 저장한 뒤 Feature의 tags가 그 딕셔너리를 정수 인덱스로 참조하며, 지오메트리는 MoveTo·LineTo 명령어와 이전 점 대비 델타 좌표로 인코딩된다는 것을 GeoJSON의 반복 저장 방식과 비교해 보여주는 다이어그램" style="width:100%;">

## 실무 포인트

- **줌 레벨이 낮을수록 `extent` 대비 실제 좌표 정밀도가 거칠어진다.** 저줌 레벨 타일에서 폴리곤 경계가 계단처럼 보이는 것은 렌더링 버그가 아니라, 낮은 줌에서 생성 시점에 좌표를 더 단순화(simplify)해 넣었기 때문인 경우가 많다. 타일 생성 도구의 줌별 simplification 옵션을 확인해야 한다.
- **속성 필터링(`filter` 표현식)이 딕셔너리 구조 위에서 동작한다는 것을 이해하면 스타일 디버깅이 쉬워진다.** 클라이언트는 정수 인덱스를 다시 문자열로 역참조해 표현식을 평가하므로, 같은 속성이라도 대소문자나 공백이 다르면 다른 딕셔너리 엔트리로 취급돼 필터가 안 먹는 흔한 실수가 여기서 비롯된다.
- **직접 타일 서버를 운영한다면 `tippecanoe`의 `-B`(base zoom), `--drop-densest-as-needed` 같은 옵션이 결국 이 딕셔너리·델타 인코딩 효율에 영향을 준다.** 속성 종류가 적고 반복이 많을수록, 지오메트리가 단순할수록 타일이 작아진다는 원리를 알면 옵션 튜닝의 방향을 잡기 쉽다.

## 마무리 요약

- MVT는 Tile 안에 여러 Layer, Layer 안에 여러 Feature가 들어가는 계층 구조를 가지며, 좌표는 절대 위경도가 아니라 타일별 로컬 정수 그리드(extent, 보통 4096) 기준으로 표현된다.
- Feature 속성은 Layer 단위 keys·values 딕셔너리를 한 번만 저장하고 정수 인덱스로 참조하며, 지오메트리는 드로잉 명령어와 이전 점 대비 델타 좌표를 varint로 인코딩해 크기를 크게 줄인다.
- 이 인코딩 구조를 이해하면 타일 생성 도구의 옵션 튜닝과 스타일 표현식 디버깅 모두에서 원인을 더 정확히 짚을 수 있다.

## 참고 자료

- [Mapbox Vector Tile Specification (mapbox/vector-tile-spec)](https://github.com/mapbox/vector-tile-spec)
- [mapbox/vector-tile-js](https://github.com/mapbox/vector-tile-js)
