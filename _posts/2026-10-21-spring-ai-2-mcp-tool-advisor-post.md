---
layout: single
title: "Spring AI 2.0 GA — MCP 서버를 Spring Boot 서비스에 바로 얹는 설계"
date: 2026-10-21 12:40:00 +0530
categories: stack
tags: ["spring-ai", "mcp", "spring-boot", "tool-calling", "java"]
toc: true
toc_sticky: true
excerpt: "AI 기능을 기존 Spring Boot 서비스에 붙여달라는 요구는 더 이상 별도 Python 서버를 세우는 일이 아니다. 2026년 6월 GA된 Spring AI 2.0의 @McpTool 어노테이션과 ToolCallingAdvisor가 기존 서비스 메서드를 MCP 도구로 바꾸는 방식과, 1.x에서 올라갈 때 무엇이 깨지는지 정리했다."
---

## 도입

"우리 재고 조회·주문 처리 로직을 에이전트가 직접 호출하게 해주세요. 근데 Python으로 따로 서버 하나 더 올리는 건 피하고 싶어요." Java·Spring 스택으로 백엔드를 운영해 온 팀이 AI 에이전트 연동을 검토할 때 흔히 부딪히는 벽이다. MCP 서버 구현체 대부분이 Python·TypeScript 생태계에 몰려 있어서, 기존 Spring Boot 서비스 로직을 그대로 쓰려면 REST API로 한 번 감싸고 그 위에 별도 MCP 서버를 또 세우는 이중 구조가 되기 쉬웠다.

2026년 6월 12일 GA된 Spring AI 2.0은 이 문제를 정면으로 겨냥한다. MCP Java SDK 2.0.0을 품고, 기존에 커뮤니티 프로젝트였던 `mcp-annotations`를 코어로 편입시켜 `@McpTool` 하나로 평범한 Spring 서비스 메서드를 MCP 도구로 노출할 수 있게 됐다. 동시에 도구 호출 루프를 어드바이저(Advisor) 체인 안으로 옮기면서 1.x의 도구 호출 방식과 완전히 같지는 않은 구조가 됐다. "그냥 AI 라이브러리 버전 올리기"로 받으면 안 되는 이유다.

## 전체 시스템에서의 위치

Spring AI 2.0을 기존 Spring Boot 아키텍처에 끼워 넣으면 어디에 무엇이 새로 들어오는지가 명확해진다.

<img src="/assets/images/posts/2026-10-21-spring-ai-2-mcp-tool-advisor-1.svg" alt="Spring Boot 서비스 레이어가 MCP 어노테이션으로 도구화되고 ChatClient 어드바이저 체인을 거쳐 에이전트와 연결되는 구조도" style="width:100%;">

- **기존 서비스 레이어**(`@Service` 빈)는 그대로 둔다. 여기에 `@McpTool` 메서드 어노테이션만 추가하면 MCP 서버의 도구 목록에 자동 등록된다.
- **ChatClient + Advisor 체인**이 도구 호출 루프를 담당한다. 1.x에서 `ToolCallback`을 직접 등록하던 방식 대신, `ToolCallingAdvisor`가 체인 중간에서 호출 여부를 가로채는 구조로 바뀌었다.
- **벡터 스토어 추상화**는 이제 코어 모듈에서 벤더별 레포지토리로 분리됐다. 어떤 벡터 DB를 쓰든 의존성만 갈아끼우면 되는 구조다.

결과적으로 앞단 에이전트(Claude Code, 사내 챗봇)는 표준 MCP 클라이언트로 접속하고, 뒷단은 기존 DB·비즈니스 로직을 그대로 재사용하는 모양이 된다.

## 선택의 트레이드오프

| 접근 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| 기존 REST API 앞에 별도 Python MCP 서버 | 생태계 성숙, 참고 자료 많음 | 비즈니스 로직 이중 구현, 두 스택 운영 부담 | AI 기능만 담당하는 독립 팀·별도 배포 단위 |
| Spring AI 2.0 `@McpTool`로 기존 서비스 직접 노출 | 비즈니스 로직 단일 소스, 기존 트랜잭션·보안 설정 재사용 | Java MCP SDK 생태계가 상대적으로 신생 | 기존 Spring Boot 서비스에 AI 기능을 점진 통합하는 경우 |
| 1.x `ToolCallback` 유지 (업그레이드 보류) | 당장 변경 비용 없음 | 신규 기능(진행형 도구 탐색, MCP 2.0)은 못 받음 | 이미 1.x로 안정적으로 운영 중이고 급할 게 없는 서비스 |
| 전체를 ToolCallingAdvisor로 전면 마이그레이션 | 장기적으로 일관된 아키텍처 | 마이그레이션 가이드 기준으로도 무중단 패치는 아님 | 2.0을 기점으로 AI 통합을 본격 확장하려는 서비스 |

