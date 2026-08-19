---
layout: single
title: "새 서비스의 API, 무엇으로 시작할까 — GraphQL vs REST vs gRPC 아키텍처 트레이드오프"
date: 2026-08-28 13:45:00 +0530
categories: system-design
tags: ["system-design", "graphql", "rest", "grpc", "api-design"]
toc: true
toc_sticky: true
excerpt: "새 서비스의 API 패러다임을 정할 때 REST·GraphQL·gRPC 중 무엇을 고를지, 클라이언트 다양성과 성능·스키마 강제력이라는 세 가지 축으로 선택 기준을 정리한다."
---

새 서비스를 설계할 때 API 패러다임 선택은 초반에 결정되고 나면 되돌리기 비용이 큰 결정 중 하나다. REST로 시작한 API를 나중에 GraphQL로 바꾸려면 클라이언트 코드 전체를 다시 짜야 하고, gRPC로 만든 내부 서비스를 외부 공개 API로 노출하려면 처음부터 다시 설계해야 하는 경우가 많다. 세 패러다임 모두 "클라이언트가 서버 데이터에 접근하는 방법"이라는 같은 문제를 풀지만, 무엇을 최적화하느냐가 근본적으로 다르다.

REST는 자원(resource) 중심으로 URL과 HTTP 메서드를 매핑하는 단순함과 생태계 성숙도를 우선한다. GraphQL은 클라이언트가 필요한 필드만 정확히 요청할 수 있는 유연성을 우선한다. gRPC는 강타입 스키마와 HTTP/2 기반 바이너리 프로토콜로 성능과 타입 안정성을 우선한다. 이 글에서는 이 세 축을 기준으로 언제 무엇을 고를지 정리한다.

## 핵심 개념 1: 클라이언트가 다양한가, 단일한가

이 선택에서 가장 먼저 물어야 할 질문은 "이 API를 소비하는 클라이언트가 얼마나 다양한가"다. 모바일 앱, 웹, 여러 서드파티가 저마다 다른 필드 조합을 필요로 하는 공개 API라면, 클라이언트마다 필요한 데이터 형태가 다르다는 문제를 서버가 각 클라이언트 전용 엔드포인트로 대응하기는 비효율적이다. GraphQL은 이런 상황에 정확히 맞는다 — 스키마는 하나로 유지하되, 각 클라이언트가 쿼리로 자신에게 필요한 필드만 선택하게 한다.

반대로 클라이언트가 소수이고 예측 가능하다면(내부 마이크로서비스 간 통신, 통제된 모바일 앱 하나) GraphQL의 유연성은 실익보다 복잡도 비용이 크다. 이 경우 REST의 단순함이나 gRPC의 성능이 더 유리하다.

## 핵심 개념 2: 오버페칭/언더페칭 vs N+1 vs 강타입 계약

세 패러다임이 각각 지닌 구조적 약점을 이해하면 선택이 명확해진다. REST는 자원 단위로 응답을 고정하기 때문에 **오버페칭**(필요 없는 필드까지 받음)과 **언더페칭**(필요한 데이터를 얻으려면 여러 엔드포인트를 추가 호출해야 함) 문제를 동시에 겪는다. GraphQL은 이 문제를 클라이언트가 필드를 선택하게 해서 풀지만, 중첩된 필드를 리졸버가 하나씩 순회하며 조회하면 **N+1 쿼리 문제**가 쉽게 발생한다(예: 게시글 100개를 조회한 뒤 각 게시글의 작성자를 100번 별도로 조회). gRPC는 Protocol Buffers로 요청·응답 스키마를 컴파일 타임에 강제하는 대신, 이 강타입 계약이 스키마 변경 시 클라이언트·서버 양쪽의 재생성과 배포를 동기화해야 하는 결합도로 이어진다.

| 기준 | REST | GraphQL | gRPC |
|---|---|---|---|
| 데이터 형태 유연성 | 낮음(고정 응답) | 높음(클라이언트가 필드 선택) | 낮음(고정 메시지 스키마) |
| 프로토콜 | HTTP/1.1 텍스트(JSON) | HTTP 위의 쿼리 언어 | HTTP/2 바이너리(Protobuf) |
| 브라우저 직접 호출 | 쉬움 | 쉬움 | 어려움(grpc-web 등 별도 필요) |
| 대표 약점 | 오버/언더페칭 | N+1 쿼리, 캐싱 복잡도 | 브라우저 친화성 낮음, 강결합 |
| 적합한 상황 | 공개 API, 단순 CRUD | 다양한 클라이언트, 복잡한 데이터 그래프 | 내부 서비스 간 고성능 통신 |

## 핵심 개념 3: 캐싱 전략의 차이

