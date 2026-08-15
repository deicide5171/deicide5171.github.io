---
layout: single
title: "디지털 트윈 도시의 설계도, CityGML — 3D 건물 모델과 LOD 이해하기"
date: 2026-08-17 13:20:00 +0530
categories: gis
tags: ["citygml", "digital-twin", "3d-city-model", "lod", "ogc"]
toc: true
toc_sticky: true
excerpt: "도시 전체를 3D로 복제하는 디지털 트윈이 확산되는 지금, 그 밑바탕이 되는 국제 표준 CityGML의 데이터 모델과 LOD(상세도) 개념을 정리한다."
---

## 왜 지금 디지털 트윈 도시인가

**디지털 트윈 도시**는 실제 도시의 건물·지형·인프라를 3D 데이터로 복제해, 도시계획 시뮬레이션·일조권 분석·재난 대응 훈련 같은 의사결정을 가상 공간에서 먼저 해보는 접근이다. 여러 지자체와 공공기관이 스마트시티 사업의 일환으로 3D 도시 모델 구축을 추진하면서, "이 건물 데이터를 누가 만들었든 어떤 소프트웨어로든 읽고 조합할 수 있어야 한다"는 요구가 커지고 있다.

앞서 Cesium 3D Tiles나 WebGL 렌더링 파이프라인을 다룬 글들이 "3D 도시 데이터를 브라우저에서 어떻게 빠르게 그리는가"에 초점을 맞췄다면, 이번 글은 한 단계 앞선 질문을 다룬다. **그 3D 건물 데이터 자체를 어떤 구조와 표준으로 담을 것인가**다. 렌더링 엔진이 무엇이든, 그 밑에는 결국 건물의 형상·속성·의미를 기술하는 데이터 모델이 있어야 하고, 이 표준화 지점에서 가장 널리 쓰이는 것이 OGC(Open Geospatial Consortium)의 **CityGML**이다.

## 핵심 개념 1: CityGML은 무엇을 표준화하는가

CityGML은 단순히 "3D 건물 도형 파일 포맷"이 아니다. GML(Geography Markup Language) 기반으로, 건물·도로·교량·수계·식생 같은 도시 객체(City Object)의 **형상(geometry)** 과 **의미 정보(semantics)**, **위상 관계(topology)** 를 함께 기술하는 데이터 모델이다. 예를 들어 하나의 건물 피처는 벽·지붕·바닥 같은 경계면을 개별 요소로 갖고, 각 요소가 "이것은 지붕이다", "이 벽에는 창문이 3개 있다" 같은 의미론적 태그를 가질 수 있다. 순수 3D 그래픽 포맷(OBJ, glTF 등)이 형상 위주라면, CityGML은 그 형상이 "무엇인지"까지 표준화된 스키마로 담는다는 점이 다르다.

| 구분 | CityGML | glTF/OBJ 등 그래픽 포맷 | 3D Tiles |
|---|---|---|---|
| 목적 | 도시 객체의 의미·형상 표준화 | 3D 모델의 시각적 표현 | 대용량 3D 데이터 스트리밍 |
| 의미 정보 | 건물·벽·지붕 등 시맨틱 포함 | 대체로 없음(메시·재질 위주) | 타일 메타데이터 수준 |
| 주 용도 | 도시계획, 분석, 데이터 교환 | 렌더링, 게임·시각화 | 웹 브라우저 실시간 렌더링 |
| 대표 확장 | CityJSON(경량 JSON 버전) | — | Cesium, 3D Tiles 생태계 |

## 핵심 개념 2: LOD(Level of Detail) — 목적에 맞는 상세도 고르기

CityGML의 가장 실무적인 개념은 **LOD(Level of Detail)** 다. 같은 건물이라도 용도에 따라 필요한 상세도가 다르기 때문에, CityGML은 하나의 건물을 여러 LOD로 각각 표현할 수 있게 한다.

<img src="/assets/images/posts/2026-08-17-digital-twin-city-citygml-1.svg" alt="CityGML LOD0부터 LOD4까지 단계별 3D 건물 모델 상세도 개념도" style="width:100%;">

- **LOD0**: 2.5D 지형에 건물 발자국(footprint)만 얹은 형태. 광역 도시 통계나 대략적 지도 시각화에 적합하다.
- **LOD1**: 건물을 평평한 지붕의 단순 블록(box)으로 압출한 형태. 도시 스카이라인 개요, 그림자 대략 분석 등에 쓰인다.
- **LOD2**: 실제 지붕 형태(박공·모임지붕 등)와 외피 텍스처까지 포함. 일조권 분석, 소음 전파 시뮬레이션처럼 지붕 형상이 결과에 영향을 주는 분석에 필요하다.
- **LOD3**: 창문·출입구·발코니 같은 건축적 디테일까지 반영한 정밀 외관 모델. 경관 시뮬레이션, 정밀 렌더링에 쓰인다.
- **LOD4**: 실내 공간(방, 계단, 통로)까지 포함하는 최고 상세도. 실내 대피 경로 시뮬레이션 등 특수 목적에 한정적으로 쓰인다.

