---
layout: single
title: "공간 관계가 뭔가요 — 포함, 교차, 접함 구분하기"
date: 2026-09-17 13:20:00 +0530
categories: gis
tags: ["공간관계", "spatialrelationship", "postgis", "gis", "입문"]
toc: true
toc_sticky: true
excerpt: "두 도형이 서로 어떤 관계인지(포함·교차·접함 등)를 판정하는 공간 관계의 개념과 대표 함수를 처음 배우는 사람 기준으로 정리했다."
---

## "이 도로가 이 구역을 지나가나?"

두 도형이 서로 겹치는지, 하나가 다른 것을 품는지, 그냥 닿아 있는지를 판단해야 할 때가 있다. 이런 **두 도형 사이의 위치 관계**를 **공간 관계(spatial relationship)**라 한다. 공간 검색·분석의 기본이며, PostGIS 등에서 함수로 판정한다.

## 대표 관계

![공간 관계들](/assets/images/posts/2026-09-17-spatial-relationship-basics-1.svg)
{: .align-center}

| 관계 | 의미 | 함수(PostGIS) |
|---|---|---|
| 포함 | A가 B를 완전히 품음 | `ST_Contains` |
| 교차 | 두 도형이 겹침 | `ST_Intersects` |
| 접함 | 경계만 닿음(내부는 안 겹침) | `ST_Touches` |
| 분리 | 전혀 안 닿음 | `ST_Disjoint` |

## 어디에 쓰나

```text
"이 구역 안의 건물" -> ST_Contains(구역, 건물)
"이 도로와 겹치는 필지" -> ST_Intersects(도로, 필지)
"인접한 행정구역" -> ST_Touches(구역A, 구역B)
```

## 실무 포인트

- **contains와 intersects를 구분하라.** "겹치기만 하면 되나(intersects)" vs "완전히 안에 있어야 하나(contains)"는 결과가 다르다. 도로가 구역을 걸치기만 해도 잡으려면 intersects, 완전히 안에 든 것만 원하면 contains를 쓴다.
- **공간 인덱스로 빠르게.** 공간 관계 판정은 무거우니, 공간 인덱스(GiST)로 후보를 먼저 좁힌 뒤 정밀 판정한다. 인덱스가 없으면 대량 데이터에서 매우 느리다.
- **좌표계·유효성을 확인.** 두 도형의 좌표계가 다르면 판정이 어긋난다. 또 도형이 자기 교차 등으로 "유효하지 않으면" 함수가 이상한 결과를 낼 수 있으니 유효성을 확인·보정한다.

## 마무리 요약

- 공간 관계는 두 도형 사이의 위치 관계(포함·교차·접함·분리 등)다.
- PostGIS의 `ST_Contains`·`ST_Intersects` 등으로 판정하며 공간 검색·분석의 기본이다.
- contains와 intersects를 목적에 맞게 구분하고, 공간 인덱스·좌표계·유효성을 챙긴다.

## 참고 자료

- [PostGIS 공식 문서 - Spatial Relationships](https://postgis.net/workshops/postgis-intro/spatial_relationships.html)
