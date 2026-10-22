---
layout: single
title: "포인트클라우드도 변환 없이 스트리밍한다 — COPC 포맷과 브라우저 디코딩 설계"
date: 2026-10-22 12:45:00 +0530
categories: gis
tags: ["copc", "포인트클라우드", "lidar", "pdal", "클라우드네이티브"]
toc: true
toc_sticky: true
excerpt: "'드론으로 찍은 LiDAR 스캔을 바로 지도에 올려 보여주세요'라는 요구는 그동안 Potree용 전용 포맷으로 변환하는 전처리 파이프라인을 의미했다. LAZ 파일을 그대로 HTTP Range Request로 스트리밍하는 COPC 포맷이 이 전처리 단계를 어떻게 없애는지, Potree 방식과의 트레이드오프와 도입 순서를 정리했다."
---

## 도입

"드론으로 찍은 LiDAR 스캔 데이터, 변환 없이 바로 지도에 올려서 보여주세요." 측량·건설 현장 담당자가 한 번쯤 던지는 요구다. 문제는 LiDAR 스캔 결과물이 보통 수억 개 점으로 이뤄진 LAS·LAZ 파일 한 덩어리라는 데 있다. 이 파일을 브라우저에 그대로 던지면 로딩만 몇 분이 걸리거나 아예 멈춘다. 그래서 지금까지 표준 해법은 Potree였다 — 원본 포인트클라우드를 옥트리(Octree) 구조로 쪼개 전용 포맷으로 미리 변환해두고, 뷰어가 필요한 LOD(Level of Detail)만 요청해 스트리밍하는 방식이다. 효과는 확실했지만 "변환 없이"라는 요구사항과는 거리가 있었다 — 서버 한쪽에 전처리 파이프라인을 또 하나 세워야 했다.

COPC(Cloud Optimized Point Cloud)는 이 전제를 바꾼다. LAS 1.4 PDRF 6·7·8 포맷만 지원하는 일반 LAZ 압축 파일 안에, 점들을 옥트리 순서로 재배치하고 그 계층 구조를 설명하는 VLR(Variable Length Record)을 끼워 넣은 것뿐이다. 파일 확장자도 그대로 `.laz`다. 그래서 COPC가 아닌 일반 LAZ 리더로 열어도 깨지지 않고, COPC를 이해하는 클라이언트는 같은 파일에서 HTTP Range Request만으로 필요한 영역·해상도의 점만 뽑아 쓴다. PMTiles가 벡터 타일에서 했던 일을 포인트클라우드에서 해내는 셈이다. 2026년 가을 Cesium·MapLibre 기반 오픈소스 플랫폼 GeoLibre가 v3.x에서 COPC 디코딩을 브라우저 엔진에 직접 넣으면서, 별도 뷰어 없이 지도 안에서 바로 포인트클라우드를 다루는 흐름이 빨라지고 있다.

## 전체 시스템에서의 위치

같은 LiDAR 원본에서 출발해도 Potree 경로와 COPC 경로는 데이터가 거치는 단계 자체가 다르다.

<img src="/assets/images/posts/2026-10-22-copc-point-cloud-streaming-browser-1.svg" alt="LiDAR 원본 데이터가 Potree 전처리 파이프라인을 거치는 경로와 COPC로 바로 변환해 정적 스토리지에서 스트리밍하는 경로를 비교한 구조도" style="width:100%;">

- **입력**은 드론·차량 LiDAR 스캐너가 뱉는 LAS/LAZ 포인트클라우드 원본이다. 보통 수억~수십억 개 점, 수십 GB 단위다.
- **Potree 경로**: `PotreeConverter`로 전용 옥트리 포맷(바이너리 타일)과 메타데이터를 생성 — 상시 또는 배치 전처리 서버가 필요하다. 결과물은 Potree 뷰어 전용이라 다른 도구와 호환되지 않는다.
- **COPC 경로**: `PDAL writers.copc` 또는 `untwine`으로 원본을 COPC로 한 번만 변환한다. 변환 자체는 필요하지만 출력물이 표준 LAZ이므로, 변환 후에는 S3·R2 같은 정적 오브젝트 스토리지에 올려두고 서버 프로세스 없이 HTTP Range Request만으로 서빙한다.
- **출력**: Cesium(Eptium 계열 뷰어), copc.js, GeoLibre 같은 클라이언트가 VLR의 옥트리 계층 정보를 읽어 화면에 보이는 영역·거리에 맞는 노드만 선택적으로 내려받는다.

결국 "전처리가 아예 없어지는" 건 아니다. 다만 Potree가 뷰어 전용 포맷으로 완전히 갈아엎었다면, COPC는 업계 표준 LAZ 포맷의 내부 배치만 바꿔 서버 운영 부담을 치워낸다.

## 선택의 트레이드오프

