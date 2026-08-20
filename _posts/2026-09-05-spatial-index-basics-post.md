---
layout: single
title: "공간 인덱스가 뭔가요 — 반경 검색이 빨라지는 원리"
date: 2026-09-05 12:20:00 +0530
categories: gis
tags: ["공간인덱스", "r-tree", "postgis", "gis입문", "성능"]
toc: true
toc_sticky: true
excerpt: "'내 위치 반경 1km 안의 가게 찾기' 같은 공간 검색이 왜 일반 인덱스로는 느린지, 공간 인덱스가 이를 어떻게 해결하는지 정리했다."
---

## 반경 검색은 왜 일반 인덱스로 안 되나

"내 위치에서 1km 안에 있는 카페를 찾아라"는 검색은 흔하지만, 일반 인덱스로는 빠르게 처리하기 어렵다. 일반 B-Tree 인덱스는 "값이 크다/작다"로 정렬된 1차원 데이터에 적합한데, 위치는 위도·경도라는 2차원 값이기 때문이다. **공간 인덱스(Spatial Index)**는 이 2차원 위치 데이터를 빠르게 검색하기 위한 전용 인덱스다.

<img src="/assets/images/posts/2026-09-05-spatial-index-basics-1.svg" alt="공간 인덱스가 지도를 사각형 경계상자(bounding box)로 계층적으로 묶어, 검색 영역과 겹치지 않는 넓은 영역을 한 번에 건너뛰며 후보를 좁히는 R-tree 원리를 보여주는 다이어그램" style="width:100%;">

## 왜 빠른가: 경계 상자로 후보 좁히기

공간 인덱스(대표적으로 R-tree)의 핵심 아이디어는 **경계 상자(bounding box)로 묶기**다. 가까운 도형들을 사각형으로 묶고, 그 사각형들을 다시 더 큰 사각형으로 묶는 계층 구조를 만든다.

```text
검색 영역과 겹치지 않는 큰 사각형은 그 안의 수천 개 점을
하나하나 확인할 필요 없이 통째로 건너뛴다.

-> 전체를 다 검사(Full Scan)하지 않고
   겹칠 가능성이 있는 영역만 파고들어 후보를 확 줄인다.
```

## PostGIS에서 공간 인덱스 만들기

```sql
-- 공간 컬럼(geom)에 GiST 공간 인덱스 생성
CREATE INDEX idx_places_geom ON places USING GIST (geom);

-- 반경 검색 (인덱스가 있으면 훨씬 빠르다)
SELECT name
FROM places
WHERE ST_DWithin(
    geom::geography,
    ST_MakePoint(126.978, 37.5665)::geography,
    1000  -- 1km
);
```

PostGIS에서는 `USING GIST`로 공간 인덱스를 만든다. 이 인덱스가 없으면 반경 검색이 테이블 전체를 훑어 데이터가 많을수록 급격히 느려진다.

## 실무 포인트

- **공간 인덱스가 있어도 쿼리를 인덱스가 탈 수 있게 써야 한다.** `ST_DWithin`처럼 인덱스를 활용하는 함수를 써야 하며, 좌표에 불필요한 변환을 씌우면 인덱스를 못 탈 수 있다.
- **경계 상자는 어디까지나 1차 필터다.** R-tree는 사각형으로 후보를 빠르게 좁히지만, 실제로 원 안에 드는지는 정밀 계산으로 다시 확인한다. 즉 "대충 걸러내고 → 정확히 판정"하는 2단계로 동작한다.
- **공간 인덱스는 데이터가 많을 때 진가를 발휘한다.** 수백 건 수준의 작은 테이블에서는 전체 스캔이 오히려 빠를 수 있으므로, 옵티마이저가 인덱스를 안 쓰기로 판단하는 것도 정상이다.

## 마무리 요약

- 위치는 2차원 데이터라 1차원용 일반 인덱스로는 반경 검색을 빠르게 못 한다.
- 공간 인덱스(R-tree)는 도형을 경계 상자로 계층적으로 묶어, 겹치지 않는 영역을 통째로 건너뛰며 후보를 좁힌다.
- PostGIS에서는 `USING GIST`로 공간 인덱스를 만들고 `ST_DWithin` 같은 함수로 인덱스를 활용해야 빠르다.

## 참고 자료

- [PostGIS 공식 문서 - 공간 인덱스](https://postgis.net/workshops/postgis-intro/indexing.html)
- [PostgreSQL 공식 문서 - GiST 인덱스](https://www.postgresql.org/docs/current/gist.html)
