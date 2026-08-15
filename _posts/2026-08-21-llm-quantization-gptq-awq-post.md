---
layout: single
title: "양자화의 과학 — GPTQ, AWQ로 LLM을 가볍게 만드는 법"
date: 2026-08-21 13:50:00 +0530
categories: ai
tags: ["ai", "llm", "quantization", "gptq", "awq", "inference"]
toc: true
toc_sticky: true
excerpt: "70B 모델을 소비자용 GPU 한 장에 올리려는 시도의 핵심인 양자화 기법을, GPTQ와 AWQ의 접근 방식 차이를 중심으로 정리한다."
---

파라미터 수가 늘어날수록 모델의 성능은 좋아지지만, 그만큼 서빙 비용도 함께 커진다. 70B급 모델을 FP16으로 그대로 올리려면 100GB가 넘는 GPU 메모리가 필요하고, 이는 A100이나 H100을 여러 장 묶어야만 가능한 수준이다. 개인 개발자나 소규모 팀이 이런 모델을 소비자용 GPU 한두 장으로 돌리고 싶다는 요구는 자연스럽게 "가중치를 더 적은 비트로 표현할 수 없을까"라는 질문으로 이어졌다.

양자화(quantization)는 바로 이 질문에 대한 답이다. 가중치를 16비트 부동소수점 대신 8비트나 4비트 정수로 근사해 표현하면, 모델 크기와 메모리 대역폭 요구량을 크게 줄일 수 있다. 문제는 단순히 비트를 잘라내면 정확도가 눈에 띄게 떨어진다는 점이다. 그래서 등장한 것이 GPTQ와 AWQ처럼, 어떤 가중치를 어떻게 근사해야 오차를 최소화할 수 있는지를 고민하는 후처리 양자화(post-training quantization) 기법들이다.

이 글에서는 두 기법이 오차를 줄이기 위해 택한 서로 다른 전략을 중심으로, 양자화의 기본 개념부터 실제 적용 시 고려할 점까지 정리한다.

## 핵심 개념 1: FP16 대비 INT4/INT8 양자화의 기본 원리

FP16은 하나의 가중치 값을 16비트로 표현하는 반면, INT8은 8비트, INT4는 4비트만 사용한다. 비트 수가 줄어드는 만큼 표현할 수 있는 값의 개수도 줄어들기 때문에, 원래의 연속적인 부동소수점 값을 정해진 개수의 정수 구간으로 매핑하는 과정이 필요하다. 이때 사용하는 것이 스케일(scale)과 영점(zero-point)이다. 실수 범위를 정수 범위로 선형 변환하는 스케일 값을 구하고, 필요하면 0이 아닌 값을 기준점으로 삼는 영점을 추가로 둔다.

양자화 단위(granularity)도 중요한 선택지다. 텐서 전체에 하나의 스케일만 쓰는 per-tensor 방식은 구현이 단순하지만 오차가 크고, 채널(channel)이나 그룹(group) 단위로 스케일을 따로 두는 per-channel/per-group 방식은 계산이 더 들지만 정확도 손실을 줄일 수 있다. GPTQ와 AWQ 모두 대체로 그룹 단위 양자화를 기본으로 사용하며, 이는 정확도와 압축률 사이의 절충안으로 자리 잡았다.

## 핵심 개념 2: GPTQ의 레이어별 오차 보정 방식

GPTQ(Generative Pre-trained Transformer Quantization)는 레이어를 하나씩 순서대로 양자화하면서, 한 가중치를 반올림할 때 생기는 오차를 아직 양자화하지 않은 나머지 가중치에 분산시켜 보정하는 방식을 쓴다. 이는 OBQ(Optimal Brain Quantization) 계열 방법에서 이어져 온 아이디어로, 레이어 입력의 2차 통계(헤시안 근사)를 이용해 어떤 방향으로 나머지 가중치를 조정해야 전체 출력 오차가 최소화되는지를 계산한다.

핵심은 이 과정이 열(column) 단위로 순차적으로 진행되며, 각 열을 양자화한 직후 남은 열들에 보정값을 더해준다는 점이다. 덕분에 재학습(fine-tuning) 없이 소량의 보정용 데이터(calibration set)만으로 전체 모델을 한 번에 양자화할 수 있다. 다만 레이어별로 헤시안 역행렬을 다루는 연산이 들어가기 때문에, 모델 크기가 클수록 양자화 자체에 걸리는 시간과 메모리 부담이 커진다는 특징이 있다.

## 핵심 개념 3: AWQ의 활성화 인식 채널 스케일링

AWQ(Activation-aware Weight Quantization)는 GPTQ와 다른 전제에서 출발한다. 모든 가중치가 똑같이 중요한 것은 아니며, 실제 추론 과정에서 활성화 값(activation)의 크기가 큰 채널에 대응하는 가중치일수록 양자화 오차가 출력에 더 크게 증폭된다는 관찰이 그 출발점이다. 이런 가중치를 "중요한(salient)" 가중치라고 부른다.

