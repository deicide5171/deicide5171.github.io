---
layout: single
title: "계약 테스트(Contract Testing)로 MSA 간 API 깨짐 막기 — Pact 실전"
date: 2026-09-24 13:25:00 +0530
categories: backend
tags: ["ContractTesting", "Pact", "MSA", "테스트전략", "API"]
toc: true
toc_sticky: true
excerpt: "서비스가 늘어날수록 매번 전체 서비스를 띄워야 하는 E2E 테스트가 느려지고 불안정해지는 문제를, 소비자가 정의한 계약을 공급자가 지키는지 독립적으로 검증하는 계약 테스트와 Pact 도구로 해결하는 구조를 정리했다."
---

## 왜 지금 계약 테스트를 다시 봐야 하는가

MSA로 서비스를 쪼개다 보면 특정 서비스의 API 응답 필드 하나를 바꿨을 뿐인데 그 API를 호출하던 다른 서비스가 배포 후에야 깨지는 사고를 겪는다. 이를 막기 위해 여러 서비스를 함께 띄워 통합적으로 검증하는 E2E 테스트를 늘리는 경우가 많지만, 서비스 수가 늘어날수록 E2E 환경 구축 자체가 무거워지고, 테스트가 느려지고, 어느 서비스 하나만 문제여도 전체 테스트가 실패해 원인 파악이 어려워지는 악순환에 빠진다. 계약 테스트(Contract Testing)는 이 문제를 "모든 서비스를 함께 띄워서 확인"하는 대신 "API를 사용하는 쪽(Consumer)이 기대하는 계약을, API를 제공하는 쪽(Provider)이 지키는지"를 각자 독립적으로 검증하는 방식으로 접근한다.

## 핵심 개념 1 — 소비자 주도 계약(Consumer-Driven Contract)

Pact가 채택한 방식은 소비자 주도 계약(CDC)이다. API를 실제로 호출하는 소비자 서비스가 먼저 "나는 이 엔드포인트를 이런 요청으로 호출하고, 이런 형태의 응답을 기대한다"는 계약(pact 파일)을 테스트 코드로 작성한다. 이 계약은 소비자 쪽 테스트를 실행하는 과정에서 Mock 서버를 통해 검증되고, JSON 파일로 산출된다. 이후 공급자 서비스는 이 계약 파일을 가져와 자신의 실제 구현이 그 계약을 만족하는지 검증하는 별도의 테스트를 실행한다. 두 서비스는 서로를 직접 띄우지 않고도, 계약이라는 매개체를 통해 API 호환성을 확인할 수 있다.

## 핵심 개념 2 — Pact Broker가 배포 안전성까지 보장하는 방식

계약 파일을 소비자와 공급자가 각자 파일로만 주고받으면 버전 관리가 금방 어려워진다. Pact Broker는 이 계약 파일들을 중앙에서 관리하고, 어떤 소비자 버전이 어떤 공급자 버전과 호환되는지 매트릭스로 추적한다. 여기서 나온 것이 `can-i-deploy` 검사다 — 공급자를 배포하기 전에, 현재 운영 중인 모든 소비자 버전의 계약을 이 새 공급자 버전이 여전히 만족하는지 CI에서 자동으로 확인한 뒤에만 배포를 진행하도록 파이프라인에 게이트를 걸 수 있다.

| 접근 방식 | 검증 범위 | 실행 속도 | 실패 원인 파악 |
|---|---|---|---|
| E2E 테스트 | 전체 시스템 통합 동작 | 느림 | 어려움 (여러 서비스 얽힘) |
| 계약 테스트 | 소비자-공급자 API 계약 | 빠름 (독립 실행) | 쉬움 (계약 위반 지점 명확) |
| 계약 + can-i-deploy | 계약 + 배포 시점 호환성 | 빠름 | 배포 전 사전 차단 가능 |

## 예제 — 소비자 측 Pact 테스트 (JavaScript)

```javascript
const { PactV3, MatchersV3 } = require('@pact-foundation/pact');
const { like } = MatchersV3;

const provider = new PactV3({
  consumer: 'OrderService',
  provider: 'CustomerService',
});

describe('CustomerService와의 계약', () => {
  it('고객 정보를 정상적으로 반환해야 한다', () => {
    provider
      .given('customer with id 42 exists')
      .uponReceiving('a request for customer 42')
      .withRequest({ method: 'GET', path: '/customers/42' })
      .willRespondWith({
        status: 200,
        body: { id: like(42), name: like('홍길동'), tier: like('gold') },
      });

    return provider.executeTest(async (mockServer) => {
      const client = new CustomerClient(mockServer.url);
      const customer = await client.getCustomer(42);
      expect(customer.name).toBeDefined();
    });
  });
});
```

이 테스트를 실행하면 `pacts/orderservice-customerservice.json` 계약 파일이 생성되고, `CustomerService` 팀은 이 파일을 자신의 프로바이더 검증 테스트에 가져와 실제 구현이 이 계약을 만족하는지 확인한다.

## 실무 포인트

- **계약 테스트는 E2E 테스트를 완전히 대체하지 않는다.** 여러 서비스가 얽힌 비즈니스 흐름 전체의 정합성은 여전히 소수의 스모크성 E2E 테스트로 별도 검증해야 하며, 계약 테스트는 그 사이의 API 호환성 문제를 훨씬 이른 시점에 값싸게 잡아내는 역할을 한다.
- **팀 간 계약 변경 프로세스를 먼저 합의하라.** 계약을 소비자가 정의한다고 해서 공급자와 소통 없이 임의로 계약을 바꾸면, 공급자 입장에서는 갑자기 나타난 새로운 요구사항이 되어 오히려 협업 마찰이 커진다.
- **`can-i-deploy`를 CI/CD 파이프라인의 필수 게이트로 넣어라.** 계약 검증만 로컬에서 통과시키고 배포 게이트에 연결하지 않으면, 계약 테스트를 도입한 실질적 효과(배포 사고 예방)를 얻지 못한다.

## 마무리 요약

- 계약 테스트는 전체 서비스를 함께 띄우지 않고도 소비자가 정의한 계약을 공급자가 지키는지 독립적으로, 빠르게 검증한다.
- Pact의 소비자 주도 계약 방식은 계약 위반 시 원인을 명확히 특정할 수 있어 E2E 테스트 대비 디버깅 비용이 훨씬 낮다.
- Pact Broker의 can-i-deploy 검사를 배포 파이프라인의 게이트로 삼으면, 계약을 어기는 배포 자체를 사전에 차단할 수 있다.

## 참고 자료

- [Pact - Consumer-Driven Contract Testing](https://docs.pact.io/)
- [Martin Fowler - Contract Test](https://martinfowler.com/bliki/ContractTest.html)
