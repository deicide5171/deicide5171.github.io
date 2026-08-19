---
layout: single
title: "모든 작업에 GPT급이 필요한 건 아니다 — SLM을 프로덕션에 투입하기"
date: 2026-08-27 13:50:00 +0530
categories: ai
tags: ["slm", "small-language-models", "llm", "cost-optimization", "model-routing"]
toc: true
toc_sticky: true
excerpt: "분류, 추출, 라우팅처럼 범위가 좁은 작업까지 매번 대형 모델을 호출하는 건 낭비다. 소형 언어모델(SLM)을 프로덕션에 투입하는 기준과 아키텍처를 정리한다."
---

"어떤 모델을 쓸까"라는 질문에 자동으로 최상위 플래그십 모델을 떠올리는 팀이 많다. 그런데 실제 프로덕션 워크로드를 뜯어보면, 감정 분류, 카테고리 태깅, 짧은 텍스트 요약, 인텐트 라우팅처럼 입력과 출력 공간이 명확히 좁은 작업이 상당 비중을 차지한다. 이런 작업에 매번 대형 모델을 호출하는 것은 트럭으로 편의점 심부름을 보내는 것과 비슷하다 — 되긴 하지만 지연시간과 비용이 그만큼 든다.

Phi, Gemma, Llama 3.2의 1B~3B급, Qwen2.5의 소형 라인업 같은 SLM(Small Language Model)들은 바로 이 좁은 작업 구간에서 대형 모델과 거의 차이 없는 정확도를 내면서 지연시간은 수십 밀리초, 비용은 수십 분의 1로 줄인다. 이 글에서는 SLM을 프로덕션에 투입할지 판단하는 기준과 실무 아키텍처를 정리한다.

## 핵심 개념 1: SLM이 유리한 조건과 불리한 조건

SLM 도입 여부는 "작업이 얼마나 좁은가"와 "정확도 요구 수준"의 교집합으로 결정된다.

| 조건 | SLM 적합 | 대형 모델 필요 |
|---|---|---|
| 출력 공간 | 고정된 카테고리(분류, 라우팅) | 자유 형식 긴 텍스트 생성 |
| 추론 난이도 | 패턴 매칭 수준(감정, 스팸 판별) | 다단계 추론, 복잡한 코드 생성 |
| 지연시간 요구 | 실시간(수십 ms) | 수 초 허용 |
| 데이터 민감도 | 온프레미스/엣지 필요 | 클라우드 API 허용 |
| 학습 데이터 확보 | 파인튜닝용 라벨 데이터 존재 | 제로샷 일반화 필요 |

핵심은 "작업이 좁을수록, 그리고 그 작업에 맞춰 파인튜닝할 데이터가 있을수록" SLM이 유리해진다는 점이다. 반대로 다양한 도메인을 넘나드는 개방형 질의응답이나 긴 추론 체인이 필요한 작업은 여전히 대형 모델이 안전하다.

## 핵심 개념 2: 증류(distillation)로 SLM 성능 끌어올리기

SLM을 그냥 파운데이션 모델 그대로 쓰면 특정 작업에서 대형 모델보다 정확도가 떨어질 수 있다. 이를 메우는 표준적인 방법이 지식 증류다. 대형 모델(교사)에게 대량의 입력을 넣어 출력을 생성시키고, 이 입출력 쌍을 SLM(학생)의 파인튜닝 데이터로 사용한다. 실무에서는 "교사 모델로 우리 실제 트래픽 샘플 수천~수만 건에 라벨을 만들고, 그걸로 SLM을 LoRA 파인튜닝"하는 흐름이 흔하다.

<img src="/assets/images/posts/2026-08-27-small-language-models-production-1.svg" alt="사용자 요청이 먼저 SLM 라우터를 거쳐 신뢰도가 높으면 SLM이 즉시 응답하고 낮으면 대형 모델로 에스컬레이션되는 아키텍처 흐름도" style="width:100%;">

## 예제: 신뢰도 기반 라우팅 (SLM 우선, 필요시 대형 모델 에스컬레이션)

```python
def classify_intent(user_message: str) -> dict:
    # 1차: SLM으로 빠르게 분류 시도 (로컬 vLLM 서빙, 3B 모델)
    slm_result = slm_client.classify(
        prompt=build_classification_prompt(user_message),
        return_logprobs=True,
    )
    confidence = slm_result.top_logprob_as_probability()

    if confidence >= 0.85:
        return {"intent": slm_result.label, "model": "slm", "confidence": confidence}

    # 2차: 신뢰도가 낮으면 대형 모델로 에스컬레이션
    llm_result = llm_client.classify(user_message)
    return {"intent": llm_result.label, "model": "escalated-llm", "confidence": None}
```

이 패턴은 트래픽의 대부분(신뢰도가 높은 쉬운 케이스)을 SLM이 처리하고, 애매한 소수 케이스만 대형 모델로 넘겨 전체 비용과 지연시간의 가중평균을 크게 낮춘다.

## 실무 포인트

- **에스컬레이션 비율을 지속 모니터링한다**: 에스컬레이션 비율이 예상보다 높다면 SLM 파인튜닝 데이터가 실제 트래픽 분포를 충분히 반영하지 못한다는 신호다. 실패 케이스를 주기적으로 수집해 재학습 데이터에 추가하는 파이프라인이 필요하다.
- **정확도뿐 아니라 실패 모드도 비교한다**: SLM은 전체 정확도는 비슷해도 특정 엣지 케이스(드문 카테고리, 애매한 표현)에서 실패 패턴이 대형 모델과 다르게 나타난다. A/B 테스트에서 평균 지표만 보지 말고 실패 사례를 직접 검토해야 한다.
- **온디바이스/엣지 배포는 양자화와 함께 검토한다**: 엣지 환경(모바일, IoT)까지 노린다면 SLM에 4비트 양자화(GGUF, AWQ)를 추가로 적용해 메모리 풋프린트를 더 줄이는 것이 일반적이다. 다만 양자화가 특정 작업의 정확도를 얼마나 깎는지는 반드시 자체 평가셋으로 검증해야 한다.

## 3줄 요약

- 분류·추출·라우팅처럼 출력 공간이 좁은 작업은 SLM으로도 대형 모델과 근접한 정확도를 내면서 비용과 지연시간을 크게 줄일 수 있다.
- 대형 모델의 출력을 교사 데이터로 삼아 SLM을 증류·파인튜닝하면 좁은 작업에서의 정확도 격차를 상당 부분 메울 수 있다.
- SLM 우선 처리 후 신뢰도가 낮은 케이스만 대형 모델로 에스컬레이션하는 라우팅 구조가 비용 대비 정확도를 가장 잘 절충한다.

## 참고 자료

- [Hugging Face: Small Language Models 가이드](https://huggingface.co/blog/smollm)
- [Microsoft Phi 모델 공식 문서](https://azure.microsoft.com/en-us/products/phi)
- [Google Gemma 공식 문서](https://ai.google.dev/gemma)
