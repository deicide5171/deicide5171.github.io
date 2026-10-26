---
layout: single
title: "\"브라우저 없이 서버에서 가시선만 계산해주세요\" — CesiumJS가 엔진에서 코어를 뽑아낸 이유"
date: 2026-10-26 12:45:00 +0530
categories: gis
tags: ["cesium", "3dtiles", "패키지분리", "서버사이드gis", "번들최적화"]
toc: true
toc_sticky: true
excerpt: "지도를 띄우지 않고 좌표 변환이나 가시선 계산만 서버 배치로 돌리고 싶다는 요구에서, CesiumJS는 오랫동안 WebGL 렌더링 엔진 전체를 끌고 와야 했다. 2026년 10월 1.146 릴리스로 분리된 @cesium/core 패키지가 이 요구를 어떻게 풀어내는지, 기존 대안과의 트레이드오프까지 정리했다."
---

## 도입

"매장 간 가시선이 확보되는지 수만 쌍을 미리 계산해서 배치로 돌려주세요. 지도를 매번 띄워서 확인할 순 없잖아요." 이런 요구는 브라우저도 사용자도 없는 서버 환경에서 순수 기하 연산만 필요하다는 뜻이다. 문제는 CesiumJS가 오랫동안 이 기하 연산용 클래스(Cartesian3, Transforms, 좌표계 변환 등)를 WebGL 기반 렌더링 엔진인 `@cesium/engine` 패키지 안에 함께 묶어 배포해 왔다는 점이다. 서버에서 좌표 계산 함수 몇 개만 쓰고 싶어도, 브라우저 렌더링에 필요한 셰이더·타일 로더·씬 그래프 코드까지 전부 설치 트리에 따라왔다.

2026년 10월 1일 출시된 CesiumJS 1.146은 이 구조를 바꿨다. 수학·지오메트리·시간·유틸리티 클래스를 `@cesium/engine`에서 떼어내 독립된 `@cesium/core` 패키지로 분리한 것이다. 이 글은 "렌더링 없이 연산만 쓰고 싶다"는 요구가 왜 패키지 분리라는 아키텍처 변화로 이어지는지, 그리고 이걸 실제 프로젝트에 어떻게 반영할지 정리한다.

## 전체 시스템에서의 위치

기존 구조에서는 지도 애플리케이션이든 서버 배치 스크립트든 상관없이 `@cesium/engine`을 설치하면 렌더링 코드와 수학 연산 코드가 한 덩어리로 따라왔다. 분리 이후에는 연산 전용 레이어와 렌더링 레이어가 독립된 의존성 그래프를 갖는다.

<img src="/assets/images/posts/2026-10-26-cesium-core-package-split-1.svg" alt="분리 전후 CesiumJS 패키지 의존성 구조 비교" style="width:100%;">

- **분리 전**: 서버 배치 작업이 좌표 변환 함수 하나만 쓰려 해도 `@cesium/engine` 전체(WebGL 컨텍스트, 타일 스트리밍, 씬 렌더 루프)를 설치 트리에 포함해야 했다.
- **분리 후**: 서버 배치 작업은 `@cesium/core`만 설치해 수학·지오메트리 함수를 그대로 쓰고, 브라우저 지도 애플리케이션은 `@cesium/engine`이 내부적으로 `@cesium/core`를 의존성으로 가져가는 구조로 바뀐다.
- `cesium` 메인 패키지로 임포트하던 코드는 변경이 필요 없다. 영향을 받는 것은 `@cesium/engine`에서 직접 수학·지오메트리 클래스를 가져오던 코드뿐이다.

## 선택의 트레이드오프

| 방식 | 설치 부담 | 기능 범위 | 적합한 상황 |
|---|---|---|---|
| `@cesium/core`만 설치 | 가볍다 (WebGL·타일 로더 제외) | 좌표 변환·지오메트리·시간 연산 | 서버 배치, 헤드리스 연산, Node.js 파이프라인 |
| 기존 `@cesium/engine` 전체 설치 | 무겁다 (렌더링 코드 포함) | 연산 + 렌더링 전부 | 브라우저에서 실제로 3D 지도를 그릴 때 |
| turf.js + proj4js 조합 | 가볍다 | 2D 평면 기하 연산 중심 | 3D Tiles·지구 타원체 좌표계가 필요 없는 2D 지도 서비스 |
| PostGIS 함수(ST_DWithin 등) | DB 서버에 의존 | SQL 안에서 바로 실행 | 이미 PostGIS에 데이터가 있고 대량 공간 쿼리가 주 용도인 경우 |

