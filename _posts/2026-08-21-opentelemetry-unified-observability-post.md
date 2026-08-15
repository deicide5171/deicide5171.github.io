---
layout: single
title: "OpenTelemetry로 통합 관측성 구축하기 — 메트릭·로그·트레이스 한 곳에서"
date: 2026-08-21 13:40:00 +0530
categories: infra
tags: ["infra", "opentelemetry", "observability", "tracing", "metrics", "monitoring"]
toc: true
toc_sticky: true
excerpt: "벤더마다 제각각이던 계측 SDK 대신, 메트릭·로그·트레이스를 하나의 표준으로 수집하는 OpenTelemetry의 아키텍처와 도입 전략을 정리한다."
---

마이크로서비스 개수가 늘어날수록 관측성(observability) 스택은 조용히 복잡해진다. 어떤 팀은 APM 벤더의 자체 에이전트를 붙이고, 다른 팀은 Prometheus 클라이언트 라이브러리를 직접 초기화하고, 또 다른 팀은 로그 포워더에 벤더 전용 필드를 심어 넣는다. 처음에는 서비스 몇 개 수준에서 큰 문제가 되지 않지만, 서비스가 수십 개로 늘어나면 계측 코드 자체가 벤더에 종속되어 버린다. 벤더를 교체하려면 애플리케이션 코드를 다시 손봐야 하는 상황이 벌어진다.

더 근본적인 문제는 트레이스, 메트릭, 로그가 서로 다른 도구와 데이터 모델로 수집되다 보니 하나의 요청이 겪은 문제를 추적할 때 세 가지 화면을 오가며 수동으로 상관관계를 맞춰야 한다는 점이다. 트레이스 ID를 로그에서 검색하고, 그 시간대의 메트릭을 다시 대시보드에서 찾는 식이다. 이 단절은 장애 대응 시간을 늘리는 직접적인 원인이 된다.

OpenTelemetry(OTel)는 이 문제를 계측 표준화로 풀어보려는 CNCF 프로젝트다. 벤더 중립적인 API와 SDK, 그리고 데이터를 수집·가공·전달하는 Collector를 통해 트레이스·메트릭·로그를 하나의 파이프라인에서 다루도록 한다. 이 글에서는 OTel의 핵심 아키텍처와 실무 도입 시 고려할 점을 정리한다.

## 핵심 개념 1: 3대 시그널 — 트레이스, 메트릭, 로그

OpenTelemetry는 관측성을 구성하는 세 가지 데이터 유형을 시그널(signal)이라 부르고, 이들을 공통 스펙 아래 통합한다.

- **트레이스(traces)**: 하나의 요청이 여러 서비스를 거치는 과정을 스팬(span)의 트리 구조로 기록한다. 각 스팬은 시작·종료 시각, 상위 스팬과의 관계, 속성(attribute)을 가진다.
- **메트릭(metrics)**: 카운터, 게이지, 히스토그램 등 시계열 수치 데이터다. 요청 수, 지연시간 분포, 에러율처럼 집계된 지표를 다룬다.
- **로그(logs)**: 특정 시점에 발생한 이벤트를 텍스트나 구조화된 필드로 남긴다. OTel은 기존 로그 포맷을 트레이스 컨텍스트(trace ID, span ID)와 연결하는 방식을 제공한다.

세 시그널이 같은 리소스(resource) 개념과 컨텍스트 전파(context propagation) 메커니즘을 공유한다는 점이 핵심이다. 트레이스 ID가 로그에 자동으로 삽입되면, 특정 로그 라인에서 곧바로 해당 요청의 전체 트레이스로 이동할 수 있다. 이 상관관계가 벤더별 도구를 따로 쓸 때는 얻기 어려운 부분이다.

## 핵심 개념 2: Collector 아키텍처 — 수집·처리·내보내기

OpenTelemetry Collector는 애플리케이션과 백엔드 사이에 위치하는 독립 프로세스로, 파이프라인을 세 단계로 구성한다.

1. **Receivers(수신기)**: OTLP(OpenTelemetry Protocol)뿐 아니라 Jaeger, Zipkin, Prometheus 등 기존 포맷도 받아들일 수 있다.
2. **Processors(처리기)**: 배치 묶음(batch), 속성 필터링, 리샘플링, 민감 정보 마스킹 등을 수행한다.
3. **Exporters(내보내기)**: 처리된 데이터를 각 백엔드(Jaeger, Tempo, Prometheus, Loki, 상용 APM 등)가 이해하는 형식으로 변환해 전송한다.

이 구조 덕분에 애플리케이션은 OTLP라는 단일 프로토콜로만 데이터를 보내면 되고, 백엔드를 교체하거나 추가할 때는 Collector 설정만 바꾸면 된다. Collector는 사이드카, 데몬셋, 게이트웨이 등 다양한 배포 형태를 지원하며, 대규모 환경에서는 에이전트 계층(각 노드)과 게이트웨이 계층(중앙 집계)을 나누어 두는 구성이 흔히 쓰인다.

