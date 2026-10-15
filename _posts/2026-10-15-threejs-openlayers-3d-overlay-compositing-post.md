---
layout: single
title: "'이 건물만 3D로 띄워주세요' — OpenLayers 위에 three.js를 합성하는 카메라 동기화 설계"
date: 2026-10-15 12:45:00 +0530
categories: gis
tags: ["openlayers", "three.js", "3d오버레이", "좌표계", "웹지도"]
toc: true
toc_sticky: true
excerpt: "지도 전체를 3D 지구본으로 바꾸는 게 아니라, 기존 2D 벡터타일 지도는 그대로 두고 특정 건물·분석 결과만 3D로 얹고 싶다는 요구를 풀려면 OpenLayers의 카메라 상태를 three.js 퍼스펙티브 카메라에 매 프레임 동기화해야 한다. 좌표계 변환, 렌더 루프 공유, Cesium·deck.gl과의 선택 기준을 정리했다."
---

## 왜 지금 이 판단이 필요한가

"지도는 지금 쓰는 2D 벡터타일 그대로 두고, 재건축 예정 건물 몇 개만 3D 매스로 올려서 보여주세요." 기획자 입장에서는 소박한 요구다. 그런데 이 요구를 "그럼 Cesium으로 다 바꾸죠"로 받으면 과잉 대응이 된다. 전체 지도를 3D 지구본 엔진으로 옮기면 기존에 공들여 만든 OpenLayers 스타일, 벡터타일 소스, 클릭 인터랙션을 전부 다시 짜야 한다. 반대로 이 요구를 "그냥 3D 모델 이미지 하나 얹죠"로 받으면, 지도를 줌·회전할 때 그 건물만 따로 놀아서 금방 들통난다.

진짜 필요한 건 **기존 2D 지도는 그대로 두고, 그 위에 3D 렌더 레이어 하나를 포개어 카메라를 동기화하는 것**이다. three.js를 OpenLayers 위에 합성하는 패턴이 바로 이 틈을 메운다. 다만 이 조합에는 공식 브리지 라이브러리가 없다 — Mapbox GL JS 생태계의 Threebox나 OpenLayers-Cesium을 잇는 OLCS 같은 성숙한 다리가 three.js+OpenLayers 조합에는 아직 없다. 그래서 카메라 동기화를 직접 구현해야 하고, 이게 바로 이 글이 다루는 설계 문제다.

## 핵심 개념 1 — 두 좌표계를 하나로 묶기

OpenLayers는 기본적으로 EPSG:3857(Web Mercator) 평면 좌표를 미터 단위로 다룬다. three.js는 원점이 임의인 로컬 3D 좌표계를 쓴다. 이 둘을 합성하려면 지도 좌표를 three.js 장면의 로컬 좌표로 변환하는 기준점(origin)을 하나 정해야 한다. 보통 화면 중심의 지도 좌표를 원점으로 잡고, 그 주변 객체들의 Web Mercator 좌표를 원점 기준 상대 좌표(미터)로 바꿔 three.js 메시 위치에 대입한다. 고위도로 갈수록 Web Mercator의 축척 왜곡이 커지므로, 변환식에 현재 위도에서의 축척 보정 계수를 곱해야 실제 크기와 어긋나지 않는다.

## 핵심 개념 2 — 카메라를 매 프레임 동기화한다

OpenLayers의 `view`가 가진 center, resolution(줌), rotation을 three.js의 `PerspectiveCamera` 위치·투영행렬로 매 프레임 변환해줘야, 지도를 드래그하거나 줌할 때 3D 객체가 지도와 같이 움직인다. 패턴은 Mapbox 생태계의 Threebox가 쓰는 CameraSync 방식과 동일하다 — 지도 뷰가 바뀔 때마다 three.js 카메라의 projection matrix와 world matrix를 다시 계산해 넣는다. OpenLayers는 `map.on('postrender', ...)` 이벤트로 이 훅을 건다.

<img src="/assets/images/posts/2026-10-15-threejs-openlayers-3d-overlay-compositing-1.svg" alt="OpenLayers 지도 뷰의 변경 이벤트가 카메라 동기화 모듈을 거쳐 three.js 퍼스펙티브 카메라의 투영행렬을 갱신하고, 두 렌더 루프가 겹쳐진 캔버스에 각각 그려지는 구조도" style="width:100%;">

## 핵심 개념 3 — 렌더 루프를 어떻게 겹칠 것인가

가장 쉬운 방법은 OpenLayers 캔버스 위에 three.js 전용 캔버스를 투명 배경으로 절대 위치시켜 포개는 것이다. 구현이 단순하고 두 렌더러가 서로의 내부 상태를 전혀 몰라도 된다. 다만 마우스 이벤트가 위쪽 캔버스에 막혀 지도 인터랙션이 끊기므로 `pointer-events: none`과 커스텀 피킹 로직이 따로 필요하고, 두 레이어가 각자 그리다 보니 깊이 테스트가 레이어 간에는 작동하지 않아 3D 객체가 지도 라벨을 항상 가리거나 항상 가려지는 식의 어색함이 남는다. 더 정교한 방법은 Google Maps의 WebGL Overlay View가 쓰는 것처럼 **같은 WebGL 컨텍스트를 공유**해 three.js가 지도의 GL 상태 안에 직접 그리는 것이다. 이러면 깊이 테스트와 폐색(occlusion)이 자연스럽게 맞아떨어지지만, three.js가 끝난 뒤 반드시 `renderer.resetState()`로 GL 상태를 되돌려줘야 지도 자체 렌더링이 깨지지 않는다 — OpenLayers 쪽에서 이 패턴을 기본 제공하지 않으므로 직접 짜야 하는 부분이다.

