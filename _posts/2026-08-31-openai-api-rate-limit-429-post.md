---
layout: single
title: "OpenAI API 429 에러 해결하기 — 레이트리밋과 재시도 전략"
date: 2026-08-31 13:50:00 +0530
categories: ai
tags: ["openai", "api", "429에러", "레이트리밋", "트러블슈팅"]
toc: true
toc_sticky: true
excerpt: "OpenAI API에서 429 Too Many Requests가 뜨는 원인을 구분하고, 재시도·백오프·큐잉으로 실제 서비스에서 대응하는 방법을 정리했다."
---

## 왜 429는 한 가지 원인이 아닌가

`429 Too Many Requests`를 보면 대부분 "요청을 너무 빨리 보냈나 보다"라고 생각하지만, 실제로는 서로 다른 세 가지 제한 중 무엇에 걸렸는지에 따라 대응법이 완전히 달라진다. 응답 헤더를 확인하지 않고 무작정 재시도 로직만 추가하면 같은 에러가 계속 반복된다.

## 429의 세 가지 원인

| 원인 | 확인 방법 | 대응 |
|---|---|---|
| RPM(분당 요청 수) 초과 | 응답 헤더 `x-ratelimit-remaining-requests` | 요청 빈도 자체를 줄이거나 큐잉 |
| TPM(분당 토큰 수) 초과 | `x-ratelimit-remaining-tokens` | 프롬프트 길이 축소, 배치 크기 조정 |
| 결제/한도 초과 | 응답 본문의 `error.code` (`insufficient_quota`) | 결제 한도 상향, 재시도로는 해결 불가 |

`insufficient_quota`인데 재시도만 반복하면 영원히 실패하므로, 에러 코드를 먼저 분기하는 것이 중요하다.

## 코드 예제: 지수 백오프 재시도

```python
import time
import random
import openai

def call_with_retry(client, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            if "insufficient_quota" in str(e):
                raise  # 재시도해도 해결되지 않는 에러는 즉시 올린다
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"429 발생, {wait:.1f}초 후 재시도 ({attempt+1}/{max_retries})")
            time.sleep(wait)
    raise RuntimeError("최대 재시도 횟수 초과")
```

지수 백오프에 무작위 지터(jitter)를 더하는 이유는, 여러 요청이 동시에 실패했을 때 전부 같은 타이밍에 재시도가 몰려 다시 레이트리밋에 걸리는 상황을 막기 위해서다.

## 실무 포인트

- **`Retry-After` 헤더가 오면 그 값을 그대로 신뢰하고 대기하는 것이 자체 계산한 백오프보다 정확하다.**
- **동시 요청 수 자체를 세마포어로 제한**해서 애초에 레이트리밋에 덜 부딪히게 만드는 것이 재시도 로직보다 근본적인 해결책이다.
- **배치 처리가 가능한 작업이라면 Batch API를 검토하라.** 실시간 응답이 필요 없는 대량 작업은 별도 한도로 처리돼 429 부담이 크게 줄어든다.

## 마무리 요약

- 429는 RPM 초과·TPM 초과·결제 한도 초과, 세 가지 중 무엇인지부터 구분해야 한다.
- 결제 한도 문제는 재시도로 해결되지 않으므로 즉시 예외를 올려 다른 대응을 유도해야 한다.
- 지터를 포함한 지수 백오프와 동시 요청 수 제한을 함께 쓰는 것이 가장 안정적이다.

## 참고 자료

- [OpenAI API 레이트리밋 공식 문서](https://platform.openai.com/docs/guides/rate-limits)
- [OpenAI Cookbook - Retry 예제](https://cookbook.openai.com/)
