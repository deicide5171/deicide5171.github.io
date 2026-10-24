---
layout: single
title: "\"필지 데이터 수십만 건을 한 번에 내려주세요\" — GeoServer WFS 대용량 요청 타임아웃을 막는 설계"
date: 2026-10-24 12:45:00 +0530
categories: gis
tags: ["geoserver", "wfs", "ogc-api-features", "postgis", "페이징"]
toc: true
toc_sticky: true
excerpt: "'외부 파트너가 우리 WFS로 지역 전체 필지 데이터를 한 번에 가져가게 해주세요'라는 요구는 GeoServer 설정값 하나로 풀리지 않는다. maxFeatures·startIndex 페이징의 실제 동작과 CSV·Shapefile처럼 공간 인덱스가 없는 스토어가 왜 같은 요청에서만 타임아웃을 내는지, 그리고 OGC API Features로 넘어가야 할 시점을 정리했다."
---

## 도입

"외부 파트너사가 우리 WFS로 특정 시·군 전체 필지 데이터를 한 번에 내려받게 해주세요." GIS 데이터 제공 업무를 맡아본 사람이라면 한 번쯤 받아봤을 요구다. 처음 몇 달은 문제없이 돌아가다가, 어느 날 수십만 건짜리 레이어 하나가 WFS 요청마다 타임아웃을 낸다. 2026년에도 GeoServer 포럼에는 "2.28.1에서 대용량 레이어만 WFS로 타임아웃 난다"는 글이 꾸준히 올라온다. 흥미로운 건 원인이 GeoServer 버전이나 설정이 아니라, 그 레이어가 공간 인덱스 없는 CSV 파일로 올라가 있었다는 데 있었다는 점이다. 즉 "WFS가 느리다"는 증상 뒤에는 보통 서비스 계층이 아니라 데이터 스토어 선택 문제가 숨어 있다.

이 문제는 GeoServer 3.0(2026년 6월, 17년 만의 메이저 개편)이 나오고, OGC API Features가 WFS 1.0/1.1/2.0 옆에 정식 벡터 서비스로 나란히 올라오는 지금 시점에 다시 짚을 필요가 있다. 대용량 요청을 "어떻게 페이징할 것인가"와 "어느 프로토콜로 내보낼 것인가"는 서로 다른 질문이고, 둘 다 설계 판단이 필요하다.

## 왜 같은 설정에서 어떤 레이어만 타임아웃이 나는가

GeoServer의 WFS `maxFeatures`(2.x 기준 기본값이 매우 큰 수치)는 안전장치가 아니라 응답 상한일 뿐이다. 실제 대용량 제어는 `startIndex`와 `count`(WFS 2.0 기준, 1.0/1.1은 `maxFeatures`)로 페이지를 나누는 것으로 한다. 여기서 핵심은 **스토어가 네이티브 정렬을 지원하는가**다.

- PostGIS·GeoPackage처럼 DB 기반 스토어는 `sortBy` 조건을 그대로 쿼리 플랜에 넘겨 인덱스로 OFFSET을 처리한다. 페이지가 깊어져도 비용이 완만히 증가한다.
- Shapefile·CSV처럼 네이티브 정렬이 없는 스토어는 GeoServer가 직접 병합정렬을 수행한다. 이때 메모리에는 최대 1,000건만 유지하고 나머지는 디스크로 스필한다. 깊은 페이지로 갈수록, 그리고 전체 건수가 늘수록 이 디스크 스필 비용이 기하급수적으로 불어난다.

포럼에 올라온 실제 사례도 정확히 이 패턴이었다 — 작은 레이어는 멀쩡한데 수십만 건짜리 레이어만 타임아웃이 났고, 원인은 그 레이어가 공간 인덱스 없는 CSV였다는 진단이었다. 결론은 단순하다: **WFS 설정을 아무리 튜닝해도 스토어가 비인덱스 파일이면 한계가 명확하다.** 대용량 다운로드를 열어줘야 하는 레이어는 먼저 PostGIS나 GeoPackage로 옮기는 것이 선결 조건이다.

## OGC API Features로 넘어가야 하는가

OGC API Features는 WFS와 같은 데이터를 내보내지만 설계 철학이 다르다. WFS가 클라이언트가 `startIndex`·`count`를 직접 계산해 요청하는 "오프셋 기반" 방식이라면, OGC API Features는 응답에 `next` 링크를 포함해 클라이언트가 그 링크만 따라가게 하는 "커서에 가까운" 방식이다. JSON(GeoJSON) 우선 설계라 범용 HTTP 클라이언트·에이전트 도구가 다루기도 더 쉽다.

다만 2026년 기준으로도 아직 완전히 성숙하진 않았다. GeoServer 2.28.2 릴리스 노트에는 OGC API Features 플러그인에서 `CloseableIterator`가 닫히지 않는 버그(GEOS-11979), 지원하지 않는 outputFormat을 WFS가 잘못 광고하던 버그(GEOS-11926) 같은 수정 사항이 포함돼 있다. 즉 핵심 조회 경로는 안정적이지만, 엣지 케이스에서 여전히 패치가 나오고 있는 단계다. "지금 당장 WFS를 완전히 걷어내도 되는가"에는 "아니오"에 가깝고, "신규 통합(특히 에이전트·범용 HTTP 클라이언트 대상)은 OGC API Features부터 검토해도 된다"가 현실적인 답이다.

