---
layout: single
title: "proj4js 실전 활용기 — EPSG 코드 지옥에서 웹 지도 좌표계 탈출하기"
date: 2026-08-20 12:20:00 +0530
categories: gis
tags: ["gis", "proj4js", "epsg", "좌표계변환", "javascript", "openlayers"]
toc: true
toc_sticky: true
excerpt: "브라우저 안에서 EPSG:4326·3857·5186 좌표를 직접 변환해야 할 때, proj4js의 defs 등록과 forward/inverse API를 실전 코드로 정리했다."
---

## 왜 브라우저에서 좌표를 직접 변환해야 하는가

서버에서 이미 좌표계를 통일해서 내려주면 이상적이지만, 실무에서는 그렇지 않은 경우가 훨씬 많다. 국내 공공데이터 API는 여전히 EPSG:5186·5179 같은 지역 좌표계로 응답하고, 지도 라이브러리는 내부적으로 EPSG:3857(Web Mercator) 타일 좌표계를 쓰면서 API 표면은 EPSG:4326(위경도)을 기대한다. 여러 출처의 데이터를 한 화면에 겹쳐야 하는 순간, 결국 **클라이언트 쪽 JavaScript 코드가 좌표를 직접 변환**해야 하는 상황이 생긴다.

`proj4js`는 이 변환을 브라우저·Node.js 어디서든 처리할 수 있게 해주는 라이브러리다. 좌표계의 수학적 정의(투영법·타원체·기준점)를 몰라도, 좌표계를 문자열로 등록하고 변환 함수를 호출하기만 하면 된다. 다만 실전에서는 "어떤 좌표계를 언제 등록해야 하는지", "축 순서가 라이브러리마다 왜 다르게 느껴지는지" 같은 부분에서 자주 막힌다. 이 글은 개념 설명이 아니라 proj4js API 자체 사용법에 집중한다.

## 핵심 개념 1: 내장 좌표계 vs 등록이 필요한 좌표계

proj4js는 EPSG:4326, EPSG:3857처럼 널리 쓰이는 좌표계는 별도 등록 없이 코드 문자열만으로 바로 쓸 수 있다. 하지만 EPSG:5186, EPSG:5179 같은 지역 좌표계는 내장되어 있지 않아서 `proj4.defs()`로 직접 정의를 등록해야 한다.

| 좌표계 | proj4js 기본 지원 | 등록 필요 여부 | 정의 문자열 출처 |
|---|---|---|---|
| EPSG:4326 (WGS84) | O | 불필요 | 내장 |
| EPSG:3857 (Web Mercator) | O | 불필요 | 내장 |
| EPSG:5186 (한국 중부원점) | X | `proj4.defs()` 필요 | epsg.io의 Proj4js 문자열 |
| EPSG:5179 (UTM-K) | X | `proj4.defs()` 필요 | epsg.io의 Proj4js 문자열 |

등록을 빠뜨려도 에러 없이 조용히 잘못된 값을 반환하는 경우가 있어서, 지역 좌표계를 다룰 때는 콘솔에 좌표 범위를 한 번 찍어 확인하는 습관이 필요하다.

<img src="/assets/images/posts/2026-08-20-proj4js-coordinate-transform-1.svg" alt="proj4js가 EPSG:4326·5186 입력 좌표를 defs 등록과 forward/inverse 호출을 거쳐 EPSG:3857·4326 출력으로 변환해 지도 라이브러리에 전달하는 흐름도" style="width:100%;">

## 핵심 개념 2: forward와 inverse, 그리고 축 순서

proj4js의 변환 API는 `forward`(정방향, 대개 도→미터)와 `inverse`(역방향, 미터→도) 두 방향으로 나뉜다. 입력·출력 모두 **[x, y]** 순서, 즉 위경도 좌표계에서는 [경도, 위도] 순서를 쓴다. 지도 라이브러리 API가 [위도, 경도]를 요구하는 경우가 섞여 있어서, 변환 직후 순서를 다시 바꿔야 하는 실수가 흔하다.

