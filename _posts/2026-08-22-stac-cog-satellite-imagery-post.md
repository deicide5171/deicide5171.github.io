---
layout: single
title: "STAC과 COG로 위성영상 다루기 — 클라우드 네이티브 지구관측 데이터"
date: 2026-08-22 12:20:00 +0530
categories: gis
tags: ["gis", "stac", "cog", "satellite-imagery", "cloud-native", "remote-sensing"]
toc: true
toc_sticky: true
excerpt: "수십 GB짜리 위성영상 파일 전체를 내려받지 않고도 필요한 영역만 스트리밍해 쓸 수 있게 하는 COG 포맷과, 방대한 영상 카탈로그를 검색 가능하게 만드는 STAC 표준을 정리한다."
---

위성영상 한 장(scene)은 밴드 구성과 해상도에 따라 다르지만 수백 MB에서 수십 GB에 이르는 경우가 드물지 않다. 전통적인 GeoTIFF 워크플로우에서는 분석하려는 관심 영역이 전체 영상의 극히 일부라 해도, 파일 전체를 로컬로 내려받은 뒤에야 원하는 부분을 잘라 쓸 수 있었다. 클라우드 스토리지에 원본이 올라가 있는 지금도 이 문제는 형태만 바뀌었을 뿐 그대로 남아 있다. 다운로드 대역폭과 로컬 디스크 용량이 분석 파이프라인의 병목이 되는 일이 흔하다.

여기에 더해 두 번째 문제가 있다. 원하는 시기와 영역, 구름 비율 조건을 만족하는 영상을 대규모 아카이브에서 찾아내는 일 자체가 쉽지 않다는 점이다. 위성 데이터 제공자마다 메타데이터 형식과 검색 인터페이스가 제각각이라, 여러 소스를 넘나들며 분석을 하려면 그때마다 새로운 API 문서를 익히고 별도의 파서를 작성해야 했다.

이 글에서는 이 두 문제를 각각 해결하는 두 표준을 정리한다. 파일 내부 구조를 바꿔 부분 읽기를 가능하게 하는 **COG(Cloud Optimized GeoTIFF)**와, 카탈로그 메타데이터를 표준화해 검색을 가능하게 하는 **STAC(SpatioTemporal Asset Catalog)**이다. 두 표준은 서로 다른 계층(파일 포맷 vs. 메타데이터 카탈로그)을 다루지만, 실무에서는 거의 항상 짝을 이뤄 쓰인다.

## 핵심 개념 1: COG의 내부 구조 — 타일링과 오버뷰

일반 GeoTIFF는 픽셀 데이터를 스트립(strip) 단위로 순차 저장하는 경우가 많아, 이미지의 특정 영역만 읽으려 해도 관련 없는 데이터를 함께 읽어야 하는 경우가 생긴다. COG는 같은 GeoTIFF 컨테이너를 쓰면서도 내부 배치를 재구성한다. 픽셀을 정사각형 타일 단위로 나눠 저장하고, 각 타일의 파일 내 오프셋과 길이를 헤더에 기록해두어, 특정 지리 좌표 영역에 해당하는 타일만 골라 읽을 수 있게 한다.

여기에 더해 COG는 원본 해상도 이미지 위에 여러 단계로 축소한 **오버뷰(overview)** 이미지를 함께 저장한다. 전체 영역을 낮은 줌 레벨(작은 축척)에서 훑어봐야 할 때는 원본 해상도 타일 대신 미리 계산된 저해상도 오버뷰를 읽으면 되므로, 지도 타일 서비스처럼 줌 레벨을 오가는 워크로드에서 불필요한 대용량 원본 읽기를 피할 수 있다. 이 타일-오버뷰 구조가 있어야, 클라이언트가 파일 헤더만 먼저 읽어 원하는 타일의 위치를 파악한 뒤 HTTP `Range` 요청으로 그 부분만 내려받는 것이 가능해진다. 즉 COG 자체는 압축이나 좌표계를 새로 정의하는 포맷이 아니라, 기존 GeoTIFF를 "부분 읽기 친화적으로" 재배열한 규약에 가깝다.

