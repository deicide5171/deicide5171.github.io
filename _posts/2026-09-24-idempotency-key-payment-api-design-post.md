---
layout: single
title: "멱등성(Idempotency) 키 설계 — 결제 API에서 중복 요청을 안전하게 처리하기"
date: 2026-09-24 13:45:00 +0530
categories: system-design
tags: ["멱등성", "IdempotencyKey", "결제시스템", "API설계", "분산시스템"]
toc: true
toc_sticky: true
excerpt: "네트워크 타임아웃 뒤 클라이언트가 재시도한 결제 요청이 실제로는 이미 처리됐을 때 중복 결제로 이어지는 문제를, 멱등성 키를 요청 식별과 응답 재현이라는 두 가지 역할로 나눠 설계하는 방법으로 정리했다."
---

## 왜 지금 멱등성 키를 다시 봐야 하는가

클라이언트가 결제 요청을 보냈는데 응답을 받기 전에 네트워크가 끊기면, 클라이언트 입장에서는 요청이 성공했는지 실패했는지 알 수 없다. 이때 클라이언트가 안전하게 취할 수 있는 유일한 행동은 재시도뿐인데, 문제는 원래 요청이 서버에서는 이미 성공적으로 처리됐을 가능성이 있다는 점이다. 재시도 요청을 서버가 새로운 결제로 그대로 처리하면 같은 금액이 두 번 청구되는 중복 결제 사고가 발생한다. 멱등성 키는 "같은 키로 여러 번 요청해도 실제 부작용은 한 번만 일어나고, 나머지는 최초 처리 결과를 그대로 돌려준다"는 계약을 클라이언트와 서버 사이에 명시적으로 맺는 메커니즘이다. 단순히 "중복 체크"라고 뭉뚱그리기 쉽지만, 실제로 안전하게 구현하려면 몇 가지 미묘한 동시성 문제를 함께 풀어야 한다.

## 핵심 개념 1 — 멱등성 키는 클라이언트가 생성하고, 요청 내용과 함께 저장해야 한다

멱등성 키는 서버가 아니라 클라이언트가 생성해서 요청 헤더(예: `Idempotency-Key`)에 담아 보낸다. 서버가 키를 생성하면 애초에 "같은 요청인지" 판단할 수 있는 주체가 없어지기 때문이다. 서버는 이 키를 받으면 저장소에서 먼저 조회하고, 처음 보는 키라면 실제 처리를 진행하면서 키와 함께 요청 본문의 해시, 그리고 최종 응답을 저장한다. 이미 존재하는 키라면 두 가지를 확인해야 한다 — 요청 본문이 최초 요청과 동일한지(다르다면 키 재사용 오류로 거부해야 한다), 그리고 최초 요청의 처리가 이미 끝났는지(아직 처리 중이라면 그 사실을 알리거나 대기시켜야 한다).

## 핵심 개념 2 — 동시에 들어온 같은 키 요청 사이의 경쟁 조건

클라이언트가 타임아웃 직후 즉시 재시도하면, 서버 입장에서는 첫 번째 요청이 아직 처리 중인데 같은 키로 두 번째 요청이 거의 동시에 들어오는 상황이 생긴다. 단순히 "키가 존재하면 저장된 응답을 반환"하는 로직만 있으면, 첫 번째 요청이 아직 응답을 저장하기 전이라 두 번째 요청도 "새로운 키"로 오인해 실제 처리를 중복 실행해버릴 위험이 있다. 이를 막으려면 키를 저장소에 기록하는 시점 자체를 원자적 연산(예: DB의 유니크 제약 위반을 이용한 INSERT, 또는 Redis의 SETNX)으로 만들어, 두 번째 요청이 "처리 중" 상태를 확인하고 첫 번째 요청의 결과를 기다리거나 즉시 충돌 응답을 받도록 설계해야 한다.

| 상태 | 의미 | 두 번째 요청에 대한 처리 |
|---|---|---|
| 키 없음 | 최초 요청 | 정상 처리 진행, 키를 원자적으로 선점 |
| 키 있음 + 처리 중 | 같은 요청이 아직 처리 중 | 대기 또는 409 Conflict로 재시도 유도 |
| 키 있음 + 완료 + 요청 동일 | 이미 처리 완료된 재시도 | 저장된 응답을 그대로 반환 |
| 키 있음 + 완료 + 요청 다름 | 키 재사용 오류 | 422 등으로 명시적 오류 반환 |

## 예제 — 원자적 키 선점과 상태 확인 (의사코드)

```java
@Transactional
public PaymentResponse processPayment(String idempotencyKey, PaymentRequest request) {
    String requestHash = hash(request);

    // 유니크 제약을 이용해 원자적으로 키를 선점 시도
    IdempotencyRecord record;
    try {
        record = idempotencyRepository.insertIfAbsent(idempotencyKey, requestHash, Status.IN_PROGRESS);
    } catch (DuplicateKeyException e) {
        record = idempotencyRepository.findByKey(idempotencyKey);
        if (!record.getRequestHash().equals(requestHash)) {
            throw new IdempotencyKeyReusedException(idempotencyKey);
        }
        if (record.getStatus() == Status.IN_PROGRESS) {
            throw new PaymentInProgressException(idempotencyKey); // 클라이언트가 잠시 후 재시도
        }
        return record.getStoredResponse(); // 완료된 결과 그대로 반환
    }

    PaymentResponse response = executeActualPayment(request);
    idempotencyRepository.markCompleted(idempotencyKey, response);
    return response;
}
```

`insertIfAbsent`가 유니크 제약 위반을 던지는 방식으로 구현되면, 동시에 들어온 두 요청 중 하나만 실제 처리 권한을 갖고 나머지는 안전하게 대기하거나 저장된 결과를 받도록 만들 수 있다.

## 실무 포인트

- **멱등성 키의 유효 기간을 명시적으로 정하라.** 무기한 보관하면 저장소가 계속 커지므로, 결제 도메인이라면 보통 24시간~수일 정도로 만료 정책을 두고 그 이후에는 같은 키라도 새 요청으로 처리한다.
- **요청 본문 해시 비교를 빠뜨리지 마라.** 키만 확인하고 본문이 다른 요청까지 저장된 응답을 그대로 돌려주면, 클라이언트의 키 재사용 버그를 서버가 조용히 감춰버려 나중에 발견하기 훨씬 어려운 문제가 된다.
- **"처리 중" 상태에서의 클라이언트 동작까지 API 계약에 명시하라.** 단순히 에러를 반환하는 것보다, 얼마 뒤에 재시도하면 되는지(Retry-After)나 폴링용 상태 조회 엔드포인트를 함께 제공하면 클라이언트 구현이 훨씬 안전해진다.

## 마무리 요약

- 멱등성 키는 클라이언트가 생성해 요청과 함께 보내야 하며, 서버는 이를 요청 해시·처리 상태·최종 응답과 함께 저장해 재시도 시 실제 부작용 없이 같은 결과를 돌려줘야 한다.
- 거의 동시에 도착하는 같은 키의 요청 사이 경쟁 조건은 유니크 제약이나 원자적 연산으로 키를 선점해야만 안전하게 처리할 수 있다.
- 만료 정책과 요청 본문 해시 검증을 빠뜨리면 멱등성 메커니즘 자체가 새로운 버그의 원인이 될 수 있으므로 설계 초기에 함께 고려해야 한다.

## 참고 자료

- [Stripe - Idempotent Requests](https://docs.stripe.com/api/idempotent_requests)
- [IETF - The Idempotency-Key HTTP Header Field (draft)](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)
