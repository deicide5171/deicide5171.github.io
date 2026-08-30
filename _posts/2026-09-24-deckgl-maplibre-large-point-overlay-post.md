---
layout: single
title: "deck.gl과 MapLibre GL JS 통합 — 대용량 포인트 데이터 오버레이 렌더링"
date: 2026-09-24 12:20:00 +0530
categories: gis
tags: ["deckgl", "MapLibre", "MapboxOverlay", "대용량렌더링", "GPU인스턴싱"]
toc: true
toc_sticky: true
excerpt: "수십만~수백만 건의 포인트 데이터를 MapLibre GL JS 지도 위에 얹으려 할 때 마커나 GeoJSON 레이어로는 브라우저가 버벅이는 이유를 짚고, deck.gl을 MapboxOverlay로 인터리브 통합해 GPU 인스턴싱으로 렌더링하는 방법을 정리했다."
---

## 왜 지금 deck.gl 통합을 알아야 하는가

수천 건 정도의 포인트 데이터는 MapLibre GL JS의 기본 마커나 GeoJSON 기반 `circle` 레이어로도 충분히 매끄럽게 렌더링된다. 문제는 데이터가 수십만~수백만 건 규모(IoT 센서, 차량 위치, 위성 관측점 등)로 커지는 순간이다. 마커는 DOM 엘리먼트 방식이라 개수가 늘어나면 브라우저 레이아웃·페인트 비용이 기하급수적으로 늘고, GeoJSON 벡터 레이어도 내부적으로 매 프레임 지오메트리를 처리하는 방식이라 특정 규모를 넘으면 프레임 드롭이 눈에 띄게 발생한다. deck.gl은 WebGL 인스턴싱을 이용해 수백만 개의 포인트를 단 한 번의 draw call로 렌더링하도록 설계된 라이브러리이며, MapLibre와 결합하면 지도 기능은 MapLibre에, 대용량 데이터 시각화는 deck.gl에 맡기는 역할 분담이 가능해진다.

## 핵심 개념 1 — 별도 캔버스 오버레이의 함정과 MapboxOverlay 인터리브 모드

deck.gl을 MapLibre와 함께 쓰는 가장 단순한 방법은 deck.gl 캔버스를 지도 캔버스 위에 `position: absolute`로 얹는 것이다. 이 방식은 구현은 쉽지만 두 캔버스가 서로 다른 렌더 루프에서 독립적으로 그려지기 때문에, 사용자가 지도를 빠르게 드래그하거나 확대하면 두 레이어 사이에 미세한 프레임 지연이 생겨 포인트가 지도 위에서 살짝 미끄러지는 것처럼 보이는 어긋남이 발생한다. `MapboxOverlay`(deck.gl이 MapLibre GL JS와도 호환되도록 제공하는 컨트롤)를 인터리브(interleaved) 모드로 쓰면, deck.gl 레이어가 MapLibre의 커스텀 레이어 메커니즘을 통해 같은 WebGL 컨텍스트와 같은 프레임 안에서 다른 지도 레이어들과 순서대로 합성되므로 이 어긋남이 사라진다.

<img src="/assets/images/posts/2026-09-24-deckgl-maplibre-large-point-overlay-1.svg" alt="별도 캔버스로 deck.gl을 오버레이했을 때 두 렌더 루프가 어긋나는 문제와, MapboxOverlay 인터리브 모드로 같은 WebGL 컨텍스트에서 배경 타일-deck.gl 포인트 레이어-레이블을 순서대로 합성하는 구조, 그리고 GPU 인스턴싱으로 수백만 포인트를 한 번의 draw call로 처리하는 흐름을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — GPU 인스턴싱이 수백만 포인트를 감당하는 원리

