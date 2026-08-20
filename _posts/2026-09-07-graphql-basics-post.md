---
layout: single
title: "GraphQL이 뭔가요 — REST와 무엇이 다른지 기초부터"
date: 2026-09-07 12:45:00 +0530
categories: system-design
tags: ["graphql", "api", "rest", "시스템설계기초", "입문"]
toc: true
toc_sticky: true
excerpt: "REST와 달리 클라이언트가 필요한 데이터만 골라 요청하는 GraphQL의 개념과 장단점을 처음 배우는 사람 기준으로 정리했다."
---

## REST의 불편함에서 출발한다

REST API에서는 "사용자 정보"를 받으려면 `/users/1`을 호출하는데, 여기엔 내가 안 쓰는 필드까지 다 딸려온다(오버페칭). 반대로 사용자와 그 사용자의 주문 목록을 함께 보려면 `/users/1`과 `/users/1/orders`를 각각 호출해야 한다(언더페칭). **GraphQL**은 클라이언트가 "필요한 데이터의 모양"을 직접 명시해 한 번에 딱 맞게 받아오는 API 방식이다.

## GraphQL 쿼리 예시

```graphql
# 필요한 필드만 골라서, 연관 데이터까지 한 번에
query {
  user(id: 1) {
    name
    email
    orders {      # 사용자의 주문까지 함께
      item
      price
    }
  }
}
```

이 한 번의 요청으로 사용자의 이름·이메일과 주문 목록을 정확히 필요한 필드만 받는다. REST라면 여러 번 호출하거나 안 쓰는 데이터까지 받아야 했을 것이다.

## REST vs GraphQL

| 항목 | REST | GraphQL |
|---|---|---|
| 엔드포인트 | 자원마다 여러 개 | 보통 하나(`/graphql`) |
| 데이터 양 | 서버가 정한 형태로 고정 | 클라이언트가 필요한 만큼 |
| 여러 자원 조회 | 여러 번 요청 | 한 번에 조합 |
| 학습·인프라 | 단순, 익숙함 | 스키마·타입 시스템 학습 필요 |
| 캐싱 | HTTP 캐싱 쉬움 | 상대적으로 까다로움 |

## 실무 포인트

- **GraphQL이 REST보다 무조건 낫다는 것은 오해다.** 클라이언트가 요구하는 데이터 형태가 다양하고 복잡할 때 빛을 발하지만, 단순한 CRUD API라면 REST가 더 간단하고 캐싱·모니터링도 쉽다.
- **N+1 문제가 서버에서 발생하기 쉽다.** 클라이언트가 연관 데이터를 자유롭게 요청하다 보면 서버가 각 항목마다 추가 쿼리를 날리게 될 수 있다. DataLoader 같은 배치 로딩 기법으로 이를 막아야 한다.
- **한 엔드포인트라 HTTP 캐싱이 까다롭다.** REST는 URL별로 캐싱하기 쉽지만, GraphQL은 모든 요청이 같은 엔드포인트로 가므로 별도의 캐싱 전략(persisted query 등)이 필요하다.

## 마무리 요약

- GraphQL은 클라이언트가 필요한 데이터의 모양을 직접 명시해 한 번에 딱 맞게 받는 API 방식이다.
- REST의 오버페칭·언더페칭 문제를 해결하지만, 스키마 학습과 캐싱·N+1 관리라는 새 과제가 생긴다.
- 데이터 요구가 다양하고 복잡하면 GraphQL이, 단순한 CRUD면 REST가 더 적합하다.

## 참고 자료

- [GraphQL 공식 사이트](https://graphql.org/learn/)
- [Apollo - GraphQL vs REST](https://www.apollographql.com/blog/graphql-vs-rest)
