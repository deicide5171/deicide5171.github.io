---
layout: single
title: "MapLibre GL JS CustomLayerInterface 딥다이브 — 지도 위에 직접 WebGL을 그리는 법"
date: 2026-09-27 12:20:00 +0530
categories: gis
tags: ["MapLibre", "CustomLayerInterface", "WebGL", "deckgl", "지도렌더링"]
toc: true
toc_sticky: true
excerpt: "MapLibre GL JS의 기본 레이어 타입으로 표현하기 어려운 커스텀 시각화를 만들려면 결국 CustomLayerInterface로 WebGL 컨텍스트에 직접 접근해야 한다. onAdd/render/onRemove 생명주기와 GL 상태 공유의 함정을 정리했다."
---

## 왜 CustomLayerInterface가 필요한가

MapLibre GL JS는 fill, line, symbol, heatmap 같은 내장 레이어 타입으로 대부분의 지도 시각화를 커버하지만, 커스텀 셰이더 효과나 대량의 포인트를 실시간으로 애니메이션해야 하는 요구사항 앞에서는 한계에 부딪힌다. deck.gl의 화려한 3D 시각화, 실시간 흐름장 애니메이션, 커스텀 파티클 효과 같은 것들은 표준 스타일 스펙으로 표현할 수 없다. 이럴 때 쓰는 것이 `CustomLayerInterface`로, MapLibre의 렌더링 파이프라인 한가운데에 자신만의 WebGL 렌더링 코드를 끼워 넣을 수 있게 해주는 저수준 확장점이다. deck.gl의 `MapboxOverlay`도 내부적으로는 바로 이 인터페이스를 구현해 MapLibre/Mapbox와 통합된다.

## 핵심 개념 1 — 렌더링 파이프라인 속 위치와 생명주기

CustomLayerInterface를 구현한 레이어는 일반 스타일 레이어와 동일하게 레이어 순서(z-order)에 참여한다. `map.addLayer(customLayer, beforeLayerId)`로 추가하면, 지정한 위치의 다른 레이어들 사이에 정확히 끼어들어 매 프레임 자신의 렌더링 코드가 호출된다. 생명주기는 세 메서드로 구성된다. `onAdd(map, gl)`는 레이어가 지도에 추가될 때 한 번 호출되며 여기서 WebGL 버퍼, 셰이더 프로그램, 텍스처를 초기화한다. `render(gl, matrix)`는 매 프레임 호출되는 핵심으로, MapLibre가 계산한 현재 카메라의 투영×모델뷰 행렬(`matrix`)을 인자로 받아 이를 자신의 셰이더 유니폼에 넣어 좌표를 지도와 정확히 일치시킨다. `onRemove(map, gl)`는 레이어 제거 시 버퍼와 텍스처를 해제해 메모리 누수를 막는다.

## 핵심 개념 2 — 같은 GL 컨텍스트를 공유하는 함정

가장 중요하고 자주 간과되는 사실은, 커스텀 레이어가 **MapLibre 본체와 동일한 WebGL 컨텍스트를 공유**한다는 점이다. 별도의 캔버스나 독립된 GL 상태가 아니라, 같은 `gl` 객체 안에서 blend 모드, depth test, 활성 텍스처 유닛 같은 전역 GL 상태를 이어받는다. 즉 `render()` 안에서 `gl.enable(gl.BLEND)`나 `gl.depthMask(false)` 같은 상태를 바꿔놓고 원래대로 복원하지 않으면, 바로 다음에 그려지는 MapLibre의 기본 레이어가 잘못된 상태에서 렌더링되어 지도가 깨지거나 반투명 처리가 엉망이 되는 버그로 이어진다.

| 메서드 | 호출 시점 | 주요 작업 |
|---|---|---|
| `onAdd(map, gl)` | 레이어 추가 시 1회 | 셰이더 컴파일, 버퍼 생성, 텍스처 로드 |
| `render(gl, matrix)` | 매 프레임 | 유니폼 설정, draw call, GL 상태 복원 |
| `onRemove(map, gl)` | 레이어 제거 시 1회 | 버퍼/텍스처/프로그램 삭제 |

## 코드 예제 — 최소 CustomLayerInterface 구현

```javascript
const customLayer = {
  id: 'highlight-triangle',
  type: 'custom',
  renderingMode: '3d',

  onAdd(map, gl) {
    const vertexSrc = `
      uniform mat4 u_matrix;
      attribute vec2 a_pos;
      void main() {
        gl_Position = u_matrix * vec4(a_pos, 0.0, 1.0);
      }`;
    const fragmentSrc = `
      void main() { gl_FragColor = vec4(1.0, 0.0, 0.0, 0.5); }`;

    this.program = createProgram(gl, vertexSrc, fragmentSrc);
    this.buffer = gl.createBuffer();
    // 좌표는 미리 경위도 -> 머케이터 좌표로 변환해둔다
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.bufferData(gl.ARRAY_BUFFER, mercatorCoords, gl.STATIC_DRAW);
  },

  render(gl, matrix) {
    gl.useProgram(this.program);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.program, 'u_matrix'), false, matrix);

    // 블렌딩 상태는 반드시 이 레이어 안에서만 켜고, 이후 복원해야 한다
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  },
};

map.on('load', () => map.addLayer(customLayer));
```

<img src="/assets/images/posts/2026-09-27-maplibre-customlayerinterface-webgl-webgpu-rendering-1.svg" alt="MapLibre 프레임 렌더링 파이프라인 속 CustomLayerInterface 생명주기 다이어그램" style="width:100%;">

## 실무 포인트

- **좌표계 변환을 잊지 마라.** MapLibre 내부 좌표계는 구면 머케이터를 정규화한 값이므로, 경위도 좌표를 직접 셰이더에 넣으면 안 되고 `mercatorZfromAltitude`, `MercatorCoordinate.fromLngLat` 같은 유틸리티로 먼저 변환해야 한다.
- **`renderingMode: '3d'`를 설정해야 depth buffer가 유지된다.** 기본값(`2d`)에서는 매 프레임 depth buffer가 지워지므로, 3D 오브젝트가 지형이나 다른 3D 레이어와 올바르게 가려지려면 이 옵션이 필요하다.
- **성능이 중요하면 deck.gl 통합을 먼저 검토하라.** 직접 WebGL을 다루는 대신 deck.gl의 `MapboxOverlay`를 CustomLayer로 등록하면, 대량 데이터 렌더링에 최적화된 레이어(ScatterplotLayer, PathLayer 등)를 그대로 재사용하면서 낮은 수준의 셰이더 관리 부담을 덜 수 있다.

## 마무리 요약

- CustomLayerInterface는 MapLibre 렌더링 파이프라인에 자신만의 WebGL 코드를 끼워 넣는 저수준 확장점으로, onAdd/render/onRemove 세 생명주기로 구성된다.
- 커스텀 레이어는 MapLibre 본체와 같은 GL 컨텍스트를 공유하므로, 변경한 GL 상태를 반드시 복원해야 다른 레이어 렌더링이 깨지지 않는다.
- 좌표계 변환과 depth buffer 옵션을 놓치기 쉬운 함정이며, 대량 데이터 시각화는 deck.gl 같은 상위 레이어 통합을 우선 고려하는 것이 효율적이다.

## 참고 자료

- [MapLibre GL JS 공식 문서 — CustomLayerInterface](https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/)
- [deck.gl 공식 문서 — Mapbox/MapLibre 통합](https://deck.gl/docs/api-reference/mapbox/overview)
