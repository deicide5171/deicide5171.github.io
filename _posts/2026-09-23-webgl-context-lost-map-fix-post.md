---
layout: single
title: "지도가 갑자기 하얗게 변할 때 — WebGL Context Lost 에러 원인과 복구 방법"
date: 2026-09-23 13:20:00 +0530
categories: gis
tags: ["webgl", "contextlost", "3d웹지도", "maplibre", "cesium"]
toc: true
toc_sticky: true
excerpt: "MapLibre나 Cesium으로 만든 3D 지도를 오래 켜두거나 다른 탭을 오가다 보면 갑자기 지도가 하얗게 변하고 아무 반응이 없어지는 WebGL Context Lost 문제를, 발생 원인과 자동 복구 코드로 정리했다."
---

## 왜 잘 쓰던 지도가 갑자기 하얗게 변할까

MapLibre GL JS나 Cesium으로 만든 3D 지도를 브라우저에 오래 켜두거나, 노트북을 절전 모드에 뒀다 다시 켜거나, GPU를 많이 쓰는 다른 탭을 여러 개 열어두면 지도 화면이 갑자기 새하얀 캔버스로 변하고 이후 어떤 조작에도 반응하지 않는 현상을 겪게 된다. 콘솔을 열어보면 에러 메시지 하나 없이 조용히 멈춰 있거나, 자세히 찾아보면 `webglcontextlost` 이벤트가 발생했다는 로그를 뒤늦게 발견하게 된다.

이 현상은 애플리케이션 코드의 버그라기보다 **브라우저와 운영체제가 GPU 자원을 관리하는 방식** 때문에 발생한다. WebGL 컨텍스트는 유한한 GPU 자원을 여러 탭·프로세스가 나눠 쓰는 구조라, 시스템이 메모리 압박을 받거나 GPU 드라이버가 크래시하면 브라우저는 특정 탭의 WebGL 컨텍스트를 강제로 회수해버릴 수 있다.

## 핵심 개념 1 — Context Lost는 예외가 아니라 이벤트로 알려진다

WebGL 컨텍스트가 유실되는 것은 자바스크립트 예외(try/catch로 잡히는 에러)가 아니라, `<canvas>` 엘리먼트에서 발생하는 `webglcontextlost`라는 별도의 이벤트로 통지된다. 이 이벤트를 리스닝하고 있지 않다면 애플리케이션은 아무 알림도 받지 못한 채 그냥 렌더링이 멈춰버린다. 그리고 컨텍스트가 유실되면 그동안 GPU에 업로드해뒀던 텍스처, 셰이더, 버퍼가 전부 사라지므로, 단순히 다시 그리라고 명령해도 아무것도 나타나지 않는다 — 처음부터 다시 만들어 올려야 한다.

<img src="/assets/images/posts/2026-09-23-webgl-context-lost-map-fix-1.svg" alt="GPU 자원 압박이나 드라이버 크래시로 브라우저가 WebGL 컨텍스트를 회수하면 webglcontextlost 이벤트가 발생하고, preventDefault로 복구를 허용한 뒤 webglcontextrestored 이벤트에서 지도 리소스를 다시 초기화하는 흐름을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 복구는 자동이 아니라 명시적으로 허가해야 한다

브라우저는 컨텍스트를 되살릴 수 있는 상황이면 `webglcontextrestored` 이벤트를 발생시켜 재생성 기회를 주지만, 기본 동작은 "복구하지 않음"이다. `webglcontextlost` 이벤트 핸들러 안에서 `event.preventDefault()`를 호출해야만 브라우저가 복구를 시도한다. 이 한 줄을 빠뜨리면 이벤트를 리스닝하고 있어도 컨텍스트는 영영 복구되지 않는다.

## 예제 — MapLibre GL JS에서 Context Lost 감지 및 복구

