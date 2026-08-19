---
layout: single
title: "지도에 저녁노을과 그림자가 생겼다 — Mapbox GL JS v3 Standard 스타일 실전"
date: 2026-08-26 13:20:00 +0530
categories: gis
tags: ["gis", "mapbox", "mapboxgl", "standard-style", "3d-lighting", "webmap"]
toc: true
toc_sticky: true
excerpt: "Mapbox GL JS v3의 Standard 스타일은 라이팅 프리셋과 config 기반 커스터마이징으로 3D 건물·그림자·시간대 표현을 코드 몇 줄로 가능하게 한다. 실전 설정 방법을 정리한다."
---

Mapbox GL JS의 스타일링은 오랫동안 "레이어를 하나씩 쌓고, 각 레이어의 paint 속성을 표현식으로 채우는" 방식이었다. 건물에 그림자를 넣거나 시간대에 따라 조명을 바꾸려면 `fill-extrusion` 레이어의 높이·색상 표현식을 손으로 조합하고, 하늘 레이어와 안개(fog) 레이어를 따로 추가해야 했다. v3부터 도입된 **Standard 스타일**은 이 작업의 상당 부분을 미리 만들어진 3D 라이팅 시스템과 `config` 옵션으로 대체한다. 개발자는 레이어를 직접 조립하는 대신, 몇 개의 config 값(라이트 프리셋, 3D 객체 표시 여부 등)만 바꿔서 사실적인 3D 지도를 얻을 수 있다.

이 변화는 스타일링 워크플로 자체를 바꾼다. 예전에는 "이 레이어의 이 속성을 이렇게 표현식으로 계산한다"는 저수준 제어가 기본이었다면, Standard 스타일에서는 "낮/밤/새벽 중 어떤 조명을 쓸지", "3D 건물을 보여줄지" 같은 고수준 옵션을 먼저 정하고, 세부 커스터마이징이 필요한 부분만 기존 방식으로 오버라이드하는 흐름이 된다. 이 글에서는 Standard 스타일의 라이팅 프리셋과 config 커스터마이징 방법을 정리한다.

## 핵심 개념 1: 라이트 프리셋 — 시간대별 조명을 통째로 바꾼다

Standard 스타일은 `dawn`, `day`, `dusk`, `night` 네 가지 라이트 프리셋을 기본 제공한다. 각 프리셋은 태양 위치, 그림자 방향과 길이, 건물 색상 톤, 하늘 색상까지 한 번에 바꾸는 사전 정의된 조명 세트다.

| 프리셋 | 특징 | 활용 예 |
|---|---|---|
| `dawn` | 낮은 태양각, 긴 그림자, 따뜻한 색조 | 아침 배송 현황 대시보드 |
| `day` | 밝은 조명, 짧은 그림자 | 기본값, 일반 내비게이션 |
| `dusk` | 저녁노을, 대비 강한 그림자 | 저녁 시간대 서비스 강조 |
| `night` | 어두운 톤, 건물 창문 발광 효과 | 야간 운행 앱, 무드 있는 지도 |

과거에는 이런 시간대별 분위기를 표현하려면 각 레이어의 색상·안개 표현식을 4세트 따로 관리해야 했지만, Standard 스타일에서는 프리셋 이름 하나만 바꾸면 관련된 모든 레이어의 색감과 그림자가 일관되게 갱신된다.

<img src="/assets/images/posts/2026-08-26-mapboxgl-v3-standard-style-1.svg" alt="Mapbox GL JS v3 Standard 스타일의 라이트 프리셋별 태양 각도와 그림자 변화, config 옵션 구조도" style="width:100%;">

## 예제: Standard 스타일 초기화와 config 커스터마이징

```javascript
import mapboxgl from 'mapbox-gl';

const map = new mapboxgl.Map({
  container: 'map',
  style: 'mapbox://styles/mapbox/standard', // v3 Standard 스타일
  center: [126.978, 37.5665],
  zoom: 15,
  pitch: 60, // 3D 건물을 보기 위한 기울기
});

map.on('style.load', () => {
  // 라이트 프리셋을 저녁으로 설정 — 관련 레이어 전체가 일괄 갱신된다
  map.setConfigProperty('basemap', 'lightPreset', 'dusk');

  // 3D 건물 표시 여부와 랜드마크 강조 등 고수준 옵션 조정
  map.setConfigProperty('basemap', 'showPointOfInterestLabels', false);
  map.setConfigProperty('basemap', 'show3dObjects', true);

  // 세부 커스터마이징이 필요한 특정 레이어는 기존 방식대로 오버라이드
  map.setPaintProperty('building', 'fill-extrusion-color', '#d9d2c5');
});
```

`setConfigProperty`가 핵심 API다. 스타일 전체를 다시 만들지 않고도 런타임에 라이트 프리셋이나 레이블 표시 여부 같은 고수준 옵션을 바꿀 수 있어, 사용자가 낮/밤 모드를 토글하는 UI를 구현할 때 스타일 재로드 없이 부드럽게 전환할 수 있다.

## 실무 포인트

- **레거시 스타일과 Standard 스타일을 같은 프로젝트에서 섞어 쓰지 않는다**: Standard 스타일은 내부적으로 v2 스타일과 다른 레이어 구조(3D 라이팅 시스템에 맞춘 내장 레이어 이름)를 쓴다. 기존 `mapbox://styles/mapbox/streets-v12` 기반 커스터마이징 코드를 그대로 Standard 스타일에 적용하면 레이어 이름이 달라 오버라이드가 먹히지 않는 경우가 많다. 마이그레이션 시 커스터마이징 코드 전체를 재검토해야 한다.
- **3D 렌더링 비용을 저사양 기기에서 검증한다**: `show3dObjects`와 라이팅 효과는 시각적으로는 만족스럽지만 GPU 부하가 늘어난다. 모바일 웹뷰나 저사양 기기를 지원해야 한다면, `pitch`를 낮추거나 `show3dObjects`를 끄는 저사양 폴백 설정을 별도로 준비하는 것이 안전하다.
- **라이트 프리셋과 실제 시간대를 자동 연동하려면 별도 로직이 필요하다**: Mapbox가 사용자의 현재 시간에 맞춰 프리셋을 자동으로 바꿔주지는 않는다. "저녁 6시 이후에는 dusk로 전환"같은 요구는 애플리케이션 코드에서 현재 시각을 확인해 `setConfigProperty`를 직접 호출해야 한다.

## 3줄 요약

- Mapbox GL JS v3 Standard 스타일은 레이어를 손으로 조립하던 3D 라이팅 작업을 라이트 프리셋과 config 옵션으로 대체한다.
- `dawn`/`day`/`dusk`/`night` 프리셋은 태양 각도, 그림자, 색조를 한 번에 바꾸고, `setConfigProperty`로 런타임에 부드럽게 전환할 수 있다.
- 레거시 v2 스타일과 레이어 구조가 다르므로 마이그레이션 시 커스터마이징 코드를 재검토해야 하고, 3D 렌더링 비용은 저사양 기기에서 별도로 검증해야 한다.

## 참고 자료

- [Mapbox 공식 문서: Standard Style](https://docs.mapbox.com/style-spec/guides/the-standard-style/)
- [Mapbox 공식 문서: Config Properties (setConfigProperty)](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#setconfigproperty)
- [Mapbox 공식 블로그: Introducing Mapbox Standard](https://www.mapbox.com/blog/standard-core-style)
