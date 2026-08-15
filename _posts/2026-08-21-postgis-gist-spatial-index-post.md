---
layout: single
title: "PostGIS 공간 인덱스 파헤치기 — GiST로 빠른 반경 검색 구현하기"
date: 2026-08-21 12:20:00 +0530
categories: gis
tags: ["gis", "postgis", "gist", "spatial-index", "postgresql", "sql"]
toc: true
toc_sticky: true
excerpt: "일반 B-tree 인덱스로는 답이 안 나오는 반경 검색·공간 조인 쿼리를, PostGIS의 GiST 공간 인덱스가 R-tree 구조로 어떻게 빠르게 처리하는지 정리한다."
---

"내 위치에서 반경 3km 이내 매장 찾기" 같은 쿼리를 처음 구현할 때, 위도(latitude)·경도(longitude) 컬럼에 일반 인덱스를 걸고 나면 얼추 될 것 같다는 착각이 든다. 하지만 실제로 `WHERE lat BETWEEN ... AND lon BETWEEN ...` 식으로 사각 범위를 걸어보면, 데이터가 조금만 늘어도 쿼리가 느려지는 경우가 많다. B-tree 인덱스는 값 하나를 기준으로 한 줄 세우기(정렬)에는 강하지만, 위도와 경도라는 두 축을 동시에 고려해 "이 점이 이 범위 안에 있는가"를 판단하는 데는 근본적으로 맞지 않는 구조이기 때문이다.

더 근본적인 문제는 실제 반경 검색이 사각 범위 비교로 끝나지 않는다는 점이다. 지구는 평면이 아니므로 정확한 거리 계산에는 구면 삼각법이나 타원체 모델이 들어가고, PostGIS에서는 이를 `ST_DWithin`, `ST_Distance` 같은 함수로 감싸 제공한다. 그런데 이런 함수를 인덱스 없이 테이블 전체 행에 대해 매번 계산하면, 행 하나하나를 순차 스캔(Seq Scan)하면서 거리 함수를 실행하는 셈이라 데이터가 많아질수록 비용이 선형으로 늘어난다. 위도·경도에 B-tree 인덱스를 걸어봐야 이 거리 계산 자체를 건너뛰게 해주지는 못한다.

이 문제를 풀기 위해 PostGIS는 `geometry`/`geography` 타입 컬럼에 GiST(Generalized Search Tree) 인덱스를 사용한다. B-tree가 값의 순서를 기준으로 트리를 구성하는 것과 달리, GiST 공간 인덱스는 도형을 감싸는 사각형(바운딩 박스)을 계층적으로 묶어, 계산량이 큰 정확한 거리 판정 전에 "애초에 후보가 될 수 없는 행"을 미리 걸러낸다.

## 핵심 개념 1: GiST 인덱스의 R-tree 기반 바운딩 박스 구조

PostGIS의 공간 인덱스는 GiST라는 범용 인덱스 프레임워크 위에, 공간 데이터를 위한 R-tree류 연산자 클래스를 얹어 구현되어 있다. 핵심 아이디어는 각 도형(점, 선, 폴리곤)을 감싸는 최소 바운딩 사각형(MBR, Minimum Bounding Rectangle)을 계산한 뒤, 가까이 있는 MBR끼리 묶어 상위 노드의 더 큰 MBR로 감싸는 과정을 반복해 트리를 쌓는다는 점이다. 리프 노드에는 실제 도형에 가까운 개별 MBR이, 루트에 가까운 상위 노드에는 그 아래 여러 MBR을 모두 포함하는 더 큰 MBR이 저장된다.

검색할 때는 루트부터 시작해, 쿼리 영역과 겹치지 않는 상위 MBR 전체를 한 번에 건너뛴다. 겹치는 가지만 따라 내려가면서 후보를 좁히고, 최종적으로 리프 노드에서 실제 도형과의 정확한 관계(포함·교차·거리)를 계산한다. 즉 GiST는 "정답을 정확히 찾아주는 인덱스"가 아니라 "명백히 답이 아닌 영역을 빠르게 제외해주는 인덱스"에 가깝다. 정확한 판정은 결국 실제 지오메트리 연산이 맡고, 인덱스는 그 연산을 실행할 후보 집합을 줄여주는 역할을 한다.

<img src="/assets/images/posts/2026-08-21-postgis-gist-spatial-index-1.svg" alt="GiST 공간 인덱스의 바운딩 박스 계층 구조와 트리 탐색 과정" style="width:100%;">

## 핵심 개념 2: 공간 함수와 인덱스가 맞물리는 방식

PostGIS의 공간 연산자와 함수는 이 GiST 구조와 맞물리도록 설계되어 있다. `&&` 연산자(바운딩 박스 겹침)는 GiST 트리를 그대로 타면서 후보를 좁히는 데 쓰이고, `ST_Intersects`, `ST_Contains`, `ST_DWithin` 같은 함수는 내부적으로 이 `&&` 연산자를 이용한 "인덱스 검색 + 정확한 재확인(recheck)" 2단계로 실행되도록 최적화되어 있다.

