---
layout: single
title: "3D 모델에 '이 건물은 몇 층인가'를 묻는다 — 3D Tiles 1.1의 메타데이터·시맨틱스 확장"
date: 2026-08-25 13:20:00 +0530
categories: gis
tags: ["3d-tiles", "cesium", "gltf", "structural-metadata", "digital-twin", "gis"]
toc: true
toc_sticky: true
excerpt: "3D Tiles가 렌더링을 위한 LOD 스트리밍 표준을 넘어, 각 타일의 지오메트리에 건물 층수·용도·소유자 같은 구조화된 속성을 부여하는 1.1의 메타데이터·시맨틱스 확장을 정리한다."
---

도시 전체 3D 모델을 웹에서 매끄럽게 렌더링하는 문제는 3D Tiles 표준과 CesiumJS의 LOD 스트리밍 구조로 상당 부분 해결됐다. 그런데 렌더링이 잘 된다고 해서 그 3D 모델이 곧바로 쓸모 있는 디지털 트윈이 되는 것은 아니다. 화면에 예쁘게 그려진 건물 메시를 클릭했을 때 "이 건물은 몇 층이고, 준공 연도는 언제이며, 소유자는 누구인가"를 물어볼 수 없다면, 그 3D 모델은 사실 정교한 배경 그림에 가깝다.

3D Tiles 1.1은 이 문제를 정면으로 다룬다. 이 글은 3D Tiles의 렌더링·LOD 스트리밍 구조 자체가 아니라, 1.1에서 정식으로 편입된 **메타데이터·시맨틱스 확장**에 집중한다. 타일 안의 지오메트리 하나하나에 구조화된 속성을 붙이고, 그 속성으로 3D 공간을 실제 데이터베이스처럼 질의할 수 있게 만드는 구조를 정리한다.

## 핵심 개념 1: 3D Tiles 1.1 이전 — 메타데이터는 부가 확장이었다

3D Tiles 1.0 시절에도 `3DTILES_batch_table`이라는 확장으로 각 지오메트리에 속성 데이터를 붙이는 것이 가능하긴 했다. 문제는 이것이 표준의 정식 명세가 아니라 **확장(extension)**으로 존재해서, 뷰어나 도구마다 지원 여부가 제각각이었고 구조도 자유 형식 JSON에 가까워 스키마 검증이나 타입 안정성이 부족했다. gITF 쪽에서도 메타데이터를 다루는 방식이 파편화돼 있어 3D Tiles와 gLTF 사이의 메타데이터 상호운용이 매끄럽지 않았다.

3D Tiles 1.1은 OGC 표준으로 정식 승격되면서 이 메타데이터 체계를 gLTF의 `EXT_structural_metadata`, `EXT_mesh_features` 확장과 정렬시켰다. 즉 3D Tiles와 gLTF가 같은 메타데이터 모델을 공유하게 되어, 3D Tiles 타일셋 안에 담긴 gLTF 자산의 메타데이터를 별도 변환 없이 동일한 방식으로 읽고 쓸 수 있게 됐다.

## 핵심 개념 2: 시맨틱 클래스와 프로퍼티 테이블

메타데이터 확장의 핵심 구조는 **스키마(schema)**, **클래스(class)**, **프로퍼티(property)**의 조합이다. 스키마에서 "Building"이라는 클래스를 정의하고, 그 클래스가 `height`(float), `floors`(uint), `yearBuilt`(uint), `usage`(enum: residential/commercial/mixed) 같은 프로퍼티를 갖도록 선언한다. 실제 데이터는 프로퍼티 테이블(property table)에 컬럼형으로 저장되고, 각 지오메트리(메시의 각 feature)는 이 테이블의 특정 행을 가리키는 방식으로 값이 연결된다.

<img src="/assets/images/posts/2026-08-25-3d-tiles-1-1-metadata-semantics-1.svg" alt="3D Tiles 1.1 메타데이터 구조 — 스키마에서 클래스와 프로퍼티를 정의하고, 각 건물 지오메트리가 프로퍼티 테이블의 행을 참조해 층수·용도 등 속성값을 얻는 구조" style="width:100%;">

이 구조 덕분에 "이 지역에서 20층 이상, 준공 20년 이상 된 건물만 강조 표시"처럼 렌더링과 무관하게 순수하게 속성 기반의 질의·필터링이 가능해진다. 클라이언트는 스키마를 한 번 읽어 각 프로퍼티의 타입과 의미를 알고, 이후 타일이 스트리밍될 때마다 프로퍼티 테이블 값을 읽어 스타일링 규칙(예: 특정 조건을 만족하는 건물만 색상 강조)을 실시간으로 적용할 수 있다.

## 핵심 개념 3: EXT_mesh_features — 메시의 어느 부분이 어느 개체인가

