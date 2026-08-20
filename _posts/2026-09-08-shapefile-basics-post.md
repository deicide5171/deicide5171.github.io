---
layout: single
title: "셰이프파일(Shapefile)이 뭔가요 — 왜 파일이 여러 개인가"
date: 2026-09-08 13:20:00 +0530
categories: gis
tags: ["셰이프파일", "shapefile", "gis", "공간데이터", "입문"]
toc: true
toc_sticky: true
excerpt: "GIS에서 가장 흔히 쓰는 셰이프파일이 무엇이고, 왜 .shp 하나가 아니라 여러 파일로 이뤄지는지 처음 배우는 사람 기준으로 정리했다."
---

## .shp 하나만 받으면 왜 안 열릴까

GIS 데이터를 받으면 `.shp`, `.shx`, `.dbf` 같은 파일이 세트로 온다. `.shp` 하나만 복사하면 제대로 안 열린다. **셰이프파일(Shapefile)**은 사실 **여러 파일이 모여 하나의 공간 데이터를 이루는 형식**이다. 1990년대 Esri가 만든 오래된 포맷이지만, 지금도 가장 널리 쓰인다.

## 구성 파일

![셰이프파일 구성 파일](/assets/images/posts/2026-09-08-shapefile-basics-1.svg)
{: .align-center}

| 확장자 | 역할 | 필수 |
|---|---|---|
| `.shp` | 도형(점·선·면)의 좌표 | 필수 |
| `.shx` | 도형 위치 색인(빠른 접근) | 필수 |
| `.dbf` | 각 도형의 속성(이름·인구 등) | 필수 |
| `.prj` | 좌표계 정보 | 권장 |

`.shp`는 모양, `.dbf`는 속성 표, `.shx`는 둘을 빠르게 연결하는 색인이다. 세 개가 같은 이름으로 함께 있어야 열린다.

## 이렇게 나뉘어 있다

```text
seoul_district.shp   <- 자치구 경계 도형(폴리곤 좌표)
seoul_district.shx   <- 도형 색인
seoul_district.dbf   <- 자치구 이름, 인구 등 속성
seoul_district.prj   <- "이 좌표는 WGS84다" 같은 좌표계 정보

-> 4개가 같은 이름(seoul_district)으로 한 폴더에 있어야 한다.
```

## 실무 포인트

- **파일을 옮길 땐 세트로 옮겨라.** `.shp`만 복사하고 `.dbf`, `.shx`를 빠뜨리면 열리지 않는다. 압축(zip)해서 통째로 주고받는 것이 안전하다.
- **`.prj`가 없으면 좌표계를 모른다.** 좌표계 정보가 빠지면 지도에 엉뚱한 위치로 찍힐 수 있다. 데이터를 받으면 `.prj` 유무와 좌표계(EPSG 코드)를 꼭 확인한다.
- **셰이프파일에는 한계가 있다.** 속성 컬럼 이름이 10자로 제한되고, 한글 인코딩 문제, 2GB 용량 제한 등이 있다. 요즘은 GeoPackage나 GeoJSON 같은 대안도 많이 쓰이니 상황에 맞게 선택한다.

## 마무리 요약

- 셰이프파일은 `.shp`·`.shx`·`.dbf` 등 여러 파일이 세트로 하나의 공간 데이터를 이루는 형식이다.
- `.shp`는 도형, `.dbf`는 속성, `.shx`는 색인, `.prj`는 좌표계 정보를 담는다.
- 파일은 세트로 옮기고 `.prj`(좌표계)를 확인해야 하며, 한계가 있어 GeoPackage 등 대안도 고려한다.

## 참고 자료

- [Esri - Shapefile 개요](https://desktop.arcgis.com/ko/arcmap/latest/manage-data/shapefiles/what-is-a-shapefile.htm)
