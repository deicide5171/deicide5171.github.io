---
layout: single
title: "멀쩡해 보이는 폴리곤이 쿼리를 깨뜨린다 — ST_IsValid 진단과 ST_MakeValid 복구"
date: 2026-08-23 13:20:00 +0530
categories: gis
tags: ["gis", "postgis", "st_isvalid", "st_makevalid", "geometry", "sql"]
toc: true
toc_sticky: true
excerpt: "지도에는 정상으로 보이는데 ST_Intersection이 TopologyException을 던지는 이유 — OGC 유효성 규칙, 꼬인 폴리곤 진단법, ST_MakeValid의 linework/structure 복구 방식과 ST_Buffer(0)의 함정을 정리한다."
---

외부에서 받은 행정구역 Shapefile을 PostGIS에 적재하고 `ST_Intersection`으로 겹침 면적을 구하는 순간, `TopologyException: side location conflict` 같은 에러가 터지는 경험은 공간 데이터를 다루는 사람이라면 한 번쯤 겪는다. 더 고약한 경우는 에러조차 나지 않는 쪽이다. `ST_Contains`가 명백히 안에 있는 점을 밖이라고 답하거나, 면적 계산이 음수에 가까운 이상한 값을 내는데, 지도에 그려보면 폴리곤은 아무 문제 없이 멀쩡해 보인다.

원인은 대부분 **유효하지 않은(invalid) 지오메트리**다. PostGIS의 공간 연산은 OGC Simple Features 사양이 정의한 유효성 규칙을 전제로 동작하는데, 디지타이징 실수, 좌표 변환 과정의 반올림, 사용자가 화면에서 그린 도형 등은 이 규칙을 어긴 채 들어오는 일이 흔하다. 렌더링은 규칙 위반을 관대하게 넘기지만, 교차·포함·버퍼 같은 연산은 전제가 깨진 입력 앞에서 예외를 던지거나 조용히 틀린 답을 내놓는다.

이번 글은 폴리곤이 "유효하지 않다"는 것이 정확히 무슨 뜻인지, `ST_IsValid` 계열 함수로 어디가 꼬였는지 짚어내는 방법, 그리고 `ST_MakeValid`로 면적 손실 없이 복구하는 방법을 정리한다.

## 유효성 규칙 — 폴리곤은 언제 '꼬였다'고 판정되는가

OGC 기준으로 폴리곤이 유효하려면 크게 다음 조건을 만족해야 한다. 링(경계선)이 자기 자신과 교차하면 안 되고, 외부 링과 내부 링(구멍)은 선으로 겹치지 않아야 하며(한 점에서 닿는 것은 허용), 구멍은 외곽 링 안에 있어야 하고, 폴리곤 내부는 하나로 연결되어 있어야 한다. 이 조건을 어기는 대표적인 사례가 흔히 나비넥타이(bowtie)라고 부르는 자기 교차 폴리곤이다. 꼭짓점 4개를 잘못된 순서로 이으면 경계선 두 변이 가운데에서 서로를 가로지르는데, 이렇게 되면 "폴리곤의 내부"가 수학적으로 모호해져서 면적·포함 판정이 정의 자체가 안 된다.

| 위반 유형 | 흔한 원인 | ST_IsValidReason 메시지 예 |
|---|---|---|
| 링 자기 교차(bowtie) | 꼭짓점 순서 오류, 편집 실수 | `Self-intersection[x y]` |
| 구멍이 외곽 밖·경계 밖 | 레이어 병합, 좌표 변환 오차 | `Hole lies outside shell` |
| 링끼리 선으로 겹침 | 인접 폴리곤 스냅 실수 | `Self-intersection` 계열 |
| 링이 닫히지 않음 | 수작업 WKT, 데이터 절단 | `Ring is not closed` |
| 중복 링·중첩 외곽 | 중복 적재, 병합 오류 | `Nested shells` |

참고로 `ST_IsSimple`은 주로 라인스트링의 자기 교차를 보는 함수라 폴리곤 검증에는 `ST_IsValid`가 맞다. 둘을 혼동하면 꼬인 폴리곤을 통과시키게 된다.

## 진단 — ST_IsValid, ST_IsValidReason, ST_IsValidDetail

진단 함수는 세 단계로 상세해진다. `ST_IsValid`는 불리언만, `ST_IsValidReason`은 위반 사유 문자열을, `ST_IsValidDetail`은 사유와 함께 **문제 지점의 지오메트리**(location)까지 돌려준다. 대량 테이블을 점검할 때는 아래처럼 위반 행만 뽑아 사유별로 집계하고, location을 지도에 찍어 눈으로 확인하는 흐름이 실용적이다.

```sql
-- 1) 유효하지 않은 행을 사유·위치와 함께 추출
SELECT id,
       reason(ST_IsValidDetail(geom))                    AS why,
       ST_AsText(location(ST_IsValidDetail(geom)))       AS where_at
FROM   admin_boundary
WHERE  NOT ST_IsValid(geom);

-- 2) 위반 유형별 규모 파악
SELECT ST_IsValidReason(geom) AS reason, count(*)
FROM   admin_boundary
WHERE  NOT ST_IsValid(geom)
GROUP  BY 1
ORDER  BY 2 DESC;
```

한 가지 주의할 점은 `ST_IsValid` 자체도 지오메트리 전체를 검사하는 비용이 드는 함수라는 것이다. 매 쿼리마다 검사하는 대신, 적재 시점에 한 번 검증하는 구조가 낫다.

## 복구 — ST_MakeValid의 두 가지 방식