## 전체 시스템에서의 위치

<img src="/assets/images/posts/2026-10-24-geoserver-wfs-pagination-ogc-api-features-1.svg" alt="클라이언트 요청이 GeoServer의 WFS 또는 OGC API Features 서비스 계층을 거쳐 PostGIS나 CSV 같은 데이터 스토어로 가는 구조도, 스토어에 따라 깊은 페이지 비용이 갈리는 모습" style="width:100%;">

눈여겨볼 지점은 GWC(GeoWebCache)가 이 경로에는 전혀 관여하지 않는다는 것이다. GWC는 렌더링된 타일(WMS 출력)을 캐시하지, `GetFeature`가 뱉는 원시 벡터 피처 응답은 캐시 대상이 아니다. 그래서 "타일은 빠른데 데이터 다운로드만 느리다"는 증상이 흔히 나온다 — 두 경로가 완전히 분리돼 있기 때문이다.

## 선택의 트레이드오프

| 방식 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| WFS 1.0/1.1 (`startIndex`+`maxFeatures`) | 가장 널리 호환, 기존 GIS 클라이언트 대부분 지원 | 깊은 오프셋에서 비인덱스 스토어는 비용 급증 | 기존 QGIS·ArcGIS 클라이언트 연동 유지 |
| WFS 2.0 (`count`+`startIndex`+`sortBy`) | 표준 페이징 파라미터, `sortBy`로 순서 결정론 보장 | 여전히 오프셋 기반, 클라이언트가 페이지 번호를 직접 관리 | 안정적인 정렬 키가 있는 DB 백엔드 레이어 |
| OGC API Features | JSON 우선, `next` 링크로 커서형 탐색, 범용 HTTP 클라이언트·에이전트 친화적 | 일부 엣지케이스 버그 존재(2.28.x 기준), 구형 GIS 클라이언트 미지원 | 신규 통합, 에이전트/툴콜 기반 소비자 |
| 전체 익스포트(ogr2ogr·DB 덤프) | 페이징 로직 자체가 필요 없음, 서버 부하 최소 | 실시간성 없음, 운영 중인 서비스와 별도 배치 필요 | 월 1회 등 정기 대량 배포 |

## 실제 프로젝트 진행 순서

1. **대용량 다운로드를 열어줄 레이어의 백엔드부터 확인한다.** Shapefile·CSV라면 PostGIS나 GeoPackage로 먼저 이관한다 — WFS 설정보다 이 작업의 효과가 크다.
2. **정렬 키를 정한다.** `sortBy`에 쓸 안정적인 유니크 키(기본키 등)가 없으면 페이지 순서가 흔들릴 수 있다.
3. **페이지 크기를 보수적으로 잡고 측정한다.** 처음부터 큰 `count`로 밀어붙이지 말고, 500~2,000건 단위로 늘려가며 응답 시간을 측정한다.
4. **기존 WFS 경로는 유지한 채 OGC API Features를 병행 노출한다.** 신규 통합부터 전환하고, 기존 클라이언트는 당장 바꾸지 않는다.
5. **타임아웃·메모리 모니터링을 건다.** 디스크 스필이 발생하는 비인덱스 스토어 레이어는 알림을 걸어 조기에 잡아낸다.

```bash
# WFS 2.0 페이징 요청 (PostGIS 기반 레이어, 정렬 키로 id 사용)
curl "https://geoserver.example.com/wfs?service=WFS&version=2.0.0&request=GetFeature\
&typeNames=parcels&count=1000&startIndex=2000&sortBy=id"

# OGC API Features 요청 (next 링크를 따라가는 방식)
curl "https://geoserver.example.com/ogc/features/collections/parcels/items?limit=1000"
```

## 실무 포인트

- `maxFeatures` 기본값을 믿지 말고, 레이어별로 실제 운영 가능한 상한을 명시적으로 설정한다.
- CSV·Shapefile 레이어에 대용량 WFS 요청이 들어올 가능성이 있다면, 서비스 노출 전에 반드시 PostGIS로 옮긴다.
- OGC API Features 도입은 "WFS 대체"가 아니라 "신규 소비자용 추가 경로"로 접근하는 편이 2026년 기준 안전하다.

## 마무리

- WFS 대용량 요청이 느려지는 진짜 원인은 대부분 서비스 설정이 아니라 데이터 스토어의 공간 인덱스 유무다.
- OGC API Features는 커서형 페이징과 JSON 우선 설계로 에이전트·범용 클라이언트에 유리하지만, 2026년에도 일부 버그 수정이 진행 중인 단계다.
- 대용량 다운로드를 설계할 때는 백엔드 이관 → 정렬 키 확정 → 페이지 크기 측정 → 신규 경로 병행 노출 순서로 접근한다.

## 참고 자료

- [GeoServer 2.28.2 Release Notes](https://geoserver.org/announcements/2026/01/21/geoserver-2-28-2-released.html)
- [GeoServer 2.28.3 Release Notes](https://geoserver.org/announcements/2026/03/20/geoserver-2-28-3-released.html)
- [WFS for the masses: adding support for paging and sorting in GeoServer](https://ftp.geosolutionsgroup.com/blog/wfs-for-the-masses-adding-support-for-paging-and-sorting-in-geoserver/)