## 핵심 개념 2: STAC의 카탈로그-컬렉션-아이템 구조

STAC은 위성/항공 영상 등 시공간 데이터를 검색 가능하게 만들기 위한 메타데이터 명세다. 계층은 세 단계로 나뉜다. 최상위의 **Catalog**는 하위 Collection이나 Item, 또는 다른 Catalog를 가리키는 링크 모음으로, 카탈로그 전체의 진입점 역할만 한다. 그 아래 **Collection**은 공통 속성(제공 기관, 라이선스, 밴드 구성, 커버리지 범위 등)을 공유하는 데이터셋 단위를 묶는다. 예를 들어 "Sentinel-2 Level-2A"가 하나의 Collection이 된다.

가장 하위의 **Item**은 실제 촬영 1건에 대응하는 STAC의 핵심 단위로, GeoJSON Feature를 확장한 형태다. 촬영 지오메트리(geometry)와 bbox, 촬영 시각(datetime), 구름 비율 같은 부가 속성을 `properties`에 담고, 실제 데이터 파일(주로 COG)이나 썸네일, 메타데이터 문서로의 링크를 `assets`에 담는다. 이 구조 덕분에 STAC API 서버는 지리적 범위와 시간 범위, 속성 조건을 조합한 질의를 표준화된 방식으로 처리할 수 있고, 클라이언트는 검색 결과로 받은 Item의 asset 링크를 그대로 COG 부분 읽기에 넘길 수 있다.

## 핵심 개념 3: 두 표준이 함께 쓰이는 이유

COG와 STAC은 서로 다른 문제를 풀지만 조합했을 때 시너지가 난다. STAC은 "어떤 영상이 존재하고, 어디에 있으며, 언제 촬영됐는지"를 알려주는 역할을, COG는 "그 영상에서 실제로 필요한 부분만 어떻게 효율적으로 읽어올지"를 담당한다. STAC Item의 `assets` 필드가 COG 파일의 URL을 직접 가리키는 구조가 관행으로 자리 잡으면서, 검색부터 데이터 접근까지 이어지는 파이프라인 전체를 다운로드 없이 클라우드 상에서 완결할 수 있게 됐다. 이런 흐름을 흔히 "클라우드 네이티브 지구관측(cloud-native geospatial)"이라 부른다.

두 표준 모두 특정 벤더에 종속되지 않는 개방형 명세라는 점도 확산에 크게 기여했다. AWS의 Sentinel-2, Landsat 오픈 데이터 버킷을 비롯해 Microsoft Planetary Computer, Element 84의 Earth Search 등 다수의 공개 STAC API가 COG 자산을 제공하고 있어, 동일한 클라이언트 코드로 여러 제공자의 데이터를 오갈 수 있다.

<img src="/assets/images/posts/2026-08-22-stac-cog-satellite-imagery-1.svg" alt="COG의 타일-오버뷰 피라미드 구조와 HTTP Range Request로 특정 타일만 읽는 흐름, STAC의 Catalog-Collection-Item-Asset 계층 구조를 나란히 보여주는 개념도" style="width:100%;">

## 예제

아래는 STAC API에 영역과 시간 범위, 구름 비율 조건을 걸어 검색하는 요청 예시다.

```bash
curl -X POST "https://earth-search.aws.element84.com/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "collections": ["sentinel-2-l2a"],
    "bbox": [126.8, 37.4, 127.2, 37.7],
    "datetime": "2026-06-01T00:00:00Z/2026-06-30T23:59:59Z",
    "query": { "eo:cloud_cover": { "lt": 20 } },
    "limit": 10
  }'
```

