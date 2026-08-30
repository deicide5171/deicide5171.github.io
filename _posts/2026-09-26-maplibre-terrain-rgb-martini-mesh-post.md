---
layout: single
title: "MapLibre GL JS Terrain-RGB와 Martini 메시 — 웹지도에서 지형을 3D로 세우는 원리"
date: 2026-09-26 12:20:00 +0530
categories: gis
tags: ["MapLibreGLJS", "TerrainRGB", "Martini", "3D지형", "RTIN"]
toc: true
toc_sticky: true
excerpt: "고도 데이터를 그리드 형태 그대로 GPU에 넘기면 평지에서도 산악만큼 촘촘한 정점을 그려야 하는 낭비 문제를, PNG 픽셀에 고도를 인코딩하는 Terrain-RGB 포맷과 지형 굴곡에 따라 삼각형 밀도를 자동 조절하는 Martini 알고리즘으로 해결하는 원리를 정리했다."
---

## 왜 지금 지형 렌더링 파이프라인을 다시 봐야 하는가

MapLibre GL JS의 `setTerrain()`을 켜면 평면 지도가 입체적인 산과 계곡으로 솟아오른다. 이 기능을 처음 붙일 때 흔히 놓치는 부분은, 이 입체감이 어디서 오는 고도 데이터를 어떤 형태로 전달받아 어떻게 3D 메시로 바꾸는지다. 원시 표고 데이터(DEM)는 보통 위경도 격자마다 실수 값 하나를 갖는 배열인데, 이걸 그대로 웹 타일로 잘라 보내면 파일 용량이 커질 뿐 아니라, 평평한 바다나 평야에도 산악 지형과 똑같이 촘촘한 격자 해상도로 삼각형을 그려야 해서 GPU가 불필요한 폴리곤을 낭비하게 된다. Mapbox가 제안하고 MapLibre 생태계가 그대로 채택한 Terrain-RGB 포맷과, Vladimir Agafonkin이 만든 Martini 알고리즘은 각각 "고도를 어떻게 저장할 것인가"와 "저장된 고도를 어떻게 효율적인 3D 메시로 바꿀 것인가"라는 서로 다른 문제를 푼다.

## 핵심 개념 1 — Terrain-RGB: 이미지 픽셀에 고도를 숨기기

Terrain-RGB의 아이디어는 표고 값을 별도 포맷으로 저장하는 대신, 이미 웹 인프라가 완벽히 지원하는 PNG 이미지의 RGB 채널에 인코딩하는 것이다. 각 픽셀의 R, G, B 8비트 값을 이어 붙이면 24비트(약 1,677만 단계) 정수를 얻을 수 있고, 여기에 오프셋과 배율을 적용해 -10,000m부터 세밀한 소수점 단위까지 고도를 표현한다. 이 방식의 진짜 이점은 기존 타일 서버 인프라(HTTP 캐싱, CDN, 표준 이미지 디코더)를 고도 데이터에도 그대로 재사용할 수 있다는 것이다. 브라우저는 별도의 커스텀 바이너리 파서 없이 표준 PNG 디코딩만으로 고도 그리드를 얻는다.

## 핵심 개념 2 — Martini: 균일한 격자를 불균일한 삼각형으로

Terrain-RGB 타일을 디코딩하면 예를 들어 256×256 크기의 균일한 고도 격자를 얻는데, 이 격자를 그대로 GPU에 넘기면 정점 65,536개짜리 메시가 된다. 문제는 평평한 지역도 산악 지역과 똑같은 밀도의 정점을 갖는다는 낭비다. Martini는 RTIN(Right-Triangulated Irregular Network)이라는 계층적 삼각분할 구조를 이진 트리 형태로 미리 계산해두고, 각 삼각형이 실제 고도값을 근사하는 오차가 지정한 임계값을 넘을 때만 그 삼각형을 재귀적으로 두 개로 쪼갠다. 평지처럼 고도 변화가 거의 없는 영역은 큰 삼각형 몇 개로도 오차가 작으니 세분화가 멈추고, 급경사 산악 지역은 오차가 클 때까지 계속 쪼개져 정점이 밀집된다. 결과적으로 같은 시각적 정확도를 훨씬 적은 정점 수로 달성한다.

