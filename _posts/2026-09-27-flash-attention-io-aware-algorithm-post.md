---
layout: single
title: "FlashAttention — GPU 메모리 계층을 이해해야 보이는 어텐션 가속의 진짜 원리"
date: 2026-09-27 12:50:00 +0530
categories: ai
tags: ["FlashAttention", "GPU최적화", "트랜스포머", "어텐션", "커널최적화"]
toc: true
toc_sticky: true
excerpt: "FlashAttention이 연산량을 줄이지 않고도 어텐션을 몇 배나 빠르게 만드는 이유는 알고리즘이 아니라 GPU 메모리 계층에 있다. SRAM/HBM 대역폭 병목과 타일링, online softmax의 동작 원리를 정리했다."
---

## 왜 지금 다시 FlashAttention을 봐야 하는가

긴 컨텍스트 윈도우가 표준이 되면서 어텐션 연산의 비용이 다시 병목으로 떠올랐다. 시퀀스 길이가 늘어나면 어텐션의 연산량과 메모리 사용량은 제곱으로 커지는데, 많은 엔지니어가 이를 "행렬곱이 느려서"라고 오해한다. 실제로는 다르다. FlashAttention 논문이 처음 보여준 것은, 표준 어텐션 구현이 느린 진짜 이유가 연산(FLOPs) 자체가 아니라 GPU의 고대역폭 메모리(HBM)와 온칩 SRAM 사이를 오가는 데이터 이동량이라는 사실이었다. vLLM, SGLang 같은 최신 서빙 엔진은 물론 PyTorch의 `scaled_dot_product_attention`까지 이 원리를 기본으로 채택하고 있으니, 왜 빠른지 이해하지 않고 그냥 쓰는 건 반쪽짜리다.

## 핵심 개념 1 — 병목은 연산이 아니라 메모리 이동이다

표준 어텐션은 Q·K로 어텐션 스코어 행렬을 만들고, softmax를 적용한 뒤, V와 곱해 출력을 만드는 세 단계를 거친다. 문제는 시퀀스 길이 N에 대해 N×N 크기의 중간 행렬을 매 단계마다 HBM에 썼다가 다시 읽어온다는 점이다. GPU의 연산 유닛은 매우 빠르지만 HBM 대역폭은 상대적으로 훨씬 느리므로, 실제 실행 시간의 대부분은 이 읽기·쓰기에 소모된다. GPU 내부에는 HBM보다 수십 배 빠르지만 용량이 훨씬 작은 SRAM(온칩 캐시)이 있는데, 표준 구현은 이 SRAM을 거의 활용하지 못하고 매번 큰 중간 행렬을 HBM에 왕복시킨다.

## 핵심 개념 2 — 타일링과 online softmax로 HBM 왕복을 없애기

FlashAttention의 해법은 두 가지 아이디어의 조합이다. 첫째는 **타일링(tiling)**으로, Q·K·V를 SRAM에 들어갈 만큼 작은 블록으로 쪼개 한 번에 하나의 블록 쌍만 처리한다. 이렇게 하면 N×N 전체 어텐션 행렬을 HBM에 저장할 필요가 없다. 둘째는 **online softmax**로, softmax는 전체 행에 대한 정규화 상수(분모의 합)를 알아야 계산할 수 있는데, 블록 단위로 처리하면서도 이 정규화를 점진적으로 갱신하는 수치적으로 안정적인 알고리즘을 쓴다. 각 블록을 처리할 때마다 현재까지의 최댓값과 누적 합을 재조정해, 마지막에 전체를 다시 훑지 않고도 정확한 softmax 결과를 얻는다.

| 구현 | HBM 왕복 횟수 | 중간 행렬 저장 | 연산량(FLOPs) |
|---|---|---|---|
| 표준 어텐션 | O(N²) 규모의 읽기/쓰기 | N×N 전체 저장 | 동일 |
| FlashAttention | O(N) 규모로 축소 | 블록 단위만 SRAM에 유지 | 동일(오히려 재계산으로 약간 증가) |

흥미로운 점은 FlashAttention이 연산량(FLOPs)을 줄이지 않는다는 것이다. 오히려 역전파 시 중간 값을 저장 대신 재계산(recomputation)하기 때문에 연산량은 미세하게 늘어난다. 그럼에도 전체 실행 시간이 크게 줄어드는 이유는 병목이 연산이 아니라 메모리 대역폭이었기 때문이다. 이것이 "IO-aware 알고리즘"이라는 이름의 의미다.

## 코드 예제 — PyTorch에서 FlashAttention 커널 활용

```python
import torch
import torch.nn.functional as F

# PyTorch 2.x는 scaled_dot_product_attention에서
# 백엔드로 FlashAttention 커널을 자동 선택한다
q = torch.randn(1, 8, 4096, 64, device="cuda", dtype=torch.float16)
k = torch.randn(1, 8, 4096, 64, device="cuda", dtype=torch.float16)
v = torch.randn(1, 8, 4096, 64, device="cuda", dtype=torch.float16)

with torch.backends.cuda.sdp_kernel(
    enable_flash=True, enable_math=False, enable_mem_efficient=False
):
    out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
```

`sdp_kernel` 컨텍스트 매니저로 백엔드를 강제 지정할 수 있는데, 시퀀스가 길고 헤드 차원이 크지 않을수록(보통 128 이하) FlashAttention 커널의 이득이 두드러진다.

## 실무 포인트

- **헤드 차원이 클수록 이득이 줄어든다.** SRAM 용량이 고정돼 있으므로 헤드 차원(head_dim)이 커지면 블록 크기를 줄여야 하고, 이는 타일링 효율을 떨어뜨린다. 최신 FlashAttention-2/3는 워프 수준 병렬화와 비동기 연산 오버랩으로 이 문제를 상당 부분 완화했다.
- **causal mask 처리 방식이 실제 속도에 영향을 준다.** 인과적 어텐션(디코더)에서는 상삼각 블록을 아예 건너뛰는 최적화가 들어가므로, 순수 self-attention보다 causal attention이 오히려 상대적으로 더 빠른 경우가 많다.
- **GQA/MQA와 결합할 때 KV 헤드 수를 확인하라.** Grouped-Query Attention을 쓰는 모델은 K·V의 헤드 수가 Q보다 적은데, 커널 구현이 이를 제대로 지원하지 않으면 K·V를 불필요하게 복제해 메모리 이득을 깎아먹는다.

## 마무리 요약

- FlashAttention이 빠른 이유는 연산량 감소가 아니라, HBM과 SRAM 사이의 데이터 이동을 O(N²)에서 O(N) 규모로 줄이는 IO-aware 설계 덕분이다.
- 타일링으로 중간 어텐션 행렬을 HBM에 저장하지 않고, online softmax로 블록 단위 정규화 상수를 점진적으로 갱신해 정확한 결과를 유지한다.
- 헤드 차원, causal mask, GQA/MQA 구조에 따라 실제 가속 폭이 달라지므로 모델 구조에 맞는 커널 선택과 설정이 필요하다.

## 참고 자료

- [FlashAttention 논문 (Dao et al., 2022)](https://arxiv.org/abs/2205.14135)
- [FlashAttention-2 논문](https://arxiv.org/abs/2307.08691)
- [PyTorch scaled_dot_product_attention 공식 문서](https://pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)
