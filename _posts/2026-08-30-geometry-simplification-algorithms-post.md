---
layout: single
title: "정점을 지워도 지형은 남아야 한다 — 지오메트리 단순화 알고리즘 실전 비교"
date: 2026-08-30 12:20:00 +0530
categories: gis
tags: ["gis", "geometry-simplification", "douglas-peucker", "visvalingam-whyatt", "topojson", "vector-tile"]
toc: true
toc_sticky: true
excerpt: "줌아웃할 때마다 해안선 폴리곤을 그대로 그리면 브라우저가 버벅인다. Douglas-Peucker와 Visvalingam-Whyatt의 서로 다른 단순화 기준, 그리고 TopoJSON이 인접 폴리곤 경계를 깨지지 않게 지키는 방법을 정리한다."
---

전국 단위 행정구역 경계 데이터를 원본 정밀도 그대로 웹 지도에 그리면, 줌 레벨 3짜리 축소된 화면에서도 수만 개의 정점을 렌더링하게 된다. 육안으로는 구분도 안 되는 굴곡까지 전부 그리는 셈이라 렌더링 성능만 낭비되는 게 아니라, 벡터 타일 크기 자체가 커져 전송 비용도 늘어난다. **지오메트리 단순화(geometry simplification)**는 시각적으로 중요한 형태 특징은 유지하면서 정점 수를 줄이는 전처리로, tippecanoe나 Mapbox의 타일 생성 파이프라인, PostGIS의 `ST_Simplify` 계열 함수가 전부 이 문제를 다룬다.

문제는 "정점을 어떻게 골라 지울 것인가"에 대한 답이 하나가 아니라는 점이다. 이 글에서는 가장 널리 쓰이는 두 알고리즘 Douglas-Peucker와 Visvalingam-Whyatt의 서로 다른 판단 기준을, 그리고 여러 폴리곤이 경계를 공유하는 지도에서 단순화가 만드는 위상 오류 문제와 TopoJSON의 해법을 정리한다.

## 핵심 개념 1: Douglas-Peucker — 거리 기준 재귀 분할

Douglas-Peucker 알고리즘은 선분의 양 끝점을 잇는 직선을 기준으로, 그 직선에서 가장 멀리 떨어진 중간 정점을 찾는다. 그 거리가 허용 오차(tolerance)보다 작으면 중간 정점들을 전부 버리고 양 끝점만 남긴다. 거리가 허용 오차보다 크면 그 정점을 기준으로 선을 둘로 나누고, 각 부분에 같은 과정을 재귀적으로 적용한다.

이 방식은 "직선에서 얼마나 벗어났는가"만을 기준으로 삼기 때문에, 완만하게 굽이치는 해안선처럼 어느 한 점도 두드러지게 튀지 않는 형태에서는 정점이 잘 안 지워지는 경향이 있다. 반대로 뾰족하게 튀어나온 곶(串)처럼 눈에 띄는 굴곡은 그 정점이 직선에서 크게 벗어나므로 확실히 보존된다. 계산 복잡도는 평균적으로 O(n log n) 근처지만 최악의 경우 O(n²)까지 나올 수 있다.

## 핵심 개념 2: Visvalingam-Whyatt — 면적 기준 유효 면적 최소값 제거

Visvalingam-Whyatt(VW) 알고리즘은 접근 자체가 다르다. 각 정점에 대해 그 정점과 양옆 이웃 정점이 이루는 삼각형의 면적(유효 면적, effective area)을 계산하고, 유효 면적이 가장 작은 정점부터 순서대로 제거한다. 정점을 하나 지울 때마다 그 이웃 정점들의 유효 면적을 다시 계산해야 하므로, 우선순위 큐를 써서 효율적으로 구현한다.

면적 기준이라는 점이 Douglas-Peucker와의 실질적 차이를 만든다. VW는 "이 정점이 없어도 전체 모양의 면적이 거의 안 바뀐다"는 기준으로 지우기 때문에, 완만한 곡선에서도 시각적으로 중요하지 않은 정점을 고르게 제거하는 경향이 있고, 결과 형태가 원본의 전반적 실루엣을 더 자연스럽게 유지한다는 평가를 받는다. Mapbox의 단순화 라이브러리(simplify.js 계열)는 기본적으로 VW 계열 방식을 채택하고 있다.

| 구분 | Douglas-Peucker | Visvalingam-Whyatt |
|---|---|---|
| 제거 기준 | 직선으로부터의 수직 거리 | 이웃 정점과 이루는 삼각형 면적 |
| 강한 보존 대상 | 두드러지게 튀어나온 굴곡 | 전체 실루엣의 면적 보존 |
| 완만한 곡선 처리 | 정점이 잘 안 지워짐 | 고르게 제거되는 경향 |
| 대표 구현 | PostGIS `ST_Simplify` | Mapbox `simplify-js`, `mapshaper` |
| 계산 방식 | 재귀 분할 | 우선순위 큐 기반 순차 제거 |

## 핵심 개념 3: 위상 보존 문제 — 이웃 폴리곤이 어긋난다

두 알고리즘 모두 폴리곤 하나만 놓고 보면 잘 작동하지만, 실전 지도 데이터의 문제는 여기서 시작된다. 시·군·구 경계처럼 서로 인접한 폴리곤들은 경계선을 공유하는데, 각 폴리곤을 **독립적으로** 단순화하면 공유 경계선의 정점이 양쪽에서 다르게 지워져 원래 딱 맞붙어 있던 경계에 미세한 틈이나 겹침이 생긴다. 확대해 보면 지도에 눈에 띄는 흰 선(gap)이나 겹친 영역이 보이는 원인이 대개 이것이다.

