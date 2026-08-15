---
layout: single
title: "프롬프트로 JSON 구걸하지 않기 — LLM 함수 호출과 구조화 출력 설계"
date: 2026-08-18 12:50:00 +0530
categories: ai
tags: ["llm", "tool-use", "function-calling", "json-schema", "structured-output"]
toc: true
toc_sticky: true
excerpt: "자유 텍스트 파싱 대신 JSON Schema로 LLM 응답을 강제하는 Tool Use와 구조화 출력 설계 방법을 정리한다."
---

## 왜 지금 함수 호출과 구조화 출력인가

RAG든 에이전트든, LLM을 실제 시스템에 연결하는 지점에는 항상 같은 문제가 있다. 모델이 자유 텍스트로 뱉어낸 답을 코드가 다시 파싱해야 한다는 점이다. "다음 형식으로만 답하라"고 프롬프트에 적어두고 정규식으로 JSON을 뽑아내는 구조는 프로토타입 단계에서는 버티지만, 모델이 설명을 한 줄 덧붙이거나 따옴표 escape 방식을 살짝 다르게 쓰는 것만으로도 쉽게 깨진다.

이 문제는 프롬프트를 더 정교하게 쓴다고 해결되지 않는다. API 차원에서 응답 형식을 강제하는 기능 — 함수 호출(Tool Use)과 구조화 출력(Structured Outputs) — 이 정확히 이 문제를 풀기 위해 만들어졌다. 모델이 형식을 최대한 지키려 노력하는 것과, API가 스키마를 검증해 그 형식이 아니면 아예 응답을 내보내지 않는 것은 신뢰성 면에서 전혀 다른 이야기다.

## 핵심 개념 1: 함수 호출(Tool Use)이 실제로 하는 일

가장 먼저 정정해야 할 오해는 "모델이 함수를 실행한다"는 것이다. 모델은 함수를 실행하지 않는다. 어떤 함수를 어떤 인자로 호출하고 싶은지를 JSON으로 서술한 `tool_use` 블록을 반환할 뿐이고, 함수를 실제로 실행하는 주체는 항상 호출하는 쪽(클라이언트) 코드다.

요청에 `tools` 배열로 함수의 이름·설명·입력 스키마를 전달하면, 모델은 응답의 `stop_reason`을 `end_turn`(바로 텍스트 답변) 또는 `tool_use`(함수 호출 요청) 중 하나로 반환한다. `tool_use`인 경우 클라이언트가 해당 함수를 직접 실행하고 결과를 `tool_result` 블록으로 대화 기록에 추가해 다시 요청을 보낸다. 이 왕복은 모델이 `end_turn`으로 답할 때까지 반복된다.

<img src="/assets/images/posts/2026-08-18-tool-use-structured-output-1.svg" alt="LLM 함수 호출(Tool Use) 왕복 흐름 - 질문 전달부터 tool_use 판단, 클라이언트 실행, tool_result 반환까지의 루프" style="width:100%;">

## 핵심 개념 2: 구조화 출력의 두 가지 경로

"모델 출력을 데이터로 강제한다"는 목표에는 두 가지 API 경로가 있고, 용도가 다르다.

| 방식 | 무엇을 강제하나 | 언제 쓰나 | 한계 |
|---|---|---|---|
| 프롬프트 지시 + 정규식 파싱(구식) | 아무것도 강제하지 않음, 관례에 의존 | 레거시 코드에서만 | 형식 이탈 시 파싱 실패, 재시도 로직 필요 |
| Strict Tool Use (`strict: true`) | `tool_use.input`이 스키마와 정확히 일치 | 에이전트가 함수를 호출해야 할 때 | `input_schema`에 `additionalProperties: false`와 `required` 명시 필요 |
| 구조화 출력 (`output_config.format`) | 최종 텍스트 응답 자체가 JSON Schema를 따름 | 추출·분류처럼 답변 자체가 데이터일 때 | 인용(citations) 기능과 동시 사용 불가 등 몇 가지 제약 존재 |

핵심 차이는 이렇다. Strict Tool Use는 "모델이 도구를 호출하려는 의도"를 스키마에 맞추는 것이고, 구조화 출력은 "모델이 최종적으로 내놓는 답변" 자체를 스키마에 맞추는 것이다. 함수를 실제로 실행해야 하는 에이전트 워크플로우라면 전자, 텍스트에서 구조화된 데이터를 뽑아내기만 하면 되는 작업이라면 후자가 자연스럽다.

## 핵심 개념 3: 스키마 설계가 신뢰성을 좌우한다

