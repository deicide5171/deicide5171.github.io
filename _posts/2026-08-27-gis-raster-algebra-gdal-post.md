---
layout: single
title: "픽셀끼리 계산한다 — GDAL로 하는 래스터 대수(Map Algebra) 실무"
date: 2026-08-27 12:20:00 +0530
categories: gis
tags: ["gdal", "raster", "map-algebra", "gis", "ndvi", "rasterio"]
toc: true
toc_sticky: true
excerpt: "벡터가 도형끼리 연산한다면 래스터는 픽셀끼리 연산한다. GDAL 기반 로컬·포컬·존별·전역 연산의 개념과 실무에서 놓치기 쉬운 함정을 정리한다."
---

벡터 GIS에서 버퍼·오버레이가 기본 연산이듯, 래스터 GIS에는 래스터 대수(Map Algebra 또는 Raster Algebra)가 있다. 위성영상, DEM, 기상 격자 데이터처럼 격자(그리드) 형태로 저장된 데이터를 픽셀 단위로 계산해 새로운 정보를 뽑아내는 것이다. NDVI 계산(밴드 간 산술), 경사도 계산(이웃 픽셀 참조), 유역별 평균 강수량 집계(존 통계)가 전부 래스터 대수의 사례다.

GDAL은 이 연산의 사실상 표준 도구다. `gdal_calc.py`로 밴드 산술을 즉시 실행할 수 있고, Python에서는 `rasterio`나 `numpy` 배열로 읽어와 원하는 연산을 자유롭게 짤 수 있다. 이 글에서는 래스터 대수를 네 가지 연산 유형으로 나눠 정리하고, GDAL로 실무에 적용할 때 놓치기 쉬운 함정을 짚는다.

## 핵심 개념 1: 래스터 대수의 네 가지 연산 유형

래스터 대수는 참조 범위 기준으로 로컬(local), 포컬(focal), 존(zonal), 글로벌(global) 네 유형으로 나뉜다.

- **로컬(local) 연산**: 같은 위치의 픽셀끼리만 계산한다. 밴드 A의 (x, y)와 밴드 B의 (x, y)를 더하거나 빼는 것. NDVI = (NIR - Red) / (NIR + Red)가 대표적이다.
- **포컬(focal) 연산**: 각 픽셀과 그 주변 이웃(보통 3×3 또는 5×5 커널)을 함께 참조한다. 경사도(slope), 음영기복(hillshade), 이동평균 스무딩이 여기 속한다.
- **존(zonal) 연산**: 별도의 존 래스터나 폴리곤으로 픽셀을 그룹 지어, 그룹별 통계(평균, 합계, 최댓값)를 낸다. "유역별 평균 강수량", "행정구역별 평균 고도"가 예시다.
- **글로벌(global) 연산**: 전체 래스터(또는 그 일부 넓은 범위)를 참조해 결과를 만든다. 유클리드 거리 변환, 흐름 누적(flow accumulation)처럼 값이 래스터 전체 구조에 의존하는 연산이 해당한다.

<img src="/assets/images/posts/2026-08-27-gis-raster-algebra-gdal-1.svg" alt="로컬 연산은 같은 픽셀 위치끼리, 포컬 연산은 3x3 이웃을 포함해, 존 연산은 그룹별 통계로, 글로벌 연산은 래스터 전체를 참조해 계산하는 네 가지 유형을 보여주는 격자 다이어그램" style="width:100%;">

## 핵심 개념 2: GDAL 도구 선택 — CLI vs Python

| 상황 | 도구 |
|---|---|
| 단순 밴드 산술(NDVI 등)을 빠르게 시도 | `gdal_calc.py` (CLI) |
| 조건문·복잡한 로직이 섞인 연산 | Python + `rasterio` + `numpy` |
| 대용량 래스터를 메모리에 안 올리고 처리 | GDAL VRT + 타일 단위 처리 |
| 존별 통계 | `rasterstats` (Python) 또는 QGIS Zonal Statistics |

`gdal_calc.py`는 셸 한 줄로 끝나 프로토타이핑에 좋지만, 조건 분기나 여러 단계 로직이 필요해지면 `rasterio`로 배열을 직접 다루는 편이 가독성과 재사용성 면에서 낫다.

## 예제: NDVI 계산 — CLI와 Python 두 가지 방법

```bash
# gdal_calc.py로 즉시 NDVI 계산 (밴드 4=NIR, 밴드 3=Red 가정)
gdal_calc.py -A input.tif --A_band=4 -B input.tif --B_band=3 \
  --outfile=ndvi.tif \
  --calc="(A.astype(float)-B)/(A.astype(float)+B)" \
  --NoDataValue=-9999
```

```python
import rasterio
import numpy as np

with rasterio.open("input.tif") as src:
    nir = src.read(4).astype(float)
    red = src.read(3).astype(float)
    profile = src.profile

# 0으로 나누는 것을 방지 (구름·물 픽셀 등에서 NIR+Red가 0에 가까울 수 있음)
denom = nir + red
ndvi = np.where(denom == 0, np.nan, (nir - red) / denom)

profile.update(dtype=rasterio.float32, count=1, nodata=np.nan)
with rasterio.open("ndvi_rasterio.tif", "w", **profile) as dst:
    dst.write(ndvi.astype(rasterio.float32), 1)
```

Python 쪽은 0으로 나누는 경우를 `NaN`으로 명시적으로 처리했다는 차이가 있다. CLI 한 줄로는 이런 예외 처리를 넣기 번거롭다.

## 실무 포인트

- **NoData와 정수 오버플로를 항상 의심한다**: 원본이 `uint8`이나 `uint16` 정수 타입인 밴드를 그대로 곱하거나 더하면 오버플로가 나서 값이 랩어라운드된다. 연산 전에 `astype(float)`로 반드시 캐스팅하고, NoData 픽셀(흔히 0 또는 -9999)이 연산 결과에 섞여 들어가지 않도록 마스킹해야 한다.
- **해상도와 좌표계를 먼저 맞춘다**: 서로 다른 소스에서 온 래스터(예: 위성영상과 DEM)는 셀 크기와 좌표계가 다른 경우가 흔하다. 래스터 대수는 픽셀 단위 정렬을 전제하므로, 연산 전에 `gdalwarp`로 동일 해상도·좌표계·격자 정렬(snap)을 맞춰야 결과가 의미를 갖는다.
- **대용량 래스터는 VRT와 타일 단위로 처리한다**: 전국 단위 고해상도 래스터를 통째로 `numpy` 배열에 올리면 메모리가 터진다. GDAL VRT로 가상 모자이크를 구성하고, `rasterio.windows`로 타일 단위로 나눠 순차 처리하는 패턴이 대용량 처리의 기본이다.

## 3줄 요약

- 래스터 대수는 참조 범위에 따라 로컬·포컬·존·글로벌 네 유형으로 나뉘며, NDVI는 로컬, 경사도는 포컬 연산의 예다.
- `gdal_calc.py`는 빠른 시도에, `rasterio`+`numpy`는 조건 분기와 예외 처리가 필요한 복잡한 연산에 적합하다.
- 정수 오버플로, NoData 마스킹, 해상도/좌표계 정렬을 놓치면 계산은 실행되지만 결과가 틀린 값이 나온다.

## 참고 자료

- [GDAL 공식 문서: gdal_calc.py](https://gdal.org/en/latest/programs/gdal_calc.html)
- [Rasterio 공식 문서](https://rasterio.readthedocs.io/en/stable/)
- [GDAL 공식 문서: gdalwarp](https://gdal.org/en/latest/programs/gdalwarp.html)
