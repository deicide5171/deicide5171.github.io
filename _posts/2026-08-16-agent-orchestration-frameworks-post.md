---
layout: single
title: "LangGraph vs CrewAI vs AutoGen — 멀티 에이전트 오케스트레이션 프레임워크 실전 비교"
date: 2026-08-16 12:50:00 +0530
categories: ai
tags: ["langgraph", "crewai", "autogen", "multi-agent", "orchestration"]
toc: true
toc_sticky: true
excerpt: "단일 LLM 호출로는 감당이 안 되는 작업이 늘면서 여러 에이전트를 조율하는 오케스트레이션 프레임워크가 필수 인프라가 됐다. LangGraph, CrewAI, AutoGen의 설계 철학 차이를 비교하고 선택 기준을 정리한다."
---

## 왜 지금 오케스트레이션 프레임워크인가

프롬프트 하나로 답을 얻던 시기를 지나, 이제는 "여러 에이전트가 역할을 나눠 협업하는" 구조를 실무에 적용하는 팀이 늘고 있다. 리서치 에이전트가 자료를 모으고, 검토 에이전트가 사실 검증을 하고, 작성 에이전트가 결과를 정리하는 파이프라인은 더 이상 실험실 데모가 아니다. 문제는 이 협업을 어떻게 코드로 표현하느냐다 — 메시지 전달, 상태 공유, 실패 시 재시도, 사람의 승인 개입까지 직접 구현하려면 복잡도가 순식간에 치솟는다.

이 빈틈을 메우는 것이 에이전트 오케스트레이션 프레임워크다. 그중 **LangGraph**, **CrewAI**, **AutoGen** 세 가지가 가장 널리 언급되는데, 셋 다 같은 문제를 풀지만 접근 방식은 상당히 다르다. 어떤 프레임워크를 선택하느냐에 따라 이후 유지보수 방식과 확장 전략이 크게 갈리므로, 설계 철학 차이를 먼저 이해하는 것이 중요하다.

## 핵심 개념 1: 세 프레임워크의 설계 철학

세 프레임워크는 협업을 표현하는 **기본 단위**가 다르다. LangGraph는 노드와 엣지로 이루어진 상태 그래프(State Graph)로 흐름을 표현하고, CrewAI는 역할(Role)을 가진 에이전트 팀이 태스크를 나눠 맡는 조직 구조로 표현하며, AutoGen은 에이전트 간 대화(Conversation) 메시지 교환으로 표현한다.

| 항목 | LangGraph | CrewAI | AutoGen |
|---|---|---|---|
| 제작 주체 | LangChain 팀 | 독립 오픈소스 | Microsoft Research |
| 핵심 추상화 | 상태 그래프(노드·엣지) | Agent·Task·Crew | Conversable Agent |
| 흐름 제어 | 명시적 그래프 + 조건부 엣지 | 순차/계층 프로세스 | 대화 턴 교환 + GroupChat |
| 사이클(반복) | 엣지로 명시적 표현 | 세밀 제어 제한적 | 종료 조건 필요 |
| 상태 영속성 | 체크포인트 내장(휴먼인더루프 유리) | 제한적 | 제한적 |
| 학습 곡선 | 상대적으로 높음 | 낮음(역할극 비유) | 중간 |

## 핵심 개념 2: 언제 무엇을 선택할까

세 프레임워크 중 무엇이 "더 낫다"는 절대적 정답은 없다. 워크플로우의 성격에 따라 적합도가 달라진다.

| 상황 | 적합한 선택 | 이유 |
|---|---|---|
| 분기·재시도·사람 승인이 섞인 복잡한 파이프라인 | LangGraph | 조건부 엣지와 체크포인트로 제어 흐름을 그래프로 명시 |
| 리서치 팀·콘텐츠 제작 팀 같은 역할극 프로토타입 | CrewAI | Role·Goal·Backstory가 직관적이라 빠르게 구현 가능 |
| 코드 리뷰·브레인스토밍처럼 자유 토론이 필요한 작업 | AutoGen | GroupChat 구조가 다자간 토론 패턴을 자연스럽게 표현 |
| 기존 LangChain 체인·툴 자산 재사용이 필요한 경우 | LangGraph | LangChain 생태계와 통합이 긴밀함 |

## 예제 1: LangGraph로 조건부 분기 그래프 만들기

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    is_done: bool

def call_agent(state: AgentState) -> AgentState:
    # LLM 호출 로직 (생략)
    state["messages"].append("에이전트 응답")
    return state

def call_tool(state: AgentState) -> AgentState:
    # 도구 실행 로직 (생략)
    state["is_done"] = True
    return state

