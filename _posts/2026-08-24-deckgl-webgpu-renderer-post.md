---
layout: single
title: "WebGL 다음은 WebGPU — deck.gl 렌더러 마이그레이션 실전"
date: 2026-08-24 13:20:00 +0530
categories: gis
tags: ["deckgl", "webgpu", "webgl", "lumagl", "3d-webgis", "point-cloud"]
toc: true
toc_sticky: true
excerpt: "대용량 포인트클라우드·3D 지도 렌더링에서 WebGL의 구조적 한계를 짚고, deck.gl이 luma.gl 추상화 계층을 통해 WebGPU 렌더러로 전환하는 배경과 실무 마이그레이션 고려사항을 정리한다."
---

수백만 포인트를 그리는 3D 웹 지도에서 WebGL의 병목은 렌더링 자체보다 CPU-GPU 사이의 커맨드 전달 오버헤드와, 필터링·집계 같은 범용 연산을 GPU에서 직접 할 수 없다는 구조적 한계에서 온다. WebGL은 그래픽 렌더링에 특화된 API라서, 포인트 개수가 늘어날수록 CPU 쪽에서 매 프레임 상태를 다시 설정하고 드로우 콜을 쌓는 비용이 커진다.

WebGPU는 이 문제를 겨냥해 설계된 차세대 브라우저 그래픽 API다. 명령형 상태 머신 대신 커맨드 버퍼 기반의 명시적 API를 쓰고, 컴퓨트 셰이더를 네이티브로 지원해 그래픽 렌더링이 아닌 범용 GPU 연산도 브라우저에서 실행할 수 있다. deck.gl은 자체 GPU 추상화 계층인 luma.gl을 통해 이 새 렌더러로의 전환을 점진적으로 지원하고 있다. 이 글에서는 두 API의 구조적 차이와 마이그레이션 시 고려할 지점을 정리한다.

## 핵심 개념 1: WebGL과 WebGPU의 아키텍처 차이

WebGL은 OpenGL ES를 브라우저에 옮긴 것으로, 전역 상태를 바인딩하고 그리는 명령형 스타일이다. 셰이더 프로그램을 바인딩하고, 버퍼를 바인딩하고, 유니폼을 설정하고, 드로우 콜을 호출하는 절차가 매 프레임 반복된다. 이 상태 전환 하나하나가 드라이버 검증을 거치므로 CPU 오버헤드가 누적된다.

WebGPU는 커맨드를 미리 인코딩해 커맨드 버퍼로 한 번에 제출하는 방식을 쓴다. 파이프라인 상태(셰이더, 렌더 상태 등)를 사전에 객체로 컴파일해두고 재사용할 수 있어, 매 프레임 반복되는 검증 비용이 크게 줄어든다. 또한 컴퓨트 셰이더를 네이티브 지원해, "화면에 보이는 포인트만 필터링" 같은 연산을 CPU가 아니라 GPU 병렬 처리로 옮길 수 있다.

<img src="/assets/images/posts/2026-08-24-deckgl-webgpu-renderer-1.svg" alt="deck.gl이 luma.gl 추상화 계층을 통해 WebGL과 WebGPU 두 렌더러를 모두 지원하는 구조, WebGPU가 컴퓨트 셰이더와 커맨드 버퍼 기반 API로 GPU 하드웨어에 접근하는 파이프라인 다이어그램" style="width:100%;">

## 핵심 개념 2: WebGL vs WebGPU 비교

| 구분 | WebGL | WebGPU |
|---|---|---|
| API 스타일 | 명령형 상태 머신 | 커맨드 버퍼 기반 명시적 API |
| 컴퓨트 셰이더 | 미지원(정점/프래그먼트만) | 네이티브 지원 |
| CPU 오버헤드 | 상태 전환마다 드라이버 검증 | 파이프라인 사전 컴파일로 절감 |
| 멀티스레드 커맨드 생성 | 제한적 | 워커에서 병렬 인코딩 가능 |
| 브라우저 지원 | 사실상 전 브라우저 | 확대 중(브라우저별 지원 시점 확인 필요) |