## 선택의 트레이드오프

| 상황 | 적합한 선택 | 이유 |
|---|---|---|
| 특정 건물·구조물만 국소적으로 3D 강조 | three.js + OpenLayers 합성 | 기존 2D 지도 자산을 거의 그대로 재사용 |
| 지형·지하·시간축까지 포함한 전역 3D 분석 | Cesium | 지구 타원체, 3D Tiles 스트리밍을 기본 제공 |
| 대량 포인트·폴리곤의 3D 집계 시각화(기둥 차트 등) | deck.gl | WebGL 레이어 자체가 대용량 집계에 최적화됨 |
| 빠른 프로토타입, 정교한 깊이 처리 불필요 | 별도 캔버스 오버레이 | 구현 난이도가 가장 낮음 |
| 라벨·3D 객체 간 가려짐까지 정확해야 하는 제품화 단계 | GL 컨텍스트 공유 | 폐색 처리가 자연스러움, 대신 구현 난이도 상승 |

흔한 함정은 "3D가 필요하니 무조건 Cesium"으로 바로 건너뛰는 것이다. 요구가 전역적 3D 지구 분석이 아니라 국소적 강조라면, 전체 지도 스택을 바꾸는 비용이 실제로 얻는 가치보다 훨씬 크다. 반대로 별도 캔버스 오버레이로 시작해놓고 나중에 "라벨이 3D 객체 뒤로 숨었다 나타났다 한다"는 디테일 버그를 뒤늦게 만나는 경우도 많다 — 이건 설계 초기에 깊이 처리 방식을 정해두지 않은 대가다.

## 실제 프로젝트 진행 순서

1. **요구를 먼저 분류한다.** "전역 3D 분석"인지 "국소 3D 오버레이"인지부터 가른다. 이 판단이 Cesium과 three.js+OpenLayers 중 어디로 갈지를 결정한다.
2. **카메라 동기화부터 프로토타입한다.** 실제 3D 모델 없이 좌표축 하나만 three.js로 그려서, 지도를 드래그·줌할 때 정확히 같이 따라오는지부터 검증한다. 여기서 막히면 뒤 단계는 의미가 없다.
3. **좌표 변환 유틸을 분리한다.** Web Mercator ↔ three.js 로컬 좌표 변환 함수를 독립 모듈로 떼어, 기준점(origin) 재설정 시 영향 범위를 좁힌다.
4. **두 렌더 루프의 프레임 버짓을 함께 측정한다.** 지도 렌더와 3D 렌더가 같은 프레임에서 경합하므로, 객체 수가 늘었을 때 어디서 프레임이 떨어지는지 프로파일링한다.
5. **깊이·폐색 처리를 마지막에 결정한다.** 별도 캔버스로 시작했더라도, 제품화 단계에서 GL 컨텍스트 공유로 옮길지 여부를 이 시점에 판단한다.

```javascript
// OpenLayers 뷰 변경을 three.js 카메라에 동기화 (개념 예시)
map.on('postrender', () => {
  const view = map.getView();
  const center = view.getCenter();       // [x, y] in EPSG:3857 meters
  const resolution = view.getResolution();
  const rotation = view.getRotation();

  // 1) 지도 좌표를 three.js 로컬 좌표(원점 기준 상대 미터)로 변환
  const local = toLocalCoords(center, origin, latitudeScaleFactor);

  // 2) 카메라 위치·줌·회전을 반영해 투영행렬 갱신
  camera.position.set(local.x, local.y, cameraHeightFromResolution(resolution));
  camera.rotation.z = -rotation;
  camera.updateProjectionMatrix();

  threeRenderer.render(scene, camera);
});
```

## 마무리 요약

- "국소 3D 강조"와 "전역 3D 분석"을 먼저 구분해야 Cesium과 three.js+OpenLayers 중 과잉 설계를 피한다.
- 카메라 동기화는 OpenLayers의 `postrender` 이벤트에서 뷰 상태를 읽어 three.js 투영행렬을 매 프레임 갱신하는 구조다.
- 별도 캔버스 오버레이는 구현이 쉽지만 폐색 처리가 어색하고, GL 컨텍스트 공유는 자연스럽지만 `resetState()` 같은 상태 복구를 직접 관리해야 한다.

## 참고 자료

- OpenLayers 공식 문서 — View, postrender 이벤트
- Threebox(Mapbox GL JS + three.js) CameraSync 구현
- Google Maps Platform, WebGL Overlay View 문서
