---
layout: single
title: "수억 개의 점을 브라우저에 뿌리다 — LiDAR 포인트클라우드와 Potree 옥트리 구조"
date: 2026-08-18 12:20:00 +0530
categories: gis
tags: ["lidar", "potree", "pointcloud", "octree", "gis"]
toc: true
toc_sticky: true
excerpt: "드론·차량 LiDAR 스캔이 만들어내는 수억 개의 점을 브라우저에서 끊김 없이 보여주기 위해, Potree가 옥트리(Octree) 기반 LOD와 포인트 예산으로 데이터를 계층적으로 스트리밍하는 원리를 정리한다."
---

## 왜 지금 LiDAR 포인트클라우드 웹 시각화인가

드론·모바일 매핑 차량·정적 스캐너에서 나오는 LiDAR 데이터는 스캔 한 번에 수천만에서 수억 개의 점(포인트)을 만들어낸다. 정밀 측량, 건설 현장 진척 관리, 문화재 디지털 아카이빙, 도로 인프라 점검처럼 "실측된 3차원 표면"이 필요한 분야에서 이 데이터를 웹 브라우저로 공유하고 검토하려는 수요가 꾸준히 늘고 있다. 문제는 규모다. 이전 글에서 다룬 Cesium 3D Tiles가 건물·지형 **메시**를 계층화하고 deck.gl이 좌표를 가진 **속성 데이터**(센서 로그, AIS 등)를 GPU로 그렸다면, LiDAR 포인트클라우드는 애초에 메시도 속성 집계도 아닌 **원본 스캔 점 그 자체**를 다뤄야 한다는 점이 다르다.

포인트 하나하나가 X/Y/Z 좌표와 색상·강도(intensity) 값을 갖는 LAS/LAZ 포맷 파일은 실무에서 수 GB~수백 GB에 이른다. 이걸 그대로 브라우저 메모리에 올리면 탭이 죽는다. 그래서 대부분의 웹 LiDAR 뷰어는 **옥트리(Octree) 기반 LOD(Level of Detail)** 로 데이터를 미리 재구성해두고, 카메라가 보는 영역과 거리에 맞춰 필요한 만큼만 스트리밍한다. 오픈소스 뷰어 **Potree**가 이 방식의 대표적인 구현체다.

## 핵심 개념 1: 옥트리(Octree)로 점을 계층화하기

옥트리는 3차원 공간을 8개의 하위 공간(옥탄트)으로 재귀적으로 분할하는 트리 구조다(쿼드트리의 3D 버전). Potree의 변환 도구(PotreeConverter)는 원본 LAS/LAZ 포인트클라우드를 읽어, 전체 경계상자를 루트 노드로 두고 점들을 옥트리 계층에 분배한다. 각 노드는 원본 점 전체가 아니라 **해당 영역을 대표하는 서브샘플**만 저장하고, 자식 노드로 내려갈수록 점 밀도가 높아져 마지막 리프 노드에서 원본 해상도에 도달한다.

<img src="/assets/images/posts/2026-08-18-lidar-pointcloud-potree-1.svg" alt="포인트클라우드 옥트리 LOD 구조 - 루트 노드의 저밀도 서브샘플에서 카메라와 가까운 옥탄트만 재귀적으로 세분화되어 원본 해상도에 도달하는 흐름" style="width:100%;">

이 구조 덕분에 뷰어는 처음에는 전체 장면의 루트 노드(가벼운 서브샘플)만 내려받아 즉시 개형을 보여주고, 사용자가 특정 영역으로 줌인하면 해당 옥탄트의 자식 노드를 추가로 요청해 점을 채워 넣는다. Cesium 3D Tiles의 타일 트리와 개념은 비슷하지만, 3D Tiles는 주로 메시·인스턴스 지오메트리를 계층화하는 반면 옥트리 포인트클라우드는 "점 자체의 서브샘플링"을 기준으로 계층을 나눈다는 차이가 있다.

## 핵심 개념 2: 포인트 예산(Point Budget)과 렌더링 제어

Potree 뷰어는 화면에 동시에 그릴 점 개수의 상한선인 **포인트 예산**을 설정할 수 있다. 카메라가 이동하면 뷰어는 현재 뷰 프러스텀 안에 들어오는 옥트리 노드들을 순회하면서, 예산 안에서 카메라와 가까운(또는 화면 오차가 큰) 노드부터 우선적으로 세분화하고 먼 노드는 상위 레벨의 성긴 서브샘플로 남겨둔다.

