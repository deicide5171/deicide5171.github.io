---
layout: single
title: "MCP Sampling이 폐기된다 — 서버가 직접 LLM을 호출하는 설계로 전환하기"
date: 2026-10-22 12:50:00 +0530
categories: ai
tags: ["mcp", "sampling", "sep-2577", "llm-integration", "에이전트설계"]
toc: true
toc_sticky: true
excerpt: "'도구가 가져온 데이터를 요약까지 해서 돌려주세요'라는 요구를 MCP 서버는 그동안 sampling으로 클라이언트의 모델에 떠넘겨 풀었다. 2026-07-28 스펙 개정(SEP-2577)이 이 sampling을 로드맵에서 폐기 경로에 올리면서, 서버가 직접 LLM 제공자 API를 호출하는 쪽으로 설계를 옮겨야 하는 이유와 전환 기준을 정리했다."
---

## 도입

"검색 도구가 찾아온 문서 10개를 그냥 다 돌려주지 말고, 핵심만 요약해서 보여주세요." MCP 서버를 만들어본 사람이라면 한 번쯤 받아봤을 요구사항이다. 요약은 LLM이 해야 하는 일인데, 서버 안에 또 다른 모델 호출 로직을 넣는 건 과한 책임처럼 느껴진다. 그래서 MCP는 처음부터 `sampling/createMessage`라는 기능을 뒀다. 서버가 "이 텍스트를 요약해줘"라는 요청을 클라이언트로 역으로 보내면, 클라이언트가 자신이 이미 쓰고 있는 모델로 추론해 결과만 서버에 돌려주는 구조다. 서버는 API 키도, 모델 선택권도 가질 필요가 없었다.

이 전제가 2026-07-28 스펙 개정으로 흔들렸다. SEP-2577이 Roots·Sampling·Logging 세 기능을 나란히 '폐기 경로(deprecated)'에 올렸다. 와이어 레벨 동작은 이 리비전에서 아직 바뀌지 않고, 폐기 선언 이후 최소 12개월간은 기존 버전들이 그대로 지원된다. 즉 내일 당장 깨지는 건 아니다. 하지만 공식 스펙 문서와 발표 블로그가 "새 구현체는 이 기능을 채택하지 말라"고 명시한 이상, 지금 서버를 새로 짜거나 리팩터링하는 팀이라면 설계 전제를 다시 세워야 한다.

## 전체 시스템에서의 위치

sampling이 있을 때와 없을 때, 추론이 일어나는 위치 자체가 달라진다.

<img src="/assets/images/posts/2026-10-22-mcp-sampling-deprecated-server-llm-call-1.svg" alt="MCP sampling 위임 구조와 서버 직접 LLM 호출 구조의 비교도" style="width:100%;">

- **기존 sampling 구조**: MCP 서버는 `sampling/createMessage` 요청을 클라이언트로 보낸다. 클라이언트는 사용자 승인을 거쳐 자신이 연결한 모델(Claude Desktop이면 Claude, 다른 호스트면 다른 모델)로 추론하고, 결과 텍스트만 서버로 돌려준다. 서버는 어떤 모델이 응답했는지조차 알 필요가 없다.
- **전환 후 구조**: 서버가 자체적으로 Anthropic·OpenAI 같은 제공자 API를 직접 호출한다. API 키, 비용, 모델 버전 관리는 전부 서버 쪽 책임이 된다. 클라이언트는 더 이상 이 왕복에 끼지 않는다.
- **서버 주도 다중 왕복이 필요한 다른 경우**(사용자 추가 입력이 필요한 작업 등)는 같은 개정에서 함께 논의 중인 MRTR(Multi Round-Trip Requests, SEP-2322) 패턴이 대신한다. 서버가 `input_required` 결과 타입과 `inputRequests`를 돌려주면, 클라이언트가 같은 호출을 `inputResponses`와 함께 재시도하는 구조다. 이건 sampling의 직접적인 후속 규격은 아니지만, '서버가 클라이언트에게 되묻는다'는 설계 축을 어떻게 다시 짤지 보여주는 참고 사례다.

## 선택의 트레이드오프

| 접근 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| sampling 계속 사용(1년 유예 기간) | 지금 당장 코드 변경 없음, API 키 관리 책임 없음 | 신규 구현 금지 권고, 클라이언트 지원 편차가 원래도 컸음 | 유예기간 안에 처리할 다른 마이그레이션이 더 급한 레거시 서버 |
| 서버가 LLM 제공자 API 직접 호출 | 모델 선택권 확보, 클라이언트 sampling 미지원 문제에서 해방, 응답 일관성 | API 키·시크릿 관리 책임, 토큰 비용을 서버 운영자가 부담 | 특정 모델 성능에 품질이 좌우되는 도구(요약·분류·추출) |
| MRTR 패턴으로 전환 | 서버 주도 왕복을 표준 메커니즘 위에서 유지 | 아직 별도 SEP로 확정 전 단계, SDK 지원이 고르지 않음 | 사용자 추가 입력이 필요한 승인·확인 흐름 |
| 하이브리드(기본은 직접 호출, 특수 클라이언트는 sampling 폴백) | 전환 리스크 분산 | 두 경로를 모두 유지보수해야 함 | 다양한 호스트 환경에 배포되는 범용 MCP 서버 패키지 |

