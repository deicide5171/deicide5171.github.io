---
layout: single
title: "API 하나로 웹도 앱도 만족시키려다 생기는 문제 — BFF 패턴 실무"
date: 2026-08-26 12:45:00 +0530
categories: system-design
tags: ["system-design", "bff", "api-gateway", "microservices", "frontend", "architecture"]
toc: true
toc_sticky: true
excerpt: "웹·모바일·서드파티가 같은 백엔드 API를 공유할 때 생기는 화면 맞춤 로직 충돌 문제를, 클라이언트별 BFF(Backend for Frontend) 계층으로 분리하는 실전 설계를 정리한다."
---

MSA로 백엔드를 여러 서비스로 쪼갠 팀이 다음으로 흔히 마주치는 문제는 "화면 하나를 그리려고 서비스 다섯 개를 호출해야 한다"는 것이다. 모바일 앱은 배터리와 네트워크를 아끼려고 최소한의 필드만 원하고, 웹 대시보드는 한 화면에 여러 도메인 데이터를 합쳐 보여줘야 하고, 서드파티 파트너는 또 다른 응답 스키마를 요구한다. 이 요구를 전부 하나의 범용 API가 만족시키려 하면, 그 API는 결국 모든 클라이언트의 특수 케이스로 뒤덮인 스파게티가 된다.

BFF(Backend for Frontend)는 이 문제를 "클라이언트 종류별로 전용 백엔드를 하나씩 둔다"는 단순한 원칙으로 푼다. 각 BFF는 도메인 서비스들을 호출해 그 클라이언트에 맞는 모양으로 데이터를 조합·가공하고, 클라이언트는 오직 자신의 BFF하고만 대화한다. 이렇게 하면 클라이언트별 맞춤 로직이 도메인 서비스 코드를 오염시키지 않고, 각 프런트엔드 팀이 자신의 BFF를 독립적으로 배포할 수 있다.

## 핵심 개념 1: BFF는 API 게이트웨이와 다른 층위의 문제를 푼다

API 게이트웨이(라우팅, 인증, 레이트리밋, 로깅 등 공통 관심사를 처리하는 진입점)와 BFF는 자주 혼동되지만 목적이 다르다. 게이트웨이는 "모든 클라이언트에 공통으로 필요한 인프라 관심사"를 처리하고, BFF는 "이 클라이언트에만 필요한 데이터 조합·변환 로직"을 처리한다. 실무에서는 두 계층을 함께 쓰는 경우가 많다: 요청이 게이트웨이 → 해당 클라이언트의 BFF → 여러 도메인 서비스 순으로 흐른다.

| 구분 | API 게이트웨이 | BFF |
|---|---|---|
| 목적 | 라우팅, 인증, 레이트리밋 | 클라이언트별 데이터 조합·가공 |
| 소유 팀 | 플랫폼/인프라 팀 | 각 프런트엔드 팀 |
| 클라이언트 인지 | 인지하지 않음(범용) | 특정 클라이언트 전용 |
| 배포 단위 | 보통 단일 | 클라이언트 수만큼 |

## 핵심 개념 2: 여러 BFF는 곧 여러 배포 단위다

BFF를 도입할 때 가장 흔한 실수는 "BFF를 하나만 만들고 그 안에서 클라이언트별 분기(if platform == 'mobile')를 처리"하는 것이다. 이렇게 하면 결국 예전의 범용 API와 같은 문제로 되돌아간다. BFF 패턴의 핵심은 **클라이언트마다 별도의 코드베이스와 배포 파이프라인을 갖는 것**이다. 웹 BFF는 웹 프런트엔드 팀이, 모바일 BFF는 모바일 팀이 소유하고 독립적으로 배포한다.

