---
layout: single
title: "벡터 타일이 화면 픽셀이 되기까지 — WebGL 지도 렌더링 파이프라인 해부"
date: 2026-08-17 12:20:00 +0530
categories: gis
tags: ["webgl", "vector-tile", "shader", "gpu-rendering", "glsl"]
toc: true
toc_sticky: true
excerpt: "Mapbox GL, MapLibre 같은 웹 지도가 수만 개의 도로·건물 폴리곤을 매끄럽게 줌·회전시킬 수 있는 이유를, 라이브러리 API가 아니라 벡터 타일이 GPU 픽셀로 변환되는 렌더링 파이프라인 원리로 파헤친다."
---

## 왜 지금 렌더링 파이프라인을 알아야 하는가

Mapbox GL이나 MapLibre로 지도를 붙여본 사람은 많지만, `map.addLayer()` 한 줄 뒤에서 실제로 무슨 일이 일어나는지 아는 사람은 적다. Canvas 2D로 그리던 예전 웹 지도와 달리, 지금의 웹 지도 라이브러리는 예외 없이 **WebGL**을 쓴다. 이유는 단순하다 — 수만 개의 도로·건물·라벨 폴리곤을 60fps로 줌·회전시키려면 CPU가 픽셀을 하나씩 그리는 방식으로는 감당이 안 되고, GPU의 수천 개 병렬 코어로 좌표 변환과 픽셀 색칠을 동시에 처리해야 한다.

이 블로그는 앞서 Cesium 3D Tiles의 LOD 트리 구조, deck.gl의 대용량 포인트 시각화, OpenLayers 커스텀 웹맵을 다뤘지만, 정작 "그 아래에서 GPU가 실제로 무엇을 하는가"는 다루지 않았다. 라이브러리마다 API는 다르지만 벡터 데이터가 화면 픽셀이 되는 파이프라인 자체는 동일한 원리를 따른다. 이 원리를 알면 왜 특정 스타일 설정이 프레임 드랍을 유발하는지, 왜 줌 애니메이션은 부드러운데 데이터 리로드는 버벅이는지가 설명된다.

## 핵심 개념 1: 벡터 타일에서 지오메트리로

웹 지도 서버는 좌표 원본을 그대로 보내지 않는다. 대신 타일 단위로 잘라 압축한 **벡터 타일(MVT, Mapbox Vector Tile)** 을 protobuf 바이너리로 내려보낸다. 브라우저가 받는 즉시 그릴 수 있는 형태가 아니라, 폴리곤 윤곽선과 속성 정보만 담긴 압축 데이터다.

여기서부터 CPU(JavaScript 메인 스레드 또는 워커)가 세 단계를 거친다. 첫째, protobuf를 디코딩해 좌표 배열로 복원한다. 둘째, GPU는 삼각형만 그릴 수 있으므로 건물 폴리곤 같은 복잡한 도형을 삼각형들로 쪼개는 **삼각분할(Tessellation)** 을 수행한다. 셋째, 이 삼각형들의 정점 좌표를 `Float32Array` 형태의 **정점 버퍼(Vertex Buffer Object)** 로 정리해 GPU에 업로드할 준비를 한다. 이 단계가 무거울수록 타일 로드 시 프레임이 끊기는 원인이 된다.

## 핵심 개념 2: 셰이더 — CPU가 GPU에 내리는 명령

버퍼가 GPU로 업로드되면, 실제 그리기는 두 종류의 작은 프로그램인 **셰이더(Shader)** 가 담당한다. GLSL(OpenGL Shading Language)로 작성되며 GPU 코어에서 병렬 실행된다.

| 셰이더 종류 | 실행 단위 | 하는 일 | 지도에서의 예 |
|---|---|---|---|
| 버텍스 셰이더 | 정점 하나당 1회 | 모델 좌표 → 화면 클립 좌표 변환(투영·줌·회전 적용) | 위경도를 화면 픽셀 위치로 매핑 |
| 프래그먼트 셰이더 | 픽셀(프래그먼트) 하나당 1회 | 최종 색상·투명도 계산 | 폴리곤 채우기 색, 도로 두께·안티앨리어싱 |