REST는 URL 자체가 캐시 키 역할을 해 HTTP 캐싱(CDN, 브라우저 캐시, `Cache-Control` 헤더)을 그대로 활용할 수 있다. GraphQL은 같은 엔드포인트(보통 `POST /graphql`)로 서로 다른 쿼리가 들어오므로 URL 기반 캐싱이 통하지 않아, 클라이언트 쪽 정규화 캐시(Apollo Client, Relay)나 응답 필드 단위 캐싱 같은 별도 전략이 필요하다. gRPC는 애초에 요청-응답이 아니라 스트리밍까지 포함하는 다양한 통신 패턴(단항, 서버 스트리밍, 클라이언트 스트리밍, 양방향 스트리밍)을 지원해, HTTP 캐싱보다는 애플리케이션 레벨의 명시적 캐싱이 기본 전제다.

<img src="/assets/images/posts/2026-08-28-api-paradigm-graphql-rest-grpc-tradeoff-1.svg" alt="REST는 오버페칭과 언더페칭, GraphQL은 N+1 쿼리, gRPC는 강타입 결합도라는 각기 다른 구조적 트레이드오프를 갖는 비교도" style="width:100%;">

## 예제: 같은 요구사항을 세 패러다임으로

```
# REST: 게시글과 작성자를 함께 보려면 두 번 호출하거나 커스텀 엔드포인트 필요
GET /posts/42          -> { id, title, body, authorId }
GET /users/7           -> { id, name, email }   (언더페칭 해결 위해 추가 호출)
```

```graphql
# GraphQL: 필요한 필드만 한 번의 쿼리로
query {
  post(id: 42) {
    title
    author {
      name       # author 관련 다른 필드(email 등)는 요청하지 않으면 응답에 없음
    }
  }
}
```

```protobuf
// gRPC: Protocol Buffers로 스키마를 컴파일 타임에 고정
service PostService {
  rpc GetPost(GetPostRequest) returns (PostResponse);
}
message PostResponse {
  int64 id = 1;
  string title = 2;
  Author author = 3; // 서버가 항상 이 구조로 응답, 클라이언트가 필드를 고를 수 없음
}
```

GraphQL 예제의 N+1 문제는 `DataLoader` 같은 배치·캐싱 유틸리티로 리졸버 호출을 한 틱 안에서 모아 한 번의 배치 쿼리로 묶어 해결하는 것이 표준적인 접근이다.

## 실무 포인트

- **하나의 패러다임만 고집할 필요는 없다**: 외부 공개 API는 GraphQL, 내부 서비스 간 통신은 gRPC, 단순 웹훅이나 헬스체크는 REST처럼 계층별로 다른 패러다임을 혼용하는 것이 실무에서는 흔하다.
- **GraphQL 도입 시 N+1과 쿼리 복잡도 제한은 필수 과제다**: `DataLoader` 없이 GraphQL을 프로덕션에 올리면 십중팔구 성능 문제를 겪는다. 또한 클라이언트가 임의로 깊은 중첩 쿼리를 보낼 수 있으므로 쿼리 깊이·복잡도 제한을 서버 쪽에서 강제해야 한다.
- **gRPC는 브라우저 직접 호출을 전제하지 말 것**: 웹 브라우저는 gRPC의 HTTP/2 트레일러를 직접 다루지 못해 grpc-web 프록시나 별도 게이트웨이가 필요하다. 프런트엔드가 직접 소비할 API라면 이 추가 계층 비용을 미리 감안해야 한다.

## 3줄 요약

- REST는 단순함과 HTTP 캐싱 생태계가, GraphQL은 다양한 클라이언트의 필드 선택 유연성이, gRPC는 강타입 스키마와 HTTP/2 성능이 각각의 최우선 가치다.
- 세 패러다임은 각기 다른 구조적 약점(REST의 오버/언더페칭, GraphQL의 N+1, gRPC의 강결합·브라우저 비친화성)을 가지므로 선택은 트레이드오프 인식 위에서 이뤄져야 한다.
- 클라이언트 다양성이 낮은 내부 서비스는 gRPC, 다양한 외부 클라이언트를 위한 공개 API는 GraphQL, 단순 CRUD는 REST처럼 계층별 혼용이 현실적인 선택이다.

## 참고 자료

- [GraphQL 공식 문서: Thinking in Graphs](https://graphql.org/learn/thinking-in-graphs/)
- [gRPC 공식 문서: Core Concepts](https://grpc.io/docs/what-is-grpc/core-concepts/)
- [Google Cloud: API Design — REST vs gRPC vs GraphQL](https://cloud.google.com/blog/products/api-management/understanding-grpc-openapi-and-rest-and-when-to-use-them)
