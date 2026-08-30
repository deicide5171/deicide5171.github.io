---
layout: single
title: "Sparse Autoencoder로 LLM 내부 들여다보기 — 기계적 해석가능성과 특징 서킷"
date: 2026-09-26 13:50:00 +0530
categories: ai
tags: ["SparseAutoencoder", "기계적해석가능성", "Interpretability", "특징서킷", "AI안전성"]
toc: true
toc_sticky: true
excerpt: "뉴런 하나가 동시에 여러 무관한 개념에 반응하는 다의성(polysemanticity) 때문에 LLM 내부를 직접 읽어낼 수 없는 문제를, 뉴런보다 훨씬 많은 수의 해석 가능한 특징으로 활성화를 재구성하는 Sparse Autoencoder와 그 위에서 찾아낸 특징 서킷 분석으로 정리했다."
---

## 왜 지금 모델 내부를 다시 봐야 하는가

LLM이 특정 답을 내놓은 이유를 설명하라고 하면, 모델 스스로 만들어내는 설명(chain-of-thought)조차 실제 내부 계산 과정과 다를 수 있다는 것이 여러 연구에서 확인됐다. 그렇다면 모델이 실제로 무엇을 계산해서 그 출력을 냈는지 직접 들여다보는 방법이 필요한데, 가장 단순한 접근인 "개별 뉴런의 활성화를 보면 되지 않나"는 곧바로 벽에 부딪힌다. 트랜스포머의 한 뉴런은 한국어 조사, 특정 프로그래밍 언어 키워드, 특정 감정 표현처럼 서로 전혀 관련 없는 개념 여러 개에 동시에 반응하는 경우가 흔하다. 이 다의성(polysemanticity) 때문에 뉴런 단위 분석으로는 "이 뉴런이 무엇을 뜻하는지" 하나로 특정할 수 없다. Sparse Autoencoder(SAE)는 이 문제를 모델 아키텍처를 건드리지 않고, 활성화 데이터를 후처리하는 별도의 작은 신경망으로 우회하는 접근이다.

## 핵심 개념 1 — 중첩 가설과 과대완비 사전

다의성이 생기는 이유는 중첩 가설(superposition hypothesis)로 설명된다. 모델이 표현해야 하는 개념의 수가 실제 뉴런 수보다 훨씬 많을 때, 모델은 여러 개념을 뉴런들의 선형 결합(방향 벡터)으로 압축해 저장한다. 즉 하나의 "진짜 개념"은 특정 뉴런 하나가 아니라 여러 뉴런에 걸친 특정 방향으로 존재한다는 것이다. SAE는 이 방향들을 다시 풀어내기 위해, 원래 활성화 벡터를 뉴런 수보다 몇 배 더 많은 차원의 "특징(feature)" 공간으로 인코딩했다가 다시 디코딩해 원본을 복원하도록 학습된다. 이때 손실 함수에 희소성(sparsity) 페널티를 강하게 걸어, 어떤 입력에 대해서도 극소수의 특징만 활성화되도록 강제한다. 학습이 끝나면 각 특징 방향은 놀랍도록 단일한 의미를 갖는 경우가 많다 — 예를 들어 "괄호가 닫히지 않은 코드", "골든게이트 브리지" 같은 구체적이고 해석 가능한 개념 하나에 대응하는 식이다.

## 핵심 개념 2 — 특징에서 서킷으로: 개입과 스티어링

개별 특징을 찾아낸 뒤 실제로 유용해지는 지점은 이 특징들을 인위적으로 켜거나 끄면서 모델 행동에 어떤 영향을 주는지 확인하는 개입(intervention) 실험이다. Anthropic이 공개한 사례처럼 "골든게이트 브리지" 특징의 활성화 값을 인위적으로 극단적으로 높이면, 모델은 어떤 질문을 받아도 골든게이트 브리지 이야기로 답을 유도하게 된다. 이는 단순히 특징이 존재한다는 것을 넘어, 그 특징이 실제로 모델의 출력 행동에 인과적으로 영향을 미친다는 것을 보여준다. 더 나아가 특징들이 서로 어떻게 연결돼 다음 특징을 활성화시키는지 추적하면, "입력의 특정 패턴 → 중간 특징 A 활성화 → 특징 A가 특징 B를 억제 → 최종 출력"과 같은 특징 서킷(feature circuit)을 그릴 수 있다.