판단 기준은 **연산이 지구 타원체·3D 좌표계를 다루는가**이다. 위경도-ECEF 변환, 3D 공간상 가시선·고도 계산처럼 Cesium이 원래 강점을 가진 영역이라면 `@cesium/core`가 가장 적은 설치 부담으로 같은 연산 로직을 서버에 그대로 옮길 수 있다. 반대로 평면 좌표계에서의 버퍼·교차 같은 2D 연산이 전부라면 turf.js가 더 가볍고, 이미 데이터가 DB에 있다면 PostGIS 함수로 끝내는 쪽이 네트워크 왕복 자체를 없앤다.

## 실제 프로젝트 진행 순서

1. **기존 코드에서 `@cesium/engine`을 직접 import하는 지점을 전수 조사한다.** `cesium` 메인 패키지로 가져오던 코드는 그대로 둬도 된다.
2. **Math, Cartesian3, Transforms, JulianDate 등 연산 클래스만 쓰는 import를 `@cesium/core`로 바꾼다.** 렌더링 관련 클래스(Viewer, Scene, Cesium3DTileset 등)는 계속 `@cesium/engine`에 남는다.
3. **마이그레이션 기한을 확인한다.** `@cesium/engine`의 재노출(re-export)은 1.150에서 제거될 예정이므로, 지금 미루면 나중에 한 번에 더 큰 변경을 떠안는다.
4. **서버 환경에서 설치 후 번들·설치 용량을 비교한다.** 브라우저 전용 API(WebGL 컨텍스트, DOM 접근)를 호출하는 코드가 섞여 있지 않은지 함께 검증한다.
5. **배치 작업에 실제로 적용해본다.** 가시선·좌표 변환 로직을 Node.js 배치 스크립트로 옮기고, 기존에 브라우저를 띄워 수동으로 확인하던 과정을 자동화된 배치로 대체한다.

```javascript
// 분리 전: @cesium/engine에서 연산 클래스까지 함께 가져오던 코드
// import { Cartesian3, Transforms } from "@cesium/engine";

// 분리 후: 서버 배치에서는 연산 전용 패키지만 설치
import { Cartesian3, Transforms, JulianDate } from "@cesium/core";

const origin = Cartesian3.fromDegrees(127.05, 37.5, 30);
const target = Cartesian3.fromDegrees(127.06, 37.51, 45);
const matrix = Transforms.eastNorthUpToFixedFrame(origin);
// 렌더링 엔진 없이 좌표 변환·거리 계산만 서버에서 배치로 수행
```

## 실무 포인트

- `@cesium/core`는 렌더링 의존성이 없을 뿐, API 자체는 `@cesium/engine`이 쓰던 것과 동일하다. 기존 지식과 코드 자산을 그대로 재사용할 수 있다는 게 가장 큰 이점이다.
- 가시선 연산처럼 3D Tiles 지형 데이터를 실제로 읽어야 하는 작업은 코어만으로는 부족하다 — 타일 로딩 자체는 여전히 엔진 영역이므로, 사전에 추출한 지형 메시나 DEM을 직접 다루는 방식으로 설계해야 한다.
- 메인 `cesium` 패키지를 쓰는 기존 프로젝트는 당장 아무것도 바꾸지 않아도 되지만, 1.150 제거 시점 전에 `@cesium/engine` 직접 import 코드가 있는지 한 번은 점검해두는 편이 안전하다.

## 마무리

- CesiumJS 1.146의 `@cesium/core` 분리는 "렌더링 없이 연산만 쓰고 싶다"는 요구를 패키지 의존성 구조로 직접 풀어낸 변화다.
- 선택 기준은 연산이 지구 타원체·3D 좌표계를 다루는지이며, 2D 평면 연산이면 turf.js, DB 안 대량 쿼리면 PostGIS가 더 맞을 수 있다.
- 적용 순서는 import 전수 조사 → 연산 클래스만 분리 → 마이그레이션 기한 확인 → 서버 환경 검증 → 배치 작업 적용이다.

## 참고 자료

- [Cesium Releases in October 2026](https://cesium.com/blog/2026/10/02/cesium-releases-in-october-2026/)
- [CesiumJS CHANGES.md](https://cdn.jsdelivr.net/npm/cesium@1.146.0/CHANGES.md)
- [CesiumJS 공식 문서](https://cesium.com/learn/cesiumjs/ref-doc/)
