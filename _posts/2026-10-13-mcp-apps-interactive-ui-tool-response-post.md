---
layout: single
title: "에이전트가 텍스트 목록만 뱉을 때의 한계 — MCP Apps로 인터랙티브 UI 응답 설계하기"
date: 2026-10-13 12:50:00 +0530
categories: ai
tags: ["mcp", "mcp-apps", "에이전트ui", "도구호출", "인터랙티브에이전트"]
toc: true
toc_sticky: true
excerpt: "식당을 추천해달라는 요구에 에이전트가 텍스트 목록만 돌려주면 사용자는 필터링도, 지도 비교도 못 한다. Anthropic과 OpenAI가 공동 설계해 Claude·ChatGPT·VS Code·Goose에 실린 MCP Apps 확장이 도구 호출 결과를 샌드박스 iframe UI로 바꾸는 구조와, 언제 이 복잡도를 감수해야 하는지 정리했다."
---

## 왜 지금 이 설계가 필요한가

"주변 식당 중에 평점 높은 곳 추천해주세요"라는 요구를 MCP 도구 하나로 처리하면, 결과는 결국 텍스트 목록이다. 에이전트가 아무리 공손하게 정리해도 사용자는 그 목록을 평점순으로 다시 정렬하거나, 지도 위에서 거리로 비교하거나, 체크박스로 몇 곳만 골라 다음 질문에 넘기는 조작을 할 수 없다. 매 조작마다 자연어로 다시 질문을 쓰고, 모델이 그 의도를 다시 해석해 도구를 재호출해야 한다. 간단한 필터링 하나에 왕복 추론 한 사이클이 더 붙는 셈이다.

이 간극을 메우려고 2025년 말 Anthropic과 OpenAI가 공동으로 설계하고 2026년 상반기 MCP 확장으로 표준화한 것이 **MCP Apps**다. 도구 호출 결과를 순수 텍스트가 아니라 호스트(Claude Desktop, ChatGPT, VS Code, Goose 등)가 직접 렌더링하는 샌드박스 UI로 돌려줄 수 있게 만드는 확장이다. 핵심 질문은 "이 기능을 쓰면 더 좋아 보이는가"가 아니라 "이 인터랙션이 정말 텍스트 왕복보다 UI 조작으로 푸는 게 맞는가"다. 모든 도구 응답에 UI를 씌우면 오히려 에이전트 루프가 호스트 종속적인 위젯 더미로 변질된다.

## 핵심 개념 1 — 구조: ui:// 리소스와 호스트의 역할 분리

MCP Apps는 기존 도구 정의에 `_meta` 필드로 UI 리소스를 가리키는 선언을 추가하는 방식으로 동작한다. 도구 자체의 입출력 스키마는 그대로 두고, 그 결과를 어떤 HTML 리소스로 렌더링할지만 별도로 선언한다.

| 구성 요소 | 역할 | 위치 |
|---|---|---|
| MCP 서버 | 도구 실행 + `ui://` URI로 UI 리소스 선언 | 서버 프로세스 |
| 호스트(Claude/ChatGPT 등) | `ui://` 리소스를 가져와 샌드박스 iframe에 렌더링 | 클라이언트 앱 |
| iframe 내부 UI | 도구 결과 표시, 사용자 조작 수집 | 샌드박스 환경 |
| postMessage 브리지 | iframe ↔ 호스트 간 JSON-RPC 메시지 왕복 | 런타임 통신 |

도구 호출 → 결과 JSON과 `ui://` 리소스 참조 반환 → 호스트가 리소스를 가져와 CSP가 적용된 iframe에 로드 → iframe이 postMessage로 호스트에 "이 도구를 다시 호출해 달라"고 요청하는 구조다. 중요한 건 iframe이 직접 MCP 서버에 접속하지 않는다는 점이다. 항상 호스트를 거쳐야 하므로, 서버는 자신이 어떤 호스트에 떠 있는지 몰라도 되고 호스트는 임의의 iframe 코드를 신뢰하지 않아도 된다.

## 핵심 개념 2 — 보안: deny-by-default 샌드박스

iframe에 임의의 HTML을 렌더링한다는 것 자체가 공급망 공격 표면이다. MCP Apps 스펙은 이를 기본값 자체를 막는 방식으로 다룬다. iframe은 네트워크 접근, 쿠키, 상위 프레임과의 직접 DOM 접근이 전부 차단된 상태로 시작하고, 도구 메타데이터에 명시적으로 선언된 권한만 열린다. 사용자가 UI에서 액션을 트리거해 새 도구 호출이 나가는 경우에도 호스트가 한 번 더 사용자 동의를 요구하는 것이 권장 패턴이다. 즉 "UI가 편해졌다"는 것이 "사용자 확인 없이 뭐든 실행된다"는 뜻이 되면 안 된다는 전제를 프로토콜 레벨에서 강제한다.

<img src="/assets/images/posts/2026-10-13-mcp-apps-interactive-ui-tool-response-1.svg" alt="MCP 서버가 도구 결과와 ui 리소스 참조를 반환하면 호스트가 샌드박스 iframe에 렌더링하고, iframe은 postMessage로만 호스트와 통신하며 호스트가 사용자 동의를 거쳐 도구를 재호출하는 구조도" style="width:100%;">

