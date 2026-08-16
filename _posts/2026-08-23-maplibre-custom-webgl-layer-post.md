---
layout: single
title: "MapLibre 커스텀 레이어 — 지도 렌더 루프에 내 WebGL 코드 끼워 넣기"
date: 2026-08-23 12:20:00 +0530
categories: gis
tags: ["gis", "maplibre", "webgl", "custom-layer", "shader", "particle"]
toc: true
toc_sticky: true
excerpt: "GeoJSON 레이어로는 안 되는 파티클 애니메이션·커스텀 히트맵을, 별도 캔버스 없이 지도와 같은 WebGL 컨텍스트 안에서 직접 그리는 MapLibre 커스텀 레이어를 해부한다."
---

## 왜 커스텀 레이어인가

MapLibre GL JS에서 대부분의 시각화는 GeoJSON 소스에 `circle`, `heatmap`, `fill` 같은 스타일 레이어를 얹는 것으로 해결된다. 하지만 바람장을 따라 흐르는 파티클 애니메이션, 프레임마다 값이 바뀌는 수만 개의 센서 포인트, 셰이더로 직접 색을 계산하는 커스텀 히트맵처럼 **스타일 스펙의 표현력 밖에 있는 요구**가 나오는 순간 벽에 부딪힌다.

이때 흔한 우회책이 지도 위에 별도의 `<canvas>`를 겹쳐 놓고 `move` 이벤트마다 다시 그리는 방식인데, 지도와 오버레이가 서로 다른 렌더 루프를 돌기 때문에 드래그나 회전 중에 오버레이가 한두 프레임씩 미끄러지는(lag) 현상을 피하기 어렵다. MapLibre의 **커스텀 레이어(`type: 'custom'`)**는 이 문제를 근본적으로 다르게 푼다. 지도가 쓰는 **같은 WebGL 컨텍스트, 같은 프레임 안에서** 내 그리기 코드를 호출해 주기 때문에 어긋남 자체가 없고, 일반 레이어처럼 순서를 지정할 수 있어 "라벨 아래, 건물 위"에 그리는 것도 가능하다.

이전 글에서 deck.gl이 대량 포인트를 그리는 방식과 벡터 타일 렌더링 파이프라인을 다뤘다면, 이번에는 그 파이프라인에 **내 셰이더를 직접 끼워 넣는 인터페이스**를 본다.

## 핵심 개념 1: 생명주기 — onAdd, render, onRemove

커스텀 레이어는 `CustomLayerInterface`를 만족하는 객체를 `map.addLayer()`에 넘기면 된다. 핵심 메서드는 세 개다.

<img src="/assets/images/posts/2026-08-23-maplibre-custom-webgl-layer-1.svg" alt="MapLibre 커스텀 레이어의 프레임 렌더 순서, 생명주기(onAdd/render/onRemove), 좌표 변환 파이프라인 구조도" style="width:100%;">

- **`onAdd(map, gl)`** — 레이어가 지도에 추가될 때 1회 호출. 셰이더 컴파일, 버퍼 생성, 데이터 업로드 등 리소스 준비는 전부 여기서 한다.
- **`render(gl, matrix)`** — 매 프레임 호출. `matrix`는 메르카토르 월드 좌표를 클립 공간으로 보내는 투영 행렬이다. 여기서는 그리기만 한다.
- **`onRemove(map, gl)`** — 레이어 제거 시 호출. 버퍼·프로그램을 해제한다.

두 가지를 기억해야 한다. 첫째, MapLibre는 화면이 바뀔 때만 렌더링하는 **온디맨드 렌더러**라서, 지도가 가만히 있으면 `render()`도 호출되지 않는다. 파티클처럼 계속 움직여야 하는 레이어는 `render()` 안에서 `map.triggerRepaint()`를 호출해 다음 프레임을 예약해야 한다. 둘째, `renderingMode`를 `'3d'`로 지정하면 지도의 깊이 버퍼를 공유해 지형이나 3D 건물에 가려지는 표현이 가능하고, 기본값 `'2d'`는 깊이를 무시하고 위에 얹는다.

