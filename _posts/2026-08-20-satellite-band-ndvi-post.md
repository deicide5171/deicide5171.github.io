---
layout: single
title: "적외선으로 식생을 읽는 법 — 위성영상 밴드 조합과 NDVI 분석"
date: 2026-08-20 12:20:00 +0530
categories: gis
tags: ["gis", "remote-sensing", "ndvi", "satellite-imagery", "python", "rasterio"]
toc: true
toc_sticky: true
excerpt: "위성이 눈에 보이지 않는 근적외선까지 촬영하는 이유와, 그 밴드를 조합해 NDVI 같은 식생 지수를 계산하는 원리를 실무 관점에서 정리한다."
---

## 왜 위성은 보이지 않는 빛까지 찍는가

위성영상을 "사진"으로만 생각하면 놓치는 부분이 있다. 상업·공공 위성 센서 대부분은 사람 눈에 보이는 Red·Green·Blue뿐 아니라, 눈에 보이지 않는 근적외선(NIR, Near-Infrared) 같은 파장대까지 별도의 **밴드(band)** 로 나눠 기록한다. 각 밴드는 특정 파장 구간의 반사율만 담은 흑백 이미지 한 장이고, 이를 어떻게 조합하느냐에 따라 완전히 다른 정보를 뽑아낼 수 있다.

식생 분석이 대표적이다. 건강한 식물의 잎은 광합성에 쓰는 Red 파장은 강하게 흡수하고, 잎 내부 세포 구조 때문에 NIR은 강하게 반사하는 독특한 반사 특성을 가진다. 이 차이를 하나의 숫자로 압축한 것이 **NDVI(Normalized Difference Vegetation Index, 정규식생지수)** 다. 항공영상 해상도가 올라가는 흐름과는 별개로, "같은 픽셀이라도 어떤 밴드를 어떻게 조합해서 보느냐"는 위성영상 분석의 가장 기초이자 강력한 도구다. 이 글에서는 밴드 조합의 기본 개념과 NDVI 계산 원리, 그리고 실무에서 흔히 겪는 함정을 정리한다.

## 핵심 개념 1: 멀티스펙트럴 밴드 구성

대표적인 광학 위성(Sentinel-2, Landsat 계열 등)은 아래와 같이 여러 밴드를 동시에 기록한다. 정확한 파장 범위는 센서·미션마다 다르므로 아래 수치는 대략적인 예시로만 참고한다.

| 밴드 | 대략적인 용도 |
|---|---|
| Blue | 대기 산란 보정, 수체·연안 관찰 |
| Green | 식생의 녹색 반사 관찰, 참(true color) 합성 |
| Red | 엽록소 흡수 관찰, NDVI 계산의 분모/분자 성분 |
| NIR(근적외선) | 식생 세포 구조 반사, NDVI 계산의 핵심 성분 |
| SWIR(단파적외선) | 수분 함량, 토양·구름 구분 |

밴드를 어떻게 묶어 RGB 채널에 배치하느냐에 따라 같은 원본 데이터에서 전혀 다른 합성영상이 나온다.

| 합성영상 종류 | R 채널 | G 채널 | B 채널 | 주 용도 |
|---|---|---|---|---|
| 참색(True Color) | Red | Green | Blue | 사람 눈에 익숙한 일반 지도 표시 |
| 컬러 적외선(False Color) | NIR | Red | Green | 식생을 선명한 붉은색으로 강조 |
| 농업용 합성 | SWIR | NIR | Red | 작물 스트레스·수분 상태 관찰 |

## 핵심 개념 2: NDVI는 왜 그렇게 계산되나

NDVI는 Red와 NIR 반사율 차이를 -1~1 사이 값으로 정규화한 지수다.

```
NDVI = (NIR − Red) / (NIR + Red)
```

건강한 식생일수록 NIR 반사율은 크고 Red 반사율은 작아 분자가 커지므로 NDVI 값도 커진다. 반대로 나지·도심·수체는 두 밴드 반사율 차이가 작거나 역전되어 NDVI가 0에 가깝거나 음수로 나온다. 분모로 두 값의 합을 쓰는 이유는 조도(빛의 세기) 차이에 따른 절대 반사율 변화를 상쇄해, 촬영 시점이 달라도 비교적 일관된 값을 얻기 위해서다.