<img src="/assets/images/posts/2026-08-21-opentelemetry-unified-observability-1.svg" alt="OpenTelemetry Collector 파이프라인 - 트레이스·메트릭·로그가 Receivers, Processors, Exporters를 거쳐 백엔드로 전달되는 흐름도" style="width:100%;">

## 핵심 개념 3: 자동 계측과 수동 계측의 차이

애플리케이션에 OTel을 도입하는 방식은 크게 둘로 나뉜다.

- **자동 계측(auto-instrumentation)**: 언어별 에이전트나 래퍼가 알려진 프레임워크(HTTP 서버, DB 드라이버, 메시지 큐 클라이언트 등)의 호출을 가로채 스팬과 메트릭을 자동 생성한다. 코드 변경 없이 빠르게 기본적인 관측성을 확보할 수 있지만, 비즈니스 로직 관점의 세부 정보는 담기지 않는다.
- **수동 계측(manual instrumentation)**: 개발자가 SDK를 직접 호출해 원하는 지점에 스팬을 열고 속성을 추가한다. 도메인 특화 정보(주문 ID, 결제 상태 등)를 담을 수 있지만, 계측 코드를 애플리케이션 전반에 퍼뜨려야 하는 부담이 있다.

실무에서는 자동 계측으로 기본 골격을 확보한 뒤, 핵심 비즈니스 흐름에만 수동 계측을 추가하는 하이브리드 방식이 흔히 쓰인다. 두 방식 모두 같은 SDK와 컨텍스트 전파 규칙을 따르기 때문에 함께 섞어 써도 트레이스가 끊기지 않는다.

## 예제

다음은 OTel Collector 설정 파일(otel-collector-config.yaml)의 단순화된 예시다.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 512
  tail_sampling:
    policies:
      - name: errors-policy
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: probabilistic-policy
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

exporters:
  otlp/tempo:
    endpoint: tempo:4317
  prometheusremotewrite:
    endpoint: http://prometheus:9090/api/v1/write
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, tail_sampling]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheusremotewrite]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki]
```

각 시그널(traces, metrics, logs)이 독립된 파이프라인으로 정의되고, 동일한 receiver를 공유하면서도 서로 다른 processor·exporter 조합을 가질 수 있다는 점이 특징이다. 여기서 `tail_sampling` processor는 에러가 발생한 트레이스는 전량 보존하고, 정상 트레이스는 일정 비율만 샘플링하는 정책을 보여준다.

## 실무 포인트

- **샘플링 전략**: 트래픽이 많은 서비스에서 모든 트레이스를 저장하면 스토리지 비용이 급격히 늘어난다. 헤드 샘플링(요청 시작 시점에 결정)은 구현이 단순하지만 에러 트레이스를 놓칠 수 있고, 테일 샘플링(전체 트레이스를 본 뒤 결정)은 에러나 지연이 큰 요청을 우선 보존할 수 있는 대신 Collector에서 더 많은 메모리와 버퍼링이 필요하다.
- **카디널리티 폭발 주의**: 메트릭이나 스팬 속성에 사용자 ID, 요청 경로의 동적 세그먼트처럼 값의 종류가 무한히 늘어나는 필드를 라벨로 붙이면, 백엔드의 시계열 개수(카디널리티)가 통제 불가능하게 늘어나 조회 성능과 비용에 악영향을 준다. 속성으로 남기고 싶은 정보는 라벨보다는 스팬 속성이나 exemplar 형태로 다루는 편이 안전하다.
- **Collector 자체의 가용성**: Collector가 단일 장애점이 되지 않도록 게이트웨이 계층은 다중 인스턴스로 구성하고, 큐 적재나 재시도 설정을 통해 백엔드 장애 시 데이터 유실을 최소화하는 것이 좋다.
- **점진적 마이그레이션**: 기존 벤더 SDK를 한 번에 걷어내기보다, OTLP를 지원하는 Collector receiver로 기존 포맷(Jaeger, Zipkin 등)을 우선 수용하면서 서비스 단위로 순차 전환하는 편이 위험을 줄인다.

## 3줄 요약

- 벤더별 계측 SDK가 뒤섞이면 벤더 종속과 트레이스·메트릭·로그 간 상관관계 부재라는 두 가지 문제가 생기며, OpenTelemetry는 이를 표준 API·SDK와 공통 컨텍스트 전파로 해결한다.
- Collector는 Receivers → Processors → Exporters 파이프라인으로 동작하며, 애플리케이션은 OTLP 하나만 알면 되고 백엔드 교체는 설정 변경만으로 가능하다.
- 자동 계측으로 기본 골격을 빠르게 확보하고 핵심 흐름에 수동 계측을 더하되, 샘플링 전략과 카디널리티 관리를 도입 초기부터 함께 설계해야 한다.

## 참고 자료

- [OpenTelemetry 공식 문서 — What is OpenTelemetry?](https://opentelemetry.io/docs/what-is-opentelemetry/)
- [OpenTelemetry Collector 문서](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Sampling 가이드](https://opentelemetry.io/docs/concepts/sampling/)
