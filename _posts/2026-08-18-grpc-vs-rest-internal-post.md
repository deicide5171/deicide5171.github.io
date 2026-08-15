---
layout: single
title: "gRPC vs REST, 사내 서비스 간 통신 프로토콜 결정 가이드"
date: 2026-08-18 12:40:00 +0530
categories: infra
tags: ["grpc", "rest", "protobuf", "msa", "api-design"]
toc: true
toc_sticky: true
excerpt: "마이크로서비스가 늘어나면서 서비스 간 내부 통신량이 외부 API 트래픽을 넘어서는 지금, REST와 gRPC 중 사내 통신 프로토콜을 무엇으로 골라야 하는지 실무 기준으로 정리한다."
---

## 왜 지금 이 선택이 중요한가

서비스를 몇 개 쪼개기 시작하면 곧바로 마주치는 질문이 있다. "서비스 A가 서비스 B를 부를 때 REST로 할까, gRPC로 할까?" 처음 한두 개 서비스일 때는 큰 차이가 없어 보이지만, 내부 호출이 수십 개로 늘어나는 순간부터 이 선택은 지연시간, 스키마 관리 비용, 팀 간 계약 방식 전체에 영향을 준다. 특히 요즘처럼 하나의 요청이 여러 내부 서비스를 거쳐 처리되는 구조가 흔해지면서, 외부에 노출하는 API보다 서비스끼리 주고받는 내부 트래픽의 비중이 훨씬 커진 조직도 많다.

문제는 "gRPC가 빠르니까 무조건 gRPC"도, "REST가 익숙하니까 무조건 REST"도 정답이 아니라는 점이다. 두 프로토콜은 애초에 다른 문제를 잘 풀도록 설계됐고, 사내 통신이라는 맥락에서만 통하는 판단 기준이 따로 있다. 이 글에서는 두 프로토콜의 근본적인 차이를 짚고, 실제로 어떤 상황에서 무엇을 고르는 게 합리적인지 정리한다.

## 핵심 개념 1: REST와 gRPC는 애초에 다른 계층에서 다른 문제를 푼다

REST는 HTTP/1.1과 JSON 위에서 "리소스"를 주고받는다는 설계 철학을 따른다. 사람이 curl로 바로 호출해볼 수 있고, 브라우저가 기본 지원하며, 텍스트 기반이라 디버깅이 쉽다. gRPC는 HTTP/2와 Protocol Buffers(Protobuf)를 기반으로 "함수를 원격으로 호출한다"는 RPC 철학을 따른다. 바이너리 직렬화와 스트림 멀티플렉싱을 전제로 설계되어 있어 REST보다 훨씬 무거운 트래픽을 더 적은 자원으로 처리하도록 최적화돼 있다.

<img src="/assets/images/posts/2026-08-18-grpc-vs-rest-internal-1.svg" alt="REST와 gRPC의 프로토콜 스택 비교 - 전송 계층, 직렬화 방식, 스트리밍 지원 차이 개념도" style="width:100%;">

| 구분 | REST (HTTP/1.1 + JSON) | gRPC (HTTP/2 + Protobuf) |
|---|---|---|
| 전송 계층 | HTTP/1.1 (연결당 요청 1개 순차 처리가 기본) | HTTP/2 (단일 연결에서 다중 스트림 동시 처리) |
| 페이로드 형식 | JSON (텍스트, 사람이 읽기 쉬움) | Protobuf (바이너리, 더 작고 파싱 빠름) |
| 계약(Contract) | OpenAPI 스펙(선택적, 느슨한 강제력) | `.proto` 파일(코드 생성 전제, 강한 타입) |
| 스트리밍 | 별도 구현 필요(SSE, 폴링 등) | 단방향·양방향 스트리밍 기본 지원 |
| 브라우저 직접 호출 | 기본 지원 | 기본 미지원(gRPC-Web 게이트웨이 필요) |
| 사람이 직접 테스트 | curl·Postman으로 즉시 가능 | 별도 클라이언트·리플렉션 도구 필요 |

## 핵심 개념 2: 강타입 계약이 만드는 실질적 차이

REST에서 요청·응답 스키마는 문서(OpenAPI)나 팀 간 약속으로 관리되는 경우가 많아, 필드 하나가 조용히 바뀌어도 컴파일 타임에는 잡히지 않는다. gRPC는 `.proto` 파일이 곧 계약이라서, 클라이언트·서버 코드를 이 파일에서 자동 생성한다. 필드 타입이 바뀌거나 필수 필드가 빠지면 코드 생성 단계나 컴파일 단계에서 바로 드러난다. 서비스가 많아질수록 이 차이는 "런타임에 터지는 버그"와 "빌드 단계에서 잡히는 버그"의 차이로 벌어진다.