deck.gl의 `ScatterplotLayer`나 `HeatmapLayer`는 각 포인트를 개별 도형으로 CPU에서 하나씩 그리지 않는다. 대신 포인트들의 위치·색상·반지름 같은 속성을 GPU 버퍼에 통째로 업로드하고, WebGL의 인스턴싱(instanced rendering) 기능을 이용해 동일한 기본 도형(원, 사각형)을 그 버퍼의 값만큼 반복해서 그리는 작업을 GPU에 한 번에 위임한다. CPU는 매 프레임 포인트 하나하나를 순회하지 않고 카메라 변환 행렬 정도만 갱신하면 되므로, 포인트 개수가 늘어나도 CPU 병목 없이 GPU 처리량 한계까지 확장할 수 있다.

| 방식 | 포인트 처리 단위 | 대략적인 감당 규모 | 특징 |
|---|---|---|---|
| MapLibre 마커(DOM) | 요소 하나당 DOM 노드 | 수백~수천 개 | 상호작용 구현 쉬움, 개수에 취약 |
| MapLibre GeoJSON 레이어 | 벡터 지오메트리 | 수만 개 | 벡터 스타일링과 통합 쉬움 |
| deck.gl (GPU 인스턴싱) | GPU 버퍼 일괄 처리 | 수십만~수백만 개 | 대규모에 강함, 초기 설정 비용 있음 |

## 예제 — MapboxOverlay로 deck.gl ScatterplotLayer 인터리브

```javascript
import { Map } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer } from '@deck.gl/layers';

const map = new Map({
  container: 'map',
  style: 'https://api.maptiler.com/maps/streets-v2/style.json?key=YOUR_KEY',
  center: [126.978, 37.5665],
  zoom: 10,
});

const overlay = new MapboxOverlay({
  interleaved: true, // 지도 레이어와 같은 컨텍스트/프레임에서 합성
  layers: [
    new ScatterplotLayer({
      id: 'sensor-points',
      data: sensorPoints, // 수십만 건의 { longitude, latitude, value } 배열
      getPosition: (d) => [d.longitude, d.latitude],
      getRadius: 30,
      getFillColor: (d) => (d.value > 80 ? [220, 50, 50] : [50, 130, 220]),
      radiusMinPixels: 2,
    }),
  ],
});

map.on('load', () => map.addControl(overlay));
```

## 실무 포인트

- **`interleaved: true` 설정을 잊지 마라.** 기본값(오버레이 모드)으로 두면 앞서 설명한 별도 캔버스 방식과 동일하게 동작해, deck.gl을 쓰는 이점 중 하나인 정확한 합성을 놓치게 된다.
- **데이터 갱신 빈도가 높다면 `updateTriggers`를 명확히 지정하라.** deck.gl은 데이터 배열 참조가 바뀌지 않으면 GPU 버퍼를 재생성하지 않으므로, 실시간 데이터를 다룰 때는 어떤 속성이 바뀌었는지 명시해야 불필요한 전체 재계산을 피할 수 있다.
- **초기 로딩 시 데이터 자체를 서버에서 이미 다운샘플링하거나 타일링하는 것도 함께 고려하라.** GPU 인스턴싱이 렌더링 병목은 해결해주지만, 수백만 건의 원본 데이터를 매번 네트워크로 통째로 내려받는 것 자체는 별도의 최적화 대상이다.

## 마무리 요약

- 마커나 GeoJSON 레이어는 포인트 수가 커지면 DOM·지오메트리 처리 비용 때문에 성능 한계에 부딪히며, deck.gl은 GPU 인스턴싱으로 이 한계를 넘어선다.
- MapboxOverlay를 인터리브 모드로 쓰면 deck.gl 레이어가 MapLibre의 다른 레이어와 같은 프레임·컨텍스트에서 합성돼, 별도 캔버스 오버레이 방식의 어긋남 문제가 사라진다.
- GPU 인스턴싱은 렌더링 병목을 해결하지만 데이터 전송·업데이트 트리거 관리는 별도로 신경 써야 실제 프로덕션에서 안정적인 성능을 낸다.

## 참고 자료

- [deck.gl - MapboxOverlay](https://deck.gl/docs/api-reference/mapbox/mapbox-overlay)
- [deck.gl - Using with MapLibre](https://deck.gl/docs/get-started/using-with-map#using-with-maplibre-gl)
