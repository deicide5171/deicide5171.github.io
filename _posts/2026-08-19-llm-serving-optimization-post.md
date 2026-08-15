---
layout: single
title: "vLLM 처리량의 비밀 — 연속 배칭과 PagedAttention으로 GPU 유휴 시간 줄이기"
date: 2026-08-19 13:50:00 +0530
categories: ai
tags: ["vllm", "llm-serving", "continuous-batching", "pagedattention", "gpu-inference"]
toc: true
toc_sticky: true
excerpt: "같은 모델, 같은 GPU에서도 서빙 엔진에 따라 처리량이 크게 갈리는 이유를 vLLM의 연속 배칭과 PagedAttention 내부 동작으로 파헤친다."
---

## 왜 지금 서빙 최적화인가

오픈소스 LLM을 직접 호스팅할 때 성능을 좌우하는 것은 "어떤 모델을 골랐는가"가 아니라 "GPU 한 장으로 동시에 몇 명의 요청을 처리할 수 있는가"다. 같은 모델, 같은 GPU라도 서빙 엔진이 무엇이냐에 따라 처리량이 크게 갈리는 이유가 여기에 있다.

Hugging Face `transformers`의 기본 `generate()`로 요청을 하나씩 처리하면 GPU는 토큰을 생성하는 짧은 순간을 빼고는 대부분 놀고 있다. vLLM은 이 유휴 문제를 겨냥해 설계된 서빙 엔진으로, **연속 배칭(continuous batching)** 과 **PagedAttention** 이라는 두 기법으로 처리량을 끌어올린다. 이 글은 vLLM이 "무엇을 자동으로 해주는가"보다, 두 기법이 내부적으로 어떤 문제를 어떻게 푸는지와 실제 운영에서 어떤 설정값을 조정해야 하는지에 집중한다.

## 핵심 개념 1: 정적 배칭의 한계와 연속 배칭

전통적인 정적 배칭(static batching)은 여러 요청을 한 번에 묶어 GPU에 올리되, **배치 안의 모든 시퀀스가 끝나야 다음 배치를 시작**한다. 문제는 요청마다 생성할 토큰 수가 제각각이라는 점이다. 짧게 끝나는 요청도 배치 내 가장 긴 요청이 끝날 때까지 그 GPU 슬롯은 비워둔 채 대기해야 한다.

연속 배칭(iteration-level scheduling)은 이 대기를 없앤다. 배치를 고정하지 않고 **매 디코딩 스텝마다 배치 구성을 다시 계산**해서, 먼저 끝난 요청의 슬롯에 대기열의 새 요청을 즉시 채워 넣는다. 배치 경계라는 개념 자체가 사라지는 셈이다.

| 기준 | 정적 배칭 | 연속 배칭 |
|---|---|---|
| 배치 구성 시점 | 배치 시작 시 1회 고정 | 매 디코딩 스텝마다 재계산 |
| 짧은 요청 완료 후 | 슬롯 유휴(배치 전체 종료까지 대기) | 즉시 새 요청으로 채움 |
| GPU 활용률 | 요청 길이 편차가 클수록 낮아짐 | 편차와 무관하게 높게 유지 |
| 구현 복잡도 | 낮음 | 스케줄러·메모리 관리 로직 필요 |

## 핵심 개념 2: KV 캐시 메모리 문제와 PagedAttention

<img src="/assets/images/posts/2026-08-19-llm-serving-optimization-1.svg" alt="정적 배칭 대비 연속 배칭의 GPU 유휴 시간 비교와 PagedAttention의 블록 단위 KV 캐시 매핑 개념도" style="width:100%;">

연속 배칭이 스케줄링 문제를 풀었다면, PagedAttention은 **메모리 문제**를 푼다. 트랜스포머 디코딩은 이전 토큰들의 키·값 벡터(KV 캐시)를 계속 누적하는데, 순진한 구현은 요청마다 "최대로 늘어날 수 있는 길이"만큼 연속된(contiguous) GPU 메모리를 미리 예약한다. 실제 생성 길이는 그보다 짧은 경우가 많아 예약분 대부분이 낭비되고, 이 낭비만큼 동시 처리 가능한 요청 수가 줄어든다.

PagedAttention은 운영체제의 가상 메모리 페이징에서 아이디어를 빌려온다. KV 캐시를 고정 크기 블록으로 잘라, 논리적으로는 이어져 있다고 취급하는 블록들을 실제로는 GPU 메모리 어디에든 흩어 놓고 **블록 테이블**로 매핑만 관리한다.