핵심은 **줌·회전·이동은 지오메트리를 다시 계산하지 않는다**는 점이다. 정점 좌표는 그대로 두고 버텍스 셰이더에 전달하는 투영 행렬(uniform)만 바꾸면 GPU가 알아서 새 화면 위치를 계산한다. 그래서 지도 조작이 부드러운 반면, 새 타일 데이터가 들어와 지오메트리와 버퍼 자체를 다시 만들어야 할 때는 상대적으로 비용이 크다.

## 예제 1: 최소 버텍스/프래그먼트 셰이더 (GLSL)

```glsl
// vertex shader — 정점마다 실행
attribute vec2 a_position;   // 타일 좌표계의 정점 위치
uniform mat4 u_matrix;       // 카메라 투영 행렬 (줌/회전/이동 반영)

void main() {
  // 지오메트리는 그대로, 행렬만 바뀌면 화면 위치가 바뀐다
  gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);
}

// fragment shader — 픽셀마다 실행
precision mediump float;
uniform vec4 u_fillColor;    // 폴리곤 채우기 색

void main() {
  gl_FragColor = u_fillColor;
}
```

## 예제 2: 정점 버퍼 업로드 (JavaScript / WebGL API)

```javascript
// 삼각분할이 끝난 정점 좌표를 GPU 버퍼로 업로드
const vertices = new Float32Array(triangulatedCoords); // CPU에서 준비한 정점 배열

const buffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW); // CPU -> GPU 전송, 프레임마다 반복하지 않음

// 카메라가 바뀔 때는 버퍼를 다시 만들지 않고 uniform만 갱신
gl.uniformMatrix4fv(matrixLocation, false, projectionMatrix);
gl.drawArrays(gl.TRIANGLES, 0, vertices.length / 2);
```

<img src="/assets/images/posts/2026-08-17-webgl-map-rendering-pipeline-1.svg" alt="벡터 타일 수신부터 GPU 셰이더를 거쳐 화면 픽셀로 출력되는 WebGL 지도 렌더링 파이프라인 단계도" style="width:100%;">

## 실무 포인트

- **드로우콜(draw call)을 줄이는 것이 최우선 최적화다.** 레이어마다 별도로 `drawArrays`를 호출하면 프레임당 호출 수가 급증한다. 같은 스타일의 폴리곤은 하나의 버퍼로 배치(batch)해 호출 횟수를 줄이는 것이 대부분의 지도 라이브러리 내부 최적화 전략이다.
- **줌·이동 애니메이션과 데이터 리로드를 구분해서 체감한다.** 카메라 조작은 uniform 행렬 갱신만으로 처리되어 가볍지만, 새 타일 디코딩·삼각분할·버퍼 재생성은 CPU 비용이 크다. 프레임 드랍이 느껴진다면 먼저 타일 로드 타이밍과 지오메트리 복잡도부터 의심한다.
- **정밀도(precision) 설정을 확인한다.** 프래그먼트 셰이더의 `precision mediump float` 같은 설정은 모바일 GPU 호환성과 성능에 직접 영향을 준다. 데스크톱에서 잘 되던 스타일이 모바일에서 깨진다면 정밀도 불일치를 먼저 점검한다.
- **좌표 정밀도 손실에 주의한다.** 위경도를 그대로 `Float32Array`에 담으면 지구 전역 범위에서 부동소수점 정밀도가 부족해질 수 있어, 대부분의 라이브러리가 타일 로컬 좌표계로 변환한 뒤 버퍼에 담는다.

## 3줄 요약

- 웹 지도는 벡터 타일(MVT)을 디코딩·삼각분할해 정점 버퍼로 만든 뒤 GPU에 업로드하고, 이후 렌더링은 버텍스·프래그먼트 셰이더가 병렬로 처리한다.
- 줌·회전·이동은 지오메트리를 그대로 두고 투영 행렬(uniform)만 바꾸는 방식이라 가볍지만, 새 타일의 디코딩·삼각분할·버퍼 재생성은 CPU 비용이 커서 프레임 드랍의 주된 원인이 된다.
- 실무 최적화의 핵심은 드로우콜 수 줄이기(배치), 셰이더 정밀도 설정, 좌표 정밀도 손실 관리 세 가지로 요약된다.

## 참고 자료

- [MDN — WebGL API](https://developer.mozilla.org/ko/docs/Web/API/WebGL_API)
- [Khronos Group — WebGL Specification](https://www.khronos.org/registry/webgl/specs/latest/1.0/)
- [Mapbox — Vector Tile Specification](https://github.com/mapbox/vector-tile-spec)
