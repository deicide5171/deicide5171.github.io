---
layout: single
title: "물은 어디로 흐르는가 — DEM 기반 수문분석, Flow Direction과 유역 추출"
date: 2026-08-27 13:20:00 +0530
categories: gis
tags: ["dem", "hydrology", "flow-direction", "watershed", "gis", "whitebox"]
toc: true
toc_sticky: true
excerpt: "DEM 한 장으로 물이 어디로 흐르고 어디에 모이는지, 유역 경계가 어디인지까지 계산할 수 있다. Flow Direction부터 유역 추출까지 표준 파이프라인을 정리한다."
---

DEM(Digital Elevation Model)은 단순히 지형을 시각화하는 데만 쓰이지 않는다. 표준 알고리즘을 순서대로 적용하면 "이 지점에 떨어진 빗물이 어느 방향으로 흐르는가", "어느 지점에 물이 가장 많이 모이는가(하천망)", "이 관측 지점 상류의 배수 구역(유역)은 어디까지인가"까지 계산해낼 수 있다. 이것이 DEM 기반 수문분석의 핵심 파이프라인이다.

이 분석은 홍수 위험 지도 제작, 도로·교량 설계 시 배수 계획, 유역 단위 수자원 관리 등에 실무적으로 쓰인다. 이 글에서는 표준 파이프라인의 각 단계와 실무에서 자주 걸리는 함정을 정리한다.

## 핵심 개념 1: 표준 파이프라인 — 전처리부터 유역 추출까지

수문분석은 보통 다음 순서를 따른다.

1. **싱크 채우기(Fill Sinks/Depressions)**: 원본 DEM에는 측량·보간 오차로 인한 인공적인 움푹 파인 지점(sink)이 곳곳에 있다. 이런 지점은 물이 흘러나갈 방향이 없어 흐름 계산이 거기서 멈춰버리므로, 주변보다 낮은 셀의 높이를 주변과 같아지도록 채워 흐름이 끊기지 않게 만든다.
2. **흐름 방향(Flow Direction) 계산**: 채워진 DEM에서 각 셀이 어느 이웃 셀로 물을 흘려보내는지 계산한다. 가장 널리 쓰이는 D8 알고리즘은 8방향 이웃 중 경사가 가장 급한 방향 하나로만 흐름을 보낸다.
3. **흐름 누적(Flow Accumulation) 계산**: 각 셀에 대해 "이 셀로 흘러드는 상류 셀의 개수"를 누적 계산한다. 이 값이 큰 셀일수록 많은 면적의 물이 모이는 지점, 즉 하천에 해당한다.
4. **하천망 추출과 유역 경계 추출**: 흐름 누적 값이 특정 임계값을 넘는 셀만 골라 하천망을 추출하고, 특정 지점(pour point, 관측소나 합류점)을 기준으로 그 지점으로 흘러드는 모든 상류 셀을 모아 유역(watershed) 경계를 그린다.

<img src="/assets/images/posts/2026-08-27-dem-hydrological-flow-analysis-1.svg" alt="D8 알고리즘이 3x3 이웃 중 가장 급경사 방향으로 흐름을 할당하는 방식과, 흐름 누적값이 높은 셀들이 이어져 하천망을 이루며 특정 pour point 기준으로 유역 경계가 그려지는 과정을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2: 도구 선택 — 무엇으로 계산할 것인가

| 도구 | 특징 |
|---|---|
| GRASS GIS `r.watershed` | 단일 명령으로 흐름방향·누적·유역을 한 번에 계산, 대용량에 강함 |
| WhiteboxTools | 오픈소스, Python 바인딩 제공, 다양한 흐름 알고리즘(D8, D-infinity, MFD) 지원 |
| ArcGIS Spatial Analyst | GUI 기반, Fill/FlowDirection/FlowAccumulation/Watershed 툴체인 표준 |
| PySheds | Python 라이브러리, 코드로 파이프라인 전체를 스크립팅하기 좋음 |