| 항목 | 기존 방식(연속 할당) | PagedAttention |
|---|---|---|
| 메모리 예약 단위 | 요청당 최대 길이 전체 | 고정 크기 블록 |
| 미사용 예약 메모리 | 큼(내부 단편화) | 블록 하나 미만으로 최소화 |
| 물리적 배치 | 반드시 연속 | 비연속 허용(블록 테이블로 매핑) |
| 동일 프리픽스 공유 | 어려움 | 블록 단위 공유(copy-on-write) 가능 |

이 구조 덕분에 동일한 시스템 프롬프트를 쓰는 여러 요청이나 병렬 샘플링처럼 앞부분이 같은 시퀀스들은 해당 블록을 복사하지 않고 공유할 수 있어, 메모리 여유가 다시 동시 처리 가능한 요청 수 증가로 이어진다.

## 예제 1: vLLM OpenAI 호환 서버 띄우기

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 256 \
  --max-model-len 8192 \
  --port 8000
```

`--gpu-memory-utilization`은 KV 캐시 블록 풀에 얼마만큼의 GPU 메모리를 배정할지를 결정하는 값이고, `--max-num-seqs`는 한 스케줄러 스텝에서 동시에 배치에 포함될 수 있는 시퀀스 수의 상한이다. 두 값 모두 하드웨어와 모델 크기에 따라 안전한 상한이 달라지므로, 실제 배포 전 부하 테스트로 확인해야 한다.

## 예제 2: 동시 요청으로 연속 배칭 체감하기

```python
import asyncio, httpx

async def ask(client, prompt):
    resp = await client.post(
        "http://localhost:8000/v1/completions",
        json={"model": "meta-llama/Llama-3.1-8B-Instruct",
              "prompt": prompt, "max_tokens": 128},
    )
    return resp.json()["choices"][0]["text"]

async def main():
    prompts = [f"질문 {i}: 짧게 답해줘" for i in range(20)]
    async with httpx.AsyncClient(timeout=60) as client:
        results = await asyncio.gather(*(ask(client, p) for p in prompts))
    print(f"{len(results)}건 완료")

asyncio.run(main())
```

동일한 요청 20건을 순차 처리 대신 동시에 보내보면, 짧게 끝나는 요청이 있어도 서버 로그에서 배치 크기가 스텝마다 변하며 새 요청이 계속 끼어드는 것을 확인할 수 있다. 이것이 연속 배칭이 실제로 동작하는 모습이다.

## 실무 포인트

- **`gpu_memory_utilization`은 보수적으로 시작한다.** KV 캐시 블록 풀과 모델 가중치, 활성화 메모리가 같은 GPU를 나눠 쓰므로, 값을 너무 높이면 다른 프로세스나 예상치 못한 메모리 스파이크에서 OOM이 날 수 있다.
- **처리량과 지연을 함께 본다.** `max_num_seqs`나 `max_num_batched_tokens`를 올리면 전체 처리량(throughput)은 늘지만, 개별 요청의 첫 토큰 지연(TTFT)이나 토큰당 지연(TPOT)이 함께 늘어날 수 있다. 서비스 요구사항에 맞는 지점을 벤치마크로 찾아야 한다.
- **컨텍스트 길이가 길어질수록 동시 처리량은 줄어든다.** KV 캐시는 시퀀스 길이에 비례해 커지므로, 동일 GPU 메모리 예산 안에서는 평균 컨텍스트 길이가 길어질수록 동시에 태울 수 있는 요청 수가 줄어드는 트레이드오프가 항상 존재한다.
- **양자화는 별개의 축으로 검토한다.** AWQ, GPTQ 같은 가중치 양자화는 메모리 여유를 늘려 동시 처리량에 도움을 줄 수 있지만, 실제 개선 폭은 모델·하드웨어·워크로드 조합마다 달라 단정하기 어렵다. 반드시 자체 벤치마크로 확인한다.

## 3줄 요약

- 연속 배칭은 매 디코딩 스텝마다 배치를 다시 구성해, 요청 길이 편차로 인한 GPU 유휴 시간을 없앤다.
- PagedAttention은 KV 캐시를 고정 크기 블록으로 나누고 블록 테이블로 매핑해, 연속 메모리 예약으로 인한 낭비와 단편화를 줄인다.
- 실제 운영에서는 `gpu_memory_utilization`, `max_num_seqs` 같은 값을 처리량-지연 트레이드오프 관점에서 벤치마크로 튜닝해야 한다.

## 참고 자료

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [Efficient Memory Management for Large Language Model Serving with PagedAttention (arXiv)](https://arxiv.org/abs/2309.06180)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