특히 반경 검색에 자주 쓰는 `ST_DWithin(geom1, geom2, distance)`는 겉보기엔 순수한 거리 계산 함수처럼 보이지만, 실제로는 실행 계획 단계에서 거리만큼 확장된 바운딩 박스로 GiST 인덱스를 먼저 탐색한 뒤, 남은 후보에 한해서만 정확한 거리 계산을 수행한다. 그래서 `ST_Distance(geom1, geom2) < 3000` 같은 식보다 `ST_DWithin(geom1, geom2, 3000)`을 쓰는 편이 인덱스를 확실히 태울 수 있어 권장된다. 전자는 옵티마이저 입장에서 인덱스를 활용하기 어려운 형태이기 때문이다.

일반 B-tree와 GiST 공간 인덱스의 차이를 정리하면 다음과 같다.

| 구분 | B-tree | GiST(공간 인덱스) |
|---|---|---|
| 기본 구조 | 정렬된 값의 이진 트리 | 바운딩 박스 계층 트리(R-tree류) |
| 강한 연산 | `=`, `<`, `>`, `BETWEEN` | `&&`, `ST_Contains`, `ST_DWithin` 등 공간 관계 |
| 다룰 수 있는 차원 | 사실상 1차원(정렬 가능한 값) | 다차원 도형(점·선·폴리곤·바운딩 박스) |
| 판정 정확도 | 인덱스만으로 정확한 결과 | 인덱스는 후보 축소, 최종 판정은 recheck 필요 |
| 대표 대상 컬럼 | id, 날짜, 문자열 등 | geometry, geography |

## 예제

```sql
-- 매장 위치 테이블에 GiST 공간 인덱스 생성
CREATE INDEX idx_stores_geom
  ON stores
  USING GIST (geom);

-- 반경 3km 이내 매장 조회 (geography 캐스팅으로 미터 단위 사용)
EXPLAIN ANALYZE
SELECT id, name
FROM stores
WHERE ST_DWithin(
  geom::geography,
  ST_SetSRID(ST_MakePoint(127.0276, 37.4979), 4326)::geography,
  3000
);
```

`EXPLAIN ANALYZE` 결과에서 `Index Scan using idx_stores_geom` 또는 `Bitmap Index Scan`이 보이면 GiST 인덱스가 실제로 사용되고 있다는 뜻이다. 반대로 `Seq Scan on stores`가 나온다면, 인덱스를 만들었더라도 옵티마이저가 이를 선택하지 않았다는 의미이므로 조건절 작성 방식이나 통계 정보를 다시 점검해야 한다.

## 실무 포인트

- **복합 인덱스로 필터 컬럼과 함께 좁히기**: 반경 검색에 매장 상태(`status = 'open'`)나 카테고리 같은 조건이 함께 붙는 경우가 많다. 이럴 때는 GiST 공간 인덱스 하나에만 의존하기보다, 자주 같이 쓰이는 일반 컬럼에 별도의 B-tree 인덱스를 두거나, PostgreSQL 버전에 따라 `btree_gist` 확장을 활용해 공간 조건과 일반 조건을 하나의 복합 GiST 인덱스로 묶는 방법을 검토할 만하다.
- **VACUUM과 통계 갱신을 소홀히 하지 않기**: 옵티마이저가 인덱스를 쓸지 순차 스캔을 쓸지는 테이블 통계(`pg_stats`)에 크게 의존한다. 대량 삽입·삭제가 잦은 테이블이라면 `ANALYZE`가 오래된 통계를 들고 있을 수 있으므로, 자동 VACUUM 설정을 점검하거나 필요 시 수동으로 `VACUUM ANALYZE`를 실행해 통계를 최신 상태로 유지하는 편이 안전하다.
- **geometry와 geography 선택도 인덱스 성능에 영향**: `geometry` 타입은 평면 좌표 기준으로 빠르지만 정확한 거리 계산에는 좌표계 변환이 필요하고, `geography`는 구면 계산을 기본으로 제공하는 대신 일반적으로 더 무겁다. 데이터 규모와 정밀도 요구 수준에 맞춰 타입을 고르고, 그에 맞는 SRID를 명시적으로 지정해야 인덱스가 의도대로 동작한다.

## 3줄 요약

- 위도·경도에 B-tree 인덱스를 걸어도 반경 검색은 빨라지지 않는다. B-tree는 다차원 공간 관계를 다루도록 설계되지 않았기 때문이다.
- PostGIS의 GiST 공간 인덱스는 바운딩 박스를 계층적으로 묶은 R-tree류 구조로, 정확한 판정 전에 명백히 답이 아닌 후보를 빠르게 걸러낸다.
- `ST_DWithin`처럼 인덱스 친화적인 함수를 쓰고, `EXPLAIN ANALYZE`로 실제 인덱스 사용 여부를 확인하며, 통계 갱신과 복합 인덱스 전략을 함께 챙겨야 실무에서 효과를 본다.

## 참고 자료

- [PostGIS 공식 문서: 공간 인덱스](https://postgis.net/docs/using_postgis_dbmanagement.html#idm590)
- [PostGIS 공식 문서: ST_DWithin](https://postgis.net/docs/ST_DWithin.html)
- [PostGIS 공식 문서: GiST 인덱스 튜닝](https://postgis.net/docs/performance_tips.html)
