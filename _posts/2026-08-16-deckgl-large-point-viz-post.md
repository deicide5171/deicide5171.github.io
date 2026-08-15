---
layout: single
title: "지도 위 수백만 포인트, deck.gl은 어떻게 끊김 없이 그릴까"
date: 2026-08-16 13:20:00 +0530
categories: gis
tags: ["deckgl", "webgl", "gis", "react", "data-visualization"]
toc: true
toc_sticky: true
excerpt: "IoT 센서, 위치 로그, 선박 AIS처럼 포인트 수가 수십만~수백만 단위로 커지는 데이터를 웹 지도에서 끊김 없이 그리려면 왜 DOM 마커 방식이 한계에 부딪히고, deck.gl의 GPU 레이어 구조가 어떻게 이를 해결하는지 정리한다."
---

## 왜 지금 대량 포인트 시각화인가

위치 기반 데이터의 크기는 계속 커지고 있다. IoT 센서 로그, 차량·선박(AIS) 위치 이력, 앱 사용자 행동 로그, 위성 관측 포인트 — 이런 데이터를 지도 위에 그대로 뿌리면 포인트 개수가 수만 개만 넘어가도 화면이 버벅이기 시작한다. Leaflet이나 지도 API의 기본 마커는 포인트 하나마다 DOM 엘리먼트를 만드는 방식이라, 브라우저의 레이아웃·페인트 비용이 포인트 수에 비례해 늘어나기 때문이다.

**deck.gl**은 우버(Uber)가 만들고 현재 OpenJS Foundation 산하 vis.gl 프로젝트로 관리되는 오픈소스 시각화 프레임워크로, WebGL(WebGL2) 기반 GPU 렌더링으로 이 문제에 접근한다. 지도 자체를 그리지 않고 Mapbox GL, MapLibre, Google Maps 같은 기존 베이스맵 위에 별도의 WebGL 캔버스를 겹쳐서, 대량의 데이터 포인트만 GPU로 빠르게 그리는 역할에 집중한다. React 생태계와의 결합도 자연스러워, 대시보드·분석 도구에 많이 쓰인다.

## 핵심 개념 1: 레이어 기반 아키텍처

deck.gl의 기본 단위는 **Layer**다. `ScatterplotLayer`(점), `LineLayer`(선), `HeatmapLayer`(밀도), `HexagonLayer`/`GridLayer`(공간 집계) 등 목적별 레이어가 준비되어 있고, 각 레이어는 데이터 배열과 **accessor 함수**(`getPosition`, `getFillColor`, `getRadius` 등)를 받아 "각 데이터 항목을 화면에서 어떻게 표현할지"를 선언적으로 정의한다. 여러 레이어를 배열로 쌓으면 그대로 합성되어 그려진다.

<img src="/assets/images/posts/2026-08-16-deckgl-large-point-viz-1.svg" alt="deck.gl 레이어 파이프라인 - 원본 데이터가 Layer 정의를 거쳐 GPU 버퍼로 업로드되고 GPU 인스턴싱으로 렌더링되어 베이스맵과 합성되는 흐름" style="width:100%;">

## 핵심 개념 2: 왜 수백만 개가 가능한가

핵심은 accessor로 정의된 값들이 매 프레임 CPU에서 다시 계산되는 게 아니라, **한 번 Typed Array(Float32Array 등)로 GPU 버퍼에 업로드된 뒤 GPU 인스턴싱**으로 그려진다는 점이다. 위경도를 화면 좌표로 바꾸는 투영 변환(Web Mercator)조차 정점 셰이더 안에서 처리되므로, 포인트 개수가 늘어도 CPU가 반복적으로 해야 할 일은 늘지 않고 GPU가 병렬로 나눠 처리한다.