| NDVI 대략적 범위 | 일반적 해석 |
|---|---|
| -1.0 ~ 0 | 물, 구름, 눈 |
| 0 ~ 0.2 | 나지, 도심, 암반 |
| 0.2 ~ 0.5 | 저밀도 식생, 관목·초지 |
| 0.5 ~ 1.0 | 고밀도·건강한 식생 |

다만 이 구간 경계는 센서, 대기보정 방식, 촬영 계절에 따라 흔들릴 수 있는 참고값이지 고정된 기준이 아니다. 그래서 실무에서는 절대값 하나만 보기보다 같은 지역의 시계열 변화를 비교하는 방식을 더 신뢰한다.

<img src="/assets/images/posts/2026-08-20-satellite-band-ndvi-1.svg" alt="위성 밴드 조합과 NDVI 계산 개념도 - Blue, Green, Red, NIR 밴드에서 NDVI 공식이 도출되는 과정과 값의 범위별 해석" style="width:100%;">

## 예제: Python(rasterio)으로 NDVI 계산하기

멀티밴드 GeoTIFF에서 Red, NIR 밴드를 읽어 NDVI를 계산하는 기본 패턴이다.

```python
import rasterio
import numpy as np

with rasterio.open("sentinel2_scene.tif") as src:
    red = src.read(4).astype("float32")   # 밴드 순서는 데이터 제공처 스펙 확인 필수
    nir = src.read(8).astype("float32")
    profile = src.profile

# 0으로 나누는 상황(구름, 마스크 영역) 방지
denominator = nir + red
ndvi = np.where(denominator == 0, 0, (nir - red) / denominator)

profile.update(dtype="float32", count=1, nodata=None)
with rasterio.open("ndvi_output.tif", "w", **profile) as dst:
    dst.write(ndvi, 1)
```

밴드 번호는 예시일 뿐이며 실제 사용하는 위성·제공처의 밴드 순서 문서를 반드시 확인해야 한다. 분모가 0이 되는 픽셀(주로 구름 마스크나 결측 영역)을 처리하지 않으면 `NaN`이나 `inf`가 섞여 후속 시각화·통계 작업이 깨질 수 있다.

## 실무 포인트

- **대기보정 여부를 먼저 확인한다**: 대기보정이 안 된 원시 반사율(TOA, Top of Atmosphere)과 지표 반사율(surface reflectance)은 같은 장면이라도 NDVI 값이 달라질 수 있다. 시계열 비교 시에는 보정 수준을 통일해야 한다.
- **구름·그림자 마스크를 먼저 적용한다**: 구름이나 그림자가 낀 픽셀은 NDVI 계산 자체가 무의미하므로, 제공처가 함께 배포하는 품질 마스크(QA 밴드)를 먼저 적용해 제외하는 것이 일반적이다.
- **NDVI만이 정답은 아니다**: 토양 배경 영향을 줄인 SAVI, 대기 영향을 추가로 보정한 EVI처럼 목적에 따라 다른 식생 지수를 쓰는 경우도 많다. NDVI는 계산이 단순하고 널리 쓰이는 기본값에 가깝다.
- **절대값보다 변화량을 본다**: 센서·촬영 시점이 다르면 절대 NDVI 값 자체를 그대로 비교하기보다, 같은 지역·같은 전처리 파이프라인에서 나온 값끼리 시계열로 비교하는 편이 안전하다.

## 3줄 요약

- 위성 센서는 눈에 보이지 않는 NIR 같은 밴드까지 별도로 기록하며, 밴드 조합 방식에 따라 전혀 다른 정보를 얻을 수 있다.
- NDVI는 `(NIR-Red)/(NIR+Red)` 공식으로 식생의 반사 특성 차이를 -1~1 값으로 정규화하며, 값이 클수록 건강한 식생을 의미하는 경향이 있다.
- 구름 마스크 적용, 대기보정 수준 통일, 절대값보다 시계열 변화 비교가 실무 정확도를 높이는 핵심 포인트다.

## 참고 자료

- [NASA Earth Observatory — Measuring Vegetation (NDVI)](https://earthobservatory.nasa.gov/features/MeasuringVegetation)
- [ESA Sentinel-2 User Guide — Spectral Bands](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/definitions)
- [rasterio 공식 문서](https://rasterio.readthedocs.io/)