| 구분 | 원본 LAS/LAZ 통째 로드 | 옥트리 LOD 스트리밍(Potree) |
|---|---|---|
| 초기 로딩 | 파일 전체를 파싱·전송해야 함 | 루트 노드만으로 즉시 개형 표시 |
| 메모리 사용 | 전체 점 수에 비례, 대용량에서 브라우저 한계 도달 | 포인트 예산으로 상한 제어 |
| 줌인 시 동작 | 추가 처리 없음(이미 전부 로드됨) | 해당 옥탄트 자식 노드를 추가 요청 |
| 적합한 규모 | 수백만 점 이하의 소규모 스캔 | 수억 점 단위의 대규모 스캔 |

## 예제 1: PotreeConverter로 LAS 파일을 옥트리로 변환하기

```bash
# PotreeConverter CLI — 원본 LAS/LAZ를 옥트리 구조(계층 폴더 + 메타데이터)로 변환
PotreeConverter input_scan.laz -o ./potree_output --generate-page viewer

# 결과: ./potree_output/pointclouds/ 아래에 octree.bin, hierarchy.bin,
# metadata.json 등이 생성되며, 뷰어가 이 메타데이터를 읽어 옥트리를 순회한다
```

## 예제 2: Potree.js 뷰어에 변환 결과 로드하기

```javascript
// Potree 뷰어 초기화 및 변환된 옥트리 포인트클라우드 로드
const viewer = new Potree.Viewer(document.getElementById("potree_render_area"));
viewer.setEDLEnabled(true);        // Eye-Dome Lighting: 굴곡을 강조해 입체감 보완
viewer.setPointBudget(2_000_000);  // 동시 렌더링 점 개수 상한(포인트 예산)

Potree.loadPointCloud("./potree_output/metadata.json", "scan", (e) => {
  const pointcloud = e.pointcloud;
  pointcloud.material.size = 1;
  pointcloud.material.pointSizeType = Potree.PointSizeType.ADAPTIVE;
  viewer.scene.addPointCloud(pointcloud);
  viewer.fitToScreen();
});
```

`setPointBudget` 값이 낮을수록 저사양 기기에서도 프레임이 안정되지만 세부 디테일이 늦게 채워지고, 값이 높을수록 디테일은 빠르지만 GPU·메모리 부담이 커진다. 실제 적정값은 대상 기기와 점밀도에 따라 달라지므로 배포 전 프로파일링이 필요하다.

## 실무 포인트

- **변환은 반드시 사전 단계로 분리한다**: PotreeConverter는 시간이 걸리는 배치 작업이므로 업로드 파이프라인에서 비동기로 처리하고, 완료 후 옥트리 메타데이터만 뷰어에 서빙하는 구조가 안전하다.
- **색상·강도 값의 존재 여부를 확인한다**: LAS 파일에 RGB가 없는 스캔은 강도(intensity)나 고도값 기반 컬러 램프로 대체 표시해야 사용자가 구조를 식별할 수 있다.
- **좌표계 변환을 변환 전에 통일한다**: 스캐너 원점 좌표계와 웹 지도 좌표계(WGS84 등)가 다르면 변환 이후 재정합이 번거로우므로, PotreeConverter 실행 전에 좌표계를 맞추는 편이 낫다.
- **포인트 예산과 EDL 같은 시각 보정 기능을 함께 튜닝한다**: 점 자체는 면이 아니므로 Eye-Dome Lighting 없이는 형태 구분이 어려운 경우가 많다.

## 3줄 요약

- LiDAR 스캔은 수억 개의 원본 점을 포함해 통째로 로드하면 브라우저가 감당하지 못하므로, 옥트리 기반 LOD로 미리 계층화해두는 전처리가 필요하다.
- Potree는 PotreeConverter로 LAS/LAZ를 옥트리 구조로 변환하고, 뷰어는 카메라 위치와 포인트 예산에 맞춰 필요한 노드만 스트리밍해서 그린다.
- 실무에서는 변환을 비동기 사전 단계로 분리하고, 좌표계 정합과 포인트 예산·EDL 튜닝을 함께 검토해야 안정적으로 서비스할 수 있다.

## 참고 자료

- [Potree 공식 GitHub](https://github.com/potree/potree)
- [PotreeConverter GitHub](https://github.com/potree/PotreeConverter)
- [ASPRS LAS Specification](https://www.asprs.org/divisions-committees/lidar-division/laser-las-file-format-exchange-activities)
