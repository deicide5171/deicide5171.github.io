---
layout: single
title: "OpenLayers도 이제 GPU로 그린다 — WebGL 벡터 타일 렌더러 스타일링 실전"
date: 2026-08-26 12:20:00 +0530
categories: gis
tags: ["gis", "openlayers", "webgl", "vectortile", "style-expressions", "webmap"]
toc: true
toc_sticky: true
excerpt: "OpenLayers의 Canvas2D 벡터 렌더러 대신 WebGL 벡터 타일 레이어를 쓰면 대용량 피처도 부드럽게 그릴 수 있다. 스타일 표현식 기반 설정법과 기존 스타일 함수와의 차이를 정리한다."
---

OpenLayers로 벡터 타일을 그릴 때 전통적인 방식은 각 피처마다 JS 스타일 함수를 호출해 Canvas2D에 그리는 것이다. 이 방식은 유연하지만, 피처 수가 수만 개를 넘어가면 매 프레임 스타일 함수 호출 비용이 병목이 된다. 줌·팬을 할 때마다 화면에 보이는 모든 피처의 스타일을 다시 계산해야 하기 때문이다. OpenLayers는 이 문제를 해결하기 위해 `ol/layer/WebGLVectorTile` 계열의 WebGL 기반 벡터 타일 레이어를 제공하며, 여기서는 JS 함수 대신 **스타일 표현식(style expression)**이라는 JSON 기반 선언적 문법으로 스타일을 정의한다.

이 변화는 단순한 성능 최적화 이상의 의미가 있다. 표현식은 GPU 셰이더로 컴파일되므로, 피처 하나하나에 대해 JS 콜백을 호출하는 대신 GPU가 병렬로 스타일을 계산한다. 대신 임의의 JS 로직(예: 복잡한 조건 분기, 외부 상태 참조)은 표현식 문법 안에서 표현 가능한 범위로 제한된다. 이 글에서는 OpenLayers WebGL 벡터 타일 레이어의 스타일 표현식 문법과, 기존 Canvas2D 스타일 함수에서 마이그레이션할 때 주의할 점을 정리한다.

## 핵심 개념 1: 스타일 함수 대 스타일 표현식

기존 OpenLayers 스타일 함수는 `(feature, resolution) => Style` 형태로, 피처 속성을 자유롭게 읽고 임의의 JS 로직으로 `ol.style.Style` 객체를 반환했다. WebGL 벡터 타일 레이어는 이 대신 `['case', ...]`, `['get', 'property']`, `['interpolate', ...]` 같은 Mapbox Style Spec과 유사한 표현식 배열을 받는다.

| 구분 | Canvas2D 스타일 함수 | WebGL 스타일 표현식 |
|---|---|---|
| 문법 | 임의의 JS 함수 | JSON 표현식 배열 (선언적) |
| 실행 위치 | CPU, 피처마다 JS 콜백 호출 | GPU 셰이더로 컴파일 |
| 대용량 렌더링 | 수만 피처에서 프레임드랍 발생 가능 | 수십만 피처도 부드럽게 처리 |
| 외부 상태 참조 | 자유로움(클로저로 캡처) | 제한적(표현식 문법 내에서만) |
| 애니메이션(줌 보간) | 수동으로 resolution마다 재계산 | `interpolate`로 선언적 처리 |

## 핵심 개념 2: 표현식으로 줌 레벨별 스타일 보간하기

WebGL 스타일의 강력한 점은 `interpolate` 표현식으로 줌 레벨에 따른 연속적인 스타일 변화를 선언적으로 표현할 수 있다는 것이다. 기존 Canvas2D 방식에서는 `resolution` 값을 보고 조건문으로 스타일을 분기해야 했지만, 표현식에서는 구간별 값을 지정하면 중간 줌 레벨은 자동으로 보간된다.