## 핵심 개념 2: 좌표 — 0~1 메르카토르 월드와 정밀도

커스텀 레이어에서 가장 먼저 헷갈리는 지점은 좌표계다. `render()`가 받는 행렬은 경위도가 아니라 **웹 메르카토르 월드 좌표(전 세계를 0~1 정사각형으로 눌러 담은 좌표)**를 입력으로 기대한다. 변환은 `maplibregl.MercatorCoordinate.fromLngLat()`이 해 준다. 즉 정점 데이터는 미리 0~1 좌표로 변환해 버퍼에 올려 두고, 셰이더에서 `u_matrix * vec4(a_pos, 0.0, 1.0)`만 곱하면 된다.

여기에 실무 함정이 하나 숨어 있다. 0~1 좌표를 `Float32Array`로 올리면 고배율 줌에서 32비트 부동소수점의 유효 자릿수가 부족해 **포인트가 부들부들 떨리는 지터(jitter)**가 생긴다. 도시 단위 이상으로 확대하는 서비스라면 기준점(anchor)을 하나 정해 상대 좌표로 버퍼를 채우고, 행렬 쪽에서 기준점 오프셋을 보정하는 방식으로 정밀도를 확보해야 한다. 또 하나, 글로브 투영이 도입된 최근 메이저 버전에서는 `render`의 두 번째 인자가 행렬 하나가 아니라 투영별 행렬을 담은 인자 객체로 바뀌었으므로, 사용 중인 버전의 `CustomLayerInterface` 문서를 먼저 확인하자.

## 어떤 방식을 골라야 하나

| 방식 | 적합한 경우 | 한계 |
|---|---|---|
| 스타일 레이어 (circle/heatmap 등) | 정적·준정적 데이터, 스펙 표현력 안의 요구 | 프레임 단위 애니메이션·커스텀 셰이더 불가 |
| deck.gl MapboxOverlay (interleaved) | 대량 데이터 + 검증된 레이어 카탈로그 활용 | 의존성 추가, 카탈로그 밖 표현은 결국 커스텀 |
| **MapLibre 커스텀 레이어** | 파티클·유체·커스텀 히트맵 등 셰이더 직접 제어 | WebGL 코드를 직접 관리, 진입 장벽 |
| 별도 캔버스 오버레이 | 지도와 느슨히 결합된 UI성 그래픽 | 이동·회전 시 프레임 어긋남, 레이어 순서 제어 불가 |

**언제 쓰지 말아야 하는가**도 분명하다. 스타일 레이어로 되는 것을 커스텀 레이어로 짜면 그때부터 셰이더·버퍼·상태 관리가 전부 우리 팀의 유지보수 부채가 된다. deck.gl의 기존 레이어로 충분하다면 그쪽이 낫다. 커스텀 레이어는 "셰이더를 직접 써야만 하는 표현"이 있을 때 꺼내는 카드다.

## 예제: 맥박처럼 뛰는 포인트 레이어

세 도시 위에서 크기가 고동치는 포인트를 그리는 완결 예제다. 그대로 붙여 넣어 동작을 확인할 수 있다.