def route(state: AgentState) -> str:
    return "end" if state["is_done"] else "tool"

graph = StateGraph(AgentState)
graph.add_node("agent", call_agent)
graph.add_node("tool", call_tool)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", route, {"tool": "tool", "end": END})
graph.add_edge("tool", "agent")  # 도구 실행 후 다시 에이전트로 순환

app = graph.compile()
result = app.invoke({"messages": [], "is_done": False})
```

`add_conditional_edges`로 분기 조건을 명시하고, `add_edge`로 순환 경로를 만드는 방식이 LangGraph의 핵심이다. 상태(`AgentState`)가 그래프 전체를 관통하며 각 노드는 이 상태를 읽고 갱신할 뿐이라, 흐름이 아무리 복잡해져도 "지금 상태가 무엇인가"만 추적하면 디버깅이 가능하다.

## 예제 2: CrewAI로 역할 기반 에이전트 팀 구성하기

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(
    role="리서처",
    goal="주제에 대한 최신 자료를 정확하게 수집한다",
    backstory="꼼꼼한 조사 전문가",
)

writer = Agent(
    role="작성자",
    goal="수집된 자료를 바탕으로 읽기 쉬운 보고서를 작성한다",
    backstory="명료한 글쓰기를 중시하는 에디터",
)

research_task = Task(
    description="주어진 주제에 대한 핵심 자료를 조사한다",
    agent=researcher,
    expected_output="핵심 사실 목록",
)

writing_task = Task(
    description="조사 결과를 바탕으로 보고서를 작성한다",
    agent=writer,
    expected_output="완성된 보고서 초안",
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
)

result = crew.kickoff()
```

CrewAI는 `role`·`goal`·`backstory`로 에이전트의 페르소나를 정의하고, `Task`로 각 에이전트가 맡을 작업을 명시한 뒤 `Crew`가 이를 순서대로(또는 계층적으로) 실행한다. LangGraph만큼 세밀한 분기 제어는 어렵지만, "어떤 역할이 어떤 일을 하는가"가 코드만 봐도 바로 읽힌다는 장점이 있다.

<img src="/assets/images/posts/2026-08-16-agent-orchestration-frameworks-1.svg" alt="LangGraph 그래프 기반, CrewAI 역할 기반, AutoGen 대화 기반 오케스트레이션 패러다임 비교도" style="width:100%;">

## 실무 포인트

- **작업 성격을 먼저 분석한다**: 분기·재시도가 많으면 LangGraph, 역할 분담이 명확하면 CrewAI, 자유 토론이 필요하면 AutoGen이 자연스럽다. 프레임워크를 먼저 정하고 워크플로우를 끼워 맞추면 나중에 리팩터링 비용이 커진다.
- **프레임워크 혼용도 가능하다**: 상위 오케스트레이션은 LangGraph로 짜고, 그 안 한 노드에서 CrewAI 크루를 서브루틴처럼 호출하는 조합도 실무에서 쓰인다.
- **관측성(Observability)을 처음부터 설계한다**: 에이전트가 늘어날수록 어느 단계에서 어떤 프롬프트·응답이 오갔는지 추적하기 어려워진다. 노드·태스크·대화 턴마다 로그를 남기는 구조를 초기에 넣어야 디버깅이 가능하다.
- **종료 조건을 명시적으로 둔다**: 대화형 구조나 순환 엣지는 종료 조건이 허술하면 무한 루프나 불필요한 LLM 호출 비용으로 이어진다. 최대 반복 횟수 같은 안전장치를 반드시 둔다.
- **API 변경 여부를 주기적으로 확인한다**: 세 프레임워크 모두 빠르게 발전하는 생태계에 속하므로, 프로덕션 적용 전 최신 공식 문서를 확인하는 습관이 필요하다.

## 3줄 요약

- LangGraph는 그래프 기반 상태 전이, CrewAI는 역할 기반 에이전트 팀, AutoGen은 대화 기반 다중 에이전트 협업으로 각각 다른 방식으로 "여러 에이전트의 협업"을 표현한다.
- 분기·재시도가 많은 파이프라인은 LangGraph, 빠른 역할극 프로토타입은 CrewAI, 자유 토론형 작업은 AutoGen이 자연스러운 선택지다.
- 실무에서는 관측성과 종료 조건을 처음부터 설계에 포함시켜야 프레임워크 선택과 무관하게 안정적으로 운영할 수 있다.

## 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [CrewAI 공식 문서](https://docs.crewai.com/)
- [AutoGen 공식 문서 (Microsoft)](https://microsoft.github.io/autogen/)
