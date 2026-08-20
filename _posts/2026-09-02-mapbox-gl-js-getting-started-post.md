---
layout: single
title: "Mapbox GL JS 처음 시작하기 — 설치와 첫 지도 띄우기"
date: 2026-09-02 12:20:00 +0530
categories: gis
tags: ["mapbox", "웹지도", "gis입문", "튜토리얼", "지도api"]
toc: true
toc_sticky: true
excerpt: "상용 웹 지도 라이브러리 Mapbox GL JS의 액세스 토큰 발급부터 첫 지도 렌더링까지, 처음 시작하는 사람을 위한 실습 가이드."
---

## Mapbox는 MapLibre와 뭐가 다른가

MapLibre GL JS를 이미 써봤다면 Mapbox GL JS의 API가 거의 똑같다는 것을 바로 알 수 있다. 실제로 MapLibre는 Mapbox GL JS v1의 오픈소스 포크에서 시작됐기 때문이다. 차이는 라이선스와 서비스 구조에 있다. Mapbox는 지도 타일, 지오코딩, 내비게이션 같은 상용 서비스를 함께 제공하는 대신 **액세스 토큰**이 필요하고 사용량에 따라 과금된다.

<img src="/assets/images/posts/2026-09-02-mapbox-gl-js-getting-started-1.svg" alt="Mapbox 계정에서 액세스 토큰을 발급받아 클라이언트 코드에 설정하고, Mapbox의 타일 서버와 통신해 지도를 렌더링하는 흐름을 보여주는 다이어그램" style="width:100%;">

## 시작하기 전 준비물

| 준비물 | 설명 |
|---|---|
| Mapbox 계정 | [mapbox.com](https://www.mapbox.com)에서 무료 가입 |
| 액세스 토큰 | 계정 대시보드에서 발급, 클라이언트 코드에 설정 |
| 무료 사용량 | 월 일정 요청 수까지 무료(정확한 한도는 공식 가격 페이지 확인) |

## 코드 예제: 첫 지도 띄우기

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://api.mapbox.com/mapbox-gl-js/v3.0.0/mapbox-gl.js"></script>
  <link href="https://api.mapbox.com/mapbox-gl-js/v3.0.0/mapbox-gl.css" rel="stylesheet">
  <style>#map { width: 100%; height: 500px; }</style>
</head>
<body>
  <div id="map"></div>
  <script>
    mapboxgl.accessToken = 'YOUR_ACCESS_TOKEN'; // Mapbox 대시보드에서 발급

    const map = new mapboxgl.Map({
      container: 'map',
      style: 'mapbox://styles/mapbox/streets-v12', // Mapbox 전용 스타일 URL
      center: [126.978, 37.5665], // [경도, 위도]
      zoom: 12,
    });

    map.addControl(new mapboxgl.NavigationControl());
  </script>
</body>
</html>
```

`style` 값이 `mapbox://styles/...` 형태인 점이 MapLibre와 가장 눈에 띄는 차이다. 이 URL 스킴은 Mapbox 서비스 전용이라 MapLibre에서는 사용할 수 없다.

## 실무 포인트

- **액세스 토큰을 프론트엔드 코드에 그대로 노출해도 되는가 걱정될 수 있는데, Mapbox는 토큰을 URL 제한(도메인 화이트리스트)으로 보호하는 것을 권장한다.** 토큰 자체보다 어느 도메인에서 호출되는지를 제한하는 방식이다.
- **무료 티어를 초과하면 과금이 시작되므로, 트래픽이 많은 서비스라면 사용량을 모니터링하는 대시보드를 반드시 확인해야 한다.**
- **라이선스 비용 없이 오픈소스로 시작하고 싶다면 MapLibre GL JS + 자체 타일 서버 조합을 검토하는 것도 방법이다.** Mapbox의 완성도 높은 지오코딩·내비게이션 API가 꼭 필요하지 않다면 오픈소스 대안으로 충분한 경우가 많다.

## 마무리 요약

- Mapbox GL JS는 MapLibre와 API가 거의 같지만 액세스 토큰이 필요하고 사용량 기반으로 과금된다.
- `style` URL이 `mapbox://styles/...` 형태라는 점이 MapLibre와의 핵심 차이다.
- 액세스 토큰은 도메인 제한으로 보호하고, 무료 티어 초과 여부를 주기적으로 모니터링해야 한다.

## 참고 자료

- [Mapbox GL JS 공식 문서](https://docs.mapbox.com/mapbox-gl-js/guides/)
- [Mapbox 가격 정책](https://www.mapbox.com/pricing)
