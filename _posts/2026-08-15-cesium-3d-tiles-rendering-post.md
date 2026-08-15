---
layout: single
title: "Cesium과 3D Tiles로 웹에서 대용량 3차원 공간 데이터 렌더링하기"
date: 2026-08-15 11:20:00 +0530
categories: gis
tags: ["gis", "cesium", "3d-tiles", "webgl", "deckgl"]
toc: true
toc_sticky: true
excerpt: "도시 전체 3D 모델이나 포인트클라우드처럼 거대한 3차원 공간 데이터를 브라우저에서 끊김 없이 렌더링하려면 어떻게 해야 할까. OGC 3D Tiles 표준과 CesiumJS의 LOD 스트리밍 구조, deck.gl과의 비교를 정리한다."
---

## 왜 지금 3D 웹 지도인가

디지털 트윈, 스마트시티 대시보드, 드론 매핑 결과물을 웹에서 그대로 보여주는 수요가 늘면서 "브라우저에서 도시 전체 3D 모델을 어떻게 끊김 없이 띄울 것인가"가 실무 문제로 떠올랐다. 문제는 데이터 크기다. 건물 모델링 데이터나 라이다 포인트클라우드는 전체를 한 번에 GPU 메모리에 올릴 수 없을 만큼 크다.

이 문제를 표준 규격으로 푼 것이 OGC **3D Tiles**이고, 이를 가장 오래·널리 구현한 오픈소스 엔진이 **CesiumJS**다. 최근에도 CesiumJS는 3D Tiles 기반 벡터 타일 렌더링(포인트·선·폴리곤에 속성 기반 스타일링), 지형에 밀착시키는 클램핑 폴리라인, CAD 자산 검사용 커스텀 카메라 컨트롤러 등을 계속 추가하며 대용량 3차원 데이터 처리 표준으로 자리를 굳히고 있다.

## 핵심 개념: 3D Tiles의 LOD 트리 구조

3D Tiles는 하나의 거대한 3D 데이터셋을 계층적인 타일 트리(타일셋)로 쪼갠다. 루트 타일은 전체 영역을 낮은 해상도로 표현하고, 카메라가 특정 영역에 가까워지면 그 부분의 자식 타일만 추가로 내려받아 세분화한다. 이 판단 기준이 **화면 공간 오차(Screen Space Error, SSE)**다. 화면에 투영했을 때 오차가 임계값보다 크면 더 정밀한 자식 타일을 요청하고, 임계값 이하면 지금 타일로 충분하다고 판단해 더 내려받지 않는다.

<img src="/assets/images/posts/2026-08-15-cesium-3d-tiles-rendering-1.svg" alt="3D Tiles 타일셋 LOD 트리 구조, 카메라와 가까운 타일만 재귀적으로 세분화되는 과정" style="width:100%;">

이 구조 덕분에 카메라 시야 밖이나 멀리 있는 영역은 계속 성긴 상태로 남고, 실제로 보이는 근접 영역만 세밀한 메시·포인트클라우드를 스트리밍한다. 결과적으로 수백 GB 규모의 원본 데이터셋도 브라우저 메모리 예산 안에서 끊김 없이 탐색할 수 있다.

## CesiumJS vs deck.gl: 3D Tiles 렌더링 비교

| 항목 | CesiumJS | deck.gl (Tile3DLayer) |
|---|---|---|
| 성격 | 완결된 지구본 뷰어 엔진(지형, 대기, 시간 애니메이션 내장) | WebGL 레이어 프레임워크(React/기존 지도와 조합) |
| 3D Tiles 지원 | 1급 시민, 벡터 타일·클램핑 등 최신 확장 지속 추가 | Tile3DLayer로 tileset 로드, TerrainController로 지형 내비게이션 |
| 적합한 상황 | 지구 규모 시각화, CAD 자산 점검, 시간축 애니메이션 | 기존 웹앱에 3D 레이어 하나를 얹고 싶은 경우, 대용량 포인트 시각화와 조합 |
| 학습 곡선 | 자체 API·카메라 모델을 새로 익혀야 함 | deck.gl 레이어 체계에 익숙하면 진입 장벽 낮음 |

