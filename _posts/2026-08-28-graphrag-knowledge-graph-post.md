---
layout: single
title: "벡터 검색이 놓치는 관계를 잡는다 — GraphRAG, 지식그래프 결합 검색 증강 생성"
date: 2026-08-28 13:50:00 +0530
categories: ai
tags: ["ai", "graphrag", "knowledge-graph", "rag", "llm"]
toc: true
toc_sticky: true
excerpt: "임베딩 유사도만으로는 답할 수 없는 다중 홉 관계 질문을, 문서에서 추출한 지식그래프와 커뮤니티 요약을 결합해 답하는 GraphRAG의 구조와 일반 RAG 대비 트레이드오프를 정리한다."
---

일반적인 RAG(Retrieval-Augmented Generation)는 질문을 임베딩하고, 벡터 DB에서 의미적으로 가장 가까운 문서 조각을 찾아 컨텍스트로 넣는다. 이 방식은 "질문과 비슷한 내용을 담은 문서를 찾는" 단일 홉 검색에는 잘 맞지만, "A 회사를 인수한 B 회사의 CEO가 이전에 몸담았던 회사는 어디인가"처럼 여러 문서에 흩어진 사실을 연결해야 답할 수 있는 **다중 홉(multi-hop)** 질문에는 취약하다. 각 사실이 서로 다른 문서 조각에 있으면 벡터 유사도만으로는 그 조각들이 서로 연결돼야 한다는 것 자체를 알아낼 방법이 없기 때문이다.

**GraphRAG**는 이 한계를 문서에서 개체(entity)와 관계(relation)를 미리 추출해 지식그래프로 구성해두고, 검색 시 벡터 유사도 대신(또는 함께) 그래프 순회로 관련 정보를 모으는 방식으로 보완한다. Microsoft Research가 2024년 공개한 GraphRAG 논문과 오픈소스 구현이 이 접근을 널리 알렸고, 이후 여러 변형이 등장했다. 이 글에서는 GraphRAG의 핵심 구성 요소와, 모든 RAG를 GraphRAG로 바꿔야 하는 것은 아닌 이유를 정리한다.

## 핵심 개념 1: 인덱싱 단계 — 그래프를 미리 만들어둔다

GraphRAG는 질의 시점이 아니라 **인덱싱 단계**에서 대부분의 무거운 작업을 끝낸다. 문서를 청크로 나눈 뒤 LLM으로 각 청크에서 개체(사람, 조직, 장소, 개념 등)와 그 사이의 관계를 추출해 그래프 형태로 저장한다. 이어서 그래프 커뮤니티 탐지 알고리즘(Leiden 알고리즘 등)으로 서로 밀접하게 연결된 개체 군집을 찾아내고, 각 군집에 대한 **요약(community summary)**을 LLM으로 미리 생성해둔다. 이 요약이 나중에 "이 문서 전체의 주제가 무엇인가" 같은 전역적 질문에 답할 때 핵심 자료가 된다.

이 사전 처리 비용이 GraphRAG의 가장 큰 트레이드오프다. 일반 RAG는 문서를 임베딩만 하면 끝나지만, GraphRAG는 문서마다 개체·관계 추출에 LLM 호출이 여러 번 들어가므로 인덱싱 비용과 시간이 훨씬 크다.

## 핵심 개념 2: 질의 단계 — 로컬 검색 vs 글로벌 검색

GraphRAG는 질문 유형에 따라 두 가지 검색 모드를 구분한다. **로컬 검색(local search)**은 질문에 언급된 특정 개체에서 출발해 그래프를 몇 홉 순회하며 관련된 이웃 개체와 그 사이 관계, 원본 텍스트 조각을 함께 모은다. "이 인수 건에서 CEO가 누구인가"처럼 구체적 개체 중심 질문에 적합하다. **글로벌 검색(global search)**은 특정 개체가 아니라 문서 전체를 아우르는 질문("이 문서 모음의 핵심 주제는 무엇인가")에 답하기 위해, 미리 만들어둔 커뮤니티 요약들을 순회하며 부분 답변을 모으고 이를 다시 종합한다.

| 검색 모드 | 적합한 질문 유형 | 사용하는 자료 |
|---|---|---|
| 벡터 유사도 검색(일반 RAG) | 단일 사실 확인, 유사 문서 찾기 | 청크 임베딩 |
| 로컬 검색(GraphRAG) | 특정 개체 중심 다중 홉 관계 질문 | 개체 이웃 그래프 + 원본 텍스트 |
| 글로벌 검색(GraphRAG) | 문서 전체를 아우르는 주제·요약 질문 | 커뮤니티 요약 |

