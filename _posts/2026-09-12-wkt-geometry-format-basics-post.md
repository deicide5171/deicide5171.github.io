---
layout: single
title: "WKT가 뭔가요 — 도형을 글자로 표현하는 방법"
date: 2026-09-12 12:20:00 +0530
categories: gis
tags: ["wkt", "wkb", "지오메트리", "gis", "입문"]
toc: true
toc_sticky: true
excerpt: "공간 도형을 사람이 읽을 수 있는 텍스트로 표현하는 WKT와 그 이진 버전 WKB의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 점·선·면을 어떻게 글자로 적나

공간 도형(점·선·면)을 파일이나 DB에 저장하고 주고받으려면 어떤 형식으로 적어야 한다. **WKT(Well-Known Text)**는 **도형을 사람이 읽을 수 있는 텍스트로 표현하는 표준 형식**이다. `POINT(126.97 37.56)`처럼 도형 종류와 좌표를 글자로 적는다.

## WKT 예시

![WKT로 표현한 도형](/assets/images/posts/2026-09-12-wkt-geometry-format-basics-1.svg)
{: .align-center}

| 도형 | WKT 표현 |
|---|---|
| 점 | `POINT(126.97 37.56)` |
| 선 | `LINESTRING(0 0, 1 1, 2 1)` |
| 면 | `POLYGON((0 0, 4 0, 4 4, 0 0))` |

도형 종류를 대문자로 쓰고, 괄호 안에 좌표를 나열한다. 면(Polygon)은 시작점과 끝점이 같아 닫혀 있다.

## WKT와 WKB

```text
WKT (텍스트):  POINT(126.97 37.56)
  -> 사람이 읽기 쉽다, 디버깅·로그에 좋다

WKB (이진):   0101000000...(바이트)
  -> 사람은 못 읽지만 저장·전송이 작고 빠르다
  -> DB 내부 저장은 보통 WKB
```

같은 도형을 텍스트로 적으면 WKT, 컴퓨터용 이진으로 적으면 WKB다.

## 실무 포인트

- **DB에서 도형을 넣고 뺄 때 자주 만난다.** PostGIS 등에서 `ST_GeomFromText('POINT(...)')`로 WKT를 도형으로 바꾸고, `ST_AsText(geom)`로 도형을 WKT로 확인한다. 저장은 내부적으로 WKB로 된다.
- **좌표 순서는 경도 위도(x y)다.** WKT는 보통 `경도 위도`(x y) 순서다. 위경도 순서를 헷갈리면 엉뚱한 위치가 되니 주의한다.
- **GeoJSON과 용도가 다르다.** WKT는 간결한 텍스트 표현, GeoJSON은 속성까지 담는 JSON 구조다. 웹 API는 GeoJSON, DB 쿼리·간단 표현은 WKT를 쓰는 경우가 많다.

## 마무리 요약

- WKT는 공간 도형을 `POINT(...)`·`POLYGON(...)`처럼 사람이 읽는 텍스트로 표현하는 표준이다.
- WKB는 같은 도형의 이진 버전으로, 저장·전송이 작고 빠르다(DB 내부 저장).
- 좌표는 경도 위도 순이며, DB 입출력에 자주 쓰이고 GeoJSON과는 용도가 구분된다.

## 참고 자료

- [PostGIS 공식 문서 - Well-Known Text](https://postgis.net/docs/using_postgis_dbmanagement.html#OpenGISWKBWKT)
