---
layout: single
title: "높이맵에서 산맥까지 — DEM 데이터로 웹 지형(Terrain) 렌더링하기"
date: 2026-08-18 13:20:00 +0530
categories: gis
tags: ["dem", "terrain-rendering", "heightmap", "quantized-mesh", "lod"]
toc: true
toc_sticky: true
excerpt: "위성·항공 측량으로 얻은 고도 격자(DEM)가 브라우저 화면 속 산과 계곡으로 바뀌기까지, 높이맵을 메시로 변환하고 카메라 거리에 따라 해상도를 조절하는 지형 렌더링 파이프라인을 정리한다."
---

## 왜 지금 지형(Terrain) 렌더링인가

웹 3D 지도라고 하면 흔히 건물 모델이나 타일 이미지를 먼저 떠올리지만, 그 아래에 깔린 **땅 자체가 평평한 평면인지, 실제 고저차를 반영한 굴곡진 표면인지**는 완전히 다른 문제다. 등산로 앱에서 능선의 경사를 보여주거나, 홍수·산사태 시뮬레이션에서 물이 어느 방향으로 흐르는지 보여주거나, 드론 비행 경로가 지형과 충돌하지 않는지 확인하려면 지도는 반드시 실제 고도값을 가진 3차원 표면이어야 한다.

이 블로그에서 앞서 다룬 Cesium 3D Tiles 글이 건물·구조물 같은 인공 객체의 LOD 트리를 다뤘다면, 이번 글은 그보다 아래 레이어 — **자연 지형 표면 자체**를 어떻게 데이터로 표현하고 실시간 렌더링 가능한 메시로 바꾸는가에 집중한다. 핵심 재료는 DEM(Digital Elevation Model)이라는 고도 격자 데이터이고, 핵심 과정은 이 격자를 삼각형 메시로 바꾸고 카메라 거리에 맞게 해상도를 조절하는 것이다.

## 핵심 개념 1: DEM이란 무엇인가

DEM은 지표면의 높이를 일정 간격의 격자(래스터)로 저장한 데이터다. 위성 레이더 측량, 항공 라이다, 드론 사진측량 등으로 만들어지며, 셀 하나가 "이 위치의 고도는 몇 미터"라는 값 하나를 담는다. 비슷한 용어들과 구분이 중요하다.

| 용어 | 담는 내용 | 예시 |
|---|---|---|
| DTM (Digital Terrain Model) | 건물·나무를 제외한 순수 지표면 고도 | 지반 높이만 필요한 토목 설계 |
| DSM (Digital Surface Model) | 건물·나무를 포함한 표면 최상단 고도 | 항공 촬영 그대로의 표면 |
| DEM | 넓은 의미로 DTM을 가리키는 경우가 많음(맥락에 따라 DSM 포함) | 지형 렌더링에서 흔히 쓰는 용어 |

공개 DEM 데이터셋은 출처와 측량 방식에 따라 격자 간격(공간 해상도)과 수직 정확도가 크게 달라지므로, 실제 프로젝트에 쓸 때는 데이터셋별 스펙 문서를 확인하고 목적에 맞는 해상도를 고르는 과정이 필요하다.

## 핵심 개념 2: 높이맵 → 메시 변환

DEM 격자 그 자체는 그릴 수 없다. GPU는 정점(vertex)과 삼각형만 이해하므로, 격자의 각 셀을 정점 하나로 보고 인접한 정점 4개마다 삼각형 2개를 만드는 **삼각분할**을 거쳐야 화면에 그릴 수 있는 메시가 된다. 이때 정점의 X·Y는 격자 위치(경위도 또는 투영 좌표)에서, Z(높이)는 DEM 셀 값에서 가져온다.

방식은 크게 두 갈래다. 하나는 **정규 격자(Regular Grid) 메시**로, 모든 셀을 그대로 정점화해 구현이 단순하지만 평지에서도 불필요하게 많은 삼각형이 생긴다. 다른 하나는 **TIN(Triangulated Irregular Network)** 으로, 높이 변화가 적은 평지는 큰 삼각형으로, 굴곡이 심한 산악 지형은 작은 삼각형으로 표현해 같은 정확도를 더 적은 정점으로 담는다. 조명 계산에는 인접 셀 값의 차이로 표면 기울기를 구하는 법선(normal) 계산도 함께 필요하다.

## 핵심 개념 3: 지형 타일링과 LOD

전 지구 단위 DEM을 한 번에 메시로 만들면 정점 수가 감당할 수 없이 커진다. 그래서 이미지 타일 피라미드와 같은 방식으로 지형도 **타일 단위 + 레벨(LOD)** 로 나눠 저장한다. 카메라에서 먼 타일은 성긴 정점(예: 수십×수십 수준)으로, 가까운 타일은 촘촘한 정점(예: 수백×수백 수준)으로 각각 미리 준비해두고, 화면에 투영했을 때의 오차(SSE, Screen Space Error)를 기준으로 필요한 레벨만 불러온다.