## 예제 1: 지역 좌표계 등록하고 변환하기 (JavaScript)

```javascript
import proj4 from "proj4";

// EPSG:5186(한국 중부원점)은 내장되어 있지 않으므로 직접 등록
proj4.defs(
  "EPSG:5186",
  "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=600000 " +
  "+ellps=GRS80 +units=m +no_defs"
);

// 공공데이터 API가 내려준 5186 좌표를 4326(위경도)으로 변환
const [lon, lat] = proj4("EPSG:5186", "EPSG:4326", [200500.12, 550300.45]);
console.log(lon, lat); // [경도, 위도] 순서로 반환됨

// 같은 Converter를 재사용하면 반복 변환 시 성능이 더 좋다
const converter = proj4("EPSG:5186", "EPSG:4326");
const points = rawList.map((p) => converter.forward([p.x, p.y]));
```

매 호출마다 `proj4(from, to)`를 새로 만들지 않고, 변환기 객체를 한 번 만들어 재사용하면 대량의 좌표를 반복 변환할 때 오버헤드를 줄일 수 있다.

## 예제 2: OpenLayers와 연동하기 (JavaScript)

OpenLayers는 proj4js가 등록해둔 좌표계 정의를 그대로 가져다 쓸 수 있는 연동 함수를 제공한다. `register()`를 호출해두면 이후 OpenLayers 내부의 `transform()`, 뷰(View)의 `projection` 옵션에서 `"EPSG:5186"` 문자열을 바로 쓸 수 있다.

```javascript
import proj4 from "proj4";
import { register } from "ol/proj/proj4";
import { get as getProjection, transform } from "ol/proj";

proj4.defs("EPSG:5186", "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 " +
  "+x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs");
register(proj4); // proj4 정의를 OpenLayers 좌표계 레지스트리에 반영

const coord3857 = transform([200500.12, 550300.45], "EPSG:5186", "EPSG:3857");
// 이제 지도의 addFeature 등에서 3857 좌표로 바로 사용 가능
```

`register(proj4)`를 호출하지 않으면 OpenLayers는 `"EPSG:5186"`이라는 문자열 자체를 인식하지 못해 별도의 알 수 없는 투영이라는 에러를 낸다.

## 실무 포인트

- **defs 등록은 앱 진입점에서 한 번만** 수행한다. 컴포넌트마다 반복 등록하면 마지막 등록값으로 덮어써지는 문제가 생길 수 있다.
- **변환기(converter) 재사용**: 대량 좌표(포인트클라우드, 대용량 GeoJSON)를 변환할 때는 `proj4(from, to)`로 만든 객체를 캐싱해서 재사용한다.
- **축 순서 검증**: 변환 직후 좌표 하나를 콘솔에 찍어, 국내 좌표라면 경도가 124~132, 위도가 33~43 범위인지부터 눈으로 확인한다.
- **정의 문자열 출처**: `+proj=...` 파라미터를 직접 손으로 작성하지 말고 epsg.io 같은 공신력 있는 출처에서 제공하는 Proj4js 문자열을 그대로 복사해 쓴다.

## 3줄 요약

- proj4js는 EPSG:4326·3857 같은 흔한 좌표계는 내장 지원하지만, 국내 지역 좌표계는 `proj4.defs()`로 직접 등록해야 한다.
- `forward`/`inverse`, 그리고 `proj4(from, to)` 변환기 재사용 패턴을 알면 대량 좌표 변환도 효율적으로 처리할 수 있다.
- OpenLayers 등 지도 라이브러리와 연동할 때는 `register(proj4)`로 정의를 공유해야 문자열 좌표계 코드를 바로 쓸 수 있다.

## 참고 자료

- [proj4js GitHub](https://github.com/proj4js/proj4js)
- [OpenLayers — ol/proj/proj4 문서](https://openlayers.org/en/latest/apidoc/module-ol_proj_proj4.html)
- [EPSG.io — 좌표계 정의 검색](https://epsg.io/)
