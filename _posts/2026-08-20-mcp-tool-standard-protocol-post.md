---
layout: single
title: "MCP(Model Context Protocol)로 도구를 표준화하다 — AI 에이전트 연동 설계"
date: 2026-08-20 12:50:00 +0530
categories: ai
tags: ["ai", "mcp", "model-context-protocol", "agent", "tool-use", "llm"]
toc: true
toc_sticky: true
excerpt: "에이전트마다 제각각이던 도구 연동 방식을 표준 프로토콜로 통일하려는 MCP의 구조와, 클라이언트-서버 모델로 컨텍스트를 주고받는 설계를 정리한다."
---

AI 에이전트가 외부 도구를 쓰게 만들려면, 그동안은 에이전트 프레임워크마다 별도의 통합 코드를 새로 짜야 했다. 어떤 도구를 A 에이전트에 붙이려면 A 전용 커넥터를, 같은 도구를 B 에이전트에도 쓰려면 B 전용 커넥터를 또 만들어야 하는 식이었다. 에이전트가 N개, 도구가 M개라면 필요한 통합 코드는 N×M에 가까워진다. 도구 제공자 입장에서는 인기 있는 에이전트마다 별도 연동을 유지보수해야 했고, 에이전트 개발자 입장에서는 새 도구 하나를 붙일 때마다 그 도구의 API를 처음부터 익혀야 했다.

**MCP(Model Context Protocol)**는 이 문제를 표준 프로토콜로 풀려는 시도다. Anthropic이 오픈소스로 공개한 뒤 여러 벤더가 클라이언트·서버 구현체를 내놓으면서 사실상 업계 표준처럼 자리잡아가고 있다. 도구 제공자는 MCP 서버 하나만 구현하면 MCP를 지원하는 모든 호스트 애플리케이션에서 그 도구를 쓸 수 있고, 에이전트 개발자는 MCP 클라이언트 하나만 구현하면 MCP 서버로 노출된 모든 도구에 접근할 수 있다. N×M이 N+M으로 줄어드는 셈이다.

이전에 다룬 개별 도구 호출(tool use) API가 "모델이 함수 하나를 어떻게 호출하는가"에 관한 것이었다면, MCP는 그보다 한 층 위에서 "그 함수(그리고 데이터, 프롬프트 템플릿)를 어떤 프로토콜로 발견하고 연결할 것인가"를 표준화한다는 점에서 다르다.

## 핵심 개념 1: 호스트-클라이언트-서버 구조

MCP는 세 역할로 구성된다. **호스트(Host)**는 사용자가 직접 쓰는 AI 애플리케이션이다(데스크톱 앱, IDE 플러그인, 자체 에이전트 등). **클라이언트(Client)**는 호스트 내부에서 하나의 MCP 서버와 1:1로 연결을 유지하는 컴포넌트로, 호스트가 서버 여러 개에 붙으면 클라이언트도 그만큼 여러 개 생긴다. **서버(Server)**는 특정 도구나 데이터 소스(파일 시스템, 데이터베이스, 이슈 트래커 API 등)를 MCP 규격으로 감싸 노출하는 프로세스다.

통신은 JSON-RPC 2.0 메시지로 이루어지며, 전송 방식은 로컬 프로세스를 표준입출력으로 붙이는 **stdio**와, 원격 서버에 HTTP로 접속하는 **Streamable HTTP** 두 가지가 대표적이다. 로컬 파일 시스템 접근처럼 신뢰 경계 안에 있는 도구는 stdio로, 여러 사용자가 공유하는 원격 서비스는 Streamable HTTP로 노출하는 편이 일반적이다.

## 핵심 개념 2: Tools, Resources, Prompts

서버가 클라이언트에 노출하는 항목은 세 종류로 나뉘고, 누가 그 사용 여부를 결정하는지가 다르다는 점이 중요하다.