<img src="/assets/images/posts/2026-08-28-graphrag-knowledge-graph-1.svg" alt="문서에서 개체와 관계를 추출해 지식그래프를 만들고, 커뮤니티 탐지로 군집을 묶어 요약을 생성한 뒤, 로컬 검색과 글로벌 검색으로 나눠 질의에 답하는 GraphRAG 파이프라인" style="width:100%;">

## 핵심 개념 3: GraphRAG가 유리한 경우와 불필요한 경우

모든 RAG 시스템을 GraphRAG로 바꿀 필요는 없다. 문서 사이에 명시적 관계가 적고 질문 대부분이 "이 개념에 대해 설명해줘" 같은 단일 문서 조회로 충분하다면, 인덱싱 비용이 훨씬 낮은 일반 RAG가 합리적이다. 반대로 조직도, 인수합병 이력, 규정 간 참조 관계처럼 개체 간 관계 자체가 질문의 핵심이 되는 도메인(법률 문서, 기업 리서치, 의료 기록 연계)에서는 GraphRAG가 벡터 검색만으로 놓치던 답을 찾아낸다.

## 예제: 그래프 인덱싱과 로컬 검색 흐름 (의사코드)

```python
# 1. 인덱싱: 청크에서 개체·관계 추출
for chunk in document_chunks:
    entities, relations = llm_extract_entities_relations(chunk)
    graph.add_entities(entities, source_chunk=chunk.id)
    graph.add_relations(relations, source_chunk=chunk.id)

# 2. 커뮤니티 탐지 + 요약 생성 (인덱싱 단계에서 미리 계산)
communities = leiden_community_detection(graph)
community_summaries = {
    c.id: llm_summarize(c.entities, c.relations) for c in communities
}

# 3. 질의 단계: 로컬 검색
def local_search(question):
    seed_entities = extract_entities_from_question(question)  # LLM 또는 NER
    subgraph = graph.expand_neighbors(seed_entities, hops=2)
    context = subgraph.entities_text() + subgraph.relations_text() + subgraph.source_chunks()
    return llm_generate_answer(question, context)

# 4. 질의 단계: 글로벌 검색 (문서 전체를 아우르는 질문용)
def global_search(question):
    partial_answers = [
        llm_answer_from_summary(question, summary)
        for summary in community_summaries.values()
    ]
    return llm_reduce_answers(question, partial_answers)
```

로컬 검색의 `hops=2`처럼 그래프 순회 깊이를 얼마나 둘지가 품질과 컨텍스트 크기의 트레이드오프를 결정한다. 홉을 늘리면 더 먼 관계까지 잡아내지만 컨텍스트가 빠르게 커져 LLM 컨텍스트 윈도우와 비용에 부담을 준다.

## 실무 포인트

- **개체 추출 품질이 전체 파이프라인 품질의 상한이다**: LLM이 개체나 관계를 잘못 추출하면 이후 커뮤니티 탐지·검색이 아무리 정교해도 잘못된 그래프 위에서 동작한다. 도메인 특화 개체 스키마(회사, 인물, 제품 등 카테고리 고정)를 미리 정의해 추출 프롬프트에 반영하면 품질이 크게 개선된다.
- **인덱싱 비용을 사전에 가늠할 것**: 문서량이 많으면 개체·관계 추출과 커뮤니티 요약 생성에 드는 LLM 호출 비용이 상당하다. 파일럿으로 소규모 문서 세트에 먼저 적용해 청크당 비용을 측정한 뒤 전체 규모로 확장하는 것이 안전하다.
- **일반 RAG와 병행 운영을 고려할 것**: 실무에서는 질문 유형을 먼저 분류해(단일 사실 vs 관계형 질문) 단순한 질문은 저비용 벡터 검색으로, 관계가 중요한 질문만 GraphRAG 경로로 라우팅하는 하이브리드 구성이 비용 대비 효율적인 경우가 많다.

## 3줄 요약

- GraphRAG는 문서에서 개체와 관계를 미리 추출해 지식그래프로 구성하고, 벡터 유사도만으로는 놓치는 다중 홉 관계 질문에 답한다.
- 로컬 검색은 특정 개체 중심 관계 질문에, 글로벌 검색은 커뮤니티 요약을 통한 문서 전체 주제 질문에 각각 적합하다.
- 인덱싱 비용이 일반 RAG보다 훨씬 크므로, 관계형 질문이 실제로 중요한 도메인에 선별 적용하거나 일반 RAG와 하이브리드로 운영하는 것이 현실적이다.

## 참고 자료

- [Microsoft Research: GraphRAG — Unlocking LLM Discovery on Narrative Private Data](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/)
- [Microsoft GraphRAG GitHub 저장소](https://github.com/microsoft/graphrag)
- [Microsoft GraphRAG 공식 문서: Query Engine](https://microsoft.github.io/graphrag/query/overview/)