| 단계 | 입력 | 출력 | 핵심 이점 |
|---|---|---|---|
| Terrain-RGB 디코딩 | PNG 타일 | 균일 고도 그리드 | 기존 이미지 인프라 재사용 |
| Martini 삼각분할 | 균일 고도 그리드 | 불균일 삼각형 메시 | 지형 굴곡에 따른 정점 밀도 자동 조절 |
| GPU 렌더링 | 불균일 메시 | 3D 지형 | 평지 영역 폴리곤 수 대폭 절감 |

<img src="/assets/images/posts/2026-09-26-maplibre-terrain-rgb-martini-mesh-1.svg" alt="PNG 픽셀의 RGB 값을 24비트 정수로 합쳐 고도를 복원하는 Terrain-RGB 디코딩 공식과, 평지는 큰 삼각형 몇 개로 근사하고 산악 지역은 오차 임계값을 넘을 때까지 재귀적으로 세분화해 정점을 밀집시키는 Martini RTIN 메시화 과정을 좌우로 비교한 다이어그램" style="width:100%;">

## 코드 예제 — MapLibre GL JS에서 Terrain-RGB 소스 연결하기

```javascript
map.on('load', () => {
  map.addSource('terrain-dem', {
    type: 'raster-dem',
    tiles: ['https://example.com/terrain-rgb/{z}/{x}/{y}.png'],
    tileSize: 256,
    maxzoom: 14,
    encoding: 'mapbox' // Terrain-RGB 인코딩 방식 지정
  });

  map.setTerrain({
    source: 'terrain-dem',
    exaggeration: 1.5 // 고도를 시각적으로 과장(연출 목적)
  });
});
```

MapLibre 내부에서 `raster-dem` 소스는 타일을 받아오면 자동으로 Martini 기반 메시 생성 로직을 거쳐 지형을 렌더링한다 — 애플리케이션 코드에서 직접 삼각분할을 호출할 필요는 없다.

## 실무 포인트

- **`encoding` 옵션을 반드시 데이터 제공처와 맞춰야 한다.** Mapbox 방식과 Terrarium(AWS) 방식은 RGB에서 고도를 복원하는 공식이 다르므로, 잘못 지정하면 지형이 뒤집히거나 극단적으로 솟아오르는 오류가 난다.
- **`exaggeration` 값은 연출 도구이지 정확도 도구가 아니다.** 실측 고도 분석이 필요한 애플리케이션에서는 이 값을 1로 고정해야 하며, 1보다 큰 값은 시각적 임팩트를 위한 왜곡임을 인지해야 한다.
- **모바일 기기에서는 지형 최대 줌 레벨을 제한하는 것이 안전하다.** 고해상도 지형 타일을 계속 요청하면 저사양 GPU에서 메시 재계산 비용이 프레임 드랍으로 이어질 수 있다.

## 마무리 요약

- Terrain-RGB는 표고 값을 PNG의 R·G·B 채널에 24비트 정수로 인코딩해, 기존 타일 인프라를 그대로 재사용하면서 고해상도 고도 데이터를 배포하는 방식이다.
- Martini는 RTIN 이진 트리 구조로 삼각형을 오차 임계값 기준으로 재귀 분할해, 평지는 성기게 산악은 촘촘하게 렌더링함으로써 같은 정확도를 더 적은 정점으로 달성한다.
- encoding 옵션 불일치와 exaggeration 값의 오용이 실무에서 가장 흔한 실수이며, 저사양 기기에서는 지형 최대 줌 레벨 제한이 필요하다.

## 참고 자료

- [MapLibre GL JS 공식 문서 — Terrain](https://maplibre.org/maplibre-gl-js/docs/examples/add-terrain/)
- [Martini 알고리즘 GitHub 저장소](https://github.com/mapbox/martini)