판단 기준은 "지금 AI 기능이 핵심 비즈니스 로직과 얼마나 가까이 있는가"다. 단순 챗봇 응답 생성처럼 비즈니스 로직과 거리가 있으면 별도 서버 유지도 나쁘지 않다. 반대로 재고·주문처럼 기존 서비스 레이어의 트랜잭션과 검증 로직을 그대로 써야 하는 도구라면, 로직을 복제하지 않는 `@McpTool` 노출 쪽이 유지보수 비용을 크게 줄인다.

## 실제 프로젝트 진행 순서

1. **먼저 플랫폼 요구사항을 맞춘다.** Spring AI 2.0은 Spring Boot 4.0/4.1·Spring Framework 7·Jackson 3를 요구한다. Boot 3.x에 머물러 있다면 AI 업그레이드보다 Boot 4 마이그레이션이 선행 과제다.
2. **노출할 서비스 메서드부터 고른다.** 아무 메서드나 도구화하지 말고, 에이전트가 호출해도 안전한(멱등하거나 명확한 권한 검사가 있는) 메서드만 추린다.
3. **`@McpTool`로 작게 시작한다.** 읽기 전용 조회 메서드 한두 개부터 어노테이션을 붙여 MCP 서버로 노출하고, Claude Code 같은 클라이언트로 실제 호출이 되는지 확인한다.
4. **쓰기 작업은 ToolCallingAdvisor 단계에서 승인 로직을 얹는다.** 주문 생성처럼 되돌리기 어려운 도구는 어드바이저 체인에 확인 단계를 끼워 넣어, 모델이 바로 실행하지 못하게 막는다.
5. **1.x `ToolCallback` 코드는 전수 조사 후 단계적으로 옮긴다.** 마이그레이션 가이드가 명시하듯 드롭인 패치가 아니므로, 기존 테스트가 모두 통과하는지 확인하며 모듈 단위로 이전한다.
6. **벡터 스토어 의존성을 분리된 레포지토리 좌표로 갱신한다.** 2.0부터 벤더별 모듈이 별도 레포지토리로 빠졌으므로 빌드 설정에서 의존성 좌표를 다시 확인한다.

```java
@Service
public class InventoryService {

    @McpTool(name = "check_stock", description = "SKU로 현재 재고 수량을 조회한다")
    public StockInfo checkStock(@McpToolParam(description = "조회할 SKU") String sku) {
        return inventoryRepository.findBySku(sku)
            .map(StockInfo::from)
            .orElseThrow(() -> new SkuNotFoundException(sku));
    }
}
```

## 실무 포인트

- `@McpTool` 메서드는 기존 `@Service` 빈의 메서드이므로 스프링 시큐리티 `@PreAuthorize` 같은 기존 권한 검사가 그대로 적용된다. 별도 인가 로직을 새로 짤 필요는 없다.
- 도구 설명(description)은 모델이 언제 이 도구를 호출할지 판단하는 유일한 단서다. 짧게 쓰지 말고 호출 조건과 반환값 의미까지 구체적으로 적는다.
- 마이그레이션 가이드에 따르면 2.0은 1.x의 드롭인 교체가 아니므로, 업그레이드 PR은 기능 추가와 분리해 별도로 검토받는다.

## 마무리

- Spring AI 2.0은 기존 Spring Boot 서비스 메서드를 별도 서버 없이 `@McpTool`로 바로 MCP 도구화할 수 있게 만든 전환점이다.
- 도구 호출 루프가 어드바이저 체인으로 옮겨가면서 1.x `ToolCallback` 코드는 드롭인 교체가 아니라 단계적 이전 대상이 된다.
- 판단 기준은 AI 기능이 핵심 비즈니스 로직과 얼마나 가까운가이며, 가까울수록 기존 서비스 레이어를 그대로 노출하는 쪽이 유지보수 비용을 줄인다.

## 참고 자료

- [Spring AI 2.0.0 GA — 공식 블로그](https://spring.io/blog/2026/06/12/spring-ai-2-0-0-GA-available-now/)
- [Spring AI Reference Documentation](https://docs.spring.io/spring-ai/reference/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
