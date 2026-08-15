---
layout: single
title: "코드로 그리는 지도 — Mapbox Style Spec으로 벡터 타일 스타일링하기"
date: 2026-08-19 12:20:00 +0530
categories: gis
tags: ["mapbox", "style-spec", "vector-tile", "maplibre", "gis"]
toc: true
toc_sticky: true
excerpt: "벡터 타일은 좌표와 속성만 담은 데이터일 뿐, 실제로 어떤 색·굵기·순서로 그려지는지는 Mapbox Style Specification의 layers 배열과 표현식(expression) 문법이 결정한다는 점을 예제로 정리했다."
---

## 왜 지금 스타일 JSON을 알아야 하는가

벡터 타일 자체는 좌표와 속성값만 담은 순수 데이터일 뿐이다. 화면에 어떤 색으로, 어떤 굵기로, 어떤 순서로 그릴지는 전적으로 스타일 정의가 결정한다. Mapbox가 만든 **Style Specification**은 지금 Mapbox GL JS뿐 아니라 오픈소스 포크인 MapLibre GL JS, 그리고 다양한 타일 서버·스타일 에디터가 공통으로 따르는 사실상 표준 문법으로 자리 잡았다.

이전 글에서 Mapbox·MapLibre·구글 맵의 선택 기준을 비교했고, OpenLayers로 지도를 직접 구성하는 방법과 WebGL 렌더링 파이프라인 내부도 다뤘지만, 정작 실무에서 가장 자주 마주치는 "스타일 JSON을 어떻게 작성하는가"는 아직 다루지 않았다. 디자이너가 만든 지도 톤앤매너를 서비스에 반영하거나, 줌 레벨별로 라벨 밀도를 조절하거나, 속성값에 따라 건물 색을 다르게 칠하는 작업은 모두 layers 배열과 표현식(expression) 문법을 이해해야 손댈 수 있다. 이 글은 스타일 스펙의 핵심 구조를 정리한다.

## 핵심 개념 1: 스타일 JSON의 최상위 구조

| 키 | 역할 |
|---|---|
| `version` | 스펙 버전(현재 8 고정) |
| `sources` | 타일 데이터의 출처(벡터/GeoJSON/래스터) 정의 |
| `layers` | 실제로 그릴 레이어 목록, **배열 순서가 곧 렌더링 순서** |
| `sprite` | 아이콘 이미지 스프라이트 URL |
| `glyphs` | 라벨에 쓸 폰트 글리프 URL 템플릿 |

<img src="/assets/images/posts/2026-08-19-mapbox-style-spec-vectortile-1.svg" alt="스타일 JSON의 최상위 구조와 layers 배열이 아래에서 위로 겹쳐 그려지는 렌더링 순서 개념도" style="width:100%;">

`layers`는 배열이라는 점이 핵심이다. 먼저 등장하는 항목이 먼저 그려지고, 나중에 등장하는 항목이 그 위에 겹쳐 그려진다. 그래서 배경(background) → 면(fill) → 선(line) → 라벨(symbol) 순서로 배치하는 것이 일반적이며, 이 순서를 바꾸면 도로 위에 그려져야 할 라벨이 건물 폴리곤 아래로 숨어버리는 식의 문제가 생긴다.

## 핵심 개념 2: 레이어 하나의 구성 — layout과 paint

레이어 객체는 `id`, `type`, `source`, `source-layer`, `layout`, `paint`로 구성된다. `source-layer`는 벡터 타일 내부에 실제로 존재하는 레이어 이름과 정확히 일치해야 하며, 오타가 있어도 에러 없이 그냥 아무것도 그려지지 않는다는 점을 기억해 둘 만하다.

| 구분 | 의미 | 예시 프로퍼티 |
|---|---|---|
| `layout` | 지오메트리 배치·가시성 관련 속성, GPU 렌더링 전에 결정 | `visibility`, `line-cap`, `text-field`, `icon-image` |
| `paint` | 색상·굵기·투명도 등 시각적 표현 속성 | `fill-color`, `line-width`, `text-color`, `fill-opacity` |

## 핵심 개념 3: 표현식(Expression)으로 데이터 기반 스타일링