**TopoJSON**은 이 문제를 근본적으로 다르게 접근해서 푼다. 각 폴리곤을 독립된 좌표 목록으로 저장하는 대신, 인접 폴리곤들이 공유하는 경계선을 **arc**라는 공용 자원으로 한 번만 저장하고, 각 폴리곤은 자신이 어떤 arc들을 어느 순서로 참조하는지만 기록한다. 단순화를 적용할 때도 각 폴리곤이 아니라 **arc 단위로 한 번만** 단순화하므로, 그 arc를 공유하는 모든 폴리곤이 항상 동일하게 단순화된 경계선을 참조하게 되어 위상적으로 어긋날 수가 없다.

<img src="/assets/images/posts/2026-08-30-geometry-simplification-algorithms-1.svg" alt="Douglas-Peucker는 직선과의 수직 거리로, Visvalingam-Whyatt는 삼각형 면적으로 정점을 제거하는 방식을 비교하고, TopoJSON이 공유 경계선을 arc로 한 번만 저장해 위상 오류를 막는 구조를 보여주는 다이어그램" style="width:100%;">

## 예제: mapshaper CLI로 위상 보존 단순화

```bash
# 1) 단순 GeoJSON 각 폴리곤을 독립적으로 단순화 (위상 오류 위험)
mapshaper input.geojson \
  -simplify dp 10% \
  -o naive-simplified.geojson

# 2) TopoJSON으로 변환 후 arc 단위로 단순화 (위상 보존)
mapshaper input.geojson \
  -simplify visvalingam 10% keep-shapes \
  -o format=topojson topology-preserved.topojson

# keep-shapes: 아주 작은 폴리곤(섬 등)이 단순화 과정에서
# 완전히 사라지지 않도록 최소 형태를 보존하는 옵션
```

`-simplify` 명령에 `visvalingam`을 지정하면 mapshaper는 내부적으로 각 좌표를 공유 arc로 재구성한 뒤 단순화를 수행하므로, 결과 GeoJSON으로 다시 내보내도(`-o format=geojson`) 인접 폴리곤 경계는 정확히 일치한다. 반대로 개별 GeoJSON 파일을 각각 `ogr2ogr`이나 PostGIS `ST_Simplify`로 따로 단순화하면 이 보장이 사라진다.

## 실무 포인트

- **허용 오차는 목표 줌 레벨에 맞춰 단계별로 다르게 적용한다.** 하나의 원본 데이터로 모든 줌 레벨을 커버하려면, 줌아웃된 레벨일수록 더 강한 단순화를, 줌인된 레벨일수록 원본에 가까운 정밀도를 쓰는 다단계 파이프라인(tippecanoe의 `-z`/`-Z` 옵션 등)이 필요하다. 한 가지 허용 오차로 모든 줌을 커버하려 하면 어느 레벨에서든 과함이나 부족함이 생긴다.
- **면적/거리 보존과 정점 수 목표를 혼동하지 말 것.** "정점을 N% 줄인다"는 목표와 "원본 형태를 시각적으로 얼마나 보존하는가"는 별개의 지표다. VW는 유효 면적이 작은 정점부터 제거하므로 원한다면 "총 면적 변화량이 X% 이하가 될 때까지" 같은 형태 보존 기준으로 중단 조건을 걸 수도 있다.
- **행정구역·소유권 경계처럼 정확성이 법적 의미를 갖는 데이터는 단순화 자체를 재검토해야 한다.** 단순화 후 경계가 실제 등록된 좌표와 달라지면 시각화 목적으로는 문제없어도, 그 데이터를 근거로 판단이 내려지는 맥락(경계 분쟁, 필지 조회)에서는 원본 정밀도 레이어를 별도로 유지해야 한다.

## 3줄 요약

- Douglas-Peucker는 직선으로부터의 수직 거리를, Visvalingam-Whyatt는 이웃 정점과 이루는 삼각형의 유효 면적을 기준으로 정점을 제거하며, 완만한 곡선 처리 결과가 서로 다르게 나타난다.
- 인접 폴리곤을 각각 독립적으로 단순화하면 공유 경계선에 틈이나 겹침이 생기는 위상 오류가 발생하므로, TopoJSON처럼 공유 경계를 arc로 한 번만 저장해 단순화하는 방식이 필요하다.
- 실전에서는 목표 줌 레벨별로 허용 오차를 다르게 적용하는 다단계 파이프라인이 필요하며, 법적 의미를 갖는 경계 데이터는 단순화된 시각화 레이어와 원본 정밀도 레이어를 분리해 관리해야 한다.

## 참고 자료

- [PostGIS 공식 문서: ST_Simplify / ST_SimplifyPreserveTopology](https://postgis.net/docs/ST_Simplify.html)
- [mapshaper GitHub: Simplification 옵션 문서](https://github.com/mbloch/mapshaper/wiki/Command-Reference)
- [TopoJSON 공식 문서](https://github.com/topojson/topojson)
- [Mike Bostock: Visvalingam-Whyatt 알고리즘 설명](https://bost.ocks.org/mike/simplify/)
