---
layout: single
title: "위성영상 수천 장을 배열 하나처럼 — 시공간 래스터 데이터큐브(xarray/zarr)"
date: 2026-08-28 12:20:00 +0530
categories: gis
tags: ["gis", "datacube", "xarray", "zarr", "raster", "remote-sensing"]
toc: true
toc_sticky: true
excerpt: "위성영상처럼 시간·위도·경도·밴드 축이 모두 있는 래스터 데이터를 파일 단위가 아니라 다차원 배열 하나로 다루는 데이터큐브 개념과, xarray·Zarr로 이를 구현하는 방법을 정리한다."
---

특정 지역의 3년치 위성영상에서 "여름철 평균 NDVI 변화"를 구하고 싶다고 하자. 데이터가 하루 단위 GeoTIFF 파일 천 개로 흩어져 있다면, 이 질문에 답하기 위해 파일을 하나씩 열고, 날짜를 파싱해 여름철만 골라내고, 좌표계를 맞춰 픽셀 단위로 합산하는 코드를 직접 짜야 한다. 파일이 몇 개 안 될 때는 참을 만하지만, 파일 수가 수천~수만 개로 늘어나면 이 방식은 코드도 지저분해지고 I/O 병목도 심각해진다.

**시공간 데이터큐브(spatiotemporal datacube)**는 이 문제를 "파일들의 모음"이 아니라 **시간·위도·경도·밴드가 축인 하나의 다차원 배열**로 재구성해서 푼다. "여름철 평균"은 더 이상 파일을 순회하는 반복문이 아니라, 그 배열에서 시간 축을 조건으로 슬라이싱한 뒤 평균을 내는 배열 연산 한 줄이 된다. 이 글에서는 데이터큐브 개념과, 파이썬 생태계에서 이를 다루는 표준 도구인 xarray와 Zarr가 어떻게 맞물리는지 정리한다.

## 핵심 개념 1: 데이터큐브 — 축이 있는 배열로 사고를 전환한다

전통적인 래스터 처리는 "파일 하나 = 특정 시점·특정 밴드의 2차원 격자"라는 단위로 사고한다. 데이터큐브는 여기에 **시간(time)**과 **밴드(band)**를 추가 차원으로 붙여, 전체를 `(time, band, y, x)` 4차원 배열 하나로 본다. 이렇게 하면 "특정 시점 조회"는 이 배열에서 time 축 하나를 인덱싱하는 것이고, "시계열 추세"는 (y, x) 좌표를 고정하고 time 축을 따라가는 것이며, "여러 밴드로 지수 계산"은 band 축 연산이 된다. 개별 파일을 여닫는 코드 없이, 원하는 질문을 배열의 축 연산으로 바로 표현할 수 있다는 것이 핵심 이점이다.

<img src="/assets/images/posts/2026-08-28-spatiotemporal-raster-datacube-1.svg" alt="시간, 밴드, 위도, 경도 네 축을 가진 데이터큐브에서 시간 슬라이싱, 픽셀 시계열 추출, 밴드 연산이 각각 어떤 단면에 해당하는지 보여주는 개념도" style="width:100%;">

## 핵심 개념 2: xarray — 축에 이름과 좌표를 붙인 배열

NumPy 배열은 강력하지만 축이 그냥 정수 인덱스(`arr[3, 1, :, :]`)라서, 그 3이 몇 번째 밴드인지 1이 어느 날짜인지는 코드를 보는 사람이 따로 기억해야 한다. **xarray**는 NumPy 배열 위에 각 축의 이름(`time`, `band`, `y`, `x`)과 실제 좌표값(실제 날짜, 밴드 이름, 위경도)을 붙인 `DataArray`/`Dataset` 구조를 제공한다. 그 결과 `cube.sel(time="2026-07-01", band="nir")`처럼 실제 의미가 담긴 값으로 슬라이싱할 수 있고, 좌표계(CRS) 정보도 `rioxarray` 확장을 통해 함께 유지된다.

집계 연산도 축 이름 기준으로 표현한다. "월별 평균"은 `cube.groupby("time.month").mean()` 한 줄이고, "여름철(6~8월) NDVI 평균"은 `cube.sel(time=cube.time.dt.month.isin([6,7,8])).mean(dim="time")`처럼 사람이 읽어도 의도가 그대로 드러나는 코드가 된다.

## 핵심 개념 3: Zarr — 클라우드에서 큐브를 청크 단위로 저장·조회한다

데이터큐브 전체를 메모리에 올리는 것은 대부분 불가능하다. 3년치 일별 위성영상이면 압축 전 기준으로 수백GB~수TB에 달할 수 있다. **Zarr**는 이런 대용량 배열을 **청크(chunk)** 단위로 나눠 저장하는 포맷으로, 클라우드 오브젝트 스토리지(S3, GCS)에 청크 파일들을 흩어 저장해두고 필요한 청크만 부분적으로 읽어올 수 있게 한다. GeoTIFF가 파일 하나에 이미지 한 장을 담는 포맷이라면, Zarr는 여러 시점·여러 밴드를 아우르는 하나의 논리적 배열을 청크로 쪼개 물리적으로 분산 저장하는 포맷이라는 차이가 있다.

