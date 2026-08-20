---
layout: single
title: "점이 다각형 안에 있나 판정하기 — Point in Polygon"
date: 2026-09-13 12:20:00 +0530
categories: gis
tags: ["pointinpolygon", "공간연산", "gis", "폴리곤", "입문"]
toc: true
toc_sticky: true
excerpt: "특정 좌표가 어떤 영역(다각형) 안에 있는지 판정하는 Point in Polygon의 개념과 레이 캐스팅 원리를 처음 배우는 사람 기준으로 정리했다."
---

## "이 위치가 우리 배달 지역 안인가?"

사용자 좌표(점)가 배달 가능 구역(다각형) 안에 들어오는지 판단해야 할 때가 있다. 이런 **"점이 다각형 내부에 있는가"를 판정하는 것**을 **Point in Polygon(PIP)**이라 한다. 지오펜싱, 행정구역 판정, 배달 권역 확인 등에 쓰인다.

## 레이 캐스팅 원리

![레이 캐스팅으로 내부 판정](/assets/images/posts/2026-09-13-point-in-polygon-basics-1.svg)
{: .align-center}

```text
점에서 한 방향으로 반직선(ray)을 쏜다.
그 선이 다각형의 변과 몇 번 교차하는지 센다.
- 홀수 번 교차 -> 점은 내부에 있다
- 짝수 번 교차 -> 점은 외부에 있다
```

밖에서 출발한 선이 경계를 한 번 넘으면 안, 두 번 넘으면 다시 밖... 이 규칙이 핵심이다.

## 실무 포인트

- **직접 구현보다 라이브러리를 써라.** 레이 캐스팅은 경계선 위의 점, 꼭짓점 통과 등 예외가 많다. PostGIS의 `ST_Contains`, Turf.js의 `booleanPointInPolygon` 등 검증된 함수를 쓰는 것이 안전하다.
- **많은 점은 공간 인덱스로 먼저 거른다.** 수많은 점 각각을 모든 다각형과 비교하면 느리다. 바운딩 박스·공간 인덱스로 후보를 좁힌 뒤 정밀 PIP를 하면 훨씬 빠르다.
- **좌표계를 맞춰라.** 점과 다각형의 좌표계(EPSG)가 다르면 판정이 어긋난다. 같은 좌표계로 맞춘 뒤 판정한다.

## 마무리 요약

- Point in Polygon은 특정 점이 다각형 내부에 있는지 판정하는 공간 연산이다.
- 레이 캐스팅(반직선의 교차 횟수 홀짝)으로 내부/외부를 가린다.
- 직접 구현보다 검증된 함수를 쓰고, 공간 인덱스로 후보를 좁히며 좌표계를 맞춰야 한다.

## 참고 자료

- [Turf.js - booleanPointInPolygon](https://turfjs.org/docs/#booleanPointInPolygon)