```javascript
const canvas = map.getCanvas();

canvas.addEventListener('webglcontextlost', (event) => {
  event.preventDefault();  // 이걸 빠뜨리면 브라우저가 복구를 아예 시도하지 않는다
  console.warn('WebGL 컨텍스트 유실 — 복구 대기 중');
  showReloadBanner();  // 사용자에게 상황을 알리는 배너 표시
});

canvas.addEventListener('webglcontextrestored', () => {
  console.info('WebGL 컨텍스트 복구됨 — 지도 리소스를 다시 초기화');
  // 대부분의 최신 지도 라이브러리는 내부적으로 스타일을 재적용하지만,
  // 커스텀 레이어나 커스텀 텍스처는 직접 다시 로드해야 하는 경우가 많다
  map.setStyle(map.getStyle());  // 강제로 스타일을 재적용해 안전하게 리소스 재생성
  hideReloadBanner();
});
```

Cesium을 쓰는 경우도 원리는 같다. `viewer.scene.canvas`에 같은 방식으로 이벤트를 걸고, 복구 시점에는 지형·타일셋·엔티티를 다시 로드하는 로직을 실행해야 한다. 다만 Cesium은 내부 상태가 훨씬 복잡해 완전 자동 복구가 보장되지 않는 경우가 많으므로, 실무에서는 복구를 시도하는 대신 아예 페이지를 새로고침하도록 유도하는 편이 안전할 때도 있다.

## 발생 원인과 대응 정리

| 원인 | 발생 상황 | 대응 |
|---|---|---|
| GPU 메모리 압박 | 여러 3D 탭 동시 실행, 대용량 텍스처 과다 사용 | 텍스처 해상도 최적화, 안 쓰는 레이어 제거 |
| 노트북 절전/GPU 전원 전환 | 외장 GPU ↔ 내장 GPU 전환 시 | contextrestored 핸들러로 재초기화 |
| GPU 드라이버 크래시 | 드라이버 버그, 오래된 드라이버 | 사용자에게 새로고침 안내 |
| 브라우저의 탭별 컨텍스트 총량 제한 | 동시에 열린 WebGL 탭이 많음 | 불필요한 지도 인스턴스 언마운트 |

## 실무 포인트

- **이벤트 리스너는 지도 생성 직후 반드시 등록하라.** Context Lost는 언제 발생할지 예측할 수 없으므로, 지도 초기화 코드와 한 세트로 항상 함께 등록해야 실전에서 놓치지 않는다.
- **복구 실패 시 사용자에게 명확한 안내를 제공하라.** 자동 복구가 항상 성공하는 것은 아니므로, 일정 시간 안에 `webglcontextrestored`가 발생하지 않으면 "지도를 새로고침해주세요" 같은 안내로 전환하는 타임아웃 로직을 추가하는 것이 좋다.
- **모바일 환경에서는 특히 더 자주 발생할 수 있다.** 모바일 브라우저는 데스크톱보다 GPU 메모리 여유가 훨씬 적어 여러 앱을 오가는 것만으로도 컨텍스트가 회수될 수 있으므로, 모바일 대상 서비스라면 복구 로직 테스트를 반드시 실제 기기에서 해봐야 한다.

## 마무리 요약

- WebGL Context Lost는 자바스크립트 예외가 아니라 별도 이벤트로 통지되며, GPU 자원 관리 때문에 애플리케이션 버그 없이도 발생할 수 있다.
- `webglcontextlost` 핸들러에서 `preventDefault()`를 호출해야만 브라우저가 복구를 시도하며, 이걸 빠뜨리면 컨텍스트는 영영 복구되지 않는다.
- 복구 시점에는 텍스처·버퍼가 모두 사라진 상태이므로 스타일과 리소스를 처음부터 다시 로드해야 하고, 복구가 오래 걸리면 새로고침 안내로 전환하는 것이 안전하다.

## 참고 자료

- [MDN - WebGL_API/WebGL_best_practices (Context Loss 섹션)](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices)
- [Khronos WebGL 명세 - Context Loss](https://www.khronos.org/registry/webgl/specs/latest/1.0/#5.15.2)
