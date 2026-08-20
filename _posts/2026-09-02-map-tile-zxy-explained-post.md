---
layout: single
title: "지도 타일 z/x/y가 뭔가요 — 타일 좌표 체계 이해하기"
date: 2026-09-02 13:20:00 +0530
categories: gis
tags: ["지도타일", "타일좌표", "gis입문", "웹지도", "슬리피맵"]
toc: true
toc_sticky: true
excerpt: "웹 지도 타일 URL에 항상 등장하는 z/x/y가 각각 무엇을 의미하는지, 타일 피라미드 개념부터 처음 배우는 사람 기준으로 정리했다."
---

## 타일 URL에 있는 그 숫자 세 개

웹 지도를 다뤄보면 `https://tile.example.com/{z}/{x}/{y}.png` 같은 URL 패턴을 항상 만난다. 이 세 숫자가 무엇인지 모르면 왜 지도가 안 보이는지, 왜 엉뚱한 지역이 나오는지 디버깅할 수 없다.

<img src="/assets/images/posts/2026-09-02-map-tile-zxy-explained-1.svg" alt="줌 레벨이 올라갈수록 타일이 4배씩 늘어나는 타일 피라미드 구조와, z/x/y 좌표가 각각 줌 레벨과 가로·세로 인덱스를 의미하는 것을 보여주는 다이어그램" style="width:100%;">

## z, x, y의 의미

| 값 | 의미 | 범위 |
|---|---|---|
| z (zoom) | 줌 레벨. 클수록 더 확대된 상세 지도 | 보통 0~22 |
| x | 해당 줌 레벨에서 가로 방향 타일 인덱스 | 0 ~ (2^z - 1) |
| y | 해당 줌 레벨에서 세로 방향 타일 인덱스 | 0 ~ (2^z - 1) |

핵심은 줌 레벨이 1 올라갈 때마다 **타일 개수가 가로·세로 각각 2배(총 4배)로 늘어난다**는 것이다.

```text
z=0: 1개 타일 (지구 전체가 256x256 픽셀 한 장)
z=1: 4개 타일 (2x2)
z=2: 16개 타일 (4x4)
z=10: 약 100만 개 타일
z=18: 약 687억 개 타일
```

이것이 타일 피라미드(tile pyramid)라고 불리는 구조다. 줌 레벨이 높아질수록 필요한 타일 수가 기하급수적으로 늘어나므로, 실무에서는 서비스에 필요한 줌 범위만 미리 만들어두는 것이 일반적이다.

## 코드 예제: 위경도를 타일 좌표로 변환

```javascript
function lonLatToTile(lon, lat, zoom) {
  const n = Math.pow(2, zoom);
  const x = Math.floor((lon + 180) / 360 * n);
  const latRad = lat * Math.PI / 180;
  const y = Math.floor(
    (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n
  );
  return { z: zoom, x, y };
}

console.log(lonLatToTile(126.978, 37.5665, 12)); // 서울 시청, 줌 12
```

이 변환식은 웹 메르카토르(EPSG:3857) 투영법을 전제로 한다. 대부분의 웹 지도 서비스가 이 투영법을 쓰기 때문에 사실상 표준 계산식이다.

## 실무 포인트

- **y축 방향이 서비스마다 다를 수 있다.** 일반적인 슬리피맵(Google, OSM 등)은 y가 위에서 아래로 증가하지만, TMS 규격은 아래에서 위로 증가한다. 지도가 상하로 뒤집혀 보이면 이 차이를 먼저 의심해야 한다.
- **줌 레벨을 무한정 지원할 필요는 없다.** 전국 단위 서비스라면 보통 z=6~18 정도로 충분하며, 그 이상은 타일 생성·저장 비용만 늘어난다.
- **타일 좌표를 알면 캐시 전략을 세우기 쉬워진다.** 같은 z/x/y는 항상 같은 이미지이므로 CDN에서 장기 캐싱하기 좋은 구조다. 데이터가 갱신될 때는 URL에 버전을 붙여 캐시를 무효화하는 방식이 흔하다.

## 마무리 요약

- z는 줌 레벨, x와 y는 그 줌 레벨에서의 가로·세로 타일 인덱스를 의미한다.
- 줌 레벨이 1 올라갈 때마다 타일 개수는 4배로 늘어나는 피라미드 구조다.
- 지도가 상하로 뒤집혀 보이면 슬리피맵과 TMS의 y축 방향 차이를 먼저 확인해야 한다.

## 참고 자료

- [OSM Wiki - Slippy map tilenames](https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames)
- [Mapbox - 지도 타일 개요](https://docs.mapbox.com/help/getting-started/web-apps/)
