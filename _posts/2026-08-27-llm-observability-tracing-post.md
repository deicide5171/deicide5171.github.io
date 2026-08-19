---
layout: single
title: "블랙박스가 된 LLM 파이프라인 열어보기 — LLM 옵저버빌리티와 트레이싱 실무"
date: 2026-08-27 12:50:00 +0530
categories: ai
tags: ["llm", "observability", "tracing", "langfuse", "opentelemetry", "monitoring"]
toc: true
toc_sticky: true
excerpt: "RAG와 에이전트 체인이 길어질수록 어디서 답이 나빠졌는지 알기 어려워진다. LLM 애플리케이션 전용 트레이싱·옵저버빌리티 설계를 정리한다."
---

RAG 파이프라인 하나가 리트리버 호출, 리랭킹, 프롬프트 조립, LLM 생성, 후처리까지 대여섯 단계를 거치는 일이 흔해졌다. 그런데 프로덕션에서 답변 품질이 떨어졌다는 신고가 들어오면 대부분의 팀은 어느 단계가 문제였는지 재구성하지 못한다. 일반 APM은 HTTP 상태 코드와 응답 시간은 잡아내지만, 그 요청 안에서 어떤 프롬프트가 어떤 컨텍스트로 어떤 모델에 들어갔고 토큰이 몇 개 나왔는지는 보여주지 않는다.

LLM 옵저버빌리티는 이 간극을 메우려는 분야다. Langfuse, LangSmith, Helicone 같은 도구들이 공통으로 하는 일은 하나의 요청을 "트레이스"로, 그 안의 각 단계(리트리버 호출, LLM 호출, 도구 호출)를 "스팬"으로 기록해 요청 하나의 전체 실행 그래프를 재구성 가능하게 만드는 것이다. 이 글에서는 LLM 트레이싱의 데이터 모델과 실무에서 놓치기 쉬운 부분을 정리한다.

## 핵심 개념 1: 트레이스-스팬 모델을 LLM 파이프라인에 맞추기

일반 분산 트레이싱과 구조는 같다. 트레이스 하나가 사용자 요청 하나에 대응하고, 그 아래 스팬들이 리트리버 조회, 프롬프트 조립, LLM 호출, 도구 실행처럼 중첩된다. 다른 점은 스팬에 담기는 내용이다. 일반 스팬은 서비스명·지연시간·상태코드면 충분하지만, LLM 스팬은 **입력 프롬프트 전문, 출력 완성 전문, 모델명과 버전, 입력/출력 토큰 수, 온도 같은 생성 파라미터, 계산된 비용**까지 담아야 사후 디버깅이 가능하다.

OpenTelemetry도 2025년부터 GenAI 시맨틱 컨벤션(`gen_ai.*` 속성)을 표준화하는 중이라, 자체 스택에 OTel을 쓰고 있다면 벤더 SDK 없이도 이 컨벤션으로 스팬을 만들 수 있다. Langfuse·LangSmith 같은 전용 도구는 여기에 프롬프트 버전 관리, 데이터셋 기반 회귀 테스트, 사용자 피드백 연결 같은 LLM 특화 기능을 얹은 것이다.

## 핵심 개념 2: 무엇을 기록하고 무엇을 가려야 하는가

| 항목 | 기록 필요성 | 주의점 |
|---|---|---|
| 프롬프트/완성 전문 | 높음 (디버깅 핵심) | 사용자 PII 포함 가능 — 저장 전 마스킹 정책 필요 |
| 토큰 수·비용 | 높음 | 모델별 단가 변경을 추적해 재계산 가능하게 유지 |
| 리트리버 반환 문서 | 높음 (근거 확인용) | 문서 원문 대신 ID+스니펫만 저장해 용량 절감 |
| 지연시간(스팬별) | 높음 | 스트리밍 응답은 TTFT(첫 토큰까지)와 총 시간을 분리 기록 |
| 사용자 피드백(👍/👎) | 있으면 매우 유용 | 트레이스 ID와 반드시 연결해야 원인 추적 가능 |

원문을 통째로 저장하는 것은 편하지만 개인정보 이슈와 저장 비용을 동시에 키운다. 실무에서는 저장 전 정규식/NER 기반으로 이메일·전화번호·주민번호 패턴을 마스킹하고, 샘플링 비율을 두어(예: 전체의 10% + 에러/저평가 트레이스는 100%) 전수 저장을 피하는 절충이 일반적이다.

<img src="/assets/images/posts/2026-08-27-llm-observability-tracing-1.svg" alt="RAG 파이프라인 요청 하나가 리트리버-리랭커-LLM 호출 스팬으로 중첩되어 하나의 트레이스를 구성하는 구조도" style="width:100%;">

## 예제: Python에서 스팬으로 RAG 파이프라인 계측하기

```python
from langfuse import Langfuse

langfuse = Langfuse()

def answer_query(query: str, user_id: str):
    trace = langfuse.trace(name="rag-answer", user_id=user_id, input=query)

    retrieval_span = trace.span(name="retrieve", input=query)
    docs = retriever.search(query, top_k=5)
    retrieval_span.end(output=[d.id for d in docs])  # 원문 대신 ID만 저장

    generation = trace.generation(
        name="generate",
        model="gpt-4.1-mini",
        input=build_prompt(query, docs),
    )
    completion = llm.chat(build_prompt(query, docs))
    generation.end(
        output=completion.text,
        usage={"input": completion.input_tokens, "output": completion.output_tokens},
    )

    trace.update(output=completion.text)
    return completion.text
```

이렇게 하면 나중에 "이 답변이 왜 이랬는지"를 트레이스 ID 하나로 리트리버가 뭘 가져왔는지부터 최종 프롬프트, 모델 응답까지 순서대로 재생할 수 있다.

## 실무 포인트

- **프롬프트 버전과 트레이스를 반드시 연결한다**: 프롬프트를 수정한 뒤 품질이 좋아졌는지 나빠졌는지는 트레이스에 프롬프트 버전 태그가 없으면 판단할 수 없다. 배포 파이프라인에서 프롬프트 변경 시 버전 태그를 함께 넘기는 규칙을 강제해야 한다.
- **평가(eval)를 트레이스에 붙여야 의미가 생긴다**: 트레이스만 쌓아두고 사람이 눈으로 훑는 건 규모가 커지면 무너진다. LLM-as-judge나 정규식 기반 자동 스코어를 트레이스에 연결해 회귀를 자동 감지하는 게 실질적 가치다.
- **비용 대시보드는 기능/사용자 단위로 쪼갠다**: 전체 비용 합계보다 "이 기능이 하루 얼마를 쓰는지"가 의사결정에 쓰인다. 트레이스 메타데이터에 feature_name, user_id를 태깅해 두면 나중에 비용 폭증의 원인 기능을 바로 짚어낼 수 있다.

## 3줄 요약

- LLM 옵저버빌리티는 일반 APM의 트레이스-스팬 모델에 프롬프트·완성·토큰·비용이라는 LLM 고유 데이터를 얹은 것이다.
- 원문 전수 저장은 PII 위험과 비용을 동시에 키우므로 마스킹과 샘플링 정책이 필수다.
- 트레이스는 프롬프트 버전, 자동 평가 점수, 사용자 피드백과 연결돼야 디버깅과 회귀 감지에 실제로 쓰인다.

## 참고 자료

- [OpenTelemetry: Semantic Conventions for Generative AI systems](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Langfuse 공식 문서: Tracing](https://langfuse.com/docs/tracing)
- [LangSmith 공식 문서: Observability](https://docs.smith.langchain.com/observability)
