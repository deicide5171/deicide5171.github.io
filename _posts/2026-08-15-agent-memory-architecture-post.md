---
layout: single
title: "AI 에이전트도 기억이 필요하다 — 3계층 메모리 아키텍처 설계"
date: 2026-08-15 11:50:00 +0530
categories: ai
tags: ["ai", "agent", "memory", "rag", "context-window"]
toc: true
toc_sticky: true
excerpt: "세션이 끝나면 모든 걸 잊는 에이전트의 한계를 넘기 위해, OS 메모리 계층에서 착안한 Core·Recall·Archival 3계층 메모리 아키텍처와 최근 벤치마크 동향을 정리한다."
---

## 왜 지금 에이전트 메모리인가

지금까지 에이전트 관련 논의는 주로 "어떤 모델을 쓸까", "도구를 어떻게 연결할까"에 집중돼 있었다. MCP나 A2A 같은 프로토콜이 에이전트와 도구, 에이전트와 에이전트를 연결하는 문제를 풀었다면, 남은 문제는 하나다. 대화가 끝나고 세션이 닫히면 에이전트는 사용자에 대해 아무것도 기억하지 못한다.

장기간 협업하는 코딩 에이전트, 몇 주에 걸쳐 프로젝트를 진행하는 리서치 에이전트가 늘어나면서 "지난주에 뭘 했는지", "이 사용자가 어떤 선호를 가졌는지"를 기억하는 능력이 제품 경쟁력으로 부상했다. 그래서 에이전트 메모리는 이제 단순한 RAG 응용이 아니라, 자체 벤치마크(LoCoMo, LongMemEval 등)와 전용 아키텍처 패턴을 가진 독립된 연구·엔지니어링 영역으로 자리 잡았다.

## 핵심 개념: OS에서 빌려온 3계층 구조

가장 널리 참조되는 설계는 운영체제의 메모리 계층 구조를 그대로 빌려온 것이다. RAM·캐시·디스크가 속도와 용량을 맞바꾸듯, 에이전트 메모리도 접근 속도와 저장 용량을 맞바꾸는 3단계로 나뉜다.

| 계층 | OS 비유 | 저장 위치 | 역할 |
|---|---|---|---|
| Core Memory | RAM | LLM 컨텍스트 윈도우 안 | 현재 대화, 사용자 프로필 등 항상 참조되는 정보 |
| Recall Memory | 디스크 캐시 | 검색 가능한 대화 이력 | 최근 세션 기록, 필요할 때 불러와 컨텍스트에 주입 |
| Archival Memory | 콜드 스토리지 | 벡터 DB·구조화 저장소 | 오래된 정보, 명시적 쿼리로만 조회하는 장기 기억 |

Core Memory는 매 요청마다 토큰 비용을 지불하므로 용량이 가장 제한적이다. Recall과 Archival은 벡터 검색이나 키워드 검색으로 필요한 순간에만 끌어와 컨텍스트에 삽입하는 방식으로 동작한다. 이 구조 덕분에 에이전트는 컨텍스트 윈도우 크기에 얽매이지 않고 사실상 무한한 기억 용량을 가진 것처럼 행동할 수 있다.

## 아키텍처 패턴: MemSync와 동기화 문제

최근 부각되는 패턴 중 하나가 **MemSync**다. 하나의 에이전트가 여러 기기·여러 도구 경계를 넘나들며 동작할 때, 메모리 상태를 어떻게 일관되게 유지할지가 문제가 된다. MemSync는 에이전트 메모리를 분산 시스템처럼 취급하고, 최종적 일관성(eventual consistency) 모델을 적용해 이 문제를 푼다.

이 접근은 단일 세션·단일 기기 환경에서는 과할 수 있지만, "웹에서 시작한 작업을 모바일 앱에서 이어간다"처럼 멀티 엔드포인트 시나리오가 흔해지면서 실무 요구사항으로 떠오르고 있다.

## 예제: 계층형 메모리 조회 흐름 (Python 의사코드)

```python
def build_context(user_id, user_message, core_budget=2000):
    core = load_core_memory(user_id)  # 항상 포함 (사용자 프로필, 최근 요약)

    # Recall: 최근 대화에서 관련도 높은 항목만 검색
    recall_hits = recall_store.search(
        query=user_message, user_id=user_id, top_k=5
    )

    # Archival: 명시적으로 필요하다고 판단될 때만 조회
    archival_hits = []
    if needs_long_term_lookup(user_message):
        archival_hits = archival_store.query(
            query=user_message, user_id=user_id, top_k=3
        )

    context = assemble(core, recall_hits, archival_hits, budget=core_budget)
    return context
```

핵심은 `needs_long_term_lookup`처럼 "지금 이 질문이 장기 기억을 필요로 하는가"를 판단하는 라우팅 로직이다. 매 요청마다 Archival까지 뒤지면 지연시간과 비용이 커지므로, 대부분의 실전 구현은 이 판단 단계를 별도 경량 모델이나 규칙 기반으로 처리한다.

## 실무 포인트

- **모든 대화를 저장하지 않는다**: Recall Memory에 원문을 그대로 쌓으면 검색 품질이 떨어진다. 요약·엔티티 추출 후 저장하는 편이 검색 정확도와 비용 모두에 유리하다.
- **출처 추적(provenance)을 남긴다**: "이 기억이 언제, 어떤 대화에서 만들어졌는가"를 함께 저장해야 오래된 정보와 최신 정보가 충돌할 때 우선순위를 판단할 수 있다.
- **메모리 신선도(staleness) 정책이 필요하다**: 사용자의 선호나 프로젝트 상태는 시간이 지나면 바뀐다. 오래된 기억을 자동으로 낮은 신뢰도로 처리하거나 만료시키는 규칙이 없으면 에이전트가 틀린 전제로 답하게 된다.
- **벤치마크로 검증한다**: LoCoMo, LongMemEval, BEAM 같은 장기 기억 벤치마크로 "며칠 전 언급을 정확히 다시 꺼내는지"를 정기적으로 측정하는 것이 좋다.

## 3줄 요약

- 에이전트 메모리는 Core(컨텍스트 내)·Recall(검색 가능한 최근 기록)·Archival(장기 저장) 3계층으로 나눠 속도와 용량을 맞바꾸는 것이 기본 설계다.
- 여러 기기·도구 경계를 넘는 에이전트에는 메모리를 분산 시스템처럼 다루는 MemSync 같은 동기화 패턴이 필요하다.
- 저장 시 요약·출처·신선도 관리를 함께 설계해야 장기 기억이 실제로 신뢰할 수 있는 정보로 남는다.

## 참고 자료

- [LongMemEval: Benchmarking Long-Term Memory](https://arxiv.org/abs/2410.10813)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- 정확한 시장 규모·성장률 수치는 조사 시점에 따라 달라지므로 최신 리포트를 직접 확인하는 것을 권장한다.