AWQ는 이 중요한 가중치를 별도로 고정밀도로 남겨두는 대신, 활성화 통계를 참고해 채널별로 적절한 스케일링 계수를 찾아 가중치와 활성화 사이의 균형을 맞춘다. 특정 채널의 가중치를 스케일 업하고 그에 대응하는 활성화를 스케일 다운하면, 수학적으로는 결과가 동일하게 유지되면서도 중요한 채널의 양자화 오차를 줄일 수 있다는 원리다. 이 스케일 계수는 소량의 보정 데이터에 대해 출력 오차를 최소화하는 방향으로 탐색되며, GPTQ처럼 레이어 내부에서 가중치를 순차적으로 재조정하는 역전파성 재구성 과정이 없어 양자화 자체의 속도가 상대적으로 빠른 편으로 알려져 있다.

## 핵심 개념 4: GPTQ와 AWQ 비교

| 구분 | GPTQ | AWQ |
|---|---|---|
| 핵심 아이디어 | 레이어별 순차 양자화 + 오차를 나머지 가중치로 보정 | 활성화 크기 기반 채널별 스케일링으로 중요 가중치 보호 |
| 필요 연산 | 헤시안(2차 통계) 근사 및 역행렬 계산 | 활성화 통계 기반 스케일 탐색 |
| 양자화 소요 시간 | 상대적으로 오래 걸릴 수 있음 | 상대적으로 빠른 편으로 알려짐 |
| 재학습 필요 여부 | 불필요(후처리 방식) | 불필요(후처리 방식) |
| 대표 구현체 | AutoGPTQ, GPTQModel | AutoAWQ, llm-awq |

두 방식 모두 "재학습 없이, 소량의 보정 데이터만으로" 정확도를 최대한 지키려 한다는 목표는 같지만, 오차를 다루는 지점이 다르다. GPTQ는 양자화가 끝난 후 남은 오차를 순차적으로 흡수시키는 데 초점을 두고, AWQ는 애초에 오차가 크게 증폭될 채널을 찾아 미리 보호하는 데 초점을 둔다.

## 예제

다음은 Hugging Face `transformers`와 관련 라이브러리를 이용해 이미 양자화된 GPTQ/AWQ 모델을 불러와 추론하는 예시다(Python).

```python
# GPTQ로 양자화된 모델 로드 및 추론
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "example-org/example-model-GPTQ"  # 예시 저장소명
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    device_map="auto",
)

inputs = tokenizer("양자화란 무엇인가?", return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

```python
# AWQ로 양자화된 모델 로드 및 추론 (autoawq 사용)
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_name = "example-org/example-model-AWQ"  # 예시 저장소명
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoAWQForCausalLM.from_quantized(model_name, fuse_layers=True)

inputs = tokenizer("양자화란 무엇인가?", return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

두 코드 모두 저장소명은 예시일 뿐이며, 실제 사용 시에는 GPTQ 또는 AWQ 형식으로 미리 양자화되어 배포된 모델을 가리켜야 한다.

## 실무 포인트

- **양자화 후 정확도 저하는 반드시 별도로 측정해야 한다.** 같은 4비트 양자화라도 모델 구조, 그룹 크기, 보정 데이터셋 구성에 따라 정확도 손실 폭이 달라질 수 있다. Perplexity 같은 일반 지표뿐 아니라, 실제로 서비스에 쓰일 다운스트림 태스크(요약, 코드 생성 등)에 대한 평가를 함께 진행하는 것이 안전하다.
- **하드웨어 호환성을 미리 확인해야 한다.** INT4 연산을 가속하는 커널(예: ExLlama 계열, Marlin 등)은 GPU 아키텍처나 드라이버 버전에 따라 지원 범위가 다르다. 양자화된 모델을 골랐다고 해서 모든 환경에서 동일한 속도 이득을 얻는 것은 아니므로, 실제 배포 환경에서 추론 속도와 메모리 사용량을 직접 확인하는 과정이 필요하다.
- **보정 데이터셋 선택이 결과에 영향을 준다.** GPTQ와 AWQ 모두 소량의 보정 데이터를 사용하지만, 이 데이터가 실제 서비스 도메인과 동떨어져 있으면 양자화 이후 성능 저하가 예상보다 커질 수 있다.

## 3줄 요약

- 양자화는 FP16 가중치를 INT4/INT8처럼 더 적은 비트로 근사해 모델 크기와 메모리 요구량을 줄이는 기법이다.
- GPTQ는 레이어를 순차적으로 양자화하며 남은 가중치로 오차를 보정하고, AWQ는 활성화 크기가 큰 채널을 미리 찾아 스케일링으로 보호한다는 점에서 접근 방식이 다르다.
- 실무에 적용할 때는 양자화 후 정확도 저하를 태스크 단위로 측정하고, 사용할 하드웨어의 커널 지원 여부를 미리 확인해야 한다.

## 참고 자료

- [GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers (arXiv:2210.17323)](https://arxiv.org/abs/2210.17323)
- [AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration (arXiv:2306.00978)](https://arxiv.org/abs/2306.00978)
- [AutoGPTQ GitHub 저장소](https://github.com/PanQiWei/AutoGPTQ)
- [llm-awq GitHub 저장소 (MIT HAN Lab)](https://github.com/mit-han-lab/llm-awq)
