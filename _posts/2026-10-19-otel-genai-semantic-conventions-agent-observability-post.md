---
layout: single
title: "\"왜 이런 답을 냈는지 알고 싶어요\" — OpenTelemetry GenAI 시맨틱 컨벤션으로 설계하는 에이전트 관측성"
date: 2026-10-19 12:50:00 +0530
categories: ai
tags: ["observability", "opentelemetry", "llm", "agent", "tracing", "mcp"]
toc: true
toc_sticky: true
excerpt: "에이전트가 왜 엉뚱한 답을 냈는지 추적하고 싶다는 요구를, 아직 Development 단계인 OpenTelemetry GenAI 시맨틱 컨벤션으로 지금 설계해도 되는지 판단 기준과 계측 순서로 정리했다."
---

## 도입

"에이전트가 가끔 엉뚱한 답을 내놓는데, 어느 단계에서 틀렸는지 좀 보여주세요." 이 요구는 생각보다 자주 온다. 단일 LLM 호출 시절에는 프롬프트와 응답 로그 한 줄이면 충분했다. 하지만 오케스트레이터가 서브에이전트를 부르고, 서브에이전트가 MCP 도구를 호출하고, 그 도구가 또 다른 API를 때리는 구조에서는 "로그 한 줄"이 통하지 않는다. 느려진 구간이 모델 추론인지, 도구 호출 네트워크인지, 벡터 검색인지조차 구분이 안 되면 디버깅은 추측 게임이 된다.

그동안 이 문제는 Langfuse, Arize, Braintrust 같은 LLM 전용 관측성 제품이 각자의 SDK로 메워왔다. 문제는 제품마다 스팬 이름과 속성 이름이 달라서, 벤더를 바꾸거나 두 제품을 동시에 붙이면 계측 코드를 다시 짜야 한다는 점이다. 이 파편화를 표준화하려는 시도가 OpenTelemetry(OTel)의 GenAI 시맨틱 컨벤션이다. 2026년 들어 범위가 단순 LLM 호출 계측을 넘어 에이전트 오케스트레이션, MCP 도구 호출, 검색(retrieval), 평가(evaluation)까지 확장됐고, Datadog·Grafana 같은 범용 백엔드와 LangGraph·CrewAI 같은 프레임워크가 네이티브 지원을 붙이기 시작했다. 다만 아직 공식 저장소 상태는 "Development"이고 확정 릴리스가 나오지 않았다는 점은 지금 도입을 판단하는 데 중요한 변수다.

## 핵심 개념: 무엇을 어떤 이름으로 기록하는가

GenAI 시맨틱 컨벤션은 세 가지 신호(스팬·메트릭·이벤트)를 `gen_ai.` 네임스페이스 아래 정의한다. 핵심은 "모델 호출 한 번"이 아니라 "에이전트 실행 전체"를 계층 구조로 기록하는 것이다.

| 계층 | 스팬 예시 | 주요 속성 |
|---|---|---|
| 에이전트 실행 전체 | `invoke_agent` | `gen_ai.agent.name`, `gen_ai.conversation.id` |
| 모델 호출 | `chat claude-sonnet-5` | `gen_ai.request.model`, `gen_ai.usage.input_tokens` |
| 도구 호출 | `execute_tool` | `gen_ai.tool.name`, `gen_ai.tool.call.id` |
| 검색 | `embeddings`, `retrieve` | `gen_ai.operation.name` |

여러 에이전트에 걸친 호출은 W3C Trace Context의 `traceparent` 헤더로 전파(propagation)된다. 오케스트레이터가 만든 trace ID를 서브에이전트, 그 서브에이전트가 부르는 MCP 서버, 그 서버가 때리는 외부 API까지 그대로 들고 다니면, 백엔드 UI에서 전체 실행을 하나의 트리로 펼쳐볼 수 있다. 아래 그림은 이 흐름을 단순화한 것이다.

<img src="/assets/images/posts/2026-10-19-otel-genai-semantic-conventions-agent-observability-1.svg" alt="오케스트레이터부터 OTel SDK, Collector, 백엔드까지 gen_ai 스팬이 흐르는 구조도" style="width:100%;">

기존 애플리케이션 트레이싱(APM)과 메커니즘 자체가 다른 건 아니다. 다른 점은 "토큰 수", "모델명", "도구 인자"처럼 LLM 고유의 속성 이름이 표준화됐다는 것뿐이다.

## 트레이드오프: 지금 OTel 컨벤션에 올라타야 하는가