xarray와 Zarr를 함께 쓰면 `xr.open_zarr()`로 큐브를 열 때 실제 데이터는 즉시 읽지 않고 **지연 평가(lazy evaluation)** 상태로 메타데이터만 로드한 뒤, 실제로 `.compute()`나 값 접근이 일어날 때만 필요한 청크를 네트워크로 가져온다. 이 지연 평가는 Dask와 결합하면 청크 단위 병렬 처리로도 자연스럽게 확장된다.

| 비교 | GeoTIFF 파일 모음 | Zarr + xarray 데이터큐브 |
|---|---|---|
| 논리 단위 | 파일 하나 = 한 시점 이미지 | 배열 하나 = 전체 시공간 범위 |
| 시계열 조회 | 파일 목록 순회 + 수동 스태킹 | 축 슬라이싱 한 줄 |
| 클라우드 부분 읽기 | Cloud-Optimized GeoTIFF로 일부 가능 | 청크 단위로 기본 지원 |
| 병렬 처리 | 별도 구현 필요 | Dask와 자연스럽게 결합 |

## 예제: xarray + Zarr로 여름철 평균 NDVI 계산

```python
import xarray as xr

# 클라우드에 저장된 Zarr 큐브를 지연 평가로 오픈 (메타데이터만 즉시 로드)
cube = xr.open_zarr("s3://example-bucket/sentinel2-cube.zarr", chunks="auto")
# 예상 차원: (time: 1095, band: 4, y: 10980, x: 10980)

nir = cube["reflectance"].sel(band="nir")
red = cube["reflectance"].sel(band="red")
ndvi = (nir - red) / (nir + red)

# 6~8월만 골라 시간 축 평균 - 실제 계산은 이 시점에 필요한 청크만 로드
summer_ndvi = ndvi.sel(time=ndvi.time.dt.month.isin([6, 7, 8])).mean(dim="time")

summer_ndvi.rio.write_crs("EPSG:32652", inplace=True)
summer_ndvi.rio.to_raster("summer_ndvi_mean.tif")
```

`chunks="auto"`로 열면 xarray가 Dask 배열 위에서 동작해 `.mean(dim="time")` 같은 연산도 청크 단위로 병렬 실행된다. 최종적으로 필요한 것은 요약된 2차원 결과 하나뿐이므로, 원본 수백GB 큐브 전체를 메모리에 올릴 필요가 없다.

## 실무 포인트

- **청크 크기는 접근 패턴에 맞춰 설계할 것**: 시계열 분석이 주 용도라면 time 축은 작게, 공간 축은 크게 청크를 잡아야 하고, 특정 시점의 전체 이미지 조회가 주 용도라면 반대로 잡아야 한다. 청크 크기가 접근 패턴과 어긋나면 매번 불필요하게 넓은 범위를 읽게 된다.
- **STAC 카탈로그와 결합해 큐브를 동적으로 구성하는 방식도 고려할 것**: `stackstac`, `odc-stac` 같은 라이브러리는 STAC API로 검색한 개별 COG 파일들을 그 자리에서 하나의 xarray 큐브처럼 묶어준다. 미리 Zarr로 재적재하지 않고도 데이터큐브 인터페이스를 얻을 수 있어, 데이터 이관 없이 시작하기 좋다.
- **좌표계·리샘플링 정합성을 사전에 확인할 것**: 여러 위성·여러 시점의 영상은 투영법이나 해상도가 다를 수 있다. 큐브로 묶기 전에 공통 격자로 리샘플링해두지 않으면, 축 연산 결과가 픽셀 단위로 미묘하게 어긋난 값을 낼 수 있다.

## 3줄 요약

- 시공간 데이터큐브는 파일들의 모음이 아니라 시간·밴드·위도·경도를 축으로 갖는 다차원 배열 하나로 래스터 시계열을 다루는 접근이다.
- xarray는 그 축에 이름과 실제 좌표값을 붙여 의미 있는 슬라이싱과 집계를 가능하게 하고, Zarr는 청크 단위 저장으로 클라우드에서 필요한 부분만 부분 조회할 수 있게 한다.
- 청크 크기를 접근 패턴에 맞춰 설계하고, 병합 전 좌표계·해상도 정합성을 맞춰야 데이터큐브의 이점을 제대로 살릴 수 있다.

## 참고 자료

- [xarray 공식 문서: Working with Multidimensional Data](https://docs.xarray.dev/en/stable/user-guide/index.html)
- [Zarr 공식 문서: Zarr Specification](https://zarr.readthedocs.io/en/stable/)
- [Pangeo 프로젝트: Data in the Cloud](https://pangeo.io/data.html)
