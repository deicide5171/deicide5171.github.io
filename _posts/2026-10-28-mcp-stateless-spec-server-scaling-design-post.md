---
layout: single
title: "\"MCP 서버를 여러 대 띄웠더니 대화가 끊겨요\" — 2026-07-28 스펙, 세션을 버리고 stateless로 가는 이유"
date: 2026-10-28 12:50:00 +0530
categories: ai
tags: ["MCP", "stateless아키텍처", "에이전트인프라", "프로토콜설계", "API게이트웨이"]
toc: true
toc_sticky: true
excerpt: "MCP 2026-07-28 스펙이 세션 ID와 initialize 핸드셰이크를 없애고 완전한 stateless 아키텍처로 전환했다. 세션 스토어 없이 수평 확장하는 서버 설계, MRTR로 바뀌는 confirmation 흐름, 인증 강화까지 빌더가 지금 점검해야 할 것을 정리했다."
---

## 도입

"MCP 서버 트래픽이 늘어서 인스턴스를 세 대로 늘렸는데, 같은 대화 중간에 요청이 다른 서버로 튀면 맥락이 끊깁니다." MCP(Model Context Protocol) 서버를 직접 운영해본 팀이라면 한 번쯤 마주쳤을 불만이다. 원인은 단순하다. 기존 MCP는 `initialize` 핸드셰이크에서 세션 ID를 발급하고, 이후 모든 요청이 `Mcp-Session-Id` 헤더를 달고 **같은 서버 인스턴스**로 돌아와야 했다. 로드밸런서는 이 세션을 기억해 항상 같은 뒷단으로 꽂아주는 sticky routing을 해야 했고, 서버는 세션 상태를 메모리나 Redis 같은 별도 스토어에 들고 있어야 했다.

2026년 7월 28일 발표된 MCP 스펙은 이 구조를 통째로 걷어냈다. `initialize`/`initialized` 핸드셰이크와 `Mcp-Session-Id` 헤더 자체가 사라졌고, 클라이언트의 신원·버전·역량 정보는 매 요청의 `_meta` 필드에 실려 함께 온다. 서버 입장에서는 "이 요청이 누구의 몇 번째 턴인지"를 서버 쪽 상태가 아니라 요청 자체에서 읽어야 하는 쪽으로 설계가 바뀐 것이다. 이 글은 이 전환이 MCP 서버·게이트웨이를 설계하는 방식을 어떻게 바꾸는지, 지금 운영 중인 서버라면 무엇부터 손대야 하는지를 다룬다.

## 왜 세션이 확장의 적이었나

세션 기반 구조에서 서버를 여러 대로 늘리는 순간 두 가지 선택지뿐이었다. 로드밸런서가 세션 ID를 보고 항상 같은 서버로 보내는 sticky routing을 쓰거나, 모든 서버가 세션 상태를 공유 스토어(Redis 등)에서 읽고 쓰게 만드는 것이다. 전자는 특정 인스턴스에 트래픽이 쏠려도 분산이 안 되고, 그 인스턴스가 재시작되면 세션이 통째로 날아간다. 후자는 매 요청마다 외부 스토어를 왕복해야 해서 지연이 늘고, 스토어 자체가 새로운 장애 지점이 된다.

stateless 전환은 이 딜레마를 "애초에 서버가 상태를 들고 있지 않는다"로 해결한다. 어떤 요청이든 필요한 정보를 이미 담고 도착하므로, 그 요청을 처리할 수 있는 서버 인스턴스는 무작위로 골라도 상관없다.

## 전체 시스템에서의 위치

요청이 클라이언트(에이전트 호스트)에서 출발해 MCP 서버를 거쳐 실제 도구·데이터에 닿기까지의 경로가 이번 전환으로 달라진다.

<img src="/assets/images/posts/2026-10-28-mcp-stateless-spec-server-scaling-design-1.svg" alt="MCP 세션 기반 아키텍처와 stateless 아키텍처를 비교한 다이어그램. 위는 sticky 로드밸런서와 세션 스토어를 거치는 기존 구조, 아래는 헤더 기반 라우팅으로 아무 서버 인스턴스에나 요청이 가는 신규 구조를 보여준다." style="width:100%;">

- **기존(stateful)**: 클라이언트 → sticky 로드밸런서(세션 ID 인식) → 세션을 들고 있는 특정 서버 인스턴스 → 세션 스토어(필요 시) → 도구/백엔드. 라우팅 계층이 JSON-RPC 바디 안의 세션 정보를 알아야 해서 범용 API 게이트웨이로는 처리하기 어려웠다.
- **신규(stateless)**: 클라이언트(`_meta`에 신원·역량 포함) → 표준 HTTP 헤더(`Mcp-Method`, `Mcp-Name`)만 보고 라우팅하는 게이트웨이 → 아무 서버 인스턴스 → 도구/백엔드. 게이트웨이가 JSON-RPC 페이로드를 파싱하지 않아도 되므로, 범용 API 게이트웨이·레이트리미터에 그대로 얹을 수 있다.
- 서버-클라이언트 간 중간 확인(예: "이 작업을 진행해도 될까요?")이 필요할 때도 달라진다. 기존에는 SSE 스트림을 계속 열어둔 채로 기다려야 했지만, 이제는 **MRTR(Multi Round-Trip Requests)**로 서버가 "추가 입력 필요" 상태를 응답하고 연결을 끊은 뒤, 클라이언트가 새 요청으로 이어 보낸다. 커넥션을 오래 들고 있을 필요가 없어지니 프록시·로드밸런서의 타임아웃 설정에 덜 휘둘린다.

