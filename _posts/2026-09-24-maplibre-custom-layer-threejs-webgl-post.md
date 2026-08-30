---
layout: single
title: "MapLibre GL JS CustomLayerInterface로 Three.js WebGL 레이어 통합하기"
date: 2026-09-24 12:20:00 +0530
categories: gis
tags: ["MapLibre", "Threejs", "WebGL", "CustomLayer", "3D웹지도"]
toc: true
toc_sticky: true
excerpt: "MapLibre GL JS 지도 위에 Three.js로 만든 3D 모델을 정확한 지리 좌표에 겹쳐 그리려 할 때, CustomLayerInterface가 매 프레임 넘겨주는 투영 행렬을 어떻게 다뤄야 하는지 렌더링 파이프라인 관점에서 정리했다."
---

## 왜 지금 커스텀 레이어를 알아야 하는가

MapLibre GL JS는 벡터 타일과 fill-extrusion 같은 내장 레이어 타입만으로도 상당한 3D 표현을 지원하지만, 실제 항공기 경로 애니메이션, 정밀한 커스텀 3D 모델(GLTF), 파티클 효과처럼 지도 라이브러리가 기본 제공하지 않는 표현이 필요해지는 순간이 온다. 이럴 때 선택지는 별도의 오버레이 캔버스를 지도 위에 얹는 것과, MapLibre의 렌더 파이프라인 안으로 직접 들어가는 것 두 가지다. 전자는 구현은 쉽지만 지도 확대·축소·회전 시 커스텀 레이어와 기본 지도 레이어 사이에 프레임 지연이나 어긋남이 생기기 쉽다. 후자, 즉 `CustomLayerInterface`를 이용하면 같은 WebGL 컨텍스트와 같은 프레임 안에서 그리기 때문에 이런 어긋남이 원천적으로 사라진다.

## 핵심 개념 1 — CustomLayerInterface가 실제로 하는 일

MapLibre는 레이어 타입으로 `"custom"`을 지정하면, 매 프레임 렌더링 시점에 개발자가 등록한 `render(gl, matrix)` 함수를 직접 호출해준다. 여기서 넘어오는 `gl`은 MapLibre가 이미 초기화해 사용 중인 WebGLRenderingContext 그 자체이고, `matrix`는 현재 카메라 위치·줌·틸트·베어링을 반영한 Mercator 투영 행렬이다. 즉 별도의 캔버스나 별도의 WebGL 컨텍스트를 만들 필요 없이, MapLibre가 이미 그리고 있는 화면 위에 정확히 같은 좌표계로 이어서 그릴 수 있다는 것이 핵심이다.

<img src="/assets/images/posts/2026-09-24-maplibre-custom-layer-threejs-webgl-1.svg" alt="MapLibre GL JS 렌더 스택에서 배경 타일, 벡터 레이어 다음에 Custom Layer가 끼어들고, 그 안에서 Three.js Scene이 같은 WebGL 컨텍스트와 Mercator 투영 행렬을 공유해 3D 모델을 렌더링하는 파이프라인을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — Three.js 카메라를 Mercator 행렬에 맞추는 법

Three.js는 자체적인 카메라·투영 시스템을 갖고 있지만, MapLibre가 넘겨주는 `matrix`는 Three.js의 일반적인 원근 카메라 설정 방식과 맞지 않는다. 이 문제를 푸는 표준적인 방법은 Three.js 카메라의 `projectionMatrix`를 MapLibre가 준 행렬로 직접 덮어쓰는 것이다. 여기에 더해, 3D 모델의 좌표를 위경도가 아니라 MapLibre의 내부 Mercator 좌표계(0~1 범위로 정규화된 평면 좌표)로 변환해서 배치해야 한다. `MercatorCoordinate` 클래스가 이 위경도-Mercator 변환을 제공한다.

