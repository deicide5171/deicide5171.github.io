---
layout: single
title: "3D Tiles로 대도시를 브라우저에 — Cesium 스트리밍 렌더링 원리"
date: 2026-08-20 13:20:00 +0530
categories: gis
tags: ["gis", "cesium", "3d-tiles", "webgl", "3d-map", "streaming"]
toc: true
toc_sticky: true
excerpt: "수십만 개 3D 건물 모델을 브라우저에서 끊김 없이 렌더링하는 비결인 3D Tiles 타일링 구조와, Cesium이 LOD·프러스텀 컬링으로 스트리밍하는 원리를 정리한다."
---

도시 하나를 통째로 3D로 표현한 건물 모델 데이터셋은 수십만 개의 메시와 수 기가바이트를 넘어가는 경우가 드물지 않다. 이 데이터를 하나의 glTF 파일이나 단일 메시로 브라우저에 통째로 로드하려 하면 네트워크 전송 시간은 물론 GPU 메모리와 프레임 드롭 문제로 사실상 실사용이 불가능해진다. 사용자는 도시 전체를 한눈에 보고 싶어 하기도 하고, 특정 건물 하나를 아주 가까이서 들여다보고 싶어 하기도 하는데, 이 두 요구를 하나의 고정된 해상도 모델로는 동시에 만족시킬 수 없다.

이 문제를 표준화된 방식으로 풀기 위해 OGC(Open Geospatial Consortium)는 **3D Tiles**라는 스펙을 채택했다. 3D Tiles는 대규모 3D 지오스페이셜 콘텐츠를 계층적인 타일 단위로 쪼개고, 각 타일에 상세도(디테일 수준)를 부여해 클라이언트가 필요한 만큼만 필요한 해상도로 내려받도록 설계된 구조다. Cesium은 이 표준을 브라우저에서 실제로 구현한 대표적인 WebGL 엔진으로, tileset.json이라는 메타데이터 트리를 읽어 화면에 보이는 영역과 카메라 거리에 따라 타일을 선택적으로 스트리밍한다. 이번 글에서는 이 타일셋 계층 구조, LOD 교체 규칙, 프러스텀 컬링이 실제로 어떻게 맞물려 동작하는지를 정리한다.

## 핵심 개념 1: 타일셋 계층 구조 — tileset.json과 bounding volume

3D Tiles 데이터셋의 진입점은 `tileset.json`이라는 JSON 문서다. 이 문서는 루트 타일에서 시작해 자식 타일로 뻗어나가는 트리 구조를 기술하는데, 각 노드(타일)는 다음 정보를 가진다.

- **boundingVolume**: 해당 타일이 공간상 차지하는 범위(구, 박스, 리전 중 하나로 표현)
- **geometricError**: 이 타일의 지오메트리가 실제 형상과 얼마나 차이 나는지를 나타내는 오차값
- **content**: 실제 렌더링 데이터(주로 glTF/glb, 또는 포인트 클라우드·배치 데이터)에 대한 참조
- **children**: 더 상세한 하위 타일 목록

지형이나 대규모 건물 집합처럼 재귀적으로 세분화 가능한 데이터는 쿼드트리나 옥트리와 유사한 방식으로 이 트리를 구성하는 경우가 많다. 도시 전체를 커버하는 루트 타일 하나가 있고, 그 아래로 지역을 나눈 자식 타일들이, 다시 그 아래로 개별 건물 블록 단위의 손자 타일들이 이어지는 식이다. 중요한 점은 Cesium이 이 tileset.json 전체를 한 번에 받아 파싱하는 게 아니라, 루트에서 시작해 카메라 시점에서 실제로 필요한 가지만 따라 내려가며 하위 JSON과 콘텐츠를 그때그때 요청한다는 것이다.

<img src="/assets/images/posts/2026-08-20-cesium-3d-tiles-streaming-rendering-1.svg" alt="3D Tiles 타일셋 계층 구조(루트-자식-손자 트리)와 카메라 프러스텀 안팎의 타일 컬링을 나타낸 개념도" style="width:100%;">

## 핵심 개념 2: LOD와 geometricError 기반 교체 규칙

3D Tiles는 밉맵과 비슷한 개념으로 상세도(LOD, Level of Detail)를 계층에 내장한다. 각 타일이 가진 geometricError는 "이 타일을 대신 그렸을 때 실제 형상과 벌어질 수 있는 최대 오차"를 의미하며, 값이 클수록 거친 근사치, 작을수록 정밀한 표현이다. Cesium은 매 프레임 카메라 위치와 화면 해상도를 기준으로 각 타일의 오차가 화면상에서 몇 픽셀로 나타나는지(screen-space error, SSE)를 계산하고, 이 값이 설정된 임계치를 넘으면 해당 타일을 자식 타일들로 교체한다.

즉 카메라가 도시를 멀리서 내려다볼 때는 geometricError가 큰 상위 타일 몇 개만으로도 화면상 오차가 임계치 이내에 들어오므로 그대로 사용하고, 카메라가 특정 건물에 다가가면 그 건물이 속한 가지의 하위 타일이 로드되어 상위 타일을 대체한다. 이 교체 방식에는 크게 두 가지가 있는데, 자식 타일이 로드되면 부모를 완전히 대체하는 **REPLACE** 방식과, 부모 콘텐츠 위에 자식을 추가로 얹는 **ADD** 방식이 있다(스펙에서는 각각 refine 속성의 `REPLACE`, `ADD` 값으로 지정한다). 어느 쪽이든 로딩 중에는 상위 타일이 화면에 남아 있다가 하위 타일 로드가 끝나면 교체되므로, 사용자 입장에서는 빈 화면 없이 점진적으로 선명해지는 경험을 하게 된다.

