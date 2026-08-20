---
layout: single
title: "deck.gl 시작하기 — 대용량 데이터를 지도에 그리는 첫걸음"
date: 2026-09-06 12:20:00 +0530
categories: gis
tags: ["deckgl", "webgl", "데이터시각화", "gis입문", "웹지도"]
toc: true
toc_sticky: true
excerpt: "수십만 개의 점도 부드럽게 그리는 WebGL 기반 지도 시각화 라이브러리 deck.gl의 기본 개념과 첫 레이어 만들기를 정리했다."
---

## 마커 라이브러리로는 안 되는 규모

Leaflet의 마커로 점 수십만 개를 그리면 브라우저가 버틴다. 이건 각 마커가 DOM 요소이기 때문이다. **deck.gl**은 접근이 다르다. GPU(WebGL)를 직접 활용해 수십만~수백만 개의 점·선·면을 한 번에 렌더링한다. 대용량 위치 데이터 시각화가 필요할 때 쓰는 라이브러리다.

<img src="/assets/images/posts/2026-09-06-deckgl-getting-started-1.svg" alt="deck.gl이 데이터를 여러 레이어로 나누고 GPU(WebGL)로 대량의 점을 한 번에 렌더링해 지도 위에 겹쳐 표시하는 구조를 보여주는 다이어그램" style="width:100%;">

## deck.gl의 핵심: 레이어

deck.gl은 데이터를 **레이어(Layer)** 단위로 그린다. 데이터 종류와 표현 방식에 따라 다양한 레이어 타입이 준비되어 있다.

| 레이어 | 용도 |
|---|---|
| ScatterplotLayer | 점(포인트) 대량 표시 |
| ArcLayer | 두 지점을 잇는 곡선(이동 흐름 등) |
| HexagonLayer | 육각형 격자로 밀집도 집계 |
| GeoJsonLayer | GeoJSON 도형 렌더링 |

## 코드 예제: 포인트 레이어

```javascript
import { Deck } from '@deck.gl/core';
import { ScatterplotLayer } from '@deck.gl/layers';

const deck = new Deck({
  initialViewState: { longitude: 126.978, latitude: 37.5665, zoom: 11 },
  controller: true,
  layers: [
    new ScatterplotLayer({
      data: points, // 수십만 개의 { position: [경도, 위도] }
      getPosition: d => d.position,
      getRadius: 30,
      getFillColor: [255, 80, 80],
    }),
  ],
});
```

`data`에 대량의 배열을 넣고, `getPosition`으로 각 데이터의 위치를 알려주면 deck.gl이 GPU로 한꺼번에 그린다. 데이터가 수십만 개여도 부드럽게 렌더링된다.

## 실무 포인트

- **deck.gl은 지도 배경을 직접 그리지 않는다.** deck.gl은 데이터 시각화 레이어를 담당하고, 배경 지도는 MapLibre·Mapbox 같은 지도 라이브러리와 함께 겹쳐 쓰는 것이 일반적이다.
- **데이터 형식을 deck.gl이 좋아하는 형태로 맞추면 성능이 좋아진다.** 특히 대용량일 때는 좌표를 평범한 객체 배열보다 타입 배열(binary) 형태로 넘기면 GPU로 올리는 속도가 크게 빨라진다.
- **모든 지도에 deck.gl이 필요한 것은 아니다.** 마커 몇 개나 수천 개 수준이면 Leaflet·MapLibre로 충분하다. deck.gl은 "일반 방식으로는 감당 안 되는 대용량"일 때 진가를 발휘한다.

## 마무리 요약

- deck.gl은 GPU(WebGL)로 수십만~수백만 개의 데이터를 부드럽게 그리는 대용량 시각화 라이브러리다.
- 데이터를 레이어 단위로 그리며, ScatterplotLayer·ArcLayer·HexagonLayer 등 다양한 레이어 타입이 있다.
- 배경 지도는 MapLibre 등과 함께 쓰고, 대용량이 아니면 굳이 deck.gl을 쓸 필요는 없다.

## 참고 자료

- [deck.gl 공식 문서](https://deck.gl/docs)
- [deck.gl 레이어 카탈로그](https://deck.gl/docs/api-reference/layers)