D8 외에 D-infinity, MFD(Multiple Flow Direction) 같은 알고리즘도 있다. D8은 구현이 단순하고 빠르지만 평탄한 지형에서 흐름을 한 방향으로만 몰아 부자연스러운 직선 패턴이 나올 수 있다. 정밀한 분석이 필요하다면 여러 방향으로 흐름을 분배하는 MFD 계열이 더 현실적인 결과를 낸다.

## 예제: PySheds로 유역 추출하기

```python
from pysheds.grid import Grid

grid = Grid.from_raster("dem.tif")
dem = grid.read_raster("dem.tif")

# 1. 싱크 채우기 (표면 채움 + 낮은 부분 평탄화)
filled_dem = grid.fill_depressions(dem)
flooded_dem = grid.resolve_flats(filled_dem)

# 2. 흐름 방향 계산 (D8)
fdir = grid.flowdir(flooded_dem)

# 3. 흐름 누적 계산
acc = grid.accumulation(fdir)

# 4. pour point(관측 지점 좌표)를 지정해 유역 delineate
x, y = 127.123, 37.456  # 예시 좌표 (실제로는 데이터 좌표계에 맞춰야 함)
x_snap, y_snap = grid.snap_to_mask(acc > 1000, (x, y))  # 하천 위로 스냅
catchment = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, xytype="coordinate")

grid.to_raster(catchment, "watershed.tif")
```

`snap_to_mask`로 사용자가 지정한 좌표를 실제 하천 셀(흐름 누적값이 큰 셀)로 스냅하는 단계가 중요하다. 좌표가 하천에서 한 셀만 벗어나도 완전히 다른 유역이 추출될 수 있다.

## 실무 포인트

- **DEM 해상도가 분석 스케일을 결정한다**: SRTM(30m)처럼 거친 해상도의 DEM으로는 작은 도심 배수 유역을 정밀하게 분석할 수 없다. 분석 목적(대륙 규모 유역 vs 도심 배수로)에 맞는 해상도의 DEM을 선택해야 하며, 필요 이상으로 고해상도를 쓰면 계산량만 늘고 노이즈(작은 인공 구조물)가 흐름 방향을 왜곡할 수 있다.
- **평탄한 지역의 흐름 방향 계산은 후처리가 필요하다**: 저지대 평야나 농경지처럼 경사가 거의 없는 지역은 D8 알고리즘이 흐름 방향을 임의로 결정해 부자연스러운 패턴을 만든다. `resolve_flats` 같은 후처리 단계로 미세한 경사를 인위적으로 부여해 흐름이 자연스럽게 이어지도록 해야 한다.
- **하천망 임계값은 검증 데이터로 보정한다**: 흐름 누적값의 임계값을 얼마로 잡느냐에 따라 추출되는 하천망의 밀도가 크게 달라진다. 임의의 값을 쓰지 말고, 실제 하천 지도(국토지리정보원 수치지도 등)와 비교해 임계값을 보정하는 과정이 필요하다.

## 3줄 요약

- DEM 수문분석은 싱크 채우기 → 흐름 방향 → 흐름 누적 → 하천망/유역 추출 순서의 표준 파이프라인을 따른다.
- D8은 단순하고 빠르지만 평탄 지역에서 부자연스러운 패턴을 만들 수 있어, 정밀 분석에는 MFD 같은 다방향 알고리즘이 더 현실적이다.
- pour point 좌표를 실제 하천 셀로 스냅하는 과정과 DEM 해상도 선택이 유역 추출 결과의 신뢰도를 좌우한다.

## 참고 자료

- [WhiteboxTools 공식 문서: Hydrological Analysis](https://www.whiteboxgeo.com/manual/wbt_book/available_tools/hydrological_analysis.html)
- [GRASS GIS 공식 문서: r.watershed](https://grass.osgeo.org/grass-stable/manuals/r.watershed.html)
- [PySheds 공식 문서](https://mattbartos.com/pysheds/)