| 접근 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| Potree(전용 옥트리 포맷) | 성숙한 생태계, 세밀한 포인트 예산·LOD 튜닝 | 전용 포맷 변환·관리 필요, 다른 도구와 비호환 | 측량·BIM 전용 뷰어를 직접 통제하는 프로젝트 |
| COPC(LAZ 내부 재배치) | 표준 LAZ 호환, 서버 없이 정적 스토리지로 서빙, PDAL 생태계 전체와 호환 | 여전히 1회 변환 필요, 뷰어 생태계가 Potree보다 아직 얇음 | 지도 플랫폼(Cesium·GeoLibre·MapLibre) 안에 포인트클라우드를 끼워 넣는 경우 |
| 원본 LAS/LAZ 그대로 서빙 | 변환 작업 전혀 없음 | 전체 파일을 받아야 디코딩 가능, 대용량에서 사실상 불가 | 수백만 점 이하의 소규모 스캔 데이터 |
| 3D Tiles로 변환(Cesium ion 등) | Cesium 생태계 전반과 완전 통합, 메쉬·타일 혼합 가능 | 변환 비용이 COPC보다 큼, 포인트클라우드 외 다른 포맷과 파이프라인 분리 필요 | 3D 건물·지형과 포인트클라우드를 한 뷰어에서 함께 렌더링해야 하는 경우 |

판단 기준은 "이 포인트클라우드를 어떤 뷰어 생태계 안에서 소비할 것인가"다. 이미 Potree 기반 워크플로가 자리 잡았고 세밀한 포인트 예산 제어가 중요하다면 바꿀 이유가 적다. 반면 2D 벡터타일 지도 위에 포인트클라우드를 얹거나, 서버 운영 부담을 PMTiles 수준으로 낮추고 싶다면 COPC가 자연스러운 선택이다.

## 실제 프로젝트 진행 순서

1. **원본 포맷부터 확인한다.** COPC는 LAS 1.4 PDRF 6·7·8만 지원한다. 오래된 스캐너 장비가 더 낮은 버전으로 출력한다면 먼저 PDAL로 LAS 1.4 승급부터 거쳐야 한다.
2. **`untwine` 또는 PDAL `writers.copc`로 변환한다.** 한 번의 배치 작업으로 끝나며, 결과물은 일반 LAZ 리더로도 열리는지 먼저 확인한다(호환성 검증).
3. **정적 스토리지에 올리고 Range Request 지원을 확인한다.** S3·R2·Cloudflare 같은 스토리지는 기본 지원하지만, 자체 서버라면 `Accept-Ranges: bytes` 헤더가 켜져 있는지 점검한다.
4. **뷰어를 고른다.** 브라우저 단독 확인은 `viewer.copc.io`에 파일을 드래그 앤 드롭해 검증하고, 실제 서비스에는 Cesium 기반 뷰어나 GeoLibre, 또는 copc.js로 직접 렌더링 레이어를 짠다.
5. **지도 위 다른 레이어(벡터타일·3D 건물)와의 좌표계·LOD 동기화를 맞춘다.** 포인트클라우드만 따로 로딩 전략을 가져가면 카메라 이동 시 다른 레이어와 끊기는 느낌이 생긴다.
6. **대용량 전면 배포 전 일부 타일로 먼저 측정한다.** 노드 크기·포인트 밀도에 따라 초기 로딩 체감이 크게 갈리므로, 작은 영역에서 Range Request 패턴과 캐시 적중률을 먼저 확인한다.

```bash
# LAS/LAZ 원본을 COPC로 변환 (PDAL)
pdal translate input.laz output.copc.laz \
  --writers.copc.forward=all

# 변환 결과가 COPC 스펙을 지키는지 확인
pdal info output.copc.laz --metadata | grep -i copc
```

## 실무 포인트

- COPC 파일의 info VLR은 파일 시작 375바이트 지점에서 시작하는 고정 160바이트 구조다. 커스텀 파서를 직접 짠다면 이 오프셋을 벗어나면 안 된다.
- `untwine`은 대용량 포인트클라우드를 병렬로 COPC 변환하도록 설계됐다. 단일 스레드 PDAL 파이프라인보다 수십 GB급 데이터에서 눈에 띄게 빠르다.
- CDN 캐시 설정 시 Range Request를 그대로 전달하는지 꼭 확인한다. 일부 CDN·프록시 설정은 전체 파일을 캐싱하려다 Range 헤더를 무시해 스트리밍 이점을 무력화한다.

## 마무리

- COPC는 포인트클라우드를 전용 포맷으로 갈아엎지 않고, 표준 LAZ 파일 내부를 옥트리 순서로 재배치해 HTTP Range Request 스트리밍을 가능하게 한다.
- Potree는 세밀한 LOD 제어가 강점이고, COPC는 서버 없는 정적 스토리지 서빙과 PDAL 생태계 호환성이 강점이다 — 뷰어 생태계 선택이 판단 기준이다.
- 변환은 `untwine`/PDAL로 한 번만 거치면 되고, 이후 운영 부담은 PMTiles 수준으로 가벼워진다.

## 참고 자료

- [COPC — Cloud Optimized Point Cloud 공식 스펙](https://copc.io/)
- [PDAL writers.copc 문서](https://pdal.io/stages/writers.copc.html)
- [COPC Viewer](https://viewer.copc.io/)