건물 하나가 통짜 메시가 아니라 벽, 창문, 지붕처럼 여러 서브 파트로 이뤄진 경우, "이 메시의 어느 정점 집합이 어느 개체에 속하는가"를 알아야 개체별 속성 조회가 가능하다. `EXT_mesh_features`는 gLTF 메시의 각 프리미티브에 **feature ID**를 부여해서, 정점이나 삼각형 단위로 어떤 개체에 속하는지를 식별한다. 이 feature ID가 앞서 설명한 프로퍼티 테이블의 행 인덱스와 연결되면서, 렌더링 메시 → 개체 식별 → 구조화된 속성이라는 전체 파이프라인이 완성된다.

| 구분 | 3D Tiles 1.0 (배치 테이블) | 3D Tiles 1.1 (구조적 메타데이터) |
|---|---|---|
| 표준화 수준 | 벤더 확장 | OGC 정식 명세 |
| gLTF와의 정합성 | 별도 변환 필요 | EXT_structural_metadata로 통일 |
| 개체 식별 방식 | batch ID | EXT_mesh_features (feature ID) |
| 스키마 검증 | 사실상 자유 형식 | 타입이 있는 스키마 정의 |
| 대규모 속성 저장 | 타일별 JSON | 이진 버퍼 기반 프로퍼티 테이블 |

## 예제: 3D Tiles 메타데이터 스키마 정의 (JSON)

```json
{
  "schema": {
    "classes": {
      "building": {
        "properties": {
          "height": { "type": "SCALAR", "componentType": "FLOAT32" },
          "floors": { "type": "SCALAR", "componentType": "UINT8" },
          "yearBuilt": { "type": "SCALAR", "componentType": "UINT16" },
          "usage": {
            "type": "ENUM",
            "enumType": "usageType"
          }
        }
      }
    },
    "enums": {
      "usageType": {
        "values": [
          { "name": "RESIDENTIAL", "value": 0 },
          { "name": "COMMERCIAL", "value": 1 },
          { "name": "MIXED", "value": 2 }
        ]
      }
    }
  },
  "propertyTables": [
    {
      "class": "building",
      "count": 3,
      "properties": {
        "height": { "values": 0 },
        "floors": { "values": 1 },
        "yearBuilt": { "values": 2 },
        "usage": { "values": 3 }
      }
    }
  ]
}
```

CesiumJS에서는 이 메타데이터를 `Cesium3DTileFeature.getProperty('floors')`처럼 클릭한 지오메트리의 feature 객체를 통해 즉시 조회할 수 있고, 스타일 표현식(`Cesium3DTileStyle`)에서도 `${floors} >= 20` 같은 조건을 직접 스타일링 규칙에 넣을 수 있다.

## 실무 포인트

- **속성을 타일 생성 파이프라인 초기부터 설계한다**: GIS 원본 데이터(BIM, CityGML, 지적도)에 있던 속성 정보가 3D Tiles로 변환되는 과정에서 누락되지 않도록, 타일링 파이프라인(예: Cesium ion, 3d-tiles-tools) 설정 단계에서 어떤 속성을 스키마에 포함시킬지 미리 정의해야 한다.
- **프로퍼티 테이블 크기와 스트리밍 성능을 함께 고려한다**: 속성이 많아질수록 타일 파일 크기가 커지고 초기 로딩이 느려질 수 있다. 자주 조회되는 속성만 프로퍼티 테이블에 넣고, 상세 정보는 별도 API로 지연 조회하는 하이브리드 구조가 실무에서 흔하다.
- **스타일링과 속성 필터링을 분리해서 설계한다**: 시각적 스타일(색상, 투명도)과 속성 기반 필터링(특정 조건의 건물만 표시)은 같은 메타데이터를 쓰지만 목적이 다르므로, UI 상에서 "필터"와 "스타일"을 별개의 조작으로 노출하는 것이 사용자 혼란을 줄인다.

## 3줄 요약

- 3D Tiles 1.1은 벤더 확장이던 배치 테이블 방식의 메타데이터를 OGC 정식 명세로 승격시키고 gLTF의 EXT_structural_metadata와 정렬시켰다.
- 스키마-클래스-프로퍼티 테이블 구조로 각 지오메트리에 타입이 있는 구조화된 속성을 부여할 수 있어, 3D 공간을 렌더링뿐 아니라 속성 질의 대상으로도 다룰 수 있다.
- EXT_mesh_features가 메시의 개체 단위를 식별해 프로퍼티 테이블과 연결하면서, 렌더링 메시부터 구조화된 속성 조회까지 이어지는 디지털 트윈 파이프라인이 완성된다.

## 참고 자료

- [OGC 3D Tiles 1.1 명세](https://docs.ogc.org/cs/22-025r4/22-025r4.html)
- [Cesium 공식 문서: 3D Tiles Metadata](https://cesium.com/learn/3d-tiles/3d-tiles-metadata/)
- [Khronos gLTF 확장: EXT_structural_metadata](https://github.com/CesiumGS/glTF/tree/proposal-EXT_structural_metadata/extensions/2.0/Vendor/EXT_structural_metadata)
