---
layout: single
title: "실시간 응답이 필요 없다면 절반 값에 처리한다 — 배치 LLM 추론 파이프라인 최적화"
date: 2026-08-30 13:50:00 +0530
categories: ai
tags: ["ai", "batch-inference", "llm", "throughput", "continuous-batching", "offline-processing"]
toc: true
toc_sticky: true
excerpt: "수백만 건의 문서 분류·요약처럼 즉시 응답이 필요 없는 작업을 실시간 채팅 API로 처리하면 처리량과 비용 양쪽에서 손해다. 배치 추론 파이프라인이 실시간 서빙과 다르게 최적화해야 하는 지점을 정리한다."
---

콜센터 상담 로그 200만 건을 감성 분석하거나, 전체 고객 데이터베이스의 이력서를 요약하는 작업에 실시간 채팅 API를 그대로 쓰면 두 가지가 함께 낭비된다. 하나는 처리량이다. 실시간 API는 응답 지연을 짧게 유지하려고 요청마다 즉시 스케줄링하는데, 이 방식은 GPU 배치 크기를 충분히 키우지 못해 처리량 상한이 낮다. 다른 하나는 비용이다. 대부분의 LLM 제공사는 지연 시간 보장이 없는 배치 API를 실시간 대비 절반 이하 가격에 제공하는데, 이 옵션을 안 쓰는 것 자체가 비용 손해다.

**배치 추론(batch inference)**은 "지금 당장 답이 필요 없다"는 제약을 역이용해 처리량과 비용을 최적화하는 별도의 파이프라인 설계다. 이 글에서는 실시간 서빙과 배치 파이프라인이 최적화 목표부터 다르다는 점, 그리고 실무에서 자주 쓰이는 두 가지 접근(연속 배칭 기반 자체 서빙, 프로바이더 배치 API)의 차이를 정리한다.

## 핵심 개념 1: 지연 시간 최적화와 처리량 최적화는 다른 문제다

실시간 서빙은 개별 요청의 지연 시간(latency)을 낮추는 게 목표다. 요청이 도착하면 최대한 빨리 배치에 끼워 넣고, 배치 크기를 무한정 키우기보다 적당한 크기에서 끊어 응답 속도를 지킨다. 반대로 배치 추론은 전체 작업 집합의 처리량(throughput), 즉 "총 N개 요청을 얼마나 빠르고 싸게 다 처리하느냐"가 목표이므로, 개별 요청의 응답이 몇 초, 몇 분 늦어도 상관없는 대신 GPU를 최대한 꽉 채워 돌리는 것이 이득이다.

이 차이는 배치 크기 선택에 직접 영향을 준다. 실시간 서빙에서 배치 크기를 늘리면 뒤에 도착한 요청이 앞선 요청의 디코딩이 끝날 때까지 기다려야 해 지연 시간이 늘어나지만, 배치 추론에서는 애초에 지연 시간 제약이 없으므로 GPU 메모리가 허용하는 한 배치 크기를 최대로 키워 GPU 활용률(utilization)을 끌어올리는 것이 곧 처리량 향상이다.

## 핵심 개념 2: 연속 배칭 — 정적 배치의 낭비를 없앤다

과거의 정적 배치(static batching)는 같은 배치에 묶인 모든 요청이 가장 긴 응답이 끝날 때까지 GPU 슬롯을 붙잡고 있어야 했다 — 짧은 응답을 생성한 요청도 배치 전체가 끝날 때까지 자리를 비우지 못하는 낭비가 있었다. **연속 배칭(continuous batching, iteration-level scheduling)**은 토큰 생성 단위로 스케줄링을 재구성해서, 응답이 먼저 끝난 요청의 슬롯에 대기 중이던 새 요청을 즉시 채워 넣는다. vLLM, TensorRT-LLM, Hugging Face TGI가 이 방식을 채택하고 있고, 배치 추론 파이프라인에서도 자체 서빙 인프라를 구축한다면 이 스케줄러를 그대로 활용하는 것이 효율적이다.

| 구분 | 정적 배치(static batching) | 연속 배칭(continuous batching) |
|---|---|---|
| 배치 구성 단위 | 요청 전체가 끝날 때까지 고정 | 토큰(iteration) 단위로 재구성 |
| 짧은 응답의 GPU 점유 | 배치 전체가 끝날 때까지 유지 | 끝나는 즉시 슬롯 반납·재사용 |
| GPU 활용률 | 응답 길이 편차가 크면 낮아짐 | 편차와 무관하게 높게 유지 |
| 적합한 워크로드 | 응답 길이가 균일한 경우 | 응답 길이 편차가 큰 대규모 배치 |