<img src="/assets/images/posts/2026-08-26-openlayers-webgl-vectortile-styling-1.svg" alt="OpenLayers Canvas2D 스타일 함수와 WebGL 스타일 표현식의 렌더링 파이프라인 비교, 줌 레벨별 interpolate 보간 흐름" style="width:100%;">

## 예제: WebGL 벡터 타일 레이어 스타일 표현식

```javascript
import WebGLVectorTileLayer from 'ol/layer/WebGLVectorTile.js';
import VectorTileSource from 'ol/source/VectorTile.js';
import MVT from 'ol/format/MVT.js';

const roadsLayer = new WebGLVectorTileLayer({
  source: new VectorTileSource({
    format: new MVT(),
    url: 'https://example.com/tiles/{z}/{x}/{y}.pbf',
  }),
  style: {
    // 도로 등급(class 속성)에 따라 선 색상 분기
    'stroke-color': [
      'match', ['get', 'class'],
      'motorway', '#e15759',
      'primary', '#f28e2b',
      'residential', '#bab0ac',
      /* 기본값 */ '#dddddd',
    ],
    // 줌 레벨 8~16 구간에서 선 두께를 1px에서 6px로 선형 보간
    'stroke-width': [
      'interpolate', ['linear'], ['zoom'],
      8, 1,
      16, 6,
    ],
    // 특정 줌 이하에서는 residential 도로 자체를 숨김
    filter: ['any',
      ['!=', ['get', 'class'], 'residential'],
      ['>=', ['zoom'], 13],
    ],
  },
});
```

`match`와 `interpolate`는 Mapbox/MapLibre Style Spec의 표현식 문법과 상당히 유사하다. OpenLayers 팀이 의도적으로 문법 호환성을 맞춘 부분이라, 다른 라이브러리의 스타일 표현식 경험이 있다면 습득 곡선이 완만하다.

## 실무 포인트

- **속성 조인이 필요한 스타일은 표현식만으로 부족할 수 있다**: 외부 API에서 실시간으로 받아온 상태(예: 실시간 혼잡도)를 반영해야 한다면, 벡터 타일 자체에 그 속성을 미리 넣거나, `featureclass`를 활용한 별도 속성 갱신 파이프라인이 필요하다. 표현식은 타일에 이미 들어있는 속성만 참조할 수 있다.
- **디버깅은 표현식을 잘게 쪼개서 확인한다**: 표현식이 복잡해지면 어느 조건에서 예상과 다른 스타일이 나오는지 추적하기 어렵다. 개발 중에는 `filter`를 단순화해 특정 조건의 피처만 남기고 색상을 고정해 확인하는 것이 효율적이다.
- **모든 브라우저가 WebGL2를 지원하는 것은 아니다**: 오래된 기기나 임베디드 웹뷰 환경에서는 WebGL 컨텍스트 생성이 실패할 수 있다. 폴백으로 Canvas2D 벡터 레이어를 함께 준비하거나, 최소 사양을 명확히 안내해야 한다.

## 3줄 요약

- OpenLayers WebGL 벡터 타일 레이어는 JS 스타일 함수 대신 GPU 셰이더로 컴파일되는 선언적 표현식을 써서 대용량 피처를 부드럽게 렌더링한다.
- `match`, `interpolate` 같은 표현식은 Mapbox/MapLibre Style Spec과 문법이 유사해 학습 곡선이 완만하다.
- 표현식은 타일에 이미 존재하는 속성만 참조할 수 있으므로, 실시간 외부 상태 반영은 별도의 속성 갱신 설계가 필요하다.

## 참고 자료

- [OpenLayers 공식 문서: ol/layer/WebGLVectorTile](https://openlayers.org/en/latest/apidoc/module-ol_layer_WebGLVectorTile.html)
- [OpenLayers 공식 문서: Style Expressions](https://openlayers.org/en/latest/apidoc/module-ol_expr_expression.html)
- [OpenLayers 예제: WebGL Vector Tile Layer](https://openlayers.org/en/latest/examples/webgl-vector-tile-layer.html)
