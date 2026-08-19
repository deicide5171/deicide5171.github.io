---
layout: single
title: "시간까지 지도에 담다 — Cesium CZML로 만드는 시계열 동적 엔티티"
date: 2026-08-24 12:20:00 +0530
categories: gis
tags: ["cesium", "czml", "3d-webgis", "time-dynamic", "webgl", "satellite-tracking"]
toc: true
toc_sticky: true
excerpt: "위성 궤도나 차량 이동처럼 시간에 따라 위치가 바뀌는 데이터를 GeoJSON으로는 표현할 수 없는 이유를 짚고, Cesium의 CZML 포맷으로 시계열 동적 엔티티를 만드는 법을 정리한다."
---

위성이 지구를 도는 궤적, 배송 차량의 실시간 이동 경로, 태풍의 시간별 진로 — 이런 데이터는 "지금 여기 있다"는 정적인 좌표 하나로는 표현이 안 된다. GeoJSON은 애초에 시간 축이라는 개념이 없어서, 시간대별 스냅샷을 여러 Feature로 쪼개 넣거나 매 프레임 애플리케이션 코드로 좌표를 다시 계산해 넣어야 하는 번거로움이 생긴다.

Cesium의 CZML(Cesium Language)은 이 문제를 포맷 레벨에서 해결한다. 하나의 엔티티에 여러 시각의 좌표 샘플을 담고, Cesium 뷰어가 타임라인(Clock)이 흐르는 대로 그 사이를 보간해 부드럽게 움직이는 것까지 자동으로 처리한다. 이 글에서는 CZML의 구조, GeoJSON/KML과의 차이, 그리고 대량 엔티티를 다룰 때의 성능 고려사항을 정리한다.

## 핵심 개념 1: CZML의 패킷 구조

CZML은 JSON 배열이며, 배열의 각 원소를 "패킷(packet)"이라 부른다. 각 패킷은 하나의 엔티티(또는 문서 전체 설정)를 기술한다.

```json
[
  {
    "id": "document",
    "name": "위성 궤적 예제",
    "version": "1.0",
    "clock": {
      "interval": "2026-08-24T09:00:00Z/2026-08-24T12:00:00Z",
      "currentTime": "2026-08-24T09:00:00Z",
      "multiplier": 60
    }
  },
  {
    "id": "satellite-1",
    "availability": "2026-08-24T09:00:00Z/2026-08-24T12:00:00Z",
    "position": {
      "epoch": "2026-08-24T09:00:00Z",
      "cartographicDegrees": [
        0,    127.0, 37.5, 700000,
        3600, 135.2, 40.1, 705000,
        7200, 142.8, 35.3, 698000,
        10800, 150.1, 30.9, 702000
      ],
      "interpolationAlgorithm": "LAGRANGE",
      "interpolationDegree": 2
    },
    "point": { "pixelSize": 10, "color": { "rgba": [255, 210, 60, 255] } }
  }
]
```

`position.cartographicDegrees`는 `[초, 경도, 위도, 고도]`가 반복되는 시퀀스다. Cesium은 `clock.currentTime`이 두 샘플 사이를 지날 때 `interpolationAlgorithm`(LINEAR, LAGRANGE, HERMITE)에 따라 중간 위치를 계산한다. 문서 자체의 시간 범위와 재생 속도(`multiplier`)도 `document` 패킷 하나로 제어된다.

<img src="/assets/images/posts/2026-08-24-cesium-czml-time-dynamic-1.svg" alt="CZML 패킷의 시간별 좌표 샘플이 Clock 진행에 따라 보간되어 Cesium 지구본 위 엔티티 위치로 반영되는 구조도" style="width:100%;">

## 핵심 개념 2: GeoJSON·KML과 시간 지원 비교

