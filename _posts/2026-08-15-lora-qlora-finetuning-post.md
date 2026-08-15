---
layout: single
title: "LoRA와 QLoRA로 나만의 모델 파인튜닝하기"
date: 2026-08-15 21:50:00 +0530
categories: ai
tags: ["LoRA", "QLoRA", "파인튜닝", "PEFT"]
toc: true
toc_sticky: true
excerpt: "저랭크 어댑터와 양자화를 결합해 소비자용 GPU 한 대로도 대형 언어모델을 파인튜닝하는 방법과 판단 기준을 정리한다."
---

## 왜 지금 이 이야기인가

RAG와 프롬프트 엔지니어링만으로는 해결되지 않는 문제들이 있다. 특정 말투나 출력 포맷을 일관되게 유지해야 하거나, 도메인 전문 용어와 문장 구조 자체를 모델이 "체화"해야 하는 경우, 아무리 프롬프트를 정교하게 짜도 한계가 드러난다. 그런데 몇 년 전까지 파인튜닝은 A100 여러 장이 필요한 부담스러운 작업으로 여겨졌다. LoRA와 QLoRA 같은 PEFT(Parameter-Efficient Fine-Tuning) 기법이 널리 쓰이면서 이 진입장벽이 크게 낮아졌고, 개인 개발자도 소비자용 GPU 한 대로 7B~13B급 모델을 파인튜닝하는 사례가 흔해졌다. 다만 여전히 "언제 파인튜닝이 필요한가"에 대한 판단은 쉽지 않은 문제로 남아 있다.

## 핵심 개념: 풀 파인튜닝 vs PEFT vs LoRA vs QLoRA

| 방식 | 학습 대상 | 메모리 요구량 | 특징 |
|---|---|---|---|
| 풀 파인튜닝 | 전체 파라미터 | 매우 높음 | 원본 가중치를 직접 수정, 성능 상한은 높지만 비용 큼 |
| PEFT (일반) | 일부 추가 파라미터 | 낮음 | 원본 가중치는 고정(freeze), 어댑터만 학습 |
| LoRA | 저랭크 어댑터 행렬 A, B | 낮음~중간 | 원본 가중치는 그대로, ΔW=BA 형태로 근사 |
| QLoRA | LoRA 어댑터 + 4bit 양자화 base | 매우 낮음 | base 모델을 4bit(NF4)로 양자화 후 그 위에 LoRA 학습 |

LoRA의 핵심 아이디어는 가중치 업데이트 행렬 ΔW를 통째로 학습하는 대신, 훨씬 작은 두 개의 저랭크 행렬 A(r×d)와 B(d×r)의 곱으로 근사한다는 것이다. r(랭크)이 8~64 정도로 작으면 학습 파라미터 수가 원본 대비 수백 분의 1로 줄어든다. 추론 시에는 BA를 원본 가중치에 더해 합칠 수 있어(merge) 별도의 추가 지연도 거의 없다.

QLoRA는 여기에 한 걸음 더 나아가, base 모델 자체를 4bit NF4(NormalFloat4) 포맷으로 양자화해 GPU 메모리에 올린 뒤, 그 위에서 LoRA 어댑터만 bf16 등 고정밀도로 학습한다. Double Quantization으로 양자화 상수 자체도 다시 압축하고, Paged Optimizer로 옵티마이저 상태의 메모리 스파이크를 CPU로 흘려보내는 방식까지 결합해, 65B급 모델도 단일 48GB GPU에서 파인튜닝이 가능해졌다고 알려져 있다.

## 언제 파인튜닝이 RAG/프롬프팅보다 나은가

- 최신 사실 정보가 자주 바뀐다면 RAG가 유리하다 — 파인튜닝된 지식은 "박제"되기 때문에 업데이트 비용이 크다.
- 반대로 말투·포맷·특정 태스크 수행 방식처럼 "행동 양식"을 바꾸고 싶다면 파인튜닝이 더 안정적인 경향이 있다.
- 프롬프트가 지나치게 길어져 지연시간과 비용이 커진 경우, 파인튜닝으로 지시문 자체를 축약할 수 있다.
- 다만 데이터가 부족하거나 품질이 낮으면 파인튜닝은 오히려 성능을 해칠 수 있어, RAG나 프롬프팅으로 먼저 문제를 해결해보고 한계를 확인한 뒤 파인튜닝을 고려하는 순서가 안전하다고 보인다.

## 예제

```yaml
# LoRA 학습 설정 예시 (개념적 형태, 실제 프레임워크마다 키 이름은 다를 수 있음)
base_model: meta-llama/Llama-3.1-8B
load_in_4bit: true          # QLoRA를 쓸 경우
lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules: ["q_proj", "v_proj", "k_proj", "o_proj"]
train:
  epochs: 3
  learning_rate: 2e-4
  batch_size: 4
  gradient_accumulation_steps: 4
```

```python
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
import torch

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-8B",
    quantization_config=bnb_config,
    device_map="auto",
)

lora_config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
```

## 실무 포인트와 주의사항

- 데이터셋 품질이 양보다 훨씬 중요하다 — 중복 제거, 포맷 일관성, 실제 사용 시나리오와의 유사성을 먼저 점검해야 한다.
- 랭크(r)와 alpha 값은 태스크마다 실험적으로 조정이 필요하며, 무조건 크게 잡는다고 성능이 좋아지지는 않는다고 알려져 있다.
- 여러 태스크별 LoRA 어댑터를 만들었다면 base 모델과 어댑터 버전을 함께 관리하는 카탈로그(레지스트리)가 필요하다 — 어댑터만으로는 재현이 안 되기 때문이다.
- 평가 없이 배포하지 말 것 — 파인튜닝 전후 성능을 같은 벤치마크/held-out 셋으로 비교해 회귀가 없는지 반드시 확인해야 한다.

## 3줄 요약

- LoRA는 원본 가중치를 고정한 채 저랭크 어댑터 행렬만 학습해 파인튜닝 비용을 크게 낮춘다.
- QLoRA는 base 모델을 4bit로 양자화해 LoRA와 결합, 소비자용 GPU에서도 대형 모델 파인튜닝을 가능하게 한다.
- 지식이 자주 바뀌면 RAG, 행동/스타일을 바꾸려면 파인튜닝이라는 기준으로 먼저 판단하는 것이 안전하다.

## 참고 자료

- [LoRA: Low-Rank Adaptation of Large Language Models (arXiv)](https://arxiv.org/abs/2106.09685)
- [QLoRA: Efficient Finetuning of Quantized LLMs (arXiv)](https://arxiv.org/abs/2305.14314)
- [Hugging Face PEFT 공식 문서](https://huggingface.co/docs/peft/index)