| 접근 | 분석 단위 | 다의성 문제 | 인과 개입 가능성 |
|---|---|---|---|
| 개별 뉴런 활성화 관찰 | 원본 뉴런 | 해결 못함(다의적) | 제한적 |
| Attention 패턴 시각화 | 어텐션 헤드 | 부분적 | 제한적 |
| Sparse Autoencoder 특징 | 학습된 특징 방향 | 대부분 단의적으로 분리 | 특징 단위로 켜고 끄기 가능 |

## 코드 예제 — SAE 학습 손실 함수 구조

```python
import torch
import torch.nn as nn

class SparseAutoencoder(nn.Module):
    def __init__(self, d_model: int, d_hidden: int):
        super().__init__()
        # d_hidden은 d_model보다 훨씬 크게(과대완비) 설정
        self.encoder = nn.Linear(d_model, d_hidden)
        self.decoder = nn.Linear(d_hidden, d_model)

    def forward(self, activations: torch.Tensor):
        features = torch.relu(self.encoder(activations))  # 음수 특징 제거
        reconstruction = self.decoder(features)
        return reconstruction, features

def loss_fn(reconstruction, original, features, l1_coeff=1e-3):
    recon_loss = ((reconstruction - original) ** 2).mean()
    sparsity_loss = features.abs().sum(dim=-1).mean()  # L1 페널티로 희소성 강제
    return recon_loss + l1_coeff * sparsity_loss
```

L1 계수를 높일수록 각 입력에서 활성화되는 특징 수는 줄지만 재구성 오차는 커지므로, 이 둘 사이의 균형점을 찾는 것이 SAE 학습의 핵심 튜닝 포인트다.

## 실무 포인트

- **SAE로 찾은 특징이 항상 완벽하게 단의적이지는 않다.** 여전히 일부 특징은 여러 개념에 걸쳐 있으며, "dead feature"(전혀 활성화되지 않는 특징)나 특징 흡수(feature absorption) 같은 알려진 실패 모드가 있어 결과 해석에 주의가 필요하다.
- **이 기법은 프로덕션 안전장치가 아니라 연구·감사 도구에 가깝다.** 현재는 대규모로 실시간 가드레일에 적용하기보다, 특정 위험 행동(예: 기만적 응답 경향)의 원인을 사후 분석하는 용도로 주로 쓰인다.
- **특징 수와 모델 규모에 따라 학습 비용이 상당하다.** 수백만~수천만 개의 특징을 학습시키려면 대량의 활성화 데이터 수집과 별도의 GPU 학습 파이프라인이 필요하다.

## 마무리 요약

- 트랜스포머 뉴런의 다의성은 중첩 가설로 설명되며, 여러 개념이 뉴런들의 선형 결합 방향으로 압축 저장되기 때문에 뉴런 단위 분석만으로는 의미를 특정할 수 없다.
- Sparse Autoencoder는 활성화를 과대완비 특징 공간으로 인코딩·디코딩하며 희소성 페널티를 걸어, 대부분 단의적인 해석 가능한 특징 방향을 찾아낸다.
- 찾아낸 특징을 인위적으로 켜고 끄는 개입 실험을 통해 실제 인과관계를 검증하고, 특징 간 연결을 추적해 서킷 수준의 설명을 얻을 수 있지만 아직 연구·감사 단계의 도구다.

## 참고 자료

- [Anthropic — Towards Monosemanticity](https://transformer-circuits.pub/2023/monosemantic-features)
- [Anthropic — Scaling Monosemanticity](https://transformer-circuits.pub/2024/scaling-monosemanticity/)