## 선택의 트레이드오프 — 언제 UI까지 가야 하는가

| 상황 | 적합한 응답 형태 | 이유 |
|---|---|---|
| 결과가 1~5개, 단순 비교만 필요 | 구조화된 텍스트/표 | UI 왕복 비용이 더 큼 |
| 다단계 필터·정렬·다중 선택이 필요 | MCP Apps UI | 매 조작마다 재추론 없이 로컬에서 해결 |
| 호스트가 MCP Apps 미지원(구버전 클라이언트) | 텍스트 폴백 필수 | UI 리소스 로드 실패 시 전체 응답 깨짐 |
| 민감 데이터(결제, 계정 변경) 포함 | 텍스트 + 명시적 확인 단계 | UI 조작 과정이 감사 로그에서 묻힐 위험 |
| 지도·차트처럼 공간·시계열 정보가 핵심 | MCP Apps UI | 텍스트로는 구조를 보존할 수 없음 |

가장 큰 함정은 "UI를 붙이면 더 멋있어 보인다"는 이유만으로 모든 도구에 `ui://` 리소스를 선언하는 것이다. 2026년 9월 기준 Claude Desktop·VS Code·Goose·Postman은 지원하지만 Claude Code CLI나 일부 서드파티 클라이언트는 아직 지원하지 않는다. 즉 도구 하나가 "UI 응답 전용"으로 설계되면 그 도구는 지원 호스트에서만 쓸모가 있고, 나머지 환경에서는 텍스트 폴백 경로를 별도로 유지보수해야 한다. 멀티 호스트 배포를 전제한다면 이 분기 비용을 먼저 계산해야 한다.

## 실무 설정 예제

```json
{
  "name": "search_restaurants",
  "description": "주변 식당을 검색하고 결과를 지도 UI로 반환한다",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lat": { "type": "number" },
      "lng": { "type": "number" },
      "radius_m": { "type": "number" }
    },
    "required": ["lat", "lng"]
  },
  "_meta": {
    "ui": {
      "resourceUri": "ui://restaurant-finder/map-view",
      "csp": {
        "frame-ancestors": "self",
        "connect-src": "none"
      },
      "fallback": "text-table"
    }
  }
}
```

```javascript
// iframe 내부 — 호스트에게 도구 재호출을 요청하는 postMessage
window.parent.postMessage({
  jsonrpc: "2.0",
  method: "tools/call",
  params: { name: "search_restaurants", arguments: { lat, lng, radius_m: 500 } }
}, "*"); // 실제로는 origin을 호스트가 지정한 값으로 고정해야 한다
```

`fallback: "text-table"`처럼 UI 리소스 로드 실패 시 되돌아갈 경로를 도구 메타데이터에 함께 선언해 두는 것이 실무에서 가장 자주 빠뜨리는 부분이다. 이 필드가 없으면 미지원 호스트에서 도구 자체가 침묵하거나 에러로 끝난다.

## 실무 포인트와 진행 순서

1. **먼저 구조화된 JSON/텍스트로 끝까지 설계한다.** UI 없이도 에이전트가 올바른 결과를 만들어내는지 먼저 검증하고, 그 다음에 "사용자가 이 결과를 조작해야 하는 지점이 어디인가"를 찾아 그 지점에만 UI를 붙인다.
2. **CSP를 가장 좁게 시작한다.** `connect-src: none`, `frame-ancestors: self`를 기본값으로 두고, 정말 필요한 외부 호출이 생길 때만 하나씩 열어준다.
3. **호스트 지원 매트릭스를 운영 체크리스트에 넣는다.** 배포 대상 호스트가 바뀔 때마다(또는 새 호스트가 추가될 때마다) MCP Apps 지원 여부를 다시 확인하고 폴백 경로를 테스트한다.
4. **UI에서 나가는 도구 재호출에 사용자 동의 단계를 생략하지 않는다.** 특히 상태를 변경하는 도구(결제, 삭제, 전송)는 UI 조작 한 번으로 바로 실행되지 않도록 설계한다.

## 마무리 요약

- MCP Apps는 도구 결과를 샌드박스 iframe UI로 렌더링하는 MCP 확장으로, `ui://` 리소스 선언과 postMessage 브리지로 호스트-iframe 간 역할을 분리한다.
- 모든 도구에 UI를 씌우는 것이 아니라, 다단계 조작이 실제로 필요한 지점에만 적용하고 나머지는 구조화된 텍스트로 남겨야 한다.
- 호스트별 지원 여부가 갈리므로 텍스트 폴백 경로와 좁은 CSP 기본값을 처음부터 설계에 포함해야 한다.

## 참고 자료

- [MCP Apps extension overview — modelcontextprotocol.io](https://modelcontextprotocol.io/extensions/apps/overview)
- [SEP: MCP Apps — Interactive User Interfaces for MCP — modelcontextprotocol.net](https://modelcontextprotocol.net/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)
- [Model Context Protocol 2026-07-28 specification changelog](https://modelcontextprotocol.net/specification/2026-07-28/changelog)