이 구조는 조직적 이점도 크다. 프런트엔드 팀이 백엔드 도메인 팀의 릴리스를 기다리지 않고 자신의 BFF에서 응답 형태를 바꿀 수 있고, 화면 요구사항 변경이 도메인 서비스까지 전파되지 않는다. 다만 도메인 서비스가 늘어날수록 BFF 수 × 도메인 서비스 수만큼 호출 경로가 늘어나므로, 인증 토큰 전파, 타임아웃/서킷브레이커, 캐싱 정책을 BFF 공통 라이브러리로 표준화하는 작업이 필요하다.

## 예제: Node.js BFF에서 여러 도메인 서비스를 병렬 조합하기

```javascript
// mobile-bff/handlers/orderSummary.js
async function getOrderSummary(req, res) {
  const userId = req.auth.userId;

  // 모바일 화면에 필요한 최소 필드만 병렬로 조회
  const [user, order, shipment] = await Promise.all([
    userService.getProfile(userId, { fields: ['name', 'tier'] }),
    orderService.getLatestOrder(userId),
    shipmentService.getTrackingStatus(userId),
  ]);

  // 모바일 앱 전용 응답 형태로 조합 — 웹 BFF와는 다른 shape
  res.json({
    greeting: `${user.name}님, 안녕하세요`,
    orderId: order.id,
    status: shipment.status,
    etaDays: shipment.etaDays,
  });
}
```

같은 데이터를 다루는 웹 BFF의 핸들러는 대시보드용 상세 필드(주문 이력, 결제 수단 목록 등)를 추가로 조합하는 별도 구현을 갖는다. 도메인 서비스(`orderService`, `shipmentService`)는 두 BFF에서 동일하게 재사용되지만, 응답 형태 결정 로직은 서로 완전히 독립적이다.

## 실무 포인트

- **BFF에 비즈니스 로직을 넣지 않는다**: BFF는 조합·변환 계층이지 도메인 규칙을 재구현하는 곳이 아니다. 할인 계산이나 재고 검증 같은 로직이 BFF에 스며들면, 웹과 모바일 BFF 사이에 같은 규칙이 중복 구현되며 불일치가 생긴다.
- **BFF도 장애 전파 경로다**: BFF가 여러 서비스를 팬아웃 호출하는 구조이므로, 한 서비스가 느려지면 BFF 응답 전체가 느려진다. 타임아웃과 부분 실패 시 그레이스풀 디그레이드(일부 필드 누락 허용) 정책을 BFF 레벨에서 명시적으로 설계해야 한다.
- **GraphQL을 BFF 대신 쓸지 함께 쓸지 정한다**: GraphQL은 클라이언트가 필요한 필드를 직접 선언할 수 있어 BFF의 존재 이유 일부를 대체하지만, 복잡한 클라이언트별 워크플로 로직(여러 단계 조합, 클라이언트 전용 캐싱)까지 대체하지는 못한다. 팀 규모가 작다면 GraphQL 게이트웨이 하나로 시작하고, 클라이언트별 요구가 뚜렷이 갈리기 시작하면 BFF를 분리하는 점진적 접근이 안전하다.

## 3줄 요약

- 화면 하나를 위해 여러 서비스를 호출하는 문제를 도메인 서비스가 아니라 클라이언트별 BFF 계층에서 흡수한다.
- BFF는 API 게이트웨이와 층위가 다르며, 클라이언트마다 독립된 코드베이스·배포 파이프라인을 갖는 것이 핵심이다.
- BFF에 비즈니스 로직을 넣지 않고, 팬아웃 호출의 장애 전파와 부분 실패 정책을 명시적으로 설계해야 한다.

## 참고 자료

- [Sam Newman: Pattern — Backends For Frontends](https://samnewman.io/patterns/architectural/bff/)
- [Netflix Tech Blog: Embracing the Differences: Inside the Netflix API Redesign](https://netflixtechblog.com/embracing-the-differences-inside-the-netflix-api-redesign-15fd8b3dc9d3)
- [Microsoft Azure Architecture Center: Backends for Frontends pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/backends-for-frontends)