상세도가 올라갈수록 데이터 용량과 구축 비용이 함께 커지기 때문에, 실무에서는 "전체 도시는 LOD1~2로, 특정 랜드마크 건물만 LOD3"처럼 **혼합 LOD 전략**을 쓰는 경우가 많다.

## 예제 1: CityGML(GML/XML)로 표현한 LOD2 건물 조각

```xml
<!-- CityGML 2.0 - 단순화한 LOD2 건물 예시 -->
<bldg:Building gml:id="bldg_001">
  <bldg:function>1000</bldg:function> <!-- 주거용 -->
  <bldg:measuredHeight uom="m">18.5</bldg:measuredHeight>
  <bldg:lod2Solid>
    <gml:Solid>
      <gml:exterior>
        <gml:CompositeSurface>
          <gml:surfaceMember>
            <gml:Polygon> <!-- 지붕면(RoofSurface) -->
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0 0 18.5  10 0 18.5  10 10 21.0  0 10 21.0  0 0 18.5
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:CompositeSurface>
      </gml:exterior>
    </gml:Solid>
  </bldg:lod2Solid>
</bldg:Building>
```

`gml:posList`의 좌표들이 건물 경계면(여기서는 지붕)의 3D 형상을, `bldg:function`·`bldg:measuredHeight` 같은 속성이 의미 정보를 담는다는 구조를 보여준다.

## 예제 2: 경량 대안, CityJSON으로 같은 정보 표현하기

CityGML의 XML 구조는 표준화 관점에서는 강력하지만, 파일 크기가 크고 파싱이 무겁다는 실무적 단점이 있다. 이를 보완하기 위해 나온 것이 **CityJSON**이다. 같은 CityGML 데이터 모델을 JSON으로 재구성해 파일 크기를 크게 줄이고 웹·스크립트 환경에서 다루기 쉽게 만든다.

```json
{
  "type": "CityJSON",
  "version": "2.0",
  "CityObjects": {
    "bldg_001": {
      "type": "Building",
      "attributes": { "function": "residential", "measuredHeight": 18.5 },
      "geometry": [
        { "type": "Solid", "lod": "2", "boundaries": [[[[0, 1, 2, 3]]]] }
      ]
    }
  },
  "vertices": [[0, 0, 18.5], [10, 0, 18.5], [10, 10, 21.0], [0, 10, 21.0]]
}
```

정점 좌표를 `vertices` 배열에 한 번만 저장하고 각 지오메트리는 인덱스로 참조하기 때문에, 반복되는 건물이 많은 도시 규모 데이터셋에서 CityGML(XML) 대비 파일 크기가 크게 줄어드는 구조다.

## 실무 포인트

- **분석 목적부터 정하고 LOD를 고른다**: LOD4까지 무조건 정밀하게 만드는 것이 능사가 아니다. 구축·유지보수 비용이 함께 커지므로, 실제로 필요한 분석(일조·소음·경관 등)에 맞춰 LOD를 선택한다.
- **CityGML ↔ 3D Tiles/glTF 변환 파이프라인을 고려한다**: 웹 브라우저에서 실시간 렌더링하려면 결국 3D Tiles나 glTF 같은 스트리밍 친화적 포맷으로 변환하는 과정이 필요하다. CityGML은 원본 데이터 교환·보관용, 3D Tiles는 서비스용으로 역할을 나누는 것이 일반적이다.
- **의미 정보 손실에 주의한다**: 렌더링 포맷으로 변환하는 과정에서 CityGML이 담고 있던 속성(건물 용도, 준공연도 등)이 누락되기 쉽다. 변환 도구가 시맨틱 정보를 메타데이터로 보존하는지 확인해야 한다.
- **버전(2.0 vs 3.0)과 확장 모듈 차이를 확인한다**: CityGML 3.0은 실내외 공간을 더 유연하게 다루는 등 이전 버전과 스키마 차이가 있어, 사용 중인 도구·데이터셋이 어떤 버전을 전제하는지 먼저 확인하는 것이 안전하다.

## 3줄 요약

- CityGML은 3D 건물의 형상뿐 아니라 의미·속성 정보까지 표준화된 스키마로 담는 OGC 표준으로, 디지털 트윈 도시 데이터 교환의 공통 언어 역할을 한다.
- LOD(Level of Detail) 개념으로 같은 건물을 목적에 맞춰 발자국 수준(LOD0)부터 실내 공간(LOD4)까지 서로 다른 상세도로 표현할 수 있다.
- 실무에서는 CityGML(또는 경량 대안인 CityJSON)을 원본 데이터로 관리하고, 웹 렌더링에는 3D Tiles·glTF 같은 포맷으로 변환해 사용하는 역할 분리가 일반적이다.

## 참고 자료

- [OGC — CityGML Standard](https://www.ogc.org/standard/citygml/)
- [CityJSON 공식 문서](https://www.cityjson.org/)
- [OGC 3D Tiles Community Standard](https://www.ogc.org/standard/3dtiles/)
