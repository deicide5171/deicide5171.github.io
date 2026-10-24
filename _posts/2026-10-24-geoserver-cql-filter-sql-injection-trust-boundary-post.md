---
layout: single
title: "\"지도에서 사용자가 직접 검색 조건을 걸게 해주세요\" — GeoServer CQL 필터가 뚫렸을 때의 신뢰 경계"
date: 2026-10-24 12:45:00 +0530
categories: gis
tags: ["geoserver", "postgis", "cql필터", "sql인젝션", "wms보안"]
toc: true
toc_sticky: true
excerpt: "지도 화면에 사용자 정의 검색 조건을 걸어달라는 요구는 GeoServer의 CQL 필터를 그대로 사용자 입력에 노출하는 설계로 이어지기 쉽다. 2026년 8월 공개된 jsonArrayContains SQL 인젝션(CVSS 9.8)은 2023년에 이미 패치했던 구멍이 되살아난 사례다. 패치만으로 끝낼 문제가 아니라 CQL 필터를 외부에 얼마나 노출할지 자체를 다시 설계해야 하는 이유를 정리했다."
---

## 왜 지금 이 판단이 필요한가

"매물 지도에서 사용자가 직접 '가격 3억 이하이면서 옵션에 발코니 포함' 같은 조건으로 검색하게 해주세요." 이런 요구를 GeoServer 기반 WMS/WFS 서비스에서 가장 빠르게 구현하는 방법은 GeoServer의 CQL 필터 파라미터(`CQL_FILTER`)를 프런트엔드 쿼리 파라미터와 거의 그대로 연결하는 것이다. GeoTools가 CQL을 내부적으로 SQL로 번역해 데이터소스에 넘겨주기 때문에, 개발자 입장에서는 별도 쿼리 빌더를 짤 필요 없이 사용자 입력을 바로 지도 레이어 필터링에 쓸 수 있다는 유혹이 크다.

2026년 8월 12일 공개된 **jsonArrayContains SQL 인젝션(CVSS 9.8)**은 바로 이 지점을 찌른다. PostGIS 데이터소스에서 JSON/JSONB 컬럼을 다루는 `jsonArrayContains` CQL 함수가 사용자 입력을 이스케이프 없이 PostgreSQL의 `jsonb_path_exists()` 표현식에 그대로 끼워 넣는다는 사실이 드러났고, 인증 없이 WMS·WFS 엔드포인트를 통해 임의 SQL을 실행할 수 있는 경로가 공개 직후부터 실제 공격 시도로 이어졌다. 더 뼈아픈 건 이것이 **2023년 CVE-2023-25158로 이미 한 번 막았던 CQL-to-SQL 인젝션 계열의 회귀(regression)**라는 점이다. 빌더에게 중요한 질문은 "이번 버전만 패치하면 끝나는가"가 아니라 "사용자 입력이 CQL 필터를 거쳐 SQL까지 도달하는 구조 자체를 계속 유지해도 되는가"다.

## 핵심 개념 1 — CQL 필터는 설계상 SQL에 가깝다

GeoServer의 CQL(Common Query Language)은 OGC 표준 필터를 사람이 읽기 쉬운 문법으로 감싼 것이고, 내부적으로 GeoTools가 이를 각 데이터소스의 네이티브 쿼리(PostGIS면 SQL, Oracle이면 PL/SQL)로 번역한다. 문제는 이 번역 계층이 "필터 문법"과 "쿼리 문자열 조립"의 경계에서 흔들린다는 점이다. `jsonArrayContains`처럼 특정 함수가 사용자 제공 값을 매개변수 바인딩 없이 문자열로 직접 삽입하면, CQL 필터는 사실상 SQL 인젝션의 입력창이 된다. PostGIS 12 이상에서 String·JSON 컬럼을 다루는 데이터소스가 영향을 받으며, 일부 보고는 기반 DB 계정 권한이 높을 경우 원격 코드 실행까지 이어질 수 있다고 지적한다.

## 핵심 개념 2 — 패치는 증상 치료, 구조 문제는 따로 있다

GeoServer 메인테이너는 3.0.1·2.28.5·2.27.6(GeoTools 35.1·34.5·33.6)에서 이 문제를 수정했다. 그런데 같은 유형의 취약점이 3년 만에 재발했다는 사실 자체가 "CQL 필터를 외부 사용자 입력에 직접 연결하는 패턴"이 구조적으로 반복 위험을 안고 있다는 신호다. 패치를 적용해도, 아직 발견되지 않은 다른 CQL 함수가 같은 실수를 반복하고 있을 가능성을 배제할 수 없다. 그래서 이번 사고를 계기로 점검해야 할 것은 버전 번호 하나가 아니라 "사용자 입력이 어디서부터 어디까지 CQL 문자열 조립에 관여하는가"라는 신뢰 경계 자체다.

## 전체 시스템에서의 위치