## 핵심 개념 3: 프러스텀 컬링으로 화면 밖 타일 스킵하기

LOD가 "얼마나 상세하게 그릴지"를 결정한다면, 프러스텀 컬링(frustum culling)은 "애초에 그릴 필요가 있는지"를 결정한다. 카메라의 시야는 절두체(frustum) 형태의 3차원 공간으로 정의되는데, Cesium은 순회 중인 각 타일의 boundingVolume이 이 절두체와 교차하는지를 검사해, 교차하지 않는 타일은 트리 순회에서 아예 건너뛴다. 화면 뒤쪽이나 화면 밖 좌우로 벗어난 지역의 타일은 이 단계에서 네트워크 요청조차 발생하지 않는다.

프러스텀 컬링과 LOD 선택은 같은 트리 순회 과정에서 함께 처리된다. 루트에서 시작해 절두체와 교차하지 않는 가지는 즉시 가지치기(prune)하고, 교차하는 가지에 대해서만 SSE를 계산해 더 내려갈지 현재 타일을 그대로 쓸지를 결정하는 식이다. 이 덕분에 도시 전체 데이터셋 중 실제로 네트워크에서 내려받고 GPU에 올리는 양은 화면에 실제로 보이는 부분과 그 상세도에 필요한 만큼으로 크게 줄어든다.

## 예제

```javascript
import * as Cesium from "cesium";

const viewer = new Cesium.Viewer("cesiumContainer");

// Cesium ion에 호스팅된 3D Tiles 데이터셋 로드 (assetId는 예시)
const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(96188);
viewer.scene.primitives.add(tileset);

// 카메라를 타일셋 전체가 보이도록 이동
viewer.zoomTo(tileset);

// 화면상 오차 임계치를 조정해 상세도 교체 시점을 튜닝
tileset.maximumScreenSpaceError = 16; // 기본값보다 크게 잡으면 더 거친 타일을 오래 유지
```

```javascript
// 자체 호스팅한 tileset.json을 로드하는 경우
const tileset = await Cesium.Cesium3DTileset.fromUrl(
  "https://example.com/tiles/buildings/tileset.json"
);
viewer.scene.primitives.add(tileset);

// 타일 로딩 상태를 이벤트로 관찰
tileset.tileLoad.addEventListener((tile) => {
  console.log("타일 로드 완료:", tile);
});
```

`maximumScreenSpaceError` 값을 키우면 같은 카메라 거리에서도 더 거친(geometricError가 큰) 타일을 오래 유지하므로 네트워크·GPU 부하는 줄지만 시각적으로는 더 뭉툭해 보인다. 반대로 값을 낮추면 더 이른 시점에 하위 타일로 교체되어 화질은 좋아지지만 요청량과 메모리 사용량이 늘어난다.

## 실무 포인트

- **타일 생성 파이프라인을 먼저 정한다**: 원본 3D 모델(예: CityGML, OBJ, 사진측량 메시)을 3D Tiles로 변환해야 하므로, Cesium ion 같은 호스팅형 변환 서비스나 오픈소스 변환 도구 중 데이터 포맷과 규모에 맞는 것을 먼저 선택해야 한다. 변환 도구별로 지원 입력 포맷과 결과물 품질 편차가 있으므로 사전 검증이 필요하다.
- **`maximumScreenSpaceError`는 트레이드오프 파라미터다**: 이 값을 낮출수록 화질은 좋아지지만 동시에 로드해야 하는 타일 수와 GPU 메모리 사용량이 늘어난다. 목표 디바이스(데스크톱 vs 모바일)에 따라 별도 값을 두는 것이 안전하다.
- **메모리 캐시 한도를 설정한다**: `tileset.cacheBytes` 같은 옵션으로 이미 로드된 타일을 얼마나 메모리에 유지할지 조절할 수 있다. 한도를 너무 낮게 잡으면 카메라를 조금만 움직여도 같은 타일을 재요청하게 되어 네트워크 부하가 늘어난다.
- **네트워크 지연이 체감 성능을 좌우한다**: 타일 자체의 지오메트리 최적화 못지않게, CDN 배치나 HTTP/2 멀티플렉싱처럼 다수의 작은 타일 요청을 빠르게 처리하는 네트워크 구성이 실제 사용자 체감 속도에 크게 영향을 준다.

## 3줄 요약

- 3D Tiles는 대규모 3D 지오스페이셜 데이터를 tileset.json 기반 계층 구조로 쪼개, 필요한 부분만 스트리밍하도록 설계된 OGC 표준이다.
- geometricError와 화면상 오차(SSE) 계산에 따라 카메라 거리별로 적절한 상세도의 타일로 교체되는 것이 LOD 메커니즘의 핵심이다.
- 프러스텀 컬링은 카메라 시야 밖의 타일을 트리 순회 단계에서 걸러내 불필요한 네트워크 요청과 렌더링을 원천적으로 줄인다.

## 참고 자료

- [Cesium 공식 문서 — 3D Tiles](https://cesium.com/learn/3d-tiles/)
- [Cesium3DTileset API 레퍼런스](https://cesium.com/learn/cesiumjs/ref-doc/Cesium3DTileset.html)
- [OGC 3D Tiles 표준 문서](https://www.ogc.org/standard/3dtiles/)