Tool Use와 구조화 출력 모두, 안정적으로 동작하는지는 API 기능 자체보다 스키마와 설명을 얼마나 정확히 썼는지에 더 크게 좌우된다.

- **설명에 "언제 호출하는지"까지 담는다.** "날씨를 가져온다"보다 "현재 날씨를 물어볼 때 호출한다"처럼 트리거 조건을 명시하면 호출 정확도가 올라간다.
- **파라미터마다 설명을 붙인다.** 모델은 이름이 아니라 설명을 근거로 값을 채운다.
- **고정된 값 집합에는 `enum`을, 필수값·엄격 검증에는 `required`와 `additionalProperties: false`를 빠뜨리지 않는다.** 특히 strict 모드에서는 이 두 가지가 없으면 검증 자체가 느슨해진다.
- **도구 개수를 과도하게 늘리지 않는다.** 등록된 도구가 많아질수록 잘못된 도구를 고를 확률도 올라간다.

## 예제 1: Tool Use 왕복 루프 (Python)

```python
import json
import anthropic

client = anthropic.Anthropic()

tools = [{
    "name": "get_weather",
    "description": "사용자가 특정 도시의 현재 날씨를 물어볼 때 호출한다.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "도시 이름, 예: Seoul"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city", "unit"],
        "additionalProperties": False,
    },
}]

messages = [{"role": "user", "content": "서울 날씨 알려줘, 섭씨로"}]

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=tools,
    messages=messages,
)

# stop_reason이 tool_use일 때만 실행 루프를 돈다
while response.stop_reason == "tool_use":
    messages.append({"role": "assistant", "content": response.content})
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            # 실제 함수 실행은 항상 클라이언트 책임
            result = {"city": block.input["city"], "temp_c": 21}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    messages.append({"role": "user", "content": tool_results})
    response = client.messages.create(
        model="claude-opus-5", max_tokens=1024, tools=tools, messages=messages,
    )

print(next(b.text for b in response.content if b.type == "text"))
```

## 예제 2: 구조화 출력으로 텍스트 추출하기 (Python)

```python
import json
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "plan": {"type": "string", "enum": ["basic", "pro", "enterprise"]},
                },
                "required": ["name", "email", "plan"],
                "additionalProperties": False,
            },
        }
    },
    messages=[{
        "role": "user",
        "content": "김민수(minsu@example.com) 고객이 엔터프라이즈 플랜에 관심을 보였다.",
    }],
)

text = next(b.text for b in response.content if b.type == "text")
data = json.loads(text)  # 스키마를 따르므로 파싱 실패 걱정이 없다
print(data["plan"])  # "enterprise"
```

## 실무 포인트

- **JSON은 항상 파서로 읽는다.** `tool_use.input`이나 구조화 출력 결과의 이스케이프 방식은 모델마다 다를 수 있다. 문자열 비교나 정규식 대신 `json.loads`/`JSON.parse`로 파싱해야 한다.
- **여러 도구 호출은 한 번에 처리한다.** 한 응답에 `tool_use` 블록이 여러 개 올 수 있다. 각각 실행한 뒤 결과는 하나의 사용자 메시지에 모아 한 번에 반환한다 — 나눠서 보내면 이후 병렬 호출 자체를 덜 하게 되는 부작용이 있다.
- **실패한 도구 호출도 결과로 돌려준다.** 실행이 실패했다면 `is_error: true`와 에러 메시지를 `tool_result`로 반환해, 모델이 다른 방법을 시도하거나 상황을 설명하게 한다.
- **일부 기능은 동시에 쓸 수 없다.** 구조화 출력은 인용(citations) 같은 일부 기능과 함께 쓸 수 없는 등 제약이 있고, 모델별 지원 범위도 계속 바뀌므로 확정적인 수치 대신 공식 문서 기준으로 확인하는 습관이 안전하다.

## 3줄 요약

- LLM 출력을 시스템에 연결할 때는 프롬프트로 형식을 유도하는 대신, Tool Use와 구조화 출력으로 API 차원에서 형식을 강제하는 편이 훨씬 안정적이다.
- 함수를 실제로 실행해야 하면 Strict Tool Use, 답변 자체가 데이터면 `output_config.format` 기반 구조화 출력을 쓴다.
- 안정성은 기능 자체보다 `description`·`enum`·`required`·`additionalProperties: false`를 얼마나 정확히 채웠는지에 더 좌우된다.

## 참고 자료

- [Anthropic — Tool Use Overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Anthropic — Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [JSON Schema 공식 사이트](https://json-schema.org/)
