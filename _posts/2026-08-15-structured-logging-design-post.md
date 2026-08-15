---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — 로그 설계와 구조화 로깅"
date: 2026-08-15 20:10:00 +0530
categories: dev-insight
tags: ["구조화로깅", "로그설계", "트레이스ID", "추천지식"]
toc: true
toc_sticky: true
excerpt: "분산 시스템과 옵저버빌리티를 다뤄봤다면, 다음 학습 주제로 로그 자체의 설계를 추천한다."
---

## 이 블로그가 걸어온 길, 그리고 다음 걸음

지금까지 이 블로그에서는 API Gateway와 서비스 메시, 멀티리전 액티브-액티브, 사가 패턴, 서킷 브레이커, 레이트 리밋, 옵저버빌리티 등 분산 시스템을 안정적으로 운영하기 위한 여러 주제를 다뤄왔다. 이런 패턴들의 공통점은 결국 "장애가 났을 때 무슨 일이 있었는지 알 수 있어야 한다"는 전제 위에 서 있다는 점이다. 그런데 정작 그 정보를 만들어내는 가장 기본적인 도구, 즉 로그 자체를 어떻게 설계할지는 상대적으로 덜 다뤄진 주제였다.

옵저버빌리티라는 큰 우산 아래에는 로그, 메트릭, 트레이스라는 세 축이 있고, 이 블로그도 그 전체 그림을 다룬 적은 있지만, 로그 그 자체의 형식과 레벨 전략, 요청 추적을 위한 상관관계 ID 설계 같은 실무적인 디테일은 별도로 짚어볼 가치가 있다. 그래서 이번 회차에서는 옵저버빌리티 전반이 아니라 "로그 한 줄을 어떻게 잘 남길 것인가"에 좁게 집중해 다음 학습 주제로 제안한다.

## 왜 로그 설계를 다음 주제로 추천하는가

| 이미 다룬 주제 | 로그 설계와의 연결점 |
|---|---|
| 서킷 브레이커, 레이트 리밋 | 이 패턴들이 언제 발동했는지는 결국 로그로 확인한다 |
| 사가 패턴, 멀티리전 액티브-액티브 | 여러 서비스에 걸친 트랜잭션 흐름 추적에 상관관계 ID가 필수 |
| 옵저버빌리티 전반 | 로그는 메트릭·트레이스와 함께 옵저버빌리티의 한 축이지만, 형식 설계는 별도 스킬 |
| API Gateway | 게이트웨이에서 발급한 요청 ID를 하위 서비스까지 전파하는 것이 로그 추적의 출발점 |

이미 여러 분산 시스템 패턴을 익혔다면, 그 패턴들이 실제로 문제 없이 작동하는지 확인할 도구인 로그를 제대로 설계하는 법을 익히는 것이 자연스러운 다음 단계로 보인다.

## 핵심 개념

**구조화 로깅(structured logging)**: 로그를 사람이 읽기 좋은 자유 텍스트가 아니라 JSON 같은 기계가 파싱하기 쉬운 형식으로 남기는 방식이다. 필드 이름을 일관되게 유지하면 로그 수집/검색 시스템에서 필터링과 집계가 훨씬 쉬워진다.

**로그 레벨 전략**: DEBUG, INFO, WARN, ERROR 같은 레벨을 어떤 기준으로 나눌지 팀 차원에서 합의해두지 않으면, 운영 환경에서 ERROR 로그가 너무 많아 정작 중요한 알림이 묻히거나, 반대로 필요한 정보가 DEBUG 레벨에 숨어 조회되지 않는 문제가 생긴다.

**상관관계 ID / 트레이스 ID**: 하나의 사용자 요청이 여러 서비스를 거치는 분산 환경에서, 요청 전체를 하나로 묶어 추적할 수 있게 해주는 식별자다. 요청이 처음 들어오는 지점(API Gateway 등)에서 발급하고, 이후 모든 서비스 호출과 로그에 이 값을 함께 남기는 것이 기본 원칙이다. 이 개념은 W3C Trace Context 같은 표준에서 더 formal하게 다뤄지지만, 옵저버빌리티 도구 도입 여부와 무관하게 로그 필드 설계 차원에서 먼저 적용할 수 있다.

## 예제

```json
{
  "timestamp": "2026-08-15T09:12:33.482Z",
  "level": "ERROR",
  "service": "order-service",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "message": "결제 처리 중 타임아웃 발생",
  "order_id": "ORD-20260815-0093",
  "duration_ms": 3021,
  "error_code": "PAYMENT_TIMEOUT"
}
```

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "service": "order-service",
        }
        return json.dumps(payload, ensure_ascii=False)

logger = logging.getLogger("order-service")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
```

## 실무 포인트와 주의사항

- 로그 필드 스키마를 팀 차원에서 정하고 문서화해두면, 이후 로그 수집 시스템을 무엇으로 바꾸든 일관성을 유지하기 쉽다.
- 상관관계 ID는 요청 진입점에서 반드시 생성하고, 이후 모든 서비스 호출(HTTP 헤더, 메시지 큐 메타데이터 등)에 전파되도록 강제해야 한다. 한 곳이라도 전파가 끊기면 추적이 단절된다.
- 개인정보나 민감정보를 로그에 그대로 남기지 않도록 필드 단위로 마스킹 규칙을 정해두는 것이 좋다.
- 로그 레벨은 "운영 중 알림이 필요한가"를 기준으로 정하는 것이 실용적이다. 단순 정보성 메시지까지 ERROR로 남기면 알림 피로도가 커진다.

## 3줄 요약

- 구조화 로깅은 로그를 기계가 파싱하기 쉬운 형식으로 남겨 검색과 집계를 쉽게 만드는 방식이다.
- 상관관계 ID/트레이스 ID는 분산 환경에서 하나의 요청 흐름을 끝까지 추적하는 핵심 도구다.
- 로그 레벨 전략과 필드 스키마를 팀 차원에서 미리 합의해두는 것이 장기적으로 유지보수 비용을 줄인다.

## 참고 자료

- [OpenTelemetry Logs 개념 문서](https://opentelemetry.io/docs/concepts/signals/logs/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [RFC 5424 - The Syslog Protocol](https://datatracker.ietf.org/doc/html/rfc5424)