## 핵심 개념 3: 프로바이더 배치 API — 인프라 없이 처리량 이득 얻기

자체 GPU 인프라를 운영하지 않는다면, Anthropic·OpenAI 같은 프로바이더가 제공하는 배치 API를 쓰는 것이 합리적이다. 요청 파일(JSONL)을 업로드하면 프로바이더가 내부적으로 자기 인프라의 유휴 용량을 활용해 처리하고, 보통 몇 시간 내(대개 24시간 이내 SLA) 완료된 결과 파일을 돌려준다. 실시간 API 대비 토큰당 단가가 절반 수준으로 낮은 대신, 개별 요청의 응답 시점을 보장하지 않는다는 제약을 받아들여야 한다.

## 예제: 배치 API 요청 파일 구성과 폴링

```python
# batch_submit.py — JSONL 배치 요청 파일 생성 및 제출
import json

requests = []
for doc_id, text in enumerate(documents):
    requests.append({
        "custom_id": f"doc-{doc_id}",
        "params": {
            "model": "claude-haiku-4-5",
            "max_tokens": 256,
            "messages": [
                {"role": "user", "content": f"다음 문서를 3문장으로 요약하라:\n\n{text}"}
            ]
        }
    })

with open("batch_requests.jsonl", "w", encoding="utf-8") as f:
    for req in requests:
        f.write(json.dumps(req, ensure_ascii=False) + "\n")

# batch = client.messages.batches.create(requests=requests)
# 이후 batch.id로 상태를 폴링하고, 완료되면 결과 파일을 스트리밍으로 받는다
```

```python
# batch_poll.py — 상태 폴링과 부분 실패 처리
def wait_for_batch(client, batch_id, interval_sec=60):
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        time.sleep(interval_sec)

    results = []
    failures = []
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            results.append(result)
        else:
            # 개별 요청 실패는 배치 전체 실패가 아니다 — 부분 재시도 대상으로 분리
            failures.append(result)
    return results, failures
```

## 실무 포인트

- **부분 실패를 배치 단위가 아니라 요청 단위로 처리해야 한다.** 배치 API는 개별 요청이 실패해도 나머지는 정상 처리해 돌려준다. 실패한 `custom_id`만 추려 새 배치로 재제출하는 재시도 파이프라인을 처음부터 설계에 넣어야, 실패율이 몇 % 있다는 이유로 전체를 다시 돌리는 낭비를 피할 수 있다.
- **프롬프트 캐싱과 배치를 함께 쓰면 이득이 배가된다.** 같은 시스템 프롬프트나 few-shot 예시를 매 요청마다 반복한다면, 프롬프트 캐싱을 배치 요청에도 적용해 반복되는 프리픽스의 처리 비용을 줄일 수 있다. 두 최적화는 서로 배타적이지 않다.
- **배치 크기를 무한정 키우는 것도 능사는 아니다.** 자체 인프라를 운영한다면 배치가 커질수록 KV 캐시 메모리 사용량도 함께 늘어 GPU 메모리 한계에 부딪힌다. 처리량과 메모리 여유 사이의 실제 최적 배치 크기는 모델 크기와 GPU 사양에 따라 실측으로 찾아야 하는 값이지, 무조건 큰 게 좋은 것은 아니다.

## 3줄 요약

- 배치 추론은 개별 요청의 지연 시간이 아니라 전체 작업 집합의 처리량과 비용을 최적화 목표로 삼으며, 이 차이가 배치 크기 선택 전략 자체를 바꾼다.
- 연속 배칭은 토큰 단위로 스케줄링을 재구성해 응답 길이 편차가 큰 대규모 배치에서도 GPU 활용률을 높게 유지하고, 자체 인프라가 없다면 프로바이더 배치 API로 같은 이득을 인프라 없이 얻을 수 있다.
- 부분 실패는 요청 단위로 분리해 재시도하고, 프롬프트 캐싱을 함께 적용하며, 배치 크기는 GPU 메모리 한계를 고려해 실측으로 최적값을 찾아야 한다.

## 참고 자료

- [Anthropic 공식 문서: Message Batches API](https://docs.claude.com/en/docs/build-with-claude/batch-processing)
- [vLLM 공식 문서: Continuous Batching](https://docs.vllm.ai/en/latest/serving/offline_inference.html)
- [NVIDIA 기술 블로그: In-Flight Batching (TensorRT-LLM)](https://developer.nvidia.com/blog/nvidia-tensorrt-llm-supercharges-large-language-model-inference-on-nvidia-h100-gpus/)
- [OpenAI 공식 문서: Batch API](https://platform.openai.com/docs/guides/batch)
