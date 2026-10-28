---
layout: single
title: "\"하천 수위 센서 값을 지도에서 실시간으로 보여주세요\" — OGC SensorThings API 도입 판단"
date: 2026-10-28 12:45:00 +0530
categories: gis
tags: ["SensorThings", "실시간센서", "IoT", "GeoServer", "공간데이터표준"]
toc: true
toc_sticky: true
excerpt: "수백 개 수위·수질 센서 값을 지도에서 실시간으로 보여달라는 요구는 WFS·WMS가 풀도록 설계된 문제가 아니다. OGC SensorThings API가 기존 공간 데이터 스택과 어떻게 공존하는지, FROST-Server 기반 구조와 도입 판단 기준을 정리했다."
---

## 도입

"하천 수위·수질 센서 수백 개 값을 지도에서 실시간으로 보여주고, 임계값을 넘으면 바로 경보를 띄워주세요." 재난 대응이나 시설 관제 부서에서 흔히 나오는 요구다. 얼핏 보면 기존 지도 서비스에 레이어 하나 더 얹는 일 같지만, 실제로는 전혀 다른 성격의 데이터를 다루게 된다. WFS로 서빙하던 필지·건물 같은 피처는 "지금 이 순간의 스냅샷"을 조회하는 데 맞춰져 있고, 변경 빈도도 낮다. 반면 센서 값은 **같은 위치에서 끊임없이 발생하는 시계열**이고, 클라이언트는 매번 다시 요청하는 대신 값이 바뀌는 순간 알림을 받고 싶어 한다.

이 둘을 같은 WFS 엔드포인트에 욱여넣으려 하면 금방 한계가 드러난다. 관측값마다 피처를 새로 만들면 테이블이 기하급수적으로 불어나고, 폴링 주기를 짧게 잡으면 서버 부하가 늘어나며, 그렇다고 길게 잡으면 "실시간"이라는 말이 무색해진다. OGC SensorThings API(STA)는 바로 이 간극—공간 데이터 표준과 시계열 센서 데이터 사이—을 메우기 위해 설계된 표준이다. 이 글은 STA를 도입할지 말지를 가르는 기준과, 기존 GeoServer·WFS 스택과 어떻게 공존시킬지를 다룬다.

## 왜 WFS·WMS로는 부족한가

WFS·WMS는 OGC 표준 중에서도 "지도 위의 지리 객체"를 다루는 데 최적화돼 있다. 피처 하나는 비교적 안정적인 지오메트리와 속성을 갖고, 클라이언트는 필요할 때 조회(pull)한다. 센서 데이터는 이 가정을 두 가지 지점에서 깬다.

- **데이터 모델 불일치**: 센서 하나가 10분마다 값을 찍으면 하루에 144개, 1년이면 5만 개가 넘는 관측값이 쌓인다. 이걸 피처 테이블에 그대로 넣으면 공간 인덱스가 감당해야 할 로우 수가 걷잡을 수 없이 늘어난다. 관측값(Observation)은 애초에 "위치가 있는 피처"가 아니라 "피처에 달린 시계열"로 모델링해야 한다.
- **전달 방식 불일치**: 임계값 초과를 "바로" 알려야 하는 요구는 폴링으로는 근본적으로 지연이 생긴다. 폴링 주기를 줄이면 변경 없는 대부분의 요청이 서버 자원만 소모한다.

STA는 Thing(관측 대상)–Sensor(센서)–Datastream(관측 계열)–Observation(관측값)이라는 데이터 모델로 이 구조를 분리하고, MQTT 구독을 표준 스펙에 포함시켜 값이 바뀌는 순간 클라이언트에 푸시할 수 있게 한다.

## 전체 시스템에서의 위치

센서 데이터는 디바이스에서 출발해 지도 화면에 닿기까지 기존 WFS 파이프라인과는 다른 경로를 탄다.

<img src="/assets/images/posts/2026-10-28-ogc-sensorthings-api-realtime-sensor-map-design-1.svg" alt="수위 센서가 MQTT 브로커를 거쳐 FROST-Server(SensorThings API)에 적재되고, 지도 클라이언트는 MQTT 구독과 REST 조회로 실시간 값과 과거 이력을 각각 받아오며, 기존 GeoServer의 정적 레이어와는 별도 경로로 공존하는 구조." style="width:100%;">

- **디바이스 → MQTT 브로커**: 센서는 측정값을 MQTT로 발행한다. 통신이 불안정한 현장(하천·산간)에서도 브로커가 재전송·버퍼링을 흡수한다.
- **브로커 → STA 서버(예: FROST-Server)**: STA 서버가 Observation으로 적재하면서 Thing·Datastream 메타데이터와 연결한다. 이 레이어가 "센서 데이터의 진실 공급원"이 된다.
- **STA 서버 → 지도 클라이언트**: 클라이언트는 과거 이력은 STA의 REST(OGC API 호환) 조회로, 실시간 갱신은 MQTT 구독으로 받는다. 두 경로를 나눠야 "지금 값"과 "추세 그래프"를 동시에 보여주는 화면을 효율적으로 만들 수 있다.
- **기존 GeoServer/WFS와의 공존**: 필지·건물처럼 변경이 드문 정적 레이어는 계속 WFS로 서빙하고, STA는 동적 관측 레이어만 전담한다. 두 스택을 억지로 합치지 않는 것이 핵심이다.
- **경보 로직**: 임계값 판정은 STA 서버 안에 넣지 않고 별도 구독자(subscriber) 서비스로 분리해, MQTT 메시지를 받아 판정만 전담하게 한다. STA 서버의 책임을 "저장·전달"로 좁게 유지하기 위해서다.

