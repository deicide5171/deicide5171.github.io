---
layout: single
title: "지도를 손안의 공간에 겹치다 — WebXR·AR 기반 공간 데이터 시각화"
date: 2026-08-29 12:20:00 +0530
categories: gis
tags: ["webxr", "ar", "geospatial", "3d-tiles", "webgl", "gis"]
toc: true
toc_sticky: true
excerpt: "브라우저에서 별도 앱 설치 없이 실행되는 WebXR로 GIS 데이터를 실제 공간에 증강해 보여주는 원리와, 좌표계 정합·앵커링 문제를 정리한다."
---

지금까지 웹 지도는 대부분 평면(2D 팬·줌) 또는 화면 안의 3D 뷰(Cesium, deck.gl의 3D 모드)로 표현돼 왔다. 사용자가 지도를 "보는" 것이지, 실제 공간 속에 그 데이터를 "겹쳐서" 체험하는 것은 아니었다. WebXR은 이 경계를 흐린다. 별도 네이티브 앱 설치 없이 브라우저만으로 카메라 영상 위에 3D 콘텐츠를 증강(AR)하거나, 몰입형 VR 세션을 열 수 있게 하는 W3C 표준 API라서, 웹 지도 라이브러리들이 여기에 GIS 데이터를 얹는 실험을 이어가고 있다.

다만 WebXR 기반 공간 시각화는 일반적인 웹 지도와는 다른 종류의 문제를 마주한다. 지리 좌표계(WGS84, 미터 단위 투영 좌표)와 기기의 로컬 추적 좌표계(기기를 켠 시점을 원점으로 하는 상대 좌표)를 정합해야 하고, 실제 물리 공간에 가상의 지형·건물을 정확히 앵커링하는 문제도 따라온다. 이 글에서는 WebXR의 동작 원리와, GIS 데이터를 여기에 올릴 때 부딪히는 좌표계·앵커링 문제를 정리한다.

## 핵심 개념 1: WebXR Device API의 두 가지 세션 모드

WebXR Device API는 크게 두 세션 모드를 제공한다.

- **`immersive-vr`**: 헤드셋을 쓰고 실제 주변 환경과 무관한 가상 공간에 몰입하는 모드. 3D 도시 모델을 통째로 걸어 다니며 살펴보는 디지털 트윈 시연 등에 쓰인다.
- **`immersive-ar`**: 스마트폰이나 AR 글래스의 카메라 영상 위에 3D 콘텐츠를 겹쳐 보여주는 모드. 실제 거리에 서서 스마트폰을 들면 화면에 지하 매설물이나 예정된 건물의 매스가 겹쳐 보이는 식의 활용이 여기 해당한다.

두 모드 모두 `navigator.xr.requestSession()`으로 세션을 요청하고, 매 프레임 `XRFrame`에서 기기의 위치·자세(pose)를 받아 렌더링 좌표계를 갱신한다. 실제 렌더링은 WebXR API 자체가 아니라 WebGL(또는 WebGPU) 컨텍스트에서 이뤄지며, WebXR은 그 컨텍스트에 "지금 카메라가 실제 공간에서 어디에 있고 어느 방향을 보는지"를 넘겨주는 역할을 한다.

## 핵심 개념 2: 지리 좌표계와 로컬 추적 좌표계의 정합

여기서 GIS 특유의 문제가 시작된다. WebXR이 기본으로 제공하는 좌표계(`local`, `local-floor`, `bounded-floor`, `unbounded`)는 모두 **세션을 시작한 시점의 기기 위치를 원점으로 하는 상대 좌표계**다. 반면 GIS 데이터는 위도·경도·고도(WGS84) 또는 특정 투영 좌표계로 저장돼 있다. 이 둘을 맞추려면 세션 시작 시점에 기기의 실제 지리 좌표(GPS)를 별도로 얻어, "이 로컬 원점이 지리 좌표계의 어느 지점에 해당하는가"를 계산해 변환 행렬을 만들어야 한다.

실무에서는 이 변환을 위해 지역 접평면 좌표계(ENU: East-North-Up)를 중간 단계로 흔히 쓴다. GPS로 얻은 기준점을 원점으로 ENU 좌표계를 구성하고, GIS 데이터의 위경도를 ENU로 변환한 뒤, 다시 WebXR의 로컬 좌표계와 정합하는 식이다. 스마트폰 GPS의 수평 오차가 통상 수 미터 수준이라, 이 초기 정합 오차가 이후 증강되는 콘텐츠의 위치 오차로 그대로 이어진다는 점이 WebXR AR을 GIS에 쓸 때 가장 먼저 부딪히는 한계다.

<img src="/assets/images/posts/2026-08-29-webxr-ar-geospatial-viz-1.svg" alt="WGS84 위경도 좌표를 ENU 접평면 좌표로 변환한 뒤 WebXR의 로컬 추적 좌표계와 정합하는 파이프라인, 그리고 앵커로 위치를 고정하는 구조" style="width:100%;">

## 핵심 개념 3: 앵커(Anchor)로 위치를 고정한다

