---
layout: single
title: "레이블 하나 잘못 붙였다가 Prometheus가 죽는다 — 메트릭 카디널리티 관리"
date: 2026-08-26 13:40:00 +0530
categories: infra
tags: ["infra", "prometheus", "cardinality", "monitoring", "observability", "metrics"]
toc: true
toc_sticky: true
excerpt: "user_id를 레이블로 넣는 순간 Prometheus의 메모리가 폭증한다. 카디널리티가 폭발하는 원인과, 이를 미리 탐지·차단하는 실전 방법을 정리한다."
---

Prometheus 운영 중 가장 흔한 장애 원인 중 하나는 디스크도 CPU도 아니라 **카디널리티 폭발(cardinality explosion)**이다. 메트릭에 레이블을 하나 추가하는 것은 코드 한 줄로 끝나는 작업처럼 보이지만, 그 레이블의 가능한 값이 수천~수백만 개라면 Prometheus는 그 조합의 수만큼 새로운 시계열(time series)을 메모리에 만든다. `http_requests_total{status="200", user_id="12345"}` 같은 메트릭을 사용자 수만큼 만들어 버리면, 메트릭 하나가 수백만 개의 시계열로 폭증해 Prometheus 프로세스가 OOM으로 죽는다.

이 문제가 특히 무서운 이유는 장애가 즉시 나타나지 않는다는 데 있다. 개발 환경에서 사용자 수가 적을 때는 레이블에 `user_id`를 넣어도 아무 문제가 없다가, 프로덕션에서 사용자가 늘어나면서 서서히 메모리 사용량이 올라가고, 어느 시점에 갑자기 스크레이프가 느려지거나 프로세스가 재시작된다. 이 글에서는 카디널리티가 왜 문제가 되는지, 어떻게 사전에 탐지하는지, 실무에서 어떤 레이블 설계 원칙을 지켜야 하는지 정리한다.

## 핵심 개념 1: 시계열 수는 레이블 값의 곱으로 늘어난다

Prometheus의 시계열은 메트릭 이름과 레이블 값 조합으로 식별된다. 레이블이 여러 개면 시계열 수는 각 레이블의 고유값 개수를 곱한 만큼 늘어난다.

| 메트릭 설계 | 레이블 | 예상 시계열 수 |
|---|---|---|
| `http_requests_total{method, status}` | method(5) × status(10) | 50 |
| `http_requests_total{method, status, endpoint}` | 위 + endpoint(200) | 10,000 |
| `http_requests_total{method, status, endpoint, user_id}` | 위 + user_id(100만) | 100억 (사실상 폭발) |

`method`나 `status`처럼 값의 종류가 유한하고 적은 레이블은 안전하지만, `user_id`, `request_id`, `session_id`, IP 주소처럼 사실상 무한히 늘어나는 값을 레이블로 쓰면 시계열 수가 통제 불능이 된다. 이런 값은 로그나 트레이스에는 넣어도 되지만, 메트릭 레이블로는 절대 넣으면 안 된다는 것이 Prometheus 운영의 기본 원칙이다.

## 핵심 개념 2: 카디널리티는 사전에 측정 가능하다

카디널리티 문제는 사고 나고 나서 알아차리는 게 아니라 사전에 측정해야 한다. Prometheus는 자체적으로 `prometheus_tsdb_head_series`(현재 활성 시계열 수)와 각 메트릭별 시계열 수를 노출하므로, 이를 대시보드로 만들어 특정 메트릭이 비정상적으로 늘어나는지 상시 감시할 수 있다.

```promql
# 메트릭 이름별 시계열 수를 내림차순으로 확인 — 카디널리티 상위 메트릭 찾기
topk(10, count by (__name__)({__name__=~".+"}))

# 특정 메트릭의 레이블 조합이 얼마나 다양한지 확인
count(count by (endpoint, status) (http_requests_total))
```

`prometheus_tsdb_head_series` 값이 시간이 지날수록 완만히 우상향하는 것은 정상(신규 배포, 신규 엔드포인트 추가)이지만, 특정 배포 직후 계단식으로 급증한다면 그 배포에서 추가된 레이블을 의심해야 한다. 배포 파이프라인에 카디널리티 증가율 체크를 넣어 임계치를 넘으면 배포를 막는 방식도 실무에서 쓰인다.

## 실무 포인트

- **무한 카디널리티 값은 메트릭이 아니라 로그/트레이스로 보낸다**: "이 요청이 어떤 사용자가 보냈는지" 같은 정보는 메트릭 레이블이 아니라 구조화 로그나 분산 트레이싱(예: OpenTelemetry span 속성)에 넣는다. 메트릭은 "얼마나 많이, 얼마나 자주"를 집계하는 용도이고, 개별 요청을 추적하는 용도가 아니다.
- **레이블 추가는 코드 리뷰 체크리스트에 넣는다**: `Counter`나 `Histogram`에 새 레이블을 추가하는 PR은 "이 레이블의 가능한 값 개수가 유한하고 작은가?"를 명시적으로 확인하는 리뷰 항목을 둔다. 특히 사용자 입력값을 그대로 레이블에 쓰는 패턴(URL 경로 전체를 레이블로 쓰는 실수 등)을 주의 깊게 본다.
- **`relabel_configs`로 스크레이프 단계에서 방어선을 하나 더 둔다**: 애플리케이션 코드 리뷰만으로 모든 실수를 막을 수는 없다. Prometheus의 `metric_relabel_configs`에서 알려진 고위험 레이블(예: 실수로 들어간 UUID 패턴)을 드롭하는 규칙을 추가해 마지막 방어선을 마련할 수 있다.

## 3줄 요약

- Prometheus 시계열 수는 레이블 값의 곱으로 늘어나므로, 값의 종류가 무한한 레이블(user_id, request_id 등) 하나가 카디널리티 폭발을 일으킬 수 있다.
- `prometheus_tsdb_head_series`와 메트릭별 시계열 수를 상시 모니터링해 배포 직후 급증을 사전에 탐지해야 한다.
- 무한 카디널리티 값은 메트릭이 아니라 로그·트레이스로 보내고, 레이블 추가는 코드 리뷰와 relabel_configs로 이중 방어해야 한다.

## 참고 자료

- [Prometheus 공식 문서: Instrumentation Best Practices](https://prometheus.io/docs/practices/instrumentation/#do-not-overuse-labels)
- [Grafana Labs: Cardinality is key](https://grafana.com/blog/2022/10/20/how-to-manage-high-cardinality-metrics-in-prometheus-and-kubernetes/)
- [Prometheus 공식 문서: relabel_config](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config)
