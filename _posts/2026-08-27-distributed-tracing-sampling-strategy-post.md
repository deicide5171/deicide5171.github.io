---
layout: single
title: "트레이스를 다 저장하면 망한다 — 분산 트레이싱 샘플링, 헤드 vs 테일"
date: 2026-08-27 12:40:00 +0530
categories: infra
tags: ["distributed-tracing", "opentelemetry", "sampling", "observability", "apm"]
toc: true
toc_sticky: true
excerpt: "마이크로서비스 트래픽이 커질수록 트레이스 전량 저장은 비용 폭탄이 된다. 헤드 샘플링과 테일 샘플링의 원리와 조합 전략을 정리한다."
---

마이크로서비스 하나가 초당 1만 건의 요청을 처리하고 요청 하나당 스팬이 평균 20개 생긴다면, 트레이스를 전부 저장하는 것만으로 초당 20만 스팬이 백엔드로 밀려든다. 대부분의 트레이싱 백엔드(Jaeger, Tempo, Datadog APM)는 이 규모를 감당하지 못하거나 감당하더라도 비용이 감당 안 될 만큼 커진다. 그래서 실무에서는 반드시 샘플링, 즉 트레이스의 일부만 골라 저장하는 정책이 필요하다.

문제는 "무엇을 남길 것인가"다. 무작위로 1%만 남기면 저장 비용은 줄지만, 하필 문제가 있던 그 요청이 표본에서 빠질 수 있다. 이 글에서는 이 딜레마를 다루는 두 가지 접근, 헤드 샘플링과 테일 샘플링을 비교하고 실무에서 어떻게 조합하는지 정리한다.

## 핵심 개념 1: 헤드 샘플링 — 시작할 때 결정한다

헤드 샘플링(head-based sampling)은 트레이스가 시작되는 순간, 즉 첫 번째 스팬이 생성될 때 이 트레이스를 저장할지 말지를 결정한다. 가장 흔한 방식은 확률적 샘플링(예: 10% 확률로 샘플링 플래그를 켬)이고, 이 결정은 트레이스 컨텍스트(trace flags)에 담겨 하위 서비스로 전파된다. 한번 결정되면 트레이스 전체에 적용되므로 구현이 단순하고, 결정을 위해 트레이스 전체를 메모리에 모아둘 필요가 없어 오버헤드가 거의 없다.

문제는 이 결정이 **트레이스의 결과(에러 여부, 지연시간)를 전혀 모르는 상태에서** 내려진다는 점이다. 전체 트래픽의 0.1%만 에러라면, 10% 확률 샘플링으로는 에러 트레이스 대부분을 놓친다. 정작 디버깅에 가장 필요한 "느렸던 요청", "실패한 요청"이 표본에 안 남을 확률이 높다.

## 핵심 개념 2: 테일 샘플링 — 결과를 보고 결정한다

테일 샘플링(tail-based sampling)은 트레이스의 모든 스팬이 도착할 때까지 기다렸다가, 트레이스가 완료된 시점에 "이 트레이스를 저장할 가치가 있는가"를 판단한다. 예를 들어 "에러가 하나라도 있으면 100% 저장", "지연시간이 P99를 넘으면 저장", "그 외에는 1%만 무작위 저장" 같은 정책 조합이 가능하다. OpenTelemetry Collector의 `tail_sampling` 프로세서가 이 역할을 한다.

대신 대가가 있다. 트레이스가 끝날 때까지 모든 스팬을 버퍼에 들고 있어야 하므로 메모리 사용량이 늘고, 분산된 여러 서비스의 스팬이 같은 Collector 인스턴스에 모이도록 라우팅해야 한다(트레이스 ID 기준 샤딩). 또한 판단을 내리기 전까지 익스포트를 미루므로 관측 지연이 늘어난다.

| 구분 | 헤드 샘플링 | 테일 샘플링 |
|---|---|---|
| 결정 시점 | 트레이스 시작 시 | 트레이스 완료 시 |
| 결정 기준 | 결과를 모름(확률적) | 에러/지연시간 등 실제 결과 |
| 오버헤드 | 거의 없음 | 버퍼링 메모리 + 관측 지연 |
| 에러 트레이스 포착율 | 낮음(확률에 종속) | 높음(정책으로 100% 가능) |
| 구현 복잡도 | 낮음 | 높음(트레이스 ID 라우팅 필요) |

<img src="/assets/images/posts/2026-08-27-distributed-tracing-sampling-strategy-1.svg" alt="헤드 샘플링은 트레이스 시작 시점에, 테일 샘플링은 모든 스팬 수집 후 완료 시점에 저장 여부를 결정하는 흐름 비교도" style="width:100%;">

## 예제: OpenTelemetry Collector 테일 샘플링 설정

```yaml
processors:
  tail_sampling:
    decision_wait: 10s          # 트레이스 완료를 기다리는 최대 시간
    num_traces: 100000          # 버퍼에 유지할 최대 트레이스 수
    policies:
      - name: errors-policy
        type: status_code
        status_code: { status_codes: [ERROR] }   # 에러는 100% 저장
      - name: slow-policy
        type: latency
        latency: { threshold_ms: 1000 }           # 1초 이상 지연도 100% 저장
      - name: baseline-sample
        type: probabilistic
        probabilistic: { sampling_percentage: 5 } # 나머지는 5%만 무작위 저장
```

이 설정은 "에러 또는 느린 요청은 전부 남기고, 정상 요청은 5%만 표본으로 남긴다"는 정책을 구현한다. 정책이 여러 개면 OR 조건으로 평가되어, 하나라도 만족하면 샘플링된다.

## 실무 포인트

- **헤드 샘플링을 먼저 앞단에 두고 테일 샘플링을 뒤에 조합한다**: 헤드 샘플링으로 트래픽을 애초에 10~20% 정도로 줄여 Collector 부하 자체를 낮추고, 그 위에서 테일 샘플링으로 "에러/지연은 100%, 나머지는 낮은 비율" 정책을 적용하는 2단계 구조가 실무에서 흔히 쓰인다.
- **트레이스 ID 기준 일관 샘플링(consistent sampling)을 놓치지 않는다**: 여러 서비스가 각자 확률적으로 결정하면 같은 트레이스의 스팬 일부만 남는 반쪽짜리 트레이스가 생긴다. 트레이스 ID를 해시해 결정하는 일관 샘플링을 써야 상위·하위 서비스가 같은 결정을 내린다.
- **`decision_wait`은 가장 긴 트레이스보다 여유 있게 잡는다**: 비동기 백그라운드 작업이 포함된 트레이스는 완료까지 수 초가 걸릴 수 있다. 이 값이 짧으면 아직 안 끝난 트레이스를 조기에 "미완성"으로 판단해 잘못 버릴 수 있다.

## 3줄 요약

- 헤드 샘플링은 결과를 모른 채 확률로 결정해 오버헤드가 적지만 에러/느린 트레이스를 놓치기 쉽다.
- 테일 샘플링은 완료된 트레이스의 실제 결과를 보고 결정해 에러·지연 트레이스를 확실히 남기지만 버퍼링 비용이 든다.
- 실무에서는 헤드 샘플링으로 전체 볼륨을 낮추고 테일 샘플링 정책으로 중요한 트레이스를 골라내는 조합이 표준적이다.

## 참고 자료

- [OpenTelemetry Collector: tailsamplingprocessor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor)
- [OpenTelemetry 공식 문서: Sampling](https://opentelemetry.io/docs/concepts/sampling/)
- [Google Dapper 논문: Large-Scale Distributed Systems Tracing Infrastructure](https://research.google/pubs/pub36356/)