`ST_MakeValid`는 GEOS의 복구 알고리즘을 이용해 **입력 좌표를 버리지 않고** 유효한 지오메트리를 만들어낸다. 나비넥타이 폴리곤이라면 교차점에서 도형을 잘라 두 개의 유효한 폴리곤으로 재조립하고, 결과는 MULTIPOLYGON이 된다.

<img src="/assets/images/posts/2026-08-23-postgis-geometry-validity-1.svg" alt="자기 교차 폴리곤이 ST_MakeValid로 두 개의 유효한 폴리곤으로 분리되는 과정" style="width:100%;">

PostGIS 3.2 이상(GEOS 3.10 이상)에서는 두 번째 인자로 복구 방식을 고를 수 있다.

| 방식 | 동작 | 특징 |
|---|---|---|
| `method=linework` (기본) | 모든 선분을 보존한 뒤 링을 재구성 | 입력 정보 최대 보존, 결과에 선·점이 섞인 GEOMETRYCOLLECTION이 나올 수 있음 |
| `method=structure` | 면 중심으로 재조립, 짜부라진 부분 제거 | 폴리곤 입력이면 폴리곤류 출력 유지, `keepcollapsed` 옵션으로 퇴화 요소 처리 선택 |

실무에서 "폴리곤을 넣었으면 폴리곤이 나와야 한다"는 요구가 대부분이므로, structure 방식을 쓰거나 결과에서 면 성분만 추리는 `ST_CollectionExtract(geom, 3)`을 함께 쓰는 편이 안전하다.

```sql
-- 유효하지 않은 행만 골라 면 성분 보존 방식으로 복구
UPDATE admin_boundary
SET    geom = ST_CollectionExtract(
                ST_MakeValid(geom, 'method=structure keepcollapsed=false'), 3)
WHERE  NOT ST_IsValid(geom);

-- 이후 재유입을 막는 CHECK 제약
ALTER TABLE admin_boundary
  ADD CONSTRAINT chk_geom_valid CHECK (ST_IsValid(geom));
```

## 흔한 함정 — ST_Buffer(geom, 0)로 고치기

오래된 자료나 블로그에는 `ST_Buffer(geom, 0)`으로 유효성을 고치는 트릭이 자주 등장한다. 버퍼 연산이 내부적으로 유효한 결과만 만들기 때문에 실제로 에러는 사라진다. 문제는 **면적이 조용히 사라질 수 있다**는 점이다. 나비넥타이 폴리곤에 버퍼 0을 적용하면 링의 방향 해석에 따라 한쪽 날개가 통째로 버려지는 경우가 있는데, 에러 없이 결과가 나오기 때문에 데이터가 절반 유실된 사실을 나중에야 알게 된다. 반면 `ST_MakeValid`는 입력의 모든 영역을 보존하도록 설계되어 있다. 버퍼 0은 유효성 복구 수단이 아니라 우연히 부작용을 이용하는 안티패턴으로 보는 것이 맞고, 복구는 `ST_MakeValid`로 하는 것이 올바른 선택이다.

## 실무 포인트와 주의사항

- **검증은 적재 파이프라인에서**: `ogr2ogr`·`shp2pgsql`로 적재한 직후 스테이징 테이블에서 검증·복구를 끝내고 본 테이블로 옮기는 구조가 좋다. 본 테이블에는 CHECK 제약을 걸어 재유입을 차단한다.
- **자동 복구가 항상 답은 아니다**: 지적도·경계 분쟁 데이터처럼 원본의 법적 의미가 중요한 경우, `ST_MakeValid`가 만든 형상이 원저작자의 의도와 다를 수 있다. 이런 데이터는 자동 UPDATE 대신 위반 목록을 리포트로 남겨 원천 데이터 수정 요청으로 돌리는 편이 안전하다.
- **geography 타입과 곡률**: geometry에서 유효하던 도형도 재투영 후 다시 꼬일 수 있다. 좌표계 변환이 끼어 있는 파이프라인이라면 변환 후 시점에 검증을 두는 것이 맞다.
- **인덱스는 위반을 못 걸러낸다**: GiST 인덱스는 바운딩 박스만 보므로 invalid 지오메트리도 인덱스는 잘 탄다. "인덱스 스캔은 되는데 recheck 단계에서 터지는" 에러가 그래서 나온다.

## 마무리 요약

- 렌더링은 멀쩡해도 자기 교차·구멍 위치 오류 같은 OGC 유효성 위반은 공간 연산을 깨뜨리며, `ST_IsValidDetail`로 사유와 좌표까지 짚어낼 수 있다.
- 복구는 면적을 보존하는 `ST_MakeValid`(가능하면 `method=structure` + `ST_CollectionExtract`)로 하고, `ST_Buffer(0)` 트릭은 면적 유실 위험이 있는 안티패턴이다.
- 검증·복구는 적재 시점에 한 번 수행하고 CHECK 제약으로 재유입을 막는 구조가, 쿼리마다 검사하는 것보다 훨씬 경제적이다.

## 참고 자료

- [PostGIS 공식 문서 — ST_IsValid](https://postgis.net/docs/ST_IsValid.html)
- [PostGIS 공식 문서 — ST_IsValidDetail](https://postgis.net/docs/ST_IsValidDetail.html)
- [PostGIS 공식 문서 — ST_MakeValid](https://postgis.net/docs/ST_MakeValid.html)
- [PostGIS 공식 문서 — ST_CollectionExtract](https://postgis.net/docs/ST_CollectionExtract.html)
- [GEOS 라이브러리](https://libgeos.org/)
