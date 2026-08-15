---
layout: single
title: "실내 지도, GPS 없이 위치를 잡는 방법들"
date: 2026-08-15 22:20:00 +0530
categories: gis
tags: ["실내측위", "IMDF", "BLE비콘", "UWB"]
toc: true
toc_sticky: true
excerpt: "GPS 신호가 닿지 않는 실내 공간에서 위치를 파악하는 다양한 측위 기술과 실내지도 데이터 포맷을 비교한다."
---

## 왜 지금 이 이야기인가

공항, 대형 쇼핑몰, 병원처럼 넓고 복잡한 실내 공간에서 "지금 내가 어디 있는지"를 안내받고 싶은 수요는 꾸준히 존재해왔다. 그런데 GPS는 건물 구조물에 신호가 가려지는 실내 환경에서는 정확도가 급격히 떨어지거나 아예 수신되지 않는다. 이 문제를 해결하기 위해 GPS를 대체하는 여러 실내 측위(Indoor Positioning System, IPS) 기술이 발전해왔고, 최근에는 스마트폰 자체의 하드웨어 발전(Wi-Fi RTT 지원, UWB 칩 탑재 등)에 힘입어 실용화 단계에 가까워지고 있는 것으로 보인다.

실내 측위는 단순히 "기술적으로 가능한가"를 넘어 설치 비용, 유지보수, 정확도 요구 수준이 서로 얽혀 있는 문제다. 공항처럼 넓은 공간과 매장 내 특정 코너 안내처럼 좁은 범위는 요구되는 정확도 자체가 다르기 때문에, 기술 선택은 결국 트레이드오프의 문제로 귀결된다.

## 주요 실내 측위 기술 비교

| 기술 | 원리 | 대략적 정확도 | 특징 |
|---|---|---|---|
| Wi-Fi RTT (IEEE 802.11mc/az 기반) | 신호 왕복 시간(Round-Trip Time) 측정 | 1~3m 수준으로 보고되는 경우가 많음 | 기존 Wi-Fi AP 인프라 활용 가능, 지원 기기 필요 |
| BLE 비콘 | 신호 세기(RSSI) 기반 근접 추정 | 수 m 단위, 환경 영향 큼 | 설치 비용 저렴, 배터리 관리 필요 |
| 지자기(Geomagnetic) 측위 | 건물 내 철골 구조가 만드는 자기장 패턴 매칭 | 환경 의존도 높음 | 별도 인프라 설치 불필요, 사전 지도화(fingerprinting) 필요 |
| UWB (Ultra-Wideband) | 초광대역 펄스 신호의 정밀 거리 측정 | 수십 cm 수준으로 알려짐 | 정확도 높지만 앵커 장비 설치 비용 발생 |

실무에서는 이 기술들을 단독으로 쓰기보다 결합(sensor fusion)하는 경우가 많다. 예를 들어 BLE로 대략적인 층/구역을 파악한 뒤 UWB나 관성 센서(IMU)로 세부 위치를 보정하는 식이다. 정확도가 높을수록 인프라 설치 비용과 유지보수 부담도 함께 커지는 경향이 있어, 요구 정확도 수준을 먼저 정의하는 것이 설계의 출발점이 된다.

## 실내지도 데이터 포맷 — IMDF

실내 공간을 지도 데이터로 표현하는 표준 포맷 중 하나로 IMDF(Indoor Mapping Data Format)가 있다. Apple이 주도해 공개한 포맷으로, GeoJSON을 기반으로 건물의 층(level), 공간(unit), 시설(amenity), 출입구(opening) 등을 표준화된 스키마로 표현한다. 실내 지도는 실외 지도와 달리 "층" 개념이 필수적이고, 같은 위/경도라도 층에 따라 완전히 다른 공간을 가리키기 때문에 이런 실내 전용 스키마가 별도로 필요하다는 점이 자주 언급된다.

## 예제

```json
// IMDF의 level(층) 피처 예시 (개념적 형태, 실제 스펙은 더 많은 필드를 요구함)
{
  "type": "Feature",
  "feature_type": "level",
  "geometry": null,
  "properties": {
    "category": "unspecified",
    "restriction": null,
    "outdoor": false,
    "ordinal": 1,
    "name": { "en": "1st Floor" },
    "short_name": { "en": "L1" },
    "address_id": null,
    "building_ids": ["b-001"]
  }
}
```

```python
# BLE 비콘 RSSI 기반 대략적 거리 추정 (로그 거리 경로 손실 모델, 개념 예시)
import math

def estimate_distance(rssi, measured_power=-59, n=2.0):
    """
    rssi: 수신 신호 세기(dBm)
    measured_power: 1m 거리에서의 기준 RSSI 값(비콘별 캘리브레이션 필요)
    n: 환경 감쇠 계수(장애물이 많을수록 커짐)
    """
    if rssi == 0:
        return -1.0
    ratio = (measured_power - rssi) / (10 * n)
    return math.pow(10, ratio)
```

## 실무 포인트와 주의사항

- 요구 정확도를 먼저 정의할 것 — "층 안내"면 BLE/Wi-Fi로 충분하지만 "정밀 내비게이션"이면 UWB나 센서 퓨전이 필요할 수 있다
- BLE RSSI 기반 거리 추정은 사람의 움직임, 금속 구조물, 습도 등 환경 요인에 민감하므로 실측 캘리브레이션이 필수적이다
- 지자기 측위는 사전 fingerprinting(지도화) 작업이 필요해 매장 레이아웃이 자주 바뀌는 공간에는 유지보수 부담이 커질 수 있다
- 실내지도 데이터를 자체 포맷으로 만들기보다 IMDF 같은 표준 스키마를 검토하면 이후 다른 실내 내비게이션 서비스와의 연동이 수월해질 수 있다

## 3줄 요약

- GPS가 닿지 않는 실내에서는 Wi-Fi RTT, BLE 비콘, 지자기 측위, UWB 등 대체 기술이 쓰인다
- 정확도가 높아질수록 인프라 설치·유지보수 비용도 함께 커지는 트레이드오프가 존재한다
- IMDF 같은 표준 실내지도 포맷을 활용하면 층 개념이 필수적인 실내 공간을 체계적으로 표현할 수 있다

## 참고 자료

- [Apple Indoor Maps Program - IMDF](https://developer.apple.com/maps/indoor-maps-program/)
- [W3C Indoor Mapping Data Format 문서](https://www.w3.org/TR/indoor-mapping-data-format/)
- [Android Wi-Fi RTT (802.11mc) 개발자 문서](https://developer.android.com/develop/connectivity/wifi/wifi-rtt)