단일 색상 대신 **표현식**을 쓰면 줌 레벨이나 피처 속성값에 따라 스타일을 동적으로 바꿀 수 있다.

| 표현식 | 용도 |
|---|---|
| `interpolate` | 두 값 사이를 부드럽게 보간(줌별 크기·색 변화 등) |
| `step` | 구간별로 값을 계단식으로 전환 |
| `match` | 속성값을 특정 케이스와 비교해 분기 |
| `case` | 조건식 여러 개를 순서대로 평가 |

## 예제 1: 표현식을 쓴 스타일 레이어 (JSON)

```json
{
  "id": "buildings-fill",
  "type": "fill",
  "source": "osm-tiles",
  "source-layer": "building",
  "paint": {
    "fill-color": [
      "match",
      ["get", "class"],
      "residential", "#f2e9dc",
      "commercial", "#dce8f2",
      "industrial", "#e8dce0",
      "#e6e6e6"
    ],
    "fill-opacity": [
      "interpolate", ["linear"], ["zoom"],
      12, 0.2,
      16, 0.9
    ]
  }
}
```

`class` 속성값에 따라 색을 나누고(`match`), 줌 레벨 12에서 16으로 갈수록 불투명도를 0.2에서 0.9로 서서히 올린다(`interpolate`). 카메라가 멀 때는 건물이 흐릿하게, 가까워질수록 뚜렷하게 보이는 효과다.

## 예제 2: 런타임에 스타일 조작하기 (JavaScript, MapLibre GL JS)

```javascript
// 레이어 순서를 명시적으로 지정: road 레이어 "바로 아래"에 새 레이어 삽입
map.addLayer(
  {
    id: "poi-highlight",
    type: "circle",
    source: "osm-tiles",
    "source-layer": "poi",
    paint: { "circle-color": "#ff5a36", "circle-radius": 6 },
  },
  "road" // beforeId — 이 레이어 바로 아래에 그려짐
);

// 기존 레이어의 paint 속성만 즉시 변경
map.setPaintProperty("buildings-fill", "fill-color", "#cccccc");
```

`addLayer`의 두 번째 인자(`beforeId`)로 삽입 위치를 지정하면 전체 스타일을 다시 로드하지 않고도 레이어 순서를 정밀하게 제어할 수 있다.

## 실무 포인트

- **`source-layer` 오타는 조용히 실패한다**: 콘솔 에러가 뜨지 않고 그냥 빈 화면으로 남으므로, 벡터 타일 스키마 문서나 타일 검사 도구로 실제 레이어 이름을 먼저 확인한다.
- **레이어 순서 = 그리는 순서**임을 항상 의식한다. 배경 → 폴리곤 → 라인 → 라벨의 큰 순서를 지키고, 세부 조정은 `beforeId`로 처리한다.
- **표현식은 zoom stop이 늘어날수록 가독성이 떨어진다**. Maputnik 같은 오픈소스 스타일 에디터로 미리보기하며 작성하면 실수를 줄일 수 있다.
- **sprite·glyphs는 별도 호스팅 리소스**다. 아이콘을 추가하거나 폰트를 바꾸면 구현체에 따라 스프라이트 재생성이나 배포 절차가 추가로 필요할 수 있으니 사용 중인 도구의 문서를 확인한다.

## 3줄 요약

- 벡터 타일은 데이터일 뿐이고, 실제 색·굵기·순서는 Mapbox Style Specification의 `layers` 배열과 `paint`/`layout` 속성이 결정한다.
- `layers` 배열의 순서가 곧 화면에 그려지는 순서이며, `match`·`interpolate` 같은 표현식으로 속성값·줌 레벨에 따른 데이터 기반 스타일링이 가능하다.
- 실무에서는 `source-layer` 이름 일치 여부, 레이어 삽입 순서(`beforeId`), 표현식 가독성, sprite·glyphs 리소스 관리를 함께 챙겨야 한다.

## 참고 자료

- [Mapbox Style Specification](https://docs.mapbox.com/style-spec/reference/)
- [MapLibre Style Specification](https://maplibre.org/maplibre-style-spec/)
- [Maputnik — 오픈소스 스타일 에디터](https://maputnik.github.io/)