<img src="/assets/images/posts/2026-10-24-geoserver-cql-filter-sql-injection-trust-boundary-1.svg" alt="사용자 입력이 프런트엔드 쿼리 파라미터를 거쳐 GeoServer CQL_FILTER로, 다시 GeoTools CQL 파서를 거쳐 PostGIS SQL로 번역되는 경로와, 신뢰 경계를 어디에 둬야 하는지 보여주는 구조도" style="width:100%;">

사용자가 지도 화면에서 입력한 검색 조건은 프런트엔드에서 `CQL_FILTER` 쿼리 파라미터로 조립돼 GeoServer WMS/WFS 엔드포인트로 전송되고, GeoTools의 CQL 파서가 이를 PostGIS SQL로 번역해 DB에 직접 질의한다. 이 경로 전체가 **인증 없이 외부에 열려 있는 WMS/WFS 레이어**라면, 신뢰 경계는 사실상 존재하지 않는 것과 같다. 안전한 구조는 사용자 입력을 CQL 문자열로 바로 전달하지 않고, 애플리케이션 서버가 허용된 필드·연산자 화이트리스트 안에서만 CQL을 조립하거나, 아예 CQL을 거치지 않는 파라미터화된 WFS 요청으로 제한하는 것이다.

## 선택의 트레이드오프

| 선택지 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| 패치만 적용, 구조 유지 | 작업량 최소, 빠른 대응 | 다음 CQL 함수 취약점에 동일하게 노출 | 내부망 전용, 신뢰된 사용자만 접근하는 서비스 |
| CQL 필드·연산자 화이트리스트 | 유연성 유지하며 공격면 축소 | 화이트리스트 유지보수 필요 | 사용자 정의 검색이 핵심 기능인 공개 서비스 |
| CQL 미노출, 사전 정의 WFS 파라미터만 허용 | 공격면 대부분 제거 | 자유도 낮은 검색 UX | 보안 민감도가 높은 공공·금융 연동 서비스 |
| DB 계정 최소 권한 분리 (근본 대책은 아님) | RCE로의 확산 차단 | SQL 인젝션 자체는 막지 못함 | 위 세 선택지와 병행하는 기본 위생 조치 |

공개 인터넷에 WMS/WFS를 열어 사용자 정의 검색을 제공하는 서비스라면 패치만으로 끝내서는 안 된다. 화이트리스트 또는 CQL 미노출 중 하나로 구조를 바꾸는 작업을 패치와 함께 로드맵에 올려야 한다.

## 실제 프로젝트 진행 순서

1. **버전부터 확인한다.** GeoServer 3.0.1/2.28.5/2.27.6 미만이고 PostGIS 데이터소스를 쓰고 있다면 최우선 긴급 패치 대상이다.
2. **패치 적용 전까지는 DB 계정 권한을 최소화한다.** GeoServer가 쓰는 PostGIS 계정에서 DDL·슈퍼유저 권한을 제거해 RCE로의 확산 경로를 차단한다.
3. **`CQL_FILTER`를 외부에서 직접 받는 엔드포인트를 전수 조사한다.** 리버스 프록시나 API 게이트웨이 단에서 해당 파라미터를 일시적으로 차단하거나 정규식으로 제한하는 임시 방어막을 건다.
4. **패치 적용 후, CQL을 사용자 입력에서 분리하는 리팩터링을 계획한다.** 애플리케이션 서버가 필드·연산자 화이트리스트로 CQL을 조립하거나, WFS 표준 파라미터(`propertyName`, `filter` XML 인코딩)로 전환한다.
5. **PostGIS 로그·GeoServer 접근 로그에서 과거 요청 중 의심스러운 CQL 패턴이 있었는지 소급 점검한다.**

```sql
-- 취약했던 패턴 예: 사용자 입력이 JSON 경로 표현식에 그대로 삽입됨
-- CQL: jsonArrayContains(properties, '${userInput}')
-- 번역된 SQL (단순화):
SELECT * FROM parcels
WHERE jsonb_path_exists(properties, '${userInput}');  -- userInput 이스케이프 없음

-- 안전한 대안: 허용된 키만 화이트리스트로 받아 파라미터 바인딩으로 조립
SELECT * FROM parcels
WHERE properties @> jsonb_build_object($1::text, $2::text);
```

## 마무리 요약

- jsonArrayContains SQL 인젝션(2026-08, CVSS 9.8)은 GeoServer CQL 필터가 사용자 입력을 PostGIS SQL로 이스케이프 없이 번역하면서 발생했고, 2023년에 패치했던 취약점의 회귀다.
- 패치(3.0.1·2.28.5·2.27.6)는 필수지만, 같은 패턴이 반복됐다는 사실 자체가 "CQL을 사용자 입력에 직접 연결하는 구조"를 다시 설계해야 한다는 신호다.
- 화이트리스트 기반 CQL 조립이나 CQL 미노출 WFS 파라미터로 전환하는 것이 장기적으로 더 안전하다.

## 참고 자료

- GeoServer 공식 GitHub Security Advisory, Unauthenticated PostGIS SQL injection in the jsonArrayContains filter function
- GeoServer 2.28.5 / 3.0.1 / 2.27.6 릴리스 노트
- GeoTools 보안 권고, CVE-2023-25158 및 관련 회귀 분석