다만 이 강타입 계약에는 대가가 따른다. `.proto` 파일을 수정하면 관련된 모든 서비스가 코드를 재생성하고 재배포해야 한다. REST는 필드를 유연하게 추가·무시할 수 있는 JSON의 관용성 덕분에 이런 동기화 부담이 상대적으로 적다.

## 핵심 개념 3: 그래서 사내 통신에는 무엇을 골라야 하나

| 상황 | 권장 |
|---|---|
| 서비스 간 호출 빈도가 높고 지연시간이 민감함(내부 마이크로서비스 체인) | gRPC |
| 스트리밍(실시간 데이터 전송, 양방향 통신)이 필요함 | gRPC |
| 외부 파트너·프론트엔드가 직접 호출해야 함 | REST |
| 팀 간 계약을 코드 생성 없이 빠르게 합의하고 자주 바꿔야 함 | REST |
| 폴리글랏 환경에서 언어 간 타입 안전성을 강하게 보장하고 싶음 | gRPC |
| 디버깅·운영 도구(curl, 브라우저 개발자 도구)로 즉시 확인해야 함 | REST |

실무에서 흔한 패턴은 "외부 게이트웨이는 REST(또는 GraphQL), 게이트웨이 뒤 내부 서비스 간 통신은 gRPC"로 계층을 나누는 방식이다. 외부 클라이언트의 접근성과 내부 통신의 성능·타입 안전성을 동시에 챙길 수 있기 때문이다.

## 예제: Protobuf로 사내 서비스 계약 정의하기

아래는 주문 서비스가 재고 서비스를 호출하는 상황을 가정한 `.proto` 정의다. 이 파일 하나로 클라이언트·서버 코드를 모두 생성할 수 있다.

```protobuf
syntax = "proto3";

package inventory.v1;

service InventoryService {
  // 단일 재고 조회
  rpc CheckStock (StockRequest) returns (StockResponse);

  // 여러 SKU의 재고 변경을 스트리밍으로 통지받기
  rpc WatchStockChanges (WatchRequest) returns (stream StockChangeEvent);
}

message StockRequest {
  string sku = 1;
}

message StockResponse {
  string sku = 1;
  int32 available_quantity = 2;
  bool is_backorder_allowed = 3;
}

message WatchRequest {
  repeated string skus = 1;
}

message StockChangeEvent {
  string sku = 1;
  int32 delta = 2;
  int64 changed_at_epoch_ms = 3;
}
```

`WatchStockChanges`처럼 `stream` 키워드 하나로 서버 스트리밍 API를 선언할 수 있다는 점이 REST 대비 두드러지는 차이다. REST로 같은 기능을 구현하려면 SSE나 롱폴링을 별도로 설계해야 하지만, gRPC는 HTTP/2 스트림을 그대로 활용해 이를 프로토콜 레벨에서 지원한다.

## 실무 포인트

- **모든 서비스를 한 번에 gRPC로 바꾸려 하지 않는다.** 트래픽이 많고 지연에 민감한 핵심 경로부터 점진적으로 전환하는 편이 리스크가 작다.
- **`.proto` 파일 버전 관리 전략을 먼저 정한다.** 필드 번호는 절대 재사용하지 않고, 필드 추가는 하위 호환을 유지하도록(옵션 필드, deprecated 표시) 팀 컨벤션을 문서화해야 한다.
- **브라우저·모바일 클라이언트가 직접 gRPC를 호출해야 한다면 gRPC-Web과 프록시(Envoy 등) 구성이 추가로 필요하다는 점을 미리 감안한다.**
- **관측성(observability) 도구가 gRPC 트래픽을 얼마나 잘 지원하는지 먼저 확인한다.** 바이너리 페이로드는 REST만큼 직관적으로 로그·트레이스에서 들여다보기 어려운 경우가 있어, APM 연동 상태를 사전에 점검하는 것이 좋다.

## 3줄 요약

- REST는 사람이 읽고 테스트하기 쉬운 리소스 중심 통신에, gRPC는 지연시간과 타입 안전성이 중요한 서비스 간 고빈도 호출에 강점이 있다.
- gRPC의 `.proto` 계약은 빌드 단계에서 스키마 불일치를 잡아주지만, 그만큼 서비스 간 재생성·재배포 동기화 비용이 따른다.
- 사내 통신은 무조건 하나를 고르기보다 "외부는 REST, 내부 핵심 경로는 gRPC"처럼 계층별로 나누어 적용하는 것이 현실적인 출발점이다.

## 참고 자료

- [gRPC 공식 문서 — Introduction](https://grpc.io/docs/what-is-grpc/introduction/)
- [Protocol Buffers 공식 문서 — Language Guide (proto3)](https://protobuf.dev/programming-guides/proto3/)
- [gRPC 공식 문서 — gRPC-Web](https://grpc.io/docs/platforms/web/basics/)
