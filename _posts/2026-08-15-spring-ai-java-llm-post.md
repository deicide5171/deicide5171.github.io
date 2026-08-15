---
layout: single
title: "Spring Boot에 LLM을 붙이는 가장 자바다운 방법 — Spring AI"
date: 2026-08-15 17:30:00 +0530
categories: web-dev
tags: ["spring-ai", "java", "llm", "spring-boot", "rag", "tool-calling"]
toc: true
toc_sticky: true
excerpt: "Spring AI로 기존 Spring Boot REST API에 프롬프트 호출, RAG, 함수 호출을 통합하는 방법과 Python 생태계 대비 장단점을 정리한다."
---

## 왜 지금 Spring AI인가

LLM을 서비스에 붙이는 작업은 한동안 Python 진영의 전유물처럼 여겨졌다. LangChain이나 LlamaIndex 같은 프레임워크가 먼저 자리를 잡았고, 자바 진영 개발자들은 REST 클라이언트를 직접 짜서 OpenAI나 Anthropic API를 호출하는 식으로 임시 대응해왔다. 문제는 회사의 핵심 도메인 로직이 이미 Spring Boot 위에 올라가 있는 경우다. LLM 기능 하나를 붙이자고 별도의 Python 마이크로서비스를 새로 띄우고, 그 사이를 HTTP나 메시지 큐로 연결하는 구조는 배포 파이프라인과 운영 부담을 눈에 띄게 늘린다.

Spring AI는 이런 상황에서 자바 개발자가 익숙한 방식 그대로 LLM 통합을 다룰 수 있게 해주는 프로젝트다. `@Autowired`로 빈을 주입하고, `application.yml`로 설정을 관리하고, Spring Boot의 자동 구성(auto-configuration)을 그대로 활용한다. 프롬프트 호출, 벡터 스토어 연동, 함수 호출(tool calling) 같은 기능들이 모두 Spring의 추상화 계층 위에 얹혀 있어서, 모델 제공자를 바꾸더라도 애플리케이션 코드는 거의 그대로 유지된다.

이 글에서는 기존 Spring Boot REST API에 Spring AI를 붙이는 세 가지 축 — 프롬프트 호출, RAG(검색 증강 생성), 함수 호출 — 을 코드와 함께 살펴보고, 자바 개발자 입장에서 Python 생태계 대비 무엇이 낫고 무엇이 아쉬운지 정리한다.

## 핵심 개념

### ChatClient — 모델 호출의 통일된 창구

Spring AI의 중심에는 `ChatClient`가 있다. OpenAI, Anthropic, Azure OpenAI, 로컬 Ollama 등 다양한 모델 제공자를 동일한 인터페이스로 호출할 수 있게 추상화한 것이다. 제공자별 세부 사항은 스타터 의존성과 설정값으로만 갈리고, 호출 코드는 그대로 유지된다.

| 요소 | 역할 |
|---|---|
| `ChatClient` | 프롬프트를 보내고 응답을 받는 최상위 인터페이스 |
| `ChatModel` | 실제 제공자별 구현체(OpenAiChatModel 등) |
| `PromptTemplate` | 변수 치환이 가능한 프롬프트 템플릿 |
| `Advisor` | 요청/응답 가로채기(로깅, 메모리, RAG 주입 등) |

### VectorStore — RAG를 위한 벡터 검색 추상화

RAG를 구현하려면 문서를 임베딩해서 벡터 DB에 저장하고, 질의 시점에 유사도 검색으로 관련 문서를 찾아 프롬프트에 끼워 넣어야 한다. Spring AI는 이 과정을 `VectorStore` 인터페이스로 추상화한다. PGVector, Redis, Elasticsearch, Chroma, Milvus 등 여러 백엔드를 같은 API로 다룰 수 있고, `similaritySearch()` 한 번으로 유사 문서를 가져올 수 있다.

### Tool Calling — 자바 메서드를 그대로 함수로 노출

함수 호출은 LLM이 필요할 때 애플리케이션의 특정 기능을 호출하도록 하는 패턴이다. Spring AI에서는 `@Tool` 애노테이션이 붙은 자바 메서드를 그대로 모델에 노출할 수 있다. 별도의 JSON 스키마를 손으로 작성할 필요 없이, 메서드 시그니처와 파라미터 설명에서 스키마가 자동 생성된다.