| 선택지 | 장점 | 단점 |
|---|---|---|
| OTel GenAI 컨벤션 | 벤더 중립, 백엔드 교체 자유, 생태계 지원 확산 중 | 스펙 미확정 — 속성 이름이 바뀔 수 있음 |
| 벤더 전용 SDK (Langfuse 등) | 당장 완성도 높은 UI, 평가·데이터셋 기능까지 포함 | 벤더 락인, 멀티에이전트 간 trace 연동이 제품 경계에서 끊길 수 있음 |
| 자체 로깅 | 완전한 커스터마이징 | 팀마다 속성 이름이 달라져 장기적으로 또 다른 파편화를 만듦 |

판단 기준은 단순하다. 지금 당장 상세한 평가 UI와 데이터셋 관리가 급하면 벤더 SDK로 빠르게 가고, 여러 모델 제공자와 여러 프레임워크를 오래 쓸 조직이라면 OTel 컨벤션 위에서 계측하되 백엔드만 벤더 제품으로 꽂는 구조를 권한다. 스펙이 아직 Development 단계이므로, 속성 이름이 바뀌는 것에 대비해 계측 코드와 비즈니스 로직 사이에 얇은 래퍼를 하나 두는 것이 안전하다.

## 실무 진행 순서

1. **모델 호출부터 계측한다.** 오케스트레이터가 직접 LLM API를 부르는 지점에 `chat` 스팬을 붙이고 토큰 사용량 속성부터 채운다. 여기서부터 비용 추적이 바로 가능해진다.
2. **도구 호출을 추가한다.** MCP 도구나 함수 호출 지점에 `execute_tool` 스팬을 붙이고 `gen_ai.tool.call.id`를 기록해, 모델이 어떤 도구를 어떤 인자로 불렀는지 남긴다.
3. **trace context를 서브에이전트 경계까지 전파한다.** 오케스트레이터 → 서브에이전트 → MCP 서버로 넘어갈 때 `traceparent`를 HTTP 헤더나 호출 인자에 실어 보낸다. 이 단계를 건너뛰면 "에이전트별로 끊긴 트레이스"만 남아 디버깅 가치가 크게 떨어진다.
4. **백엔드를 연결한다.** Collector를 하나 세우고 Datadog·Grafana·자체 Jaeger 중 하나로 내보낸다. 여기서부터 전체 실행을 트리로 보기 시작할 수 있다.
5. **알림을 설계한다.** 토큰 사용량 급증, 특정 도구 호출 실패율, 평균 스팬 지연 같은 메트릭에 임계값을 걸어 사후 분석이 아니라 사전 감지로 넘어간다.

예제(Python, OpenTelemetry SDK로 모델 호출 스팬 계측):

```python
from opentelemetry import trace

tracer = trace.get_tracer("my-agent")

def call_model(prompt, model="claude-sonnet-5"):
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.operation.name", "chat")
        response = llm_client.chat(prompt, model=model)
        span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)
        return response
```

## 실무 포인트

- 멀티에이전트 구조에서는 스팬 개수가 금방 수천 개로 불어난다. 샘플링 전략(에러가 난 trace는 100% 보존, 정상 trace는 비율 샘플링)을 처음부터 설계에 넣어야 비용이 터지지 않는다.
- 프롬프트·응답 전체를 속성에 그대로 담으면 PII가 트레이스 백엔드에 그대로 노출된다. 컨벤션은 "content capture"를 별도 옵트인으로 분리해 두었으니, 민감 데이터는 기본적으로 끄고 필요한 구간만 켜는 것이 안전하다.
- 프레임워크(LangGraph, CrewAI 등)가 자체적으로 일부 계측을 제공하기 시작했지만 버전마다 지원 범위가 다르다. 자동 계측에만 의존하지 말고 핵심 비즈니스 경로는 수동으로 스팬을 추가해 빠지는 구간이 없는지 확인한다.

## 마무리

- 멀티에이전트·멀티도구 구조에서 "느린 구간, 틀린 구간"을 찾는 문제는 로그 한 줄이 아니라 트레이스 트리로만 풀린다.
- OTel GenAI 컨벤션은 아직 미확정 스펙이지만, 벤더 중립성과 생태계 확산 속도를 보면 장기 투자 가치가 있다 — 단, 속성 이름 변경에 대비한 래퍼는 필수다.
- 모델 호출 → 도구 호출 → trace propagation → 백엔드 연결 → 알림 순서로 계측 범위를 넓혀가는 것이 가장 리스크가 적은 진행 방식이다.

## 참고 자료

- [OpenTelemetry Semantic Conventions (GitHub)](https://github.com/open-telemetry/semantic-conventions)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
