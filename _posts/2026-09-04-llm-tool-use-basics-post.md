---
layout: single
title: "LLM 도구 호출(tool use)이 뭔가요 — AI가 함수를 부르는 원리"
date: 2026-09-04 13:50:00 +0530
categories: ai
tags: ["tool use", "function calling", "llm", "ai에이전트", "입문"]
toc: true
toc_sticky: true
excerpt: "LLM이 스스로 함수를 호출해 실시간 정보를 가져오거나 작업을 수행하는 도구 호출(tool use)의 동작 원리를 처음 배우는 사람 기준으로 정리했다."
---

## LLM은 왜 도구가 필요한가

LLM은 학습된 지식으로 텍스트를 생성할 뿐, "지금 날씨"나 "내 DB의 주문 데이터" 같은 실시간·외부 정보는 알지 못한다. **도구 호출(tool use, function calling)**은 이 한계를 넘는 방법이다. 개발자가 사용할 수 있는 함수 목록을 LLM에게 알려주면, LLM이 필요할 때 "이 함수를 이 인자로 불러주세요"라고 요청하고, 개발자 코드가 실제로 함수를 실행해 결과를 다시 LLM에게 준다.

## 동작 흐름

```text
1. 개발자가 사용 가능한 도구(함수) 목록과 각 인자 형식을 LLM에게 전달
2. 사용자가 "서울 날씨 알려줘"라고 질문
3. LLM이 "get_weather 함수를 city=서울로 호출해줘"라고 응답 (직접 실행하지 않음)
4. 개발자 코드가 실제로 get_weather("서울")을 실행 -> 결과 획득
5. 그 결과를 LLM에게 다시 전달
6. LLM이 결과를 바탕으로 자연스러운 문장으로 최종 답변 생성
```

핵심은 **LLM이 함수를 직접 실행하는 게 아니라, "이걸 실행해달라"고 요청만 한다**는 것이다. 실제 실행은 개발자 코드가 하고, 그 결과를 다시 넣어줘야 대화가 이어진다.

## 코드 예제

```python
tools = [{
    "name": "get_weather",
    "description": "도시의 현재 날씨를 조회한다",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}]

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "서울 날씨 알려줘"}],
)

# 모델이 도구 호출을 원하면 stop_reason이 tool_use
if response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")
    result = get_weather(tool_call.input["city"])  # 실제 함수 실행은 내 코드가
    # result를 tool_result로 다시 넣어 대화를 이어간다
```

## 실무 포인트

- **도구의 `description`을 명확하게 쓰는 것이 성능에 직결된다.** LLM은 이 설명만 보고 언제 어떤 도구를 쓸지 판단하므로, "무엇을 하는 함수인지, 언제 써야 하는지"를 구체적으로 적어야 엉뚱한 호출을 줄일 수 있다.
- **도구 실행 결과가 틀리거나 위험할 수 있는 작업은 사람 확인을 거쳐야 한다.** 예를 들어 "데이터 삭제" 같은 도구를 LLM이 자동으로 실행하게 두면 위험하므로, 실행 전 승인 단계를 두는 것이 안전하다.
- **이것이 바로 AI 에이전트의 기본 뼈대다.** 여러 도구를 주고 LLM이 스스로 어떤 도구를 언제 쓸지 판단하며 작업을 수행하게 하면, 그것이 곧 에이전트가 된다.

## 마무리 요약

- 도구 호출은 LLM이 실시간·외부 정보에 접근하거나 작업을 수행하게 해주는 메커니즘이다.
- LLM은 함수를 직접 실행하지 않고 "실행해달라"고 요청만 하며, 실제 실행과 결과 전달은 개발자 코드의 몫이다.
- 도구 설명을 명확히 쓰고, 위험한 작업에는 사람 승인 단계를 두는 것이 안전한 설계다.

## 참고 자료

- [Anthropic - Tool use 가이드](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview)
- [OpenAI - Function calling](https://platform.openai.com/docs/guides/function-calling)