판단 기준은 "이 도구가 모델 호출 결과의 품질에 얼마나 민감한가"다. 요약·추출처럼 결과 품질이 곧 도구의 가치인 기능이라면, 애초에 클라이언트가 어떤 모델을 쓰는지 모르는 sampling 위임 자체가 리스크였다. 반대로 단순 텍스트 변환 수준이라면 유예기간 동안은 굳이 서두를 필요가 없다.

## 실제 프로젝트 진행 순서

1. **sampling 의존 지점부터 전수 조사한다.** 서버 코드에서 `createMessage` 또는 SDK의 `ctx.sample()` 호출을 모두 찾아 목록화한다.
2. **도구별로 전환 우선순위를 정한다.** 결과 품질이 도구의 핵심 가치인 도구(요약, 분류, 코드 리뷰)를 먼저, 단순 포맷 변환 성격의 도구는 나중으로 미룬다.
3. **키·시크릿 관리 설계를 먼저 끝낸다.** 서버가 API 키를 직접 들고 추론을 돌리는 순간 비밀 관리, 레이트 리밋, 비용 모니터링이 서버 운영 범위로 들어온다. 이 부분이 전환의 실제 공수 대부분을 차지한다.
4. **제공자 락인을 피할 추상화 계층을 둔다.** Anthropic SDK를 직접 호출하더라도, 도구 로직과 "어떤 모델을 어떻게 부르는가"를 분리해두면 나중에 제공자를 바꾸기 쉽다.
5. **서버 주도 되묻기가 필요한 도구는 MRTR을 검토한다.** 아직 확정 전 단계이므로, 급하지 않다면 SDK 지원이 안정화될 때까지 기존 동기 응답 구조로 버텨도 된다.
6. **12개월 유예기간을 역산해 일정을 잡는다.** 급하게 전부 바꾸기보다, 품질 민감도가 높은 도구부터 순서대로 옮기고 나머지는 유예기간 안에 자연스럽게 정리한다.

```typescript
// 전환 전: 클라이언트에게 추론을 위임
async function summarizeDocs(docs: string[], ctx: McpContext) {
  const result = await ctx.sample({
    messages: [{ role: "user", content: `다음 문서를 요약해줘:\n${docs.join("\n")}` }],
    maxTokens: 500,
  });
  return result.content;
}

// 전환 후: 서버가 직접 제공자 API를 호출
async function summarizeDocs(docs: string[]) {
  const response = await anthropic.messages.create({
    model: "claude-sonnet-5-5",
    max_tokens: 500,
    messages: [{ role: "user", content: `다음 문서를 요약해줘:\n${docs.join("\n")}` }],
  });
  return response.content;
}
```

## 실무 포인트

- Sampling만 바뀌는 게 아니다. SEP-2577은 Roots(작업 디렉터리 공유)와 Logging도 같은 폐기 경로에 올렸다. 서버가 이 두 기능에 의존한다면 같이 점검한다.
- 와이어 프로토콜은 이번 리비전에서 아직 바뀌지 않았다. "폐기 예고"와 "제거"를 혼동해 성급하게 전체 코드를 갈아엎지 않는다.
- 공식 SEP 문서는 대체 메커니즘을 명시적으로 지정하지 않는다. "직접 제공자 API 통합"과 "MRTR" 모두 커뮤니티가 수렴해가는 방향이므로, 사용 중인 SDK(TypeScript·Python·Go·C#)의 마이그레이션 노트를 직접 확인하고 설계를 맞춘다.

## 마무리

- MCP 2026-07-28 스펙(SEP-2577)이 Sampling·Roots·Logging을 폐기 경로에 올리며, 서버가 클라이언트 모델에 추론을 위임하던 전제가 바뀌고 있다.
- 와이어 레벨은 아직 그대로지만 12개월 유예 안에, 결과 품질이 도구 가치를 좌우하는 기능부터 서버 직접 LLM 호출로 옮기는 게 안전하다.
- 전환의 실제 비용은 모델 호출 코드 자체가 아니라 API 키·비용·레이트 리밋을 서버 책임으로 끌어오는 운영 설계에 있다.

## 참고 자료

- [SEP-2577 — Deprecate Roots, Sampling, and Logging](https://modelcontextprotocol.io/seps/2577-deprecate-roots-sampling-and-logging)
- [Model Context Protocol 2026-07-28 스펙 공지](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