| 구분 | GeoJSON | KML | CZML |
|---|---|---|---|
| 시간 축 네이티브 지원 | 없음(관례적 확장 필요) | `gx:Track`으로 제한적 지원 | 네이티브, 핵심 설계 목표 |
| 보간 방식 | 없음(직접 구현 필요) | 선형만 | LINEAR/LAGRANGE/HERMITE 선택 |
| 스트리밍 갱신 | 재요청·재파싱 필요 | 재요청 필요 | 패킷 추가로 점진적 갱신 가능 |
| 주 사용처 | 정적 벡터 데이터 | Google Earth 경로 | Cesium 3D 시계열 시각화 |

GeoJSON으로 시간 데이터를 억지로 표현하려면 결국 타임스탬프를 속성(property)에 넣고 애플리케이션이 매 프레임 필터링·보간하는 로직을 직접 짜야 한다. CZML은 이 책임을 포맷과 렌더러 쪽으로 옮겨, 애플리케이션 코드는 데이터만 공급하면 된다.

## 예제: CZML 로드와 Clock 바인딩 (JavaScript)

```javascript
const viewer = new Cesium.Viewer("cesiumContainer");

const dataSource = await Cesium.CzmlDataSource.load("satellite-track.czml");
viewer.dataSources.add(dataSource);

// CZML의 document.clock 설정을 뷰어 Clock/Timeline에 그대로 반영
viewer.clock.shouldAnimate = true;
viewer.timeline.zoomTo(dataSource.clock.startTime, dataSource.clock.stopTime);

// 엔티티를 계속 화면 중심에 따라가게 하려면
viewer.trackedEntity = dataSource.entities.getById("satellite-1");
```

`viewer.trackedEntity`를 지정하면 카메라가 엔티티의 보간된 위치를 매 프레임 따라가므로, 위성 추적 뷰 같은 것을 몇 줄로 구현할 수 있다.

## 실무 포인트

- **샘플 간격과 보간 알고리즘을 데이터 특성에 맞춘다**: 위성처럼 매끄러운 궤도는 `LAGRANGE`나 `HERMITE`가 자연스럽고, 신호등처럼 이산적으로 상태가 바뀌는 데이터는 `interpolationAlgorithm` 없이 `interval` 기반 스텝 값을 쓰는 것이 맞다. 잘못된 보간 알고리즘 선택은 실제로 존재하지 않는 경로로 엔티티가 미끄러지는 시각적 오류를 만든다.
- **대량 엔티티는 `interval` 기반 가용성으로 로드를 줄인다**: 수천 개의 시계열 엔티티를 한 번에 로드하면 초기 파싱과 메모리 사용량이 급증한다. `availability` 구간을 짧게 나눠 필요한 시간대의 패킷만 스트리밍으로 추가하는 방식이 실무에서 쓰인다.
- **좌표 정밀도와 고도 처리를 미리 검증한다**: `cartographicDegrees`는 WGS84 경위도/고도 기준이므로, 원본 데이터가 다른 좌표계(예: UTM)라면 CZML 생성 전 변환이 필요하다. 고도 값을 빠뜨리면 지형 위에 파묻히거나 붕 뜨는 렌더링 오류가 흔히 발생한다.

## 3줄 요약

- CZML은 하나의 엔티티에 여러 시각의 좌표 샘플을 담고 Cesium이 Clock 진행에 맞춰 자동 보간하는, 시계열 시각화를 위한 JSON 기반 포맷이다.
- GeoJSON/KML은 시간 축을 네이티브로 지원하지 않아 애플리케이션이 직접 보간 로직을 구현해야 하지만, CZML은 이를 포맷과 렌더러 책임으로 옮긴다.
- 데이터 특성에 맞는 보간 알고리즘 선택과, 대량 엔티티에서의 availability 기반 스트리밍 로드가 실무 적용의 핵심이다.

## 참고 자료

- [Cesium 공식 문서: CZML Guide](https://github.com/CesiumGS/cesium/wiki/CZML-Guide)
- [Cesium 공식 문서: CZML Structure](https://github.com/CesiumGS/cesium/wiki/CZML-Structure)
- [Cesium API 문서: CzmlDataSource](https://cesium.com/learn/cesiumjs/ref-doc/CzmlDataSource.html)
- [Cesium Sandcastle: CZML 예제 모음](https://sandcastle.cesium.com/)