```javascript
import maplibregl from 'maplibre-gl';

const pulsingLayer = {
  id: 'pulsing-points',
  type: 'custom',
  renderingMode: '2d',

  onAdd(map, gl) {
    this.map = map;
    const vs = `
      attribute vec2 a_pos;
      uniform mat4 u_matrix;
      uniform float u_time;
      void main() {
        gl_Position = u_matrix * vec4(a_pos, 0.0, 1.0);
        gl_PointSize = 18.0 + 8.0 * sin(u_time * 3.0);
      }`;
    const fs = `
      precision mediump float;
      void main() {
        float d = distance(gl_PointCoord, vec2(0.5));
        if (d > 0.5) discard;
        gl_FragColor = vec4(0.95, 0.25, 0.2, 1.0 - d * 1.6);
      }`;
    const compile = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return s;
    };
    this.program = gl.createProgram();
    gl.attachShader(this.program, compile(gl.VERTEX_SHADER, vs));
    gl.attachShader(this.program, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(this.program);
    this.aPos = gl.getAttribLocation(this.program, 'a_pos');
    this.uMatrix = gl.getUniformLocation(this.program, 'u_matrix');
    this.uTime = gl.getUniformLocation(this.program, 'u_time');

    // 경위도 → 0~1 메르카토르 월드 좌표로 변환해 1회 업로드
    const cities = [[126.978, 37.5665], [129.0756, 35.1796], [126.7052, 37.4563]];
    const data = new Float32Array(cities.flatMap(([lng, lat]) => {
      const m = maplibregl.MercatorCoordinate.fromLngLat({ lng, lat });
      return [m.x, m.y];
    }));
    this.buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.count = cities.length;
  },

  render(gl, matrix) {
    gl.useProgram(this.program);
    gl.uniformMatrix4fv(this.uMatrix, false, matrix);
    gl.uniform1f(this.uTime, performance.now() / 1000);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.enableVertexAttribArray(this.aPos);
    gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.POINTS, 0, this.count);
    this.map.triggerRepaint(); // 애니메이션: 다음 프레임 예약
  },

  onRemove(map, gl) {
    gl.deleteProgram(this.program);
    gl.deleteBuffer(this.buffer);
  }
};

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json',
  center: [127.5, 36.5],
  zoom: 6
});
map.on('load', () => map.addLayer(pulsingLayer));
```

## 실무 포인트와 흔한 함정

**안티패턴: `render()` 안에서 버퍼를 만들거나 데이터를 올리는 것.** 매 프레임 `createBuffer`/`bufferData`를 호출하면 프레임마다 CPU→GPU 업로드가 발생하고, 매번 새로 만드는 `Float32Array`가 GC 압박을 일으켜 파티클 수가 늘어날수록 프레임이 뚝뚝 끊긴다. 리소스 생성은 `onAdd`에서 1회, 데이터 갱신은 실제로 값이 바뀐 시점에만 `bufferSubData`로 부분 갱신하는 것이 올바른 구조다. 파티클 위치 이동처럼 "매 프레임 전부 바뀌는" 값은 CPU에서 갱신하지 말고 시간 유니폼(`u_time`)을 넘겨 셰이더에서 계산하게 하면 업로드 자체가 사라진다.

그 밖에 세 가지를 챙기자. 첫째, **GL 상태 누수** — 커스텀 레이어에서 바꾼 blend·depth 설정이 이후 지도 렌더링에 영향을 줄 수 있으니, 기본값과 다르게 만진 상태는 되돌리는 습관이 안전하다. 둘째, `map.setStyle()`로 스타일을 갈아끼우면 레이어가 다시 추가되며 `onAdd`가 재호출될 수 있으므로 리소스 재생성이 가능한 구조로 짜야 한다. 셋째, `triggerRepaint()`는 애니메이션이 필요한 동안만 호출해야 한다. 정적 화면에서도 무조건 호출하면 지도가 쉬지 못해 모바일 배터리를 갉아먹는다.

## 마무리 요약

- 커스텀 레이어는 지도와 **같은 WebGL 컨텍스트·같은 프레임**에서 그리므로, 별도 캔버스 오버레이의 프레임 어긋남 없이 파티클·커스텀 히트맵을 얹을 수 있다.
- 좌표는 경위도가 아니라 `MercatorCoordinate`의 0~1 월드 좌표이며, 리소스 생성은 `onAdd`, 그리기는 `render`, 애니메이션은 `triggerRepaint()`로 역할을 나눈다.
- 스타일 레이어나 deck.gl로 되는 표현이면 그쪽을 먼저 쓰고, 셰이더를 직접 제어해야 할 때만 커스텀 레이어를 선택하는 것이 유지보수 관점에서 옳다.

## 참고 자료

- [MapLibre GL JS — CustomLayerInterface](https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/)
- [MapLibre GL JS — MercatorCoordinate](https://maplibre.org/maplibre-gl-js/docs/API/classes/MercatorCoordinate/)
- [MapLibre GL JS — Examples](https://maplibre.org/maplibre-gl-js/docs/examples/)
- [deck.gl — MapboxOverlay](https://deck.gl/docs/api-reference/mapbox/mapbox-overlay)
