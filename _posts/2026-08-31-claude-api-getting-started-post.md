---
layout: single
title: "Claude API 처음 써보기 — 메시지·스트리밍·도구 호출 5분 만에 끝내기"
date: 2026-08-31 12:50:00 +0530
categories: ai
tags: ["claude", "api", "llm", "튜토리얼", "입문"]
toc: true
toc_sticky: true
excerpt: "Claude API 키 발급부터 첫 메시지 호출, 스트리밍 응답, 도구 호출(tool use)까지 5분 안에 따라 할 수 있는 실전 입문 가이드."
---

## 왜 지금 Claude API인가

사내 챗봇이든 사이드 프로젝트든, "일단 LLM API 하나 붙여보자"는 순간이 온다. 문제는 공식 문서가 개념 설명에 치우쳐 있어서 처음 붙이는 사람 입장에서는 어디서부터 시작해야 할지 막막하다는 점이다. 이 글은 계정 생성 이후 단계, 즉 API 키 발급부터 첫 메시지 호출·스트리밍·도구 호출까지 실제로 코드를 돌려보는 순서로만 정리했다.

Claude API는 OpenAI Chat Completions와 구조가 비슷하지만 몇 가지 이름과 파라미터가 다르다. 이 차이를 먼저 알고 시작하면 삽질을 크게 줄일 수 있다.

## 핵심 개념 3가지

| 개념 | 설명 |
|---|---|
| Messages API | 대화 턴을 `role`(user/assistant)과 `content` 배열로 주고받는 단일 엔드포인트 |
| `system` 파라미터 | OpenAI처럼 메시지 배열 안에 넣지 않고 최상위 파라미터로 분리되어 있다 |
| `max_tokens` 필수 | OpenAI와 달리 응답 최대 토큰 수를 반드시 지정해야 요청이 성공한다 |

## 코드 예제 1: 첫 메시지 호출

```python
import anthropic

client = anthropic.Anthropic(api_key="YOUR_API_KEY")

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    system="너는 친절한 한국어 코딩 도우미야.",
    messages=[
        {"role": "user", "content": "파이썬으로 피보나치 수열 함수를 짜줘"}
    ],
)

print(response.content[0].text)
```

## 코드 예제 2: 스트리밍과 도구 호출

응답이 길어질수록 스트리밍이 체감 지연을 크게 줄여준다. `stream=True` 대신 전용 컨텍스트 매니저를 쓰는 점이 특징이다.

```python
with client.messages.stream(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "서울 날씨 알려줘"}],
    tools=[{
        "name": "get_weather",
        "description": "도시 이름으로 현재 날씨를 조회한다",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    }],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final = stream.get_final_message()
    if final.stop_reason == "tool_use":
        tool_call = next(b for b in final.content if b.type == "tool_use")
        print("\n호출된 도구:", tool_call.name, tool_call.input)
```

`stop_reason`이 `tool_use`면 모델이 도구를 호출하고 싶다는 뜻이므로, 실제 함수를 실행한 뒤 결과를 `tool_result` role로 다시 넣어 대화를 이어가야 한다.

## 실무 포인트

- **요금은 입력·출력 토큰이 따로 과금**된다. 긴 시스템 프롬프트를 반복 호출한다면 프롬프트 캐싱을 검토하자.
- `max_tokens`를 너무 낮게 잡으면 `stop_reason: "max_tokens"`로 답변이 중간에 잘린다. 응답 길이를 가늠해 여유 있게 설정한다.
- 프로덕션에서는 429(레이트리밋)와 529(서버 과부하) 응답에 대한 지수 백오프 재시도 로직을 반드시 넣는다.

## 마무리 요약

- Claude Messages API는 `system`을 분리하고 `max_tokens`를 필수로 요구한다는 점이 OpenAI와 다르다.
- 스트리밍은 `client.messages.stream()` 컨텍스트 매니저로 처리하며 `text_stream`을 순회하면 된다.
- 도구 호출은 `stop_reason == "tool_use"`를 확인한 뒤 결과를 다시 대화에 넣는 왕복 구조로 동작한다.

## 참고 자료

- [Anthropic 공식 API 문서](https://docs.anthropic.com/)
- [Anthropic Python SDK GitHub](https://github.com/anthropics/anthropic-sdk-python)