WebXR AR에서 콘텐츠를 실제 공간의 한 지점에 "고정"해두는 기능이 **앵커(Anchor)**다. 앵커 없이 초기 정합만으로 콘텐츠를 배치하면, 기기가 움직이는 동안 센서 드리프트(누적 오차)가 쌓여 시간이 지날수록 가상 콘텐츠가 실제 위치에서 서서히 벗어나 보인다. WebXR Anchors API는 특정 위치에 앵커를 생성해두면, 기기의 SLAM(동시적 위치추정 및 지도작성) 시스템이 그 앵커의 실제 공간상 위치를 지속적으로 재보정해 드리프트를 줄여준다.

대규모 GIS 콘텐츠(건물 전체, 도로망)를 다룰 때는 단일 앵커 하나로는 부족하고, 여러 지점에 앵커를 분산 배치한 뒤 그 사이를 보간하는 전략이 쓰인다. 또한 실외처럼 GPS 신호는 있지만 시각적 특징점이 부족한 환경(넓은 공터, 잔디밭)에서는 SLAM 기반 앵커의 재보정 품질이 떨어질 수 있어, 특징점이 풍부한 지물(건물 모서리, 표지판) 근처에서 초기 앵커를 잡는 것이 실무 팁으로 통용된다.

| 구분 | 일반 웹 지도(2D/3D) | WebXR AR 공간 시각화 |
|---|---|---|
| 좌표계 | 지리 좌표계/투영 좌표계 단일 | 지리 좌표계 + 기기 로컬 좌표계 정합 필요 |
| 위치 정확도 기준 | 타일·벡터 렌더링 정확도 | GPS 오차 + SLAM 드리프트 누적 |
| 대표 API | Leaflet, MapLibre, Cesium | WebXR Device API + WebGL/WebGPU |
| 위치 고정 방식 | 지도 좌표 자체가 기준 | Anchor로 실제 공간에 재보정 |
| 대표 활용 | 지도 탐색, 경로 안내 | 현장 실측 확인, 지하 시설물 증강, 건축 매스 스터디 |

## 예제: WebXR AR 세션에서 지리 좌표를 ENU로 변환해 배치

```javascript
// 1. AR 세션 시작 시 기준 GPS 좌표 확보 (최초 1회)
const refPosition = await getCurrentGPSPosition(); // { lat, lon, alt }

// 2. WGS84 위경도를 기준점 중심의 ENU(동-북-상) 미터 좌표로 변환
function wgs84ToENU(lat, lon, alt, ref) {
  const R = 6378137; // WGS84 장반경(m)
  const dLat = (lat - ref.lat) * Math.PI / 180;
  const dLon = (lon - ref.lon) * Math.PI / 180;
  const east = dLon * R * Math.cos(ref.lat * Math.PI / 180);
  const north = dLat * R;
  const up = alt - ref.alt;
  return { x: east, y: up, z: -north }; // WebGL 좌표계(Y-up)로 매핑
}

// 3. XRFrame마다 로컬 추적 좌표계 기준으로 3D 오브젝트 위치 갱신
function onXRFrame(time, frame) {
  const pose = frame.getViewerPose(referenceSpace);
  if (!pose) return;
  buildingMesh.position.set(enuPosition.x, enuPosition.y, enuPosition.z);
  // 앵커가 있다면 앵커의 재보정된 pose로 위치를 주기적으로 덮어써 드리프트 완화
  session.requestAnimationFrame(onXRFrame);
}
```

## 실무 포인트

- **GPS 정확도의 한계를 사용자에게 알린다**: 스마트폰 GPS만으로는 실내·고층 밀집 지역에서 수십 미터까지 오차가 날 수 있다. 정밀한 위치 정합이 필요한 서비스라면 RTK 보정이나 시각 기반 위치 인식(VPS)을 병행하는 것을 고려해야 한다.
- **앵커 재계산 빈도와 성능을 함께 본다**: 앵커를 과도하게 많이 생성하면 SLAM 재계산 부하가 늘어 프레임이 떨어질 수 있다. 콘텐츠 밀도에 맞춰 앵커 개수를 최소화하는 것이 좋다.
- **기기·브라우저 지원 범위를 사전에 확인한다**: WebXR immersive-ar 세션은 모든 브라우저·기기에서 동일하게 지원되지 않으므로, 미지원 환경을 위한 폴백(2D/3D 지도 뷰)을 함께 준비하는 것이 실무에서는 필수적이다.

## 3줄 요약

- WebXR은 별도 앱 설치 없이 브라우저에서 AR/VR 세션을 열 수 있는 W3C 표준으로, GIS 데이터를 실제 공간에 증강하는 실험의 기반이 되고 있다.
- WebXR의 로컬 추적 좌표계는 GIS의 지리 좌표계와 원점·단위가 다르므로, ENU 접평면 좌표를 매개로 한 변환과 정합 과정이 필요하다.
- Anchor로 콘텐츠를 실제 공간에 고정해 센서 드리프트를 줄일 수 있지만, GPS 초기 정합 오차와 SLAM 재보정 품질이 최종 위치 정확도의 한계를 결정한다.

## 참고 자료

- [W3C WebXR Device API 명세](https://www.w3.org/TR/webxr/)
- [W3C WebXR Anchors Module 명세](https://immersive-web.github.io/anchors/)
- [MDN: WebXR Device API 가이드](https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API)