| 항목 | 통제 주체 | 성격 | 예시 |
|---|---|---|---|
| Tools | 모델이 판단 | 모델이 호출하는 함수(부작용 있음) | 이슈 생성, 메일 발송 |
| Resources | 애플리케이션이 판단 | 모델에 제공할 데이터(조회에 가까움) | 파일 내용, DB 레코드, 로그 |
| Prompts | 사용자가 판단 | 재사용 가능한 프롬프트 템플릿 | 슬래시 커맨드로 노출되는 정형 질의 |

Tools는 기존 tool use API의 함수 호출과 비슷하지만, MCP 서버가 스키마째로 정의해 여러 호스트에서 재사용된다는 점이 다르다. Resources는 모델이 스스로 판단해 부르는 것이 아니라, 호스트 애플리케이션이 컨텍스트에 넣을지 말지 결정하는 데이터다. Prompts는 사용자가 UI에서 직접 선택하는 정형화된 요청 템플릿으로, 반복되는 작업 패턴을 서버 쪽에 미리 정의해둘 수 있다.

## 예제: MCP 서버 정의(TypeScript)

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "weather-server", version: "1.0.0" });

// Tool: 모델이 필요할 때 호출하는 함수
server.tool(
  "get_weather",
  "주어진 도시의 현재 날씨를 조회한다.",
  { city: z.string().describe("도시 이름, 예: Seoul") },
  async ({ city }) => {
    const data = await fetchWeather(city);
    return { content: [{ type: "text", text: `${city}: ${data.summary}` }] };
  }
);

// Resource: 애플리케이션이 컨텍스트로 읽어들이는 데이터
server.resource("recent-alerts", "weather://alerts/recent", async (uri) => ({
  contents: [{ uri: uri.href, text: await getRecentAlerts() }],
}));

const transport = new StdioServerTransport();
await server.connect(transport);
```

간단한 예시지만, 이 서버 하나만 배포하면 stdio를 지원하는 어떤 MCP 호스트에서도 `get_weather` 도구와 `recent-alerts` 리소스를 그대로 쓸 수 있다.

## 실무 포인트

- **서버는 신뢰 경계 밖의 코드다**: MCP 서버는 임의의 코드를 실행할 수 있으므로, 검증되지 않은 서드파티 서버를 그대로 연결하는 것은 임의 코드 실행을 허용하는 것과 다르지 않다. 출처가 분명한 서버만 연결하고, 파일 시스템 접근 경로나 API 스코프 같은 권한 범위를 최소화해야 한다.
- **전송 방식은 신뢰 경계에 맞춰 고른다**: 로컬 전용 도구는 stdio, 여러 사용자나 원격 배포가 필요한 도구는 Streamable HTTP(및 OAuth 인증)를 쓰는 편이 자연스럽다.
- **스펙이 계속 바뀐다**: MCP는 아직 활발히 개정되는 표준이라, 클라이언트·서버 SDK 버전 간 호환성 문제가 생길 수 있다. 프로덕션에 붙이기 전에 사용 중인 호스트가 지원하는 프로토콜 버전을 확인하는 편이 안전하다.
- **도구 설명이 곧 성능이다**: 도구 설명(description)이 부실하거나 도구 수가 지나치게 많으면 모델이 적절한 도구를 고르지 못한다. 서버 쪽에서부터 설명을 충실히 작성하는 것이, 호스트 프롬프트를 아무리 다듬어도 못 채우는 부분을 채운다.

## 3줄 요약

- MCP는 에이전트마다 제각각이던 도구 연동을 표준 프로토콜로 통일해, N×M 통합 문제를 N+M으로 줄이려는 시도다.
- 호스트-클라이언트-서버 구조 위에서 Tools(모델이 호출), Resources(앱이 읽음), Prompts(사용자가 선택) 세 가지를 표준 방식으로 주고받는다.
- 실무에서는 서버를 신뢰 경계 밖 코드로 다루고, 전송 방식(stdio/Streamable HTTP)을 용도에 맞게 고르며, 스펙 변경에 대비해야 한다.

## 참고 자료

- [Model Context Protocol 공식 사이트](https://modelcontextprotocol.io/)
- [MCP 소개 문서](https://modelcontextprotocol.io/introduction)
- [Anthropic MCP 발표 글](https://www.anthropic.com/news/model-context-protocol)
