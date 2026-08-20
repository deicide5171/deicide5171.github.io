---
layout: single
title: "동기 vs 비동기 처리, 언제 무엇을 써야 할까"
date: 2026-09-01 13:45:00 +0530
categories: system-design
tags: ["동기비동기", "비동기처리", "시스템설계기초", "메시지큐", "입문"]
toc: true
toc_sticky: true
excerpt: "요청을 즉시 처리할지, 큐에 넣고 나중에 처리할지 결정하는 동기/비동기 처리의 기본 개념과 실무 판단 기준을 정리했다."
---

## 왜 모든 요청을 즉시 처리하면 안 되는가

회원가입 API를 예로 들면, DB에 사용자를 저장하는 작업은 즉시 끝나야 하지만 환영 이메일 발송은 몇 초 늦어져도 사용자 경험에 문제가 없다. 이 두 작업을 똑같이 "즉시 처리(동기)"로 묶어버리면, 이메일 발송 서버가 느려지거나 잠깐 죽었을 때 회원가입 자체가 실패하는 불필요한 결합이 생긴다.

## 동기 처리 vs 비동기 처리

| 항목 | 동기(Synchronous) | 비동기(Asynchronous) |
|---|---|---|
| 처리 방식 | 요청 후 결과가 나올 때까지 대기 | 요청만 넣고 즉시 응답, 실제 처리는 나중에 |
| 응답 시간 | 전체 작업 시간에 비례 | 요청 접수 시간만큼만 |
| 실패 영향 | 하나가 느리면 전체가 느려짐 | 느린 작업이 전체 응답에 영향 없음 |
| 적합한 작업 | 결제 승인처럼 결과를 바로 알아야 하는 작업 | 이메일 발송, 통계 집계처럼 결과를 바로 몰라도 되는 작업 |

## 판단 흐름

```text
1. 사용자가 이 작업의 결과를 화면에서 바로 확인해야 하는가?
   → 그렇다면 동기 처리 (예: 결제 승인 결과, 로그인 성공 여부)

2. 작업 실패가 전체 요청 실패로 이어져도 괜찮은가?
   → 안 된다면 비동기로 분리 (예: 이메일 발송 실패로 회원가입 자체가 실패하면 안 된다)

3. 작업이 오래 걸리는가?
   → 오래 걸리는 작업(대용량 파일 처리, 리포트 생성)은 비동기 + 상태 조회 API 조합이 일반적이다
```

## 코드 예제: 메시지 큐를 이용한 비동기 처리

```java
@PostMapping("/signup")
public ResponseEntity<?> signup(@RequestBody SignupRequest request) {
    User user = userService.createUser(request); // 동기: 즉시 확인해야 함

    eventPublisher.publish(new UserSignedUpEvent(user.getId())); // 비동기: 큐에 넣기만 함

    return ResponseEntity.ok(user);
}

// 별도 컨슈머가 이벤트를 구독해 이메일 발송을 나중에 처리
@EventListener
public void handleUserSignedUp(UserSignedUpEvent event) {
    emailService.sendWelcomeEmail(event.getUserId());
}
```

회원가입 API의 응답 시간은 이메일 발송 속도와 무관해지고, 이메일 서버 장애가 있어도 회원가입 자체는 성공한다.

## 실무 포인트

- **비동기로 처리한 작업의 실패는 눈에 보이지 않는다.** 큐에 넣고 끝이 아니라, 실패한 작업을 재시도하거나 알림을 보내는 모니터링 체계가 함께 있어야 한다.
- **모든 것을 비동기로 만들면 시스템이 오히려 복잡해진다.** 사용자가 결과를 바로 알아야 하는 핵심 흐름까지 비동기로 만들면 "언제 처리되나요"를 계속 확인해야 하는 나쁜 UX가 된다.
- **비동기 처리를 도입하려면 메시지 큐(Kafka, RabbitMQ, SQS 등) 같은 별도 인프라가 필요해진다.** 처음부터 모든 곳에 도입하기보다, 실제로 결합도가 문제 되는 지점부터 점진적으로 분리하는 것이 안전하다.

## 마무리 요약

- 사용자가 즉시 결과를 알아야 하는 작업은 동기로, 그렇지 않은 작업은 비동기로 분리하는 것이 기본 원칙이다.
- 비동기 처리는 실패한 작업을 감지하고 재시도하는 체계가 함께 있어야 안전하다.
- 모든 작업을 비동기화하기보다 결합도가 실제로 문제 되는 지점부터 점진적으로 분리하는 것이 좋다.

## 참고 자료

- [AWS 공식 문서 - 비동기 메시징 패턴](https://docs.aws.amazon.com/whitepapers/latest/microservices-on-aws/asynchronous-communication-and-lightweight-messaging.html)