| 구분 | DOM 마커 / Canvas 2D | deck.gl (GPU 레이어) |
|---|---|---|
| 렌더링 단위 | 포인트마다 개별 DOM/draw 호출 | 동일 지오메트리를 GPU 인스턴싱으로 일괄 처리 |
| 좌표 변환 위치 | CPU (JS) | GPU (셰이더) |
| 데이터 갱신 비용 | 포인트 수에 비례해 증가 | 버퍼 재업로드 범위에 따라 결정 |
| 적합한 규모 | 수백~수천 개 | 대규모(수십만 단위 이상, 기기·데이터에 따라 상이) |
| 대표 레이어 | 지도 라이브러리 기본 마커 | ScatterplotLayer, HexagonLayer 등 |

집계가 필요할 만큼 포인트가 극단적으로 많을 때는 `HexagonLayer`나 `GridLayer`처럼 GPU에서 공간 집계를 먼저 수행하는 레이어를 쓰면 점을 하나하나 그리지 않고도 밀도 패턴을 표현할 수 있다.

## 예제: React에서 deck.gl로 포인트 레이어 그리기

```jsx
import { DeckGL } from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
import Map from 'react-map-gl/maplibre';

const INITIAL_VIEW_STATE = {
  longitude: 127.0, latitude: 37.5, zoom: 10,
};

function PointMap({ points }) {
  // points: [{ position: [lng, lat], value: number }, ...] 형태의 대용량 배열
  const layer = new ScatterplotLayer({
    id: 'points',
    data: points,
    getPosition: d => d.position,
    getFillColor: d => (d.value > 50 ? [220, 60, 60] : [40, 130, 220]),
    getRadius: 30,
    radiusMinPixels: 1,
    pickable: true,
  });

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW_STATE}
      controller
      layers={[layer]}
    >
      <Map mapStyle="https://demotiles.maplibre.org/style.json" />
    </DeckGL>
  );
}
```

`ScatterplotLayer`는 `data` 배열과 accessor만 넘기면 되고, 실제 GPU 버퍼 생성·업로드는 deck.gl 내부에서 처리한다. `radiusMinPixels`는 줌아웃 시 점이 너무 작아져 안 보이는 문제를 막아준다.

## 실무 포인트

- **`updateTriggers`로 불필요한 재계산을 막는다**: accessor 함수가 참조하는 값이 바뀔 때만 GPU 버퍼를 다시 만들도록 `updateTriggers`를 지정하지 않으면, 관련 없는 리렌더에도 매번 버퍼를 재생성해 성능이 떨어질 수 있다.
- **바이너리 데이터 포맷을 우선 고려한다**: 데이터가 매우 크다면 일반 JS 객체 배열보다 `{ length, attributes: { getPosition: { value: Float32Array, size: 2 } } }` 형태의 바이너리 포맷을 직접 넘기면 deck.gl 내부 변환 비용을 줄일 수 있다.
- **집계 레이어를 먼저 검토한다**: 개별 포인트를 다 구분해서 보여줄 필요가 없다면 `HexagonLayer` 같은 집계 레이어로 밀도를 표현하는 편이 시각적으로도, 성능면에서도 유리한 경우가 많다.
- **WebGL2 지원 여부와 기기 성능 편차를 감안한다**: 실제 처리 가능한 포인트 규모는 GPU 성능, 브라우저, 동시에 켠 레이어 수에 따라 크게 달라지므로 목표 환경에서 직접 프로파일링해보는 것이 안전하다.

## 3줄 요약

- deck.gl은 베이스맵 위에 별도 WebGL 캔버스를 겹쳐, 대량 포인트 렌더링을 GPU 인스턴싱으로 처리하는 시각화 프레임워크다.
- 좌표 변환까지 GPU 셰이더에서 수행되기 때문에 DOM 마커 방식과 달리 포인트 수가 늘어도 CPU 부담이 비례해서 커지지 않는다.
- 실무에서는 `updateTriggers`, 바이너리 데이터 포맷, 집계 레이어(HexagonLayer 등) 활용 여부를 데이터 규모에 맞춰 판단해야 한다.

## 참고 자료

- [deck.gl 공식 문서](https://deck.gl/docs)
- [deck.gl — ScatterplotLayer](https://deck.gl/docs/api-reference/layers/scatterplot-layer)
- [vis.gl (OpenJS Foundation)](https://www.openjsf.org/projects/)
