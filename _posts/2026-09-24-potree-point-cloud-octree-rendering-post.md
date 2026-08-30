---
layout: single
title: "Potree로 대용량 포인트클라우드(LAS/LAZ) 웹에서 렌더링하기"
date: 2026-09-24 12:20:00 +0530
categories: gis
tags: ["Potree", "포인트클라우드", "LAS", "옥트리", "3D웹지도"]
toc: true
toc_sticky: true
excerpt: "드론·라이다로 촬영한 수억 개 점으로 이뤄진 LAS/LAZ 포인트클라우드를 브라우저에서 통째로 로드하지 않고도 매끄럽게 탐색할 수 있게 해주는 Potree의 옥트리 기반 LOD 스트리밍 구조를 정리했다."
---

## 왜 지금 Potree를 알아야 하는가

라이다(LiDAR) 스캔이나 드론 사진측량으로 얻는 포인트클라우드 데이터는 한 현장을 촬영해도 수천만~수억 개의 점으로 구성되는 경우가 흔하다. 이런 데이터를 일반적인 3D 웹 라이브러리로 그대로 로드하려 하면 브라우저 메모리가 감당하지 못하거나, 로드하는 데만 수 분이 걸려 실용성이 없어진다. Potree는 이런 초대용량 포인트클라우드를 웹에서도 매끄럽게 탐색할 수 있도록, 데이터를 미리 옥트리(octree) 구조로 전처리해두고 카메라 위치·거리에 따라 필요한 부분만 점진적으로 스트리밍하는 방식으로 이 문제를 해결한다.

## 핵심 개념 1 — 옥트리 전처리: 공간을 재귀적으로 8분할한다

Potree를 쓰려면 먼저 원본 LAS/LAZ 파일을 Potree Converter 같은 도구로 전처리해야 한다. 이 전처리 단계에서 전체 포인트클라우드가 차지하는 3차원 공간을 하나의 박스로 감싼 뒤, 그 박스를 8개의 동일한 크기의 하위 박스로 재귀적으로 나누는 옥트리 구조를 만든다. 각 옥트리 노드에는 그 노드가 담당하는 공간 범위 안의 포인트 중 일부(전체를 대표할 수 있도록 서브샘플링된 점들)가 저장되고, 더 하위 노드로 내려갈수록 더 세밀한 포인트가 추가된다. 이 구조 덕분에 "지금 화면에 필요한 상세도"만큼만 옥트리를 얕게 또는 깊게 순회해 필요한 노드만 불러오면 된다.

<img src="/assets/images/posts/2026-09-24-potree-point-cloud-octree-rendering-1.svg" alt="수억 개의 원본 LAS/LAZ 포인트가 옥트리로 재귀적으로 8분할 전처리된 뒤, 카메라 거리에 따라 근접 노드는 조밀하게 원거리 노드는 성기게 스트리밍되며 화면 밖 노드는 아예 로드되지 않는 Potree의 LOD 렌더링 구조를 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 카메라 거리 기반 LOD 스트리밍

브라우저에서 Potree 뷰어가 화면을 렌더링할 때마다, 카메라의 절두체(view frustum) 안에 들어오는 옥트리 노드만 후보로 삼고, 그 중에서도 카메라와의 거리에 따라 어느 깊이까지 하위 노드를 추가로 불러올지 결정한다. 카메라에 가까운 영역은 더 깊은(더 세밀한) 노드까지 불러와 조밀한 포인트를 그리고, 멀리 있는 영역은 상위 노드의 성긴 포인트만으로 충분한 시각적 인상을 준다. 이 방식은 지도 타일링에서 줌 레벨에 따라 다른 해상도의 타일을 불러오는 것과 개념적으로 동일하며, 사용자가 카메라를 움직이는 동안 필요한 노드만 계속 비동기로 요청·해제하면서 항상 일정한 프레임레이트를 유지하려 시도한다.

| 항목 | 설명 |
|---|---|
| 옥트리 노드 | 3차원 공간을 재귀적으로 8분할한 계층 구조의 단위 |
| 노드별 저장 포인트 | 서브샘플링된 대표 점 (하위로 갈수록 추가) |
| LOD 결정 기준 | 카메라와의 거리 + 화면상 투영 크기 |
| Frustum Culling | 카메라 시야 밖 노드는 아예 로드 대상에서 제외 |

## 예제 — Potree 뷰어 초기화와 포인트클라우드 로드

```javascript
window.viewer = new Potree.Viewer(document.getElementById('potree_render_area'));
viewer.setEDLEnabled(true);       // Eye-Dome-Lighting으로 형태 인지도 향상
viewer.setFOV(60);
viewer.setPointBudget(2_000_000); // 한 프레임에 그릴 최대 포인트 수 예산

Potree.loadPointCloud('pointclouds/site-scan/metadata.json', 'siteScan', (e) => {
  const pointcloud = e.pointcloud;
  const material = pointcloud.material;

  material.size = 1;
  material.pointSizeType = Potree.PointSizeType.ADAPTIVE; // 거리에 따라 점 크기 자동 조절
  material.shape = Potree.PointShape.CIRCLE;

  viewer.scene.addPointCloud(pointcloud);
  viewer.fitToScreen();
});
```

`setPointBudget`으로 지정한 예산 안에서 Potree가 자동으로 어느 옥트리 노드까지 로드할지 조절하므로, 기기 성능에 따라 이 값을 낮추면 저사양 기기에서도 프레임 드롭 없이 탐색할 수 있다.

## 실무 포인트

- **전처리(옥트리 변환)는 반드시 배포 전에 완료해두라.** Potree Converter는 CPU와 디스크 I/O를 많이 쓰는 배치성 작업이므로, 클라이언트 요청 시점이 아니라 데이터 업로드·배치 파이프라인 단계에서 미리 수행해둬야 한다.
- **`pointBudget`을 기기군별로 다르게 설정하는 것을 고려하라.** 데스크톱과 모바일이 같은 예산을 쓰면 모바일에서는 버벅이고 데스크톱에서는 과도하게 낮은 상세도로 보이는 불균형이 생긴다.
- **좌표계 변환을 전처리 단계에서 미리 처리하라.** 라이다 원본 데이터가 지역 좌표계(예: 측량 기준점 기준 로컬 좌표)로 되어 있는 경우가 많으므로, 웹 지도의 위경도나 다른 3D 콘텐츠와 정렬하려면 변환 행렬을 전처리 시점에 함께 구워두는 것이 실행 시점 계산보다 안전하다.

## 마무리 요약

- Potree는 초대용량 포인트클라우드를 옥트리로 미리 전처리해, 브라우저가 전체 데이터를 한 번에 로드하지 않고도 탐색 가능하게 만든다.
- LOD 스트리밍은 카메라와의 거리와 화면 투영 크기를 기준으로 어느 깊이의 옥트리 노드까지 불러올지 결정해, 가까운 영역은 조밀하게 먼 영역은 성기게 그린다.
- `pointBudget` 같은 런타임 파라미터로 기기 성능에 맞춰 로드량을 조절할 수 있으며, 좌표계 정렬은 전처리 단계에서 미리 해결해두는 것이 안전하다.

## 참고 자료

- [Potree - GitHub](https://github.com/potree/potree)
- [Potree Converter - GitHub](https://github.com/potree/PotreeConverter)