검색 결과로 받은 STAC Item의 asset URL(COG)에서 관심 영역만 부분적으로 읽을 때는 rasterio(GDAL 기반)를 흔히 쓴다.

```python
import rasterio
from rasterio.windows import from_bounds

cog_url = "https://.../S2A_..._B04.tif"  # STAC Item의 assets에서 얻은 COG URL

with rasterio.open(cog_url) as src:
    # 관심 영역의 좌표(minx, miny, maxx, maxy)에 해당하는 창(window)만 계산
    window = from_bounds(126.9, 37.5, 127.0, 37.6, transform=src.transform)
    # 이 창에 해당하는 타일만 HTTP Range Request로 읽어온다
    data = src.read(1, window=window)
```

파일을 열 때부터 `rasterio.open`이 GDAL의 `/vsicurl/` 계열 드라이버를 통해 원격 파일을 열고, `window` 인자로 필요한 영역만 지정하면 GDAL이 내부적으로 필요한 타일에 해당하는 바이트 범위만 HTTP Range 요청으로 가져온다. 전체 파일을 로컬에 내려받는 과정은 일어나지 않는다.

## 실무 포인트

- **오버뷰 레벨 생성 시 고려사항**: COG를 생성할 때(`gdal_translate`, `rio cogeo` 등) 오버뷰를 몇 단계까지 만들지, 리샘플링 방법(최근접, 평균, bilinear 등)을 무엇으로 할지 정해야 한다. 오버뷰 단계가 부족하면 축소 보기 시에도 원본 해상도 타일을 읽어야 해 이점이 줄고, 반대로 과도하게 많이 만들면 파일 크기와 생성 시간이 늘어난다. 데이터 성격(연속값 래스터인지, 범주형 분류 결과인지)에 따라 적절한 리샘플링 방법이 달라지므로, 값의 의미가 왜곡되지 않는 방식을 선택해야 한다.
- **STAC 카탈로그 호스팅 옵션**: 자체 STAC API 서버를 구축하려면 pgSTAC(PostgreSQL 기반)이나 stac-fastapi 같은 오픈소스 구현체를 활용할 수 있고, 별도 서버 없이 정적 JSON 파일만으로 카탈로그를 구성하는 정적 STAC(static STAC) 방식도 소규모 데이터셋에는 충분할 수 있다. 검색 질의량과 카탈로그 규모, 갱신 빈도를 함께 고려해 선택하는 편이 합리적이다.
- **인증과 접근 제어**: 공개 데이터가 아닌 자체 위성영상을 STAC/COG로 서비스한다면, asset URL에 대한 서명된 URL 발급이나 별도 인증 계층을 함께 설계해야 한다. STAC 명세 자체는 인증 방식을 규정하지 않으므로 이 부분은 구현 시 별도로 챙겨야 하는 영역이다.

## 3줄 요약

- COG는 GeoTIFF를 타일 단위로 재배열하고 오버뷰를 함께 저장해, HTTP Range Request로 필요한 영역만 부분적으로 읽을 수 있게 한다.
- STAC은 Catalog-Collection-Item 계층으로 위성영상 메타데이터를 표준화해, 지리적·시간적 조건으로 원하는 영상을 검색 가능하게 만든다.
- 두 표준은 STAC Item의 asset이 COG 파일을 직접 가리키는 방식으로 결합돼, 검색부터 데이터 접근까지 다운로드 없이 클라우드 상에서 처리하는 워크플로우를 가능하게 한다.

## 참고 자료

- [STAC 공식 명세 (stacspec.org)](https://stacspec.org/)
- [Cloud Optimized GeoTIFF 공식 사이트 (cogeo.org)](https://cogeo.org/)
- [STAC API 명세 (Element 84 Earth Search 예시)](https://stacspec.org/en/about/stac-spec/)
- [rasterio 문서 — Windowed Reading](https://rasterio.readthedocs.io/en/stable/topics/windowed-rw.html)