| 항목 | 일반적인 Three.js 사용 | MapLibre CustomLayer 안에서 |
|---|---|---|
| 카메라 투영 | `PerspectiveCamera`가 자체 계산 | MapLibre의 `matrix`를 그대로 주입 |
| 좌표계 | 임의의 3D 월드 좌표 | Mercator 정규화 좌표로 변환 필요 |
| 렌더 호출 시점 | requestAnimationFrame 자체 관리 | MapLibre의 `render(gl, matrix)` 콜백 안에서만 |
| WebGL 컨텍스트 | Three.js가 새로 생성 | MapLibre가 이미 만든 것을 재사용 |

## 예제 — 최소 CustomLayer 구현

```javascript
import * as THREE from 'three';
import { MercatorCoordinate } from 'maplibre-gl';

const modelOrigin = [126.978, 37.5665]; // 위경도
const modelAsMercatorCoordinate = MercatorCoordinate.fromLngLat(modelOrigin, 0);

const customLayer = {
  id: '3d-model-layer',
  type: 'custom',
  renderingMode: '3d',

  onAdd(map, gl) {
    this.camera = new THREE.Camera();
    this.scene = new THREE.Scene();
    const light = new THREE.DirectionalLight(0xffffff, 1);
    this.scene.add(light);
    // GLTF 로더 등으로 모델을 scene에 추가하는 부분 생략

    this.renderer = new THREE.WebGLRenderer({
      canvas: map.getCanvas(),
      context: gl,          // MapLibre의 gl 컨텍스트를 그대로 재사용
      antialias: true,
    });
    this.renderer.autoClear = false;
  },

  render(gl, matrix) {
    const m = new THREE.Matrix4().fromArray(matrix);
    const scale = modelAsMercatorCoordinate.meterInMercatorCoordinateUnits();

    const l = new THREE.Matrix4()
      .makeTranslation(
        modelAsMercatorCoordinate.x,
        modelAsMercatorCoordinate.y,
        modelAsMercatorCoordinate.z
      )
      .scale(new THREE.Vector3(scale, -scale, scale));

    this.camera.projectionMatrix = m.multiply(l);
    this.renderer.resetState();
    this.renderer.render(this.scene, this.camera);
    map.triggerRepaint();
  },
};

map.on('load', () => map.addLayer(customLayer));
```

## 실무 포인트

- **`renderer.autoClear = false`를 반드시 설정하라.** Three.js 렌더러가 기본값대로 화면을 지워버리면 이미 그려진 MapLibre의 지도 레이어까지 지워진다.
- **`map.triggerRepaint()`를 애니메이션이 있는 경우 매 프레임 호출하라.** 그렇지 않으면 지도가 정적일 때(사용자가 조작하지 않을 때) 커스텀 레이어의 애니메이션도 함께 멈춘다.
- **z-fighting과 깊이 버퍼 공유 문제를 초기에 테스트하라.** MapLibre의 fill-extrusion 3D 건물과 Three.js 모델이 같은 깊이 버퍼를 공유하므로, 모델의 스케일이나 깊이 설정이 어긋나면 건물 뒤에 있어야 할 모델이 앞으로 튀어나오는 렌더링 오류가 생긴다.

## 마무리 요약

- CustomLayerInterface는 별도 캔버스 오버레이 없이 MapLibre가 이미 쓰고 있는 WebGL 컨텍스트와 프레임 안에서 직접 그릴 수 있게 해준다.
- Three.js를 통합하려면 카메라의 projectionMatrix를 MapLibre가 넘긴 행렬로 덮어쓰고, 모델 좌표를 MercatorCoordinate로 변환해 배치해야 한다.
- autoClear 비활성화, triggerRepaint 호출, 깊이 버퍼 충돌 확인이 실제 프로덕션에서 가장 흔히 부딪히는 세 가지 함정이다.

## 참고 자료

- [MapLibre GL JS - CustomLayerInterface](https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/)
- [MapLibre GL JS - Add a 3D model with three.js example](https://maplibre.org/maplibre-gl-js/docs/examples/add-3d-model-with-threejs/)
