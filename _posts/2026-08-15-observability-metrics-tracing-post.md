---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — 옵저버빌리티, 메트릭과 트레이싱"
date: 2026-08-15 23:10:00 +0530
categories: dev-insight
tags: ["옵저버빌리티", "메트릭", "분산트레이싱", "OpenTelemetry"]
toc: true
toc_sticky: true
excerpt: "로그 설계만으로는 채워지지 않는 지점을 짚고, 다음 학습 주제로 메트릭과 분산 트레이싱을 추천하는 이유를 로드맵과 함께 정리한다."
---

## 로그만으로는 부족한 지점

이 블로그에서는 그동안 장애 대응, 로그 설계, 서킷 브레이커, 레이트 리밋처럼 시스템을 안정적으로 운영하기 위한 여러 주제를 다뤄왔다. 그중에서도 로그 설계는 "무슨 일이 있었는지 기록하는" 가장 기본적인 도구로 다뤘는데, 실제로 장애를 겪어본 사람이라면 로그만으로는 한계가 있다는 것을 느껴봤을 것이다.

로그는 "특정 순간에 무슨 일이 있었는지"를 알려주지만, "지금 시스템 전체가 건강한가"라는 질문에는 잘 답하지 못한다. 초당 요청 수, 에러율, 응답 시간 분포 같은 추세를 로그만으로 파악하려면 방대한 로그를 집계해야 하는데, 이는 비효율적이고 느리다. 또한 하나의 요청이 여러 마이크로서비스를 거쳐 갈 때, 로그만으로는 "이 요청이 어느 서비스에서 어디에서 지연됐는지"를 재구성하기가 매우 어렵다. 각 서비스의 로그가 따로따로 쌓여 있기 때문이다.

이 지점에서 필요한 것이 메트릭(metrics)과 분산 트레이싱(distributed tracing)이다. 로그, 메트릭, 트레이싱은 흔히 "옵저버빌리티의 세 기둥"으로 불리며, 서로 다른 질문에 답하기 위해 함께 쓰인다. 로그 설계를 다뤄본 다음 단계로 이 두 가지를 학습하는 것을 추천하는 이유가 여기에 있다.

## 학습 로드맵

| 단계 | 학습 주제 | 목표 |
|---|---|---|
| 1단계 | 메트릭 기초(카운터, 게이지, 히스토그램) | 시스템 상태를 수치로 표현하고 집계하는 법 이해 |
| 2단계 | Prometheus 등 메트릭 수집/저장 도구 | 메트릭을 수집·저장·질의하는 실습 |
| 3단계 | 분산 트레이싱 개념과 OpenTelemetry | 요청 하나의 전체 흐름을 서비스 간에 추적하는 법 이해 |
| 4단계 | 대시보드/알림 설계(Grafana 등) | 수집한 데이터를 실제 운영에 쓸 수 있게 시각화·경보화 |
| 5단계 | SLO/SLI와 연계 | 메트릭을 서비스 수준 목표와 연결해 의사결정에 활용 |

로그 설계를 이미 다뤄봤다면 1~2단계는 비교적 빠르게 진행할 수 있을 것으로 보이며, 실무에 바로 적용하려면 3단계(분산 트레이싱)까지는 반드시 경험해보는 것을 권한다.

## 핵심 개념: 로그·메트릭·트레이싱 삼각형

- **로그(Log)**: 특정 시점에 발생한 이산적인 이벤트의 상세 기록. "무슨 일이 있었나"에 답한다.
- **메트릭(Metric)**: 시간에 따라 집계된 수치 데이터(카운터, 게이지, 히스토그램). "지금 상태가 어떤가"에 답하며, 대시보드와 알림의 기반이 된다.
- **트레이싱(Trace)**: 하나의 요청이 여러 서비스를 거치는 전체 경로를 스팬(span) 단위로 기록한 것. "이 요청이 어디서 느려졌나"에 답한다.

이 세 가지를 통합적으로 다루기 위해 최근에는 **OpenTelemetry**가 사실상의 표준으로 자리 잡아가는 것으로 보인다. OpenTelemetry는 로그·메트릭·트레이스를 하나의 계측(instrumentation) API/SDK로 통일해 수집하고, Prometheus, Jaeger, Grafana 등 다양한 백엔드로 데이터를 내보낼 수 있게 해준다.

## 예제

OpenTelemetry로 Node.js 애플리케이션에 트레이싱을 계측하는 간단한 예시:

```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({ url: 'http://otel-collector:4318/v1/traces' }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();
```

Prometheus 스타일의 히스토그램 메트릭 정의 예시:

```yaml
# 요청 처리 시간 히스토그램
http_request_duration_seconds:
  type: histogram
  buckets: [0.1, 0.3, 0.5, 1, 2, 5]
  labels: [method, route, status_code]
```

## 실무 포인트와 주의사항

- 트레이싱은 모든 요청을 100% 수집하면 비용과 성능 부담이 커지므로, 샘플링 전략(고정 비율, 에러 우선 샘플링 등)을 함께 설계해야 한다.
- 메트릭 카디널리티(레이블 조합 수)가 과도하게 커지면 저장 비용이 급격히 늘어날 수 있으므로 레이블 설계에 주의해야 한다.
- 로그·메트릭·트레이스를 서로 연결(trace ID를 로그에 남기는 등)해야 세 데이터를 오가며 원인을 추적할 수 있다.
- 알림은 "임계치를 넘었다"는 사실만 알리는 것보다, SLO 기반으로 "사용자 경험에 실제로 영향을 주는" 신호에 집중해 설계하는 것이 알림 피로를 줄이는 데 도움이 된다.

## 3줄 요약

- 로그는 개별 이벤트를, 메트릭은 추세를, 트레이싱은 요청의 전체 흐름을 보여주며 셋이 함께 있어야 옵저버빌리티가 완성된다.
- OpenTelemetry가 세 데이터를 통합 계측하는 사실상의 표준으로 자리 잡아가고 있다.
- 다음 학습 단계로 메트릭 수집 도구, 분산 트레이싱, 대시보드/알림 설계 순으로 로드맵을 잡는 것을 추천한다.

## 참고 자료

- [OpenTelemetry 공식 문서](https://opentelemetry.io/docs/)
- [Prometheus 공식 문서](https://prometheus.io/docs/introduction/overview/)
- [Grafana 공식 문서](https://grafana.com/docs/)