두 라이브러리 모두 3D Tiles 표준을 따르므로 같은 타일셋 데이터를 그대로 재사용할 수 있다는 점이 중요하다. "지구본 중심의 완결된 뷰어가 필요하냐"와 "기존 웹앱에 3D 레이어를 얹는 것이냐"가 선택의 갈림길이다.

## 예제: CesiumJS로 3D Tiles 타일셋 불러오기

```javascript
import * as Cesium from "cesium";

const viewer = new Cesium.Viewer("cesiumContainer", {
  terrain: Cesium.Terrain.fromWorldTerrain(),
});

// OGC 3D Tiles 타일셋 로드 (예: 건물 모델링 데이터)
const tileset = await Cesium.Cesium3DTileset.fromUrl(
  "https://example.com/tileset/buildings/tileset.json"
);
viewer.scene.primitives.add(tileset);

// 타일셋 범위로 카메라 이동
await viewer.zoomTo(tileset);

// SSE 임계값을 낮추면 더 정밀한 타일을 더 적극적으로 요청한다(품질↑, 트래픽↑)
tileset.maximumScreenSpaceError = 8;
```

`maximumScreenSpaceError` 값이 낮을수록 더 정밀한 타일을 적극적으로 요청해 화질은 좋아지지만 네트워크·GPU 부담이 커진다. 기본값(보통 16)에서 시작해 타깃 디바이스 성능에 맞춰 조정하는 것이 일반적이다.

## 실무 포인트

- **타일 생성 파이프라인부터 검증한다**: 원본 데이터(포토그래메트리 메시, 라이다 포인트클라우드, CAD 모델)를 3D Tiles로 변환하는 도구(Cesium ion, 3d-tiles-tools 등)의 압축·양자화(quantization) 옵션이 최종 화질과 전송량을 크게 좌우한다.
- **SSE 임계값을 디바이스별로 분리한다**: 데스크톱과 모바일에서 같은 임계값을 쓰면 한쪽은 과도하게 무겁거나 다른 쪽은 화질이 떨어진다.
- **메모리 예산을 명시적으로 관리한다**: `tileset.cacheBytes`처럼 캐시 상한을 설정해두지 않으면 장시간 세션에서 GPU 메모리가 계속 쌓여 성능이 저하될 수 있다.
- **좌표계·원점 정렬을 먼저 맞춘다**: 3D Tiles는 지구 중심 좌표계(ECEF) 기반으로 배치되므로, 로컬 좌표계 데이터는 변환 단계에서 원점과 축 정렬을 미리 검증해야 나중에 "건물이 땅에 파묻힌다" 류의 문제를 피할 수 있다.

## 3줄 요약

- 3D Tiles는 거대한 3차원 데이터셋을 LOD 트리로 쪼개고, 화면 공간 오차(SSE) 기준으로 카메라 근처만 세분화해 스트리밍하는 표준이다.
- CesiumJS는 지구 규모의 완결된 뷰어로, deck.gl의 Tile3DLayer는 기존 웹앱에 3D 레이어를 얹는 용도로 각각 강점이 다르다.
- 실제 도입 시에는 타일 생성 파이프라인의 압축 품질, SSE 임계값, 메모리 캐시 상한을 함께 튜닝해야 끊김 없는 경험을 만들 수 있다.

## 참고 자료

- [OGC 3D Tiles Specification](https://www.ogc.org/standards/3DTiles/)
- [CesiumJS Documentation](https://cesium.com/learn/cesiumjs-learn/)
- [deck.gl — Using with 3D Tiles](https://deck.gl/docs/developer-guide/base-maps/using-with-3d-tiles)
