---
layout: single
title: "OpenTelemetry 분산 트레이싱 심화 — Context Propagation과 샘플링 전략"
date: 2026-09-24 12:40:00 +0530
categories: infra
tags: ["OpenTelemetry", "분산트레이싱", "ContextPropagation", "샘플링", "관측성"]
toc: true
toc_sticky: true
excerpt: "MSA 환경에서 트레이스가 서비스 경계를 넘을 때마다 끊기거나, 샘플링 설정을 잘못해 정작 필요한 에러 트레이스가 수집되지 않는 문제를 OpenTelemetry의 Context Propagation과 샘플링 전략 관점에서 정리했다."
---

## 왜 지금 트레이스 전파와 샘플링을 다시 봐야 하는가

분산 트레이싱을 도입하는 초기 단계에서는 SDK를 설치하고 대시보드에 트레이스가 뜨는 것만으로도 충분히 만족스럽다. 하지만 서비스 수가 늘어나고 트래픽이 커지면 두 가지 문제가 반드시 나타난다. 첫째, 서비스 A에서 시작된 요청이 큐를 거쳐 서비스 B로 넘어가는 순간 트레이스가 끊겨 별개의 트레이스 두 개로 보이는 문제다. 둘째, 모든 요청을 100% 수집하면 저장 비용과 오버헤드가 감당할 수 없는 수준으로 커지는데, 그렇다고 무작정 샘플링 비율을 낮추면 정작 디버깅에 필요한 에러나 느린 요청의 트레이스가 통째로 누락되는 문제다. 이 둘은 각각 Context Propagation과 샘플링 전략의 설계 문제이며, 둘 다 제대로 이해하지 못하면 관측성 도구를 도입해놓고도 정작 필요할 때 못 쓰는 상황에 빠진다.

## 핵심 개념 1 — Context Propagation이 트레이스 연속성을 만드는 방식

하나의 요청이 여러 서비스를 거칠 때 이를 하나의 트레이스로 묶어주는 것이 트레이스 컨텍스트(trace context)다. OpenTelemetry는 W3C Trace Context 표준을 따라 `traceparent`라는 HTTP 헤더에 trace ID, span ID, 샘플링 여부 플래그를 인코딩해 서비스 간에 전달한다. HTTP 호출에서는 이 헤더 전파가 비교적 직관적이지만, 메시지 큐(Kafka, RabbitMQ)나 비동기 배치 작업처럼 HTTP 헤더가 없는 경로에서는 개발자가 메시지 속성(property)이나 메타데이터에 트레이스 컨텍스트를 수동으로 실어 보내고, 수신 측에서 이를 명시적으로 추출(extract)해 컨텍스트를 이어받아야 한다. 이 수동 전파 지점을 놓치는 것이 실무에서 트레이스가 끊기는 가장 흔한 원인이다.

## 핵심 개념 2 — 샘플링 전략: 비율 기반에서 우선순위 기반으로

가장 단순한 샘플링은 head-based sampling으로, 요청이 시작되는 시점에 정해진 확률(예: 5%)로 트레이스를 수집할지 미리 결정한다. 구현이 간단하지만, 결정 시점에는 이 요청이 나중에 에러를 낼지 느려질지 알 수 없다는 근본적 한계가 있다. 이를 보완하는 것이 tail-based sampling이다. 요청이 완전히 끝난 뒤 실제 결과(에러 여부, 지연시간)를 보고 수집 여부를 결정하기 때문에, 에러나 느린 요청을 우선적으로 보존할 수 있다. 대신 모든 스팬을 일단 버퍼링해야 하므로 컬렉터 계층에 추가 인프라(OpenTelemetry Collector 등)가 필요하다.

| 샘플링 방식 | 결정 시점 | 장점 | 단점 |
|---|---|---|---|
| Head-based (확률 기반) | 요청 시작 시점 | 구현 단순, 오버헤드 적음 | 에러·이상 요청을 놓칠 수 있음 |
| Tail-based (결과 기반) | 요청 종료 후 | 에러·느린 요청 우선 보존 | 버퍼링 인프라 필요, 지연 발생 |
| 우선순위 기반 하이브리드 | 시작+종료 결합 | 균형 잡힌 수집 | 설정 복잡도 증가 |

## 예제 — 메시지 큐를 통한 수동 컨텍스트 전파 (Java)

```java
// 발행 측: 현재 컨텍스트를 메시지 헤더에 주입
TextMapPropagator propagator = GlobalOpenTelemetry.getPropagators()
    .getTextMapPropagator();

Map<String, String> headers = new HashMap<>();
propagator.inject(Context.current(), headers, (carrier, key, value) -> carrier.put(key, value));
kafkaMessage.headers().forEach((k, v) -> headers.put(k, v));
producer.send(new ProducerRecord<>(topic, key, value, toKafkaHeaders(headers)));

// 소비 측: 메시지 헤더에서 컨텍스트 추출 후 스팬 시작
Context extractedContext = propagator.extract(Context.current(), kafkaHeaders,
    (carrier, key) -> carrier.get(key));

try (Scope scope = extractedContext.makeCurrent()) {
    Span span = tracer.spanBuilder("process-order-message").startSpan();
    // 이후 로직은 원래 트레이스에 이어짐
    span.end();
}
```

## 실무 포인트

- **비동기 경계마다 전파 여부를 명시적으로 점검하라.** HTTP 클라이언트는 대부분 자동 계측 라이브러리가 헤더 전파를 대신해주지만, 메시지 큐·스케줄러·스레드풀 경계는 자동 계측이 커버하지 못하는 경우가 많아 직접 확인해야 한다.
- **초기에는 head-based로 시작하되 에러 트레이스는 별도 규칙으로 강제 수집하라.** 예를 들어 HTTP 상태 코드가 5xx이거나 지연시간이 임계치를 넘으면 샘플링 확률과 무관하게 100% 수집하는 규칙을 추가하면, tail-based 인프라 없이도 상당 부분의 이득을 얻을 수 있다.
- **샘플링 비율을 서비스별로 다르게 가져가라.** 트래픽이 많은 게이트웨이 서비스와 호출 빈도가 낮은 배치 서비스에 동일한 샘플링 비율을 적용하면 한쪽은 과도한 비용, 다른 쪽은 데이터 부족에 시달리게 된다.

## 마무리 요약

- Context Propagation은 HTTP 헤더 전파가 자동화된 경로와, 메시지 큐처럼 수동 전파가 필요한 경로를 구분해 관리해야 트레이스 연속성이 깨지지 않는다.
- Head-based 샘플링은 단순하지만 에러를 놓칠 수 있고, tail-based 샘플링은 정확하지만 버퍼링 인프라가 필요한 트레이드오프 관계다.
- 에러·고지연 요청에 대한 강제 수집 규칙을 추가하면 인프라 부담을 늘리지 않고도 샘플링 품질을 크게 개선할 수 있다.

## 참고 자료

- [OpenTelemetry - Context Propagation](https://opentelemetry.io/docs/concepts/context-propagation/)
- [OpenTelemetry - Sampling](https://opentelemetry.io/docs/concepts/sampling/)