### Python 생태계 대비 장단점

| 항목 | Spring AI | Python(LangChain 등) |
|---|---|---|
| 기존 자바 시스템 통합 | 매우 자연스러움 (DI, 트랜잭션, 보안 재사용) | 별도 서비스 분리 필요한 경우 많음 |
| 커뮤니티·레퍼런스 양 | 상대적으로 적음 | 압도적으로 많음 |
| 최신 LLM 기능 반영 속도 | 다소 늦는 편 | 신규 기능이 가장 먼저 등장 |
| 타입 안정성 | 강함 (컴파일 타임 검증) | 약함 (런타임 오류 위험) |
| 운영 안정성 | JVM 생태계의 성숙한 모니터링·튜닝 활용 가능 | 별도 스택 구축 필요 |

## 코드로 보는 통합

기존 REST 컨트롤러에 프롬프트 호출을 붙이는 가장 단순한 형태다.

```java
@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatClient chatClient;

    public ChatController(ChatClient.Builder builder) {
        this.chatClient = builder.build();
    }

    @PostMapping
    public String chat(@RequestBody String question) {
        return chatClient.prompt()
                .user(question)
                .call()
                .content();
    }
}
```

RAG와 함수 호출을 함께 적용하면 다음과 같은 형태가 된다. 벡터 스토어에서 관련 문서를 찾아 컨텍스트로 주입하고, 재고 조회 같은 도메인 함수를 도구로 등록한다.

```java
@Service
public class ProductAssistantService {

    private final ChatClient chatClient;
    private final VectorStore vectorStore;

    public ProductAssistantService(ChatClient.Builder builder, VectorStore vectorStore) {
        this.vectorStore = vectorStore;
        this.chatClient = builder
                .defaultAdvisors(new QuestionAnswerAdvisor(vectorStore))
                .build();
    }

    public String ask(String question) {
        return chatClient.prompt()
                .user(question)
                .tools(new InventoryTools())
                .call()
                .content();
    }
}

class InventoryTools {

    @Tool(description = "상품명으로 현재 재고 수량을 조회한다")
    int getStockQuantity(String productName) {
        // 실제로는 재고 서비스나 리포지토리를 호출
        return InventoryRepository.findQuantityByName(productName);
    }
}
```

## 실무 포인트

프로덕션에 적용할 때 챙겨야 할 것들이 있다. 먼저 **비용과 지연 시간**이다. LLM 호출은 일반 REST 호출보다 훨씬 느리고(수백 ms~수 초) 토큰당 과금이 붙으므로, 타임아웃과 재시도 정책을 명시적으로 설정해야 한다. 둘째, **함수 호출의 신뢰성**이다. 모델이 항상 올바른 도구를 올바른 인자로 호출한다고 가정하면 안 되며, 도구 함수 내부에서 방어적인 검증이 필요하다. 셋째, **벡터 스토어 선택**은 신중해야 한다. 이미 PostgreSQL을 쓰고 있다면 PGVector로 시작하는 편이 별도 인프라를 늘리지 않아 운영 부담이 적다. 마지막으로 Spring AI는 아직 활발히 개발 중인 프로젝트이므로, 마이너 버전 업그레이드마다 API 변경 가능성을 염두에 두고 의존성 버전을 신중히 관리하는 것이 좋다.

## 3줄 요약

- Spring AI는 기존 Spring Boot 애플리케이션에 프롬프트 호출·RAG·함수 호출을 자연스럽게 통합할 수 있게 해주는 추상화 계층이다.
- `ChatClient`, `VectorStore`, `@Tool` 세 가지 개념만 이해하면 대부분의 LLM 통합 시나리오를 다룰 수 있다.
- Python 생태계보다 최신 기능 반영은 느리지만, 기존 자바 시스템과의 통합·타입 안정성·운영 성숙도 면에서 이점이 크다.

## 참고 자료

- [Spring AI 공식 문서](https://docs.spring.io/spring-ai/reference/)
- [Spring AI GitHub 저장소](https://github.com/spring-projects/spring-ai)
- [Spring AI ChatClient 레퍼런스](https://docs.spring.io/spring-ai/reference/api/chatclient.html)
- [Spring AI RAG 가이드](https://docs.spring.io/spring-ai/reference/api/retrieval-augmented-generation.html)
