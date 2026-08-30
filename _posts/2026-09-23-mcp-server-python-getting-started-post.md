---
layout: single
title: "나만의 MCP 서버 만들기 — Python SDK로 첫 설정하고 흔한 에러 잡기"
date: 2026-09-23 12:50:00 +0530
categories: ai
tags: ["mcp", "modelcontextprotocol", "ai에이전트", "python", "ai도구"]
toc: true
toc_sticky: true
excerpt: "회사 내부 API나 사내 DB를 AI 에이전트가 직접 쓰게 하려 할 때, Python SDK로 나만의 MCP 서버를 처음 띄우면서 마주치는 초기화 실패와 도구 미인식 문제를 해결하는 방법을 정리했다."
---

## 왜 지금 MCP 서버를 직접 만들어야 하나

AI 에이전트가 파일을 읽고, 웹을 검색하고, 사내 시스템을 조회하는 시대다. 그런데 검색이나 파일시스템 같은 범용 도구는 이미 공개된 MCP 서버가 많지만, 사내 티켓 시스템이나 자체 DB, 내부 배포 파이프라인처럼 회사 고유의 시스템은 직접 MCP 서버를 만들어 연결하는 수밖에 없다. 문제는 문서를 따라 몇 줄 코드를 붙여넣었는데 클라이언트가 서버를 인식하지 못하거나, 도구 목록이 아예 비어 보이는 경우가 흔하다는 것이다. 이 글은 Python SDK 기준으로 처음 MCP 서버를 띄울 때 겪는 실패 지점을 중심으로 정리한다.

MCP(Model Context Protocol)는 AI 모델이 외부 도구·데이터 소스와 통신하는 방식을 표준화한 프로토콜이다. 서버를 직접 만든다는 건 결국 "이 함수를 도구로 노출하겠다"고 선언하고, 클라이언트(Claude Desktop, IDE 확장 등)가 그 선언을 표준 스키마로 읽어가게 만드는 작업이다.

## 핵심 개념 1 — 서버는 stdio로 통신한다

로컬에서 실행하는 MCP 서버 대부분은 HTTP가 아니라 **표준 입출력(stdio)** 으로 클라이언트와 통신한다. 클라이언트가 서버 프로세스를 직접 실행시키고, 그 프로세스의 stdin/stdout으로 JSON-RPC 메시지를 주고받는 구조다. 이 점을 모르고 서버 코드 안에 `print()`로 디버그 로그를 찍으면, 그 출력이 stdout으로 나가면서 프로토콜 메시지와 뒤섞여 클라이언트가 서버를 완전히 인식하지 못하는 사고가 난다. 디버그 출력은 반드시 `sys.stderr`나 로깅 모듈로 보내야 한다.

## 핵심 개념 2 — 도구 등록은 데코레이터, 하지만 타입 힌트가 스키마가 된다

Python SDK(`mcp` 패키지)는 함수에 데코레이터를 붙이는 것만으로 도구를 등록하게 해주지만, 그 함수의 타입 힌트와 docstring이 그대로 클라이언트에 노출되는 스키마가 된다. 타입 힌트를 생략하면 클라이언트가 파라미터 타입을 모르는 채로 도구를 호출하려다 실패하거나, 아예 도구 목록에서 흐릿하게 표시되는 경우가 많다.

<img src="/assets/images/posts/2026-09-23-mcp-server-python-getting-started-1.svg" alt="AI 클라이언트가 stdio로 로컬 MCP 서버 프로세스를 실행하고 JSON-RPC로 도구 목록과 호출 결과를 주고받는 흐름을 보여주는 다이어그램" style="width:100%;">

## 예제 — FastMCP로 최소 서버 만들기

```python
# server.py
from mcp.server.fastmcp import FastMCP
import sys

mcp = FastMCP("internal-ticket-server")

@mcp.tool()
def get_ticket_status(ticket_id: str) -> str:
    """티켓 ID로 사내 이슈 트래커의 현재 상태를 조회한다."""
    # 실제로는 사내 API를 호출하는 로직이 들어간다
    print(f"조회 요청: {ticket_id}", file=sys.stderr)  # stdout이 아니라 stderr!
    return f"티켓 {ticket_id}: 진행중"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

클라이언트 설정(예: Claude Desktop의 설정 파일)에는 이 스크립트를 실행할 절대 경로와 인터프리터를 명시해야 한다. 상대 경로나 `python` 같은 PATH 의존 명령을 그대로 쓰면, 클라이언트가 다른 작업 디렉터리에서 프로세스를 띄우면서 모듈을 못 찾는 에러가 자주 발생한다.

```json
{
  "mcpServers": {
    "internal-ticket-server": {
      "command": "/usr/bin/python3",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## 흔한 실수와 원인

| 증상 | 원인 | 해결 |
|---|---|---|
| 도구 목록이 비어 보임 | print()가 stdout을 오염시킴 | stderr나 logging 모듈 사용 |
| 서버 실행은 되는데 클라이언트가 인식 못 함 | 설정 파일 경로가 상대 경로 | 절대 경로로 command/args 지정 |
| 도구 호출 시 파라미터 타입 에러 | 함수 타입 힌트 누락 | 모든 파라미터에 타입 힌트 명시 |
| 서버가 조용히 죽음 | 미처리 예외가 프로세스를 종료시킴 | 도구 함수 내부에 try/except로 에러 메시지 반환 |

특히 미처리 예외 문제는 초기 개발 단계에서 자주 놓친다. 도구 함수 안에서 예외가 그대로 올라가면 클라이언트 쪽에는 그냥 "서버가 응답하지 않는다"로만 보이고, 정작 원인이 된 스택 트레이스는 로그 파일을 따로 열어봐야만 확인할 수 있다.

## 실무 포인트

- **도구 설명(docstring)을 모델이 읽는다고 생각하고 써라.** 모델은 사람이 아니라 이 docstring을 보고 언제 이 도구를 호출할지 판단한다. "티켓 상태 조회"보다 "티켓 ID를 받아 현재 처리 상태(대기/진행중/완료)를 문자열로 반환한다"처럼 구체적으로 쓸수록 잘못된 시점에 호출되는 일이 줄어든다.
- **입력 검증은 서버 쪽에서 반드시 다시 하라.** 클라이언트가 스키마를 지킨다는 보장이 없다. 특히 사내 DB나 파일시스템에 접근하는 도구라면 경로 탈출(path traversal)이나 SQL 인젝션 가능성을 서버 코드 자체에서 막아야 한다.
- **원격 배포가 필요하면 stdio 대신 HTTP/SSE transport를 검토하라.** 로컬 개발에는 stdio가 간편하지만, 여러 사람이 공유하는 사내 서버라면 인증이 가능한 HTTP 기반 transport로 바꾸는 게 맞다.

## 마무리 요약

- MCP 서버는 stdio로 통신하므로 디버그 출력을 stdout이 아니라 stderr로 보내야 프로토콜이 깨지지 않는다.
- 도구 함수의 타입 힌트와 docstring이 그대로 클라이언트가 읽는 스키마가 되므로 구체적으로 작성해야 모델이 도구를 올바르게 호출한다.
- 클라이언트 설정에는 절대 경로를 쓰고, 도구 내부 예외는 반드시 잡아서 에러 메시지로 반환해야 디버깅이 쉬워진다.

## 참고 자료

- [Model Context Protocol 공식 문서](https://modelcontextprotocol.io/)
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk)