## 선택의 트레이드오프

| 기준 | OGC SensorThings API | 자체 시계열DB(Influx/Timescale) + 커스텀 API | WFS에 관측값을 피처로 적재 |
|---|---|---|---|
| 표준 호환성 | OGC 표준, 기존 GIS 클라이언트·프레임워크와 호환 | 없음, 직접 문서화·유지보수 필요 | WFS 호환이지만 모델이 맞지 않음 |
| 실시간 전달 | MQTT 구독이 스펙에 포함 | 별도로 Kafka/WebSocket 구축 필요 | 폴링 외 방법 없음 |
| 공간 질의 | 위치 기반 Thing 조회 지원 | 시계열 질의는 강하나 공간 질의는 약함 | 공간 질의는 강하나 시계열에 비효율 |
| 초기 구축 비용 | FROST-Server 등 레퍼런스 구현 존재, 러닝커브 있음 | 구성요소를 직접 조합해야 함 | 낮음(기존 인프라 재사용) |
| 적합하지 않은 경우 | 센서 수가 적고 실시간성이 중요하지 않을 때는 과한 구조 | 공간 질의가 핵심 요구일 때는 부적합 | 관측값 양이 적고 변경이 드물 때만 그나마 성립 |

센서 수가 수십 개 수준이고 "하루 한 번 집계만 보면 된다"는 요구라면 STA 도입은 과한 투자다. 반대로 센서가 수백~수천 개로 늘어나거나, 실시간 경보가 핵심 기능이라면 표준을 따르는 쪽이 클라이언트 생태계(기존 STA 호환 뷰어·분석 도구)를 그대로 가져다 쓸 수 있어 장기적으로 싸다.

## 코드 예제

```http
# STA REST API로 새 관측값 등록 (HTTP POST)
POST /v1.1/Datastreams(12)/Observations
Content-Type: application/json

{
  "phenomenonTime": "2026-10-28T03:15:00Z",
  "result": 2.47,
  "resultQuality": "good"
}
```

```javascript
// 클라이언트에서 MQTT로 실시간 구독
const client = mqtt.connect('mqtt://sta-broker.example.com');
client.subscribe('v1.1/Datastreams(12)/Observations');
client.on('message', (topic, payload) => {
  const obs = JSON.parse(payload.toString());
  updateMapMarker(datastreamId, obs.result); // 지도 위 값만 갱신, 레이어 전체 리로드 없음
});
```

## 실무 포인트

- **Thing/Datastream 설계를 먼저 끝낸다.** 센서 하나가 여러 관측 항목(수위·수온)을 가질 수 있으므로, Datastream을 항목별로 분리할지 묶을지부터 정해야 나중에 쿼리 패턴이 꼬이지 않는다.
- **경보 임계값 로직은 STA 서버 밖에 둔다.** 표준 구현체(FROST-Server 등)에 커스텀 로직을 끼워 넣으면 업그레이드할 때마다 포크 유지보수 부담이 생긴다.
- **MQTT 브로커의 가용성이 전체 실시간성을 좌우한다.** 브로커가 단일 장애점이 되지 않도록 클러스터링이나 관리형 브로커 사용을 먼저 검토한다.
- **기존 WFS 레이어를 STA로 옮기려 하지 않는다.** 두 표준은 애초에 다른 문제를 풀도록 설계됐으므로, 정적 레이어와 동적 관측 레이어를 같은 서버에 합치려는 시도 자체가 설계 실수로 이어지기 쉽다.

## 마무리

- 실시간 센서 데이터는 "위치가 있는 시계열"이라 WFS·WMS가 가정하는 정적 피처 모델과 근본적으로 다르다.
- OGC SensorThings API는 Thing–Sensor–Datastream–Observation 모델과 MQTT 구독으로 저장·전달 문제를 표준화하며, 기존 GeoServer 스택은 정적 레이어 전담으로 남겨 공존시키는 것이 현실적이다.
- 센서 수가 적고 실시간성이 중요하지 않다면 표준 도입은 과투자이며, 수백 개 이상·실시간 경보가 핵심일 때 도입 가치가 커진다.

## 참고 자료

- [OGC SensorThings API — OGC 공식 표준 페이지](https://www.ogc.org/standards/sensorthings/)
- [FROST-Server — Fraunhofer IOSB 레퍼런스 구현](https://github.com/FraunhoferIOSB/FROST-Server)
- [OGC SensorThings API 2.0 Public Comment](https://www.ogc.org/requests/ogc-seeks-public-comment-on-proposed-ogc-sensorthings-api-version-2-0/)