deck.gl 관점에서 WebGPU의 실질적 이득은 대용량 레이어(`PointCloudLayer`, `ScatterplotLayer`에 수백만 개 요소)에서 두드러진다. 컴퓨트 셰이더로 뷰포트 밖 포인트를 GPU에서 미리 걸러내거나, 집계(aggregation) 연산을 GPU로 옮기면 CPU 쪽 병목이 크게 줄어든다.

## 예제: deck.gl에서 WebGPU 디바이스 지정

```javascript
import { Deck } from '@deck.gl/core';
import { WebGPUDevice } from '@luma.gl/webgpu';

const deck = new Deck({
  // luma.gl의 Device 추상화를 통해 렌더러를 선택
  deviceProps: {
    type: 'webgpu', // 'webgl'로 두면 기존 방식 유지
  },
  initialViewState: {
    longitude: 127.0, latitude: 37.5, zoom: 10
  },
  layers: [
    new PointCloudLayer({
      id: 'point-cloud',
      data: 'https://example.com/large-pointcloud.bin',
      getPosition: d => d.position,
      pointSize: 2
    })
  ]
});
```

`deviceProps.type`을 명시하지 않으면 luma.gl은 브라우저 지원 여부를 감지해 WebGPU를 우선 시도하고 지원하지 않으면 WebGL로 자동 폴백하는 방식을 지향한다. 프로덕션에서는 명시적으로 지정하고 `@supports`에 준하는 기능 감지 후 분기하는 것이 안전하다.

## 실무 포인트

- **브라우저 지원 현황을 배포 전에 반드시 재확인한다**: WebGPU는 브라우저별로 지원 시점과 활성화 조건(플래그, 버전)이 계속 바뀌고 있는 영역이므로, 이 글에서 단정하기보다 각 배포 시점의 Can I Use나 브라우저 공식 릴리스 노트를 직접 확인해야 한다. 지원하지 않는 브라우저를 위한 WebGL 폴백 경로는 항상 유지해야 한다.
- **luma.gl 버전과 deck.gl 버전의 호환 매트릭스를 확인한다**: WebGPU 지원은 두 라이브러리 모두 활발히 개발 중인 영역이라, 마이너 버전 간에도 API가 바뀔 수 있다. 마이그레이션 전에 공식 체인지로그에서 WebGPU 관련 변경사항을 반드시 검토해야 한다.
- **성능 이득은 데이터 규모와 레이어 종류에 따라 다르다**: 포인트 수가 적은 레이어에서는 WebGPU 전환 효과가 미미하거나 오히려 초기화 오버헤드가 늘어날 수 있다. 실제 프로덕션 데이터 규모로 두 렌더러를 벤치마크한 뒤 전환 여부를 결정하는 것이 안전하다.

## 3줄 요약

- WebGPU는 커맨드 버퍼 기반의 명시적 API와 네이티브 컴퓨트 셰이더 지원으로, WebGL의 상태 전환 오버헤드와 GPU 범용 연산 부재라는 구조적 한계를 해결한다.
- deck.gl은 luma.gl 추상화 계층을 통해 WebGL/WebGPU 렌더러를 모두 지원하며, 대용량 포인트클라우드 레이어에서 이득이 가장 크게 나타난다.
- 브라우저 지원 현황과 라이브러리 버전 호환성을 배포 시점마다 재확인하고, 실제 데이터 규모로 벤치마크한 뒤 전환을 결정하는 것이 실무에서 중요하다.

## 참고 자료

- [deck.gl 공식 문서: Device (WebGL/WebGPU) API](https://deck.gl/docs/api-reference/core/deck)
- [luma.gl 공식 문서: WebGPU Backend](https://luma.gl/docs/api-reference/webgpu/webgpu-device)
- [W3C WebGPU 공식 스펙](https://www.w3.org/TR/webgpu/)
- [MDN: WebGPU API](https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API)