## 선택의 트레이드오프

| 기준 | 기존(stateful, 세션 기반) | 신규(stateless, 2026-07-28) |
|---|---|---|
| 수평 확장 | sticky routing 또는 공유 세션 스토어 필요 | 아무 인스턴스나 처리 가능, 추가 인프라 불필요 |
| 인스턴스 재시작 | 세션 유실 → 클라이언트 재연결 필요 | 영향 없음, 다음 요청도 다른 인스턴스가 처리 |
| 중간 확인 흐름 | SSE 스트림을 열어두고 대기(연결 유지 비용) | MRTR로 짧은 요청-응답을 반복(연결 유지 불필요) |
| 게이트웨이 요구사항 | JSON-RPC 바디까지 파싱해야 라우팅 가능 | 표준 헤더만으로 라우팅 가능 |
| 인증 | Dynamic Client Registration 중심 | OAuth2/OIDC 정렬 강화, Client ID Metadata Document |
| 마이그레이션 비용 | 해당 없음(기존 구조) | 세션 의존 코드 전면 재작성, 구버전 클라이언트 호환 고려 필요 |

언제 기존 구조를 그대로 둬도 되는가도 짚어야 한다. 사내 전용으로 인스턴스가 한 대뿐이고 확장 계획이 없다면, 당장 마이그레이션 비용을 들여 stateless로 바꿀 유인은 적다. 하지만 외부에 노출하거나 트래픽이 늘어날 가능성이 있는 서버라면, 세션 의존 코드가 쌓이기 전에 지금 전환하는 쪽이 나중의 재작성 비용보다 싸다.

## 코드 예제

```javascript
// 기존: 세션 ID로 서버 쪽 상태를 조회하는 방식
app.post('/mcp', (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  const session = sessionStore.get(sessionId); // 외부 스토어 왕복
  const result = handleRequest(session, req.body);
  res.json(result);
});
```

```javascript
// 신규: 요청 자체에 실린 _meta로 처리, 서버는 상태를 들고 있지 않음
app.post('/mcp', (req, res) => {
  const { _meta, ...rpc } = req.body;
  // _meta.clientInfo, _meta.capabilities 등을 매 요청마다 읽는다
  const result = handleStatelessRequest(_meta, rpc);
  res.json(result); // 다음 요청이 다른 인스턴스로 가도 문제없다
});
```

## 실무 포인트

- **구버전 클라이언트와의 공존**을 먼저 설계한다. 전 클라이언트가 한 번에 신규 스펙으로 넘어가지 않으므로, 서버는 당분간 `Mcp-Session-Id`가 있으면 구버전 흐름으로, 없으면 신규 흐름으로 분기하는 호환 레이어를 둬야 한다.
- **인증 전환이 따로 움직인다.** Dynamic Client Registration에 의존하던 클라이언트 등록 로직이 있다면 Client ID Metadata Document 방식으로 바뀌는 흐름을 별도로 검증해야 한다. 세션 제거와 인증 강화는 같은 릴리스에 묶여 있지만 영향 범위는 다르다.
- **sampling·roots 폐기**는 "서버가 클라이언트의 LLM 호출 능력을 빌려 쓰던" 패턴 자체를 막는다. 이 부분에 의존한 서버가 있다면 서버가 직접 모델을 호출하는 구조로 바꿔야 하며, 이는 세션 제거와는 별개의 마이그레이션 작업으로 다뤄야 한다.
- 이번 변화는 블로그·뉴스레터의 재구성 보도가 먼저 퍼졌고 세부 필드명이 글마다 조금씩 다르게 소개된다. 실제 구현에 들어가기 전에는 반드시 공식 스펙 문서(`modelcontextprotocol.io`)와 SDK 체인지로그를 직접 확인한다.

## 마무리

- MCP 2026-07-28 스펙은 세션 ID와 `initialize` 핸드셰이크를 없애고, 클라이언트 정보를 매 요청의 `_meta`에 싣는 완전한 stateless 구조로 전환했다.
- 서버를 여러 대로 늘릴 때 sticky routing이나 공유 세션 스토어가 필요 없어지고, 게이트웨이는 `Mcp-Method`/`Mcp-Name` 헤더만으로 라우팅할 수 있다.
- 마이그레이션은 세션 의존 코드 제거, 구버전 호환 레이어, 인증 흐름 재검증, MRTR 기반 확인 플로우 재구현 순으로 접근하는 것이 안전하다.

## 참고 자료

- [The 2026-07-28 Specification — Model Context Protocol](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [Bringing MCP 2026-07-28 to Claude](https://claude.com/blog/bringing-mcp-2026-07-28-to-claude)
- [Stateless MCP: What the 2026-07-28 specification changes for security](https://equixly.com/blog/2026/08/05/stateless-mcp/)
