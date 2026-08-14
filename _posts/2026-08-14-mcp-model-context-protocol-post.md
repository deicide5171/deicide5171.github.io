---
layout: single
title: "AI 에이전트 시대의 연결 표준, MCP(Model Context Protocol) 정리"
date: 2026-08-14 12:00:00 +0900
categories: ai
tags: ["ai", "mcp", "agent", "llm", "architecture"]
toc: true
toc_sticky: true
excerpt: "AI 에이전트가 외부 도구·데이터와 연결되는 방식을 표준화한 MCP의 구조와 핵심 개념, 최소 예제, 실무 도입 시 주의점을 정리한다."
---

## 왜 지금 MCP인가

LLM 활용의 중심이 "채팅"에서 "에이전트"로 옮겨가고 있다. 이제 모델은 단순히 답변만 생성하는 것이 아니라 직접 파일을 읽고, DB를 조회하고, 외부 API를 호출하면서 작업을 수행한다.

문제는 연결 방식이었다. 모델마다, 도구마다 통합 코드를 따로 만들어야 했기 때문에 모델 N개 × 도구 M개 = **N×M 통합 문제**가 발생했다. 새 도구 하나를 붙이려면 모든 AI 앱에 맞춰 어댑터를 다시 짜야 했던 것이다.

**MCP(Model Context Protocol)** 는 이 연결 방식을 표준화한 오픈 프로토콜이다. 2024년 11월 Anthropic이 공개한 이후 OpenAI, Google 등 주요 사업자와 수많은 개발 도구가 채택하면서 사실상의 표준으로 자리 잡았다. 흔히 **"AI 업계의 USB-C"** 라고 비유된다. 어떤 기기든 하나의 포트 규격으로 연결되듯, 어떤 AI 앱이든 MCP만 지원하면 같은 도구 생태계를 공유할 수 있다.

## 아키텍처: Host / Client / Server

MCP는 세 가지 구성 요소로 이루어진다.

| 구성 요소 | 역할 | 예시 |
|---|---|---|
| **Host** | 사용자와 만나는 AI 애플리케이션 | Claude Desktop, IDE, 챗봇 서비스 |
| **Client** | Host 내부에서 서버와 1:1 연결을 유지하는 커넥터 | Host에 내장 |
| **Server** | 도구·데이터를 표준 방식으로 노출하는 경량 프로세스 | GitHub 서버, DB 조회 서버, 사내 API 래퍼 |

전송 방식은 두 가지다.

- **stdio**: 로컬 프로세스로 띄워서 표준 입출력으로 통신 (개인 개발 환경에 적합)
- **Streamable HTTP**: 원격 서버로 배포해서 HTTP로 통신 (팀·조직 단위 공유에 적합)

## 서버가 노출하는 3가지 기능

MCP 서버는 세 종류의 기능을 제공할 수 있다.

- **Tools**: 모델이 호출하는 함수. 검색, 파일 쓰기, API 호출처럼 부수효과가 있는 동작을 담당한다.
- **Resources**: 읽기 전용 데이터. 파일 내용, DB 스키마처럼 모델에게 컨텍스트로 제공되는 정보다.
- **Prompts**: 재사용 가능한 프롬프트 템플릿. 자주 쓰는 작업 지시를 서버 쪽에 정의해 둔다.

"모델이 실행하는 것(Tools)"과 "모델이 읽는 것(Resources)"을 구분한다는 점이 설계상 중요한 포인트다. 권한 관리의 경계가 여기서 갈린다.

## 최소 예제로 감 잡기

Python SDK(FastMCP)를 쓰면 서버를 몇 줄로 만들 수 있다.

```python
# weather_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")

@mcp.tool()
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 반환한다."""
    # 실제로는 날씨 API를 호출
    return f"{city}: 맑음, 27도"

if __name__ == "__main__":
    mcp.run()
```

이 서버를 Claude Desktop 같은 호스트에 등록하는 설정은 JSON 몇 줄이면 된다.

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["weather_server.py"]
    }
  }
}
```

이제 호스트의 모델은 "서울 날씨 어때?"라는 질문을 받으면 `get_weather` 도구를 스스로 찾아 호출한다. 함수 시그니처와 docstring이 곧 모델에게 전달되는 인터페이스 명세가 된다.

## 아키텍처 관점에서 본 의미

MCP의 본질은 **어댑터 패턴의 표준화**다.

- 통합 비용이 N×M에서 **N+M**으로 줄어든다. 도구는 MCP 서버를 한 번만 구현하면 되고, AI 앱은 MCP 클라이언트를 한 번만 구현하면 된다.
- 특정 벤더에 종속되지 않는다. 호스트(AI 앱)를 바꿔도 이미 구축한 서버 생태계는 그대로 재사용된다.
- 조직 입장에서는 사내 DB, 내부 API, 레거시 시스템을 MCP 서버로 한 번 감싸 두면 어떤 AI 도구에서든 재사용할 수 있다. AI 도입의 인프라 계층이 되는 셈이다.

## 실무 도입 시 주의점

편리함만큼 공격 표면도 늘어난다. 도입 전에 반드시 짚어야 할 것들:

1. **프롬프트 인젝션**: 서버가 가져온 외부 데이터(웹페이지, 이슈 코멘트 등)에 악의적 지시문이 섞여 있으면 모델이 이를 명령으로 오인할 수 있다. 외부 데이터는 "명령"이 아니라 "데이터"로 취급하는 방어 설계가 필요하다.
2. **최소 권한 원칙**: 읽기 전용으로 충분한 서버에 쓰기 권한을 주지 말 것. Tools와 Resources의 구분을 권한 경계로 활용한다.
3. **위험한 동작에는 승인 게이트**: 삭제, 결제, 외부 발송처럼 되돌리기 어려운 동작은 사람의 확인(Human-in-the-loop)을 거치도록 설계한다.
4. **공급망 검증**: 서드파티 MCP 서버는 코드를 확인하고 신뢰할 수 있는 출처의 것만 설치한다. npm 패키지 검증과 같은 관점이 필요하다.
5. **감사 로그**: 어떤 도구가 언제 어떤 인자로 호출됐는지 기록해야 사고 시 추적이 가능하다.

## 마무리

- MCP는 AI 앱과 도구·데이터를 잇는 표준 프로토콜로, N×M 통합 문제를 N+M으로 바꿨다.
- Host/Client/Server 구조에서 서버는 Tools(실행), Resources(읽기), Prompts(템플릿)를 노출한다.
- 도입 효과가 큰 만큼 최소 권한, 승인 게이트, 공급망 검증 같은 보안 설계를 함께 가져가야 한다.

## 참고 자료

- [MCP 공식 사이트](https://modelcontextprotocol.io)
- [MCP 명세(Specification)](https://modelcontextprotocol.io/specification)
- [Python SDK (GitHub)](https://github.com/modelcontextprotocol/python-sdk)