| 방식 | 저장 형태 | 특징 |
|---|---|---|
| 래스터 높이맵 타일(PNG/GeoTIFF) | 픽셀당 고도값 | 구현 단순, 정점화는 클라이언트가 매번 수행 |
| 양자화 메시(quantized-mesh) | 이미 삼각분할된 정점·인덱스 버퍼 | Cesium 등에서 사용, 클라이언트 연산 부담 감소 |

레벨이 바뀌는 순간 지형이 툭 튀어 보이는 "팝핑(popping)"을 막기 위해, 두 레벨의 정점 높이를 짧은 시간 동안 보간하며 전환하는 **지오모핑(geomorphing)** 기법이 흔히 쓰인다. 또한 해상도가 다른 인접 타일 사이에는 미세한 틈(crack)이 생길 수 있어, 타일 가장자리를 아래로 살짝 늘어뜨리는 **스커트(skirt)** 로 틈을 가리는 처리도 함께 필요하다.

## 예제 1: 높이맵 배열로 메시 정점 변위시키기 (Three.js)

```javascript
// PlaneGeometry의 각 정점을 heightData 배열 값만큼 Z축으로 밀어올린다
const size = 64; // 64x64 격자
const geometry = new THREE.PlaneGeometry(100, 100, size - 1, size - 1);
const heightData = loadHeightmapArray(); // DEM에서 뽑은 Float32Array, 길이 size*size

const position = geometry.attributes.position;
for (let i = 0; i < position.count; i++) {
  const elevation = heightData[i]; // 미터 단위 고도
  position.setZ(i, elevation * verticalExaggeration); // 필요 시 과장 계수 적용
}
position.needsUpdate = true;
geometry.computeVertexNormals(); // 조명을 위한 법선 재계산
```

## 예제 2: 텍스처 기반 정점 변위 (GLSL 버텍스 셰이더)

정점 수가 많아지면 CPU에서 매번 좌표를 계산하는 대신, 높이맵을 텍스처로 GPU에 올려 버텍스 셰이더가 직접 샘플링하게 하는 방식이 더 효율적이다.

```glsl
uniform sampler2D u_heightmap; // DEM을 인코딩한 텍스처
uniform float u_verticalExaggeration;
attribute vec2 a_uv;           // 격자 내 정규화 좌표 (0~1)

void main() {
  float elevation = texture2D(u_heightmap, a_uv).r * 255.0; // 예시 인코딩
  vec3 displaced = position + vec3(0.0, 0.0, elevation * u_verticalExaggeration);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
```

## 실무 포인트

- **수직 과장(vertical exaggeration)은 표기와 함께 써야 한다.** 완만한 구릉을 시각적으로 강조하려고 높이값에 배수를 곱하는 경우가 많은데, 실제 축척이 왜곡된다는 점을 화면이나 범례에 명시하지 않으면 사용자가 실제 경사를 오해할 수 있다.
- **수직 기준면(datum) 불일치를 확인한다.** 서로 다른 출처의 DEM을 섞어 쓰면 수평 좌표계는 맞아도 고도 기준(지오이드 기준 등)이 달라 경계에서 단차가 생길 수 있다. 데이터셋 문서에서 수직 기준을 반드시 확인한다.
- **No-data(구멍) 셀을 미리 처리한다.** 구름·그림자로 값이 비어있는 셀을 그대로 두면 메시에 뾰족한 스파이크가 생기므로, 주변 값으로 보간하거나 별도 마스크로 표시한다.
- **타일 경계 이음새와 LOD 전환을 함께 설계한다.** 스커트나 정점 공유로 크랙을 막고, 지오모핑으로 레벨 전환 시 튐을 줄이는 처리를 초기 설계 단계에 포함시킨다.

## 3줄 요약

- DEM은 지표면 고도를 격자로 저장한 데이터이며, 각 셀이 정점 하나가 되어 삼각분할을 거쳐야 화면에 그릴 수 있는 메시가 된다.
- 전 지구 단위 지형은 이미지 타일처럼 타일+LOD로 나눠 저장하고, 카메라 거리(SSE 기준)에 따라 필요한 해상도의 타일만 불러오며 지오모핑으로 전환 시 팝핑을 줄인다.
- 실무에서는 수직 과장 표기, 수직 기준면 정합, No-data 처리, 타일 경계 이음새 처리를 함께 챙겨야 자연스러운 지형이 완성된다.

## 참고 자료

- [CesiumGS — quantized-mesh 지형 포맷 스펙 (GitHub)](https://github.com/CesiumGS/quantized-mesh)
- [Three.js — PlaneGeometry 문서](https://threejs.org/docs/#api/en/geometries/PlaneGeometry)
- [OpenTopography — 공개 DEM/라이다 데이터 포털](https://opentopography.org/)
