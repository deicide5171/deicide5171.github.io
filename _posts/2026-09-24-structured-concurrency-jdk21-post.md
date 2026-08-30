---
layout: single
title: "구조화된 동시성(Structured Concurrency)으로 JDK 21 비동기 코드 정리하기"
date: 2026-09-24 12:25:00 +0530
categories: backend
tags: ["StructuredConcurrency", "JDK21", "가상스레드", "동시성", "Java"]
toc: true
toc_sticky: true
excerpt: "여러 하위 작업을 병렬로 실행하고 그중 하나가 실패하면 나머지를 정리해야 하는 로직을 CompletableFuture로 짤 때마다 반복되는 취소·예외 전파 보일러플레이트를, JDK의 구조화된 동시성 API가 어떻게 해결하는지 정리했다."
---

## 왜 지금 구조화된 동시성을 다시 봐야 하는가

여러 개의 독립적인 하위 작업(예: 사용자 정보 조회, 주문 내역 조회, 추천 상품 조회)을 병렬로 실행한 뒤 모두 완료되면 결과를 합치는 패턴은 백엔드에서 흔하다. `CompletableFuture`로 이를 구현하면 동작 자체는 문제없지만, "하나의 작업이 실패하면 나머지 진행 중인 작업도 취소한다"거나 "부모 스레드가 인터럽트되면 자식 작업들도 함께 취소돼야 한다" 같은 요구사항을 만족시키려면 상당한 보일러플레이트 코드가 필요해진다. 게다가 `CompletableFuture` 체인에서 발생한 예외의 스택 트레이스는 원래 호출 흐름과 단절돼 있어 디버깅이 까다롭다. 구조화된 동시성(Structured Concurrency)은 "여러 스레드에 걸친 하위 작업들의 생명주기를 하나의 코드 블록 범위로 묶는다"는 원칙으로 이 문제들을 근본적으로 해결하려는 시도다.

## 핵심 개념 1 — 작업의 생명주기를 코드 블록에 종속시킨다

구조화된 동시성의 핵심 아이디어는 단순하다. 하위 작업(subtask)들은 그것을 생성한 코드 블록보다 먼저 끝나거나, 그 블록이 끝나는 시점에는 반드시 함께 종료돼야 한다는 것이다. 이는 마치 일반적인 순차 코드에서 함수 안에서 호출한 다른 함수가 그 함수보다 오래 살아남을 수 없는 것과 같은 직관을 동시성 코드에 그대로 적용한 것이다. `StructuredTaskScope`를 try-with-resources 블록으로 열면, 그 블록 안에서 fork한 모든 하위 작업은 블록이 닫히기 전에 반드시 join되거나 취소된다 — 스코프를 빠져나가면서 하위 작업이 백그라운드에 좀비처럼 남아있는 상황 자체가 구조적으로 불가능해진다.

## 핵심 개념 2 — 실패 정책(ShutdownOnFailure)이 취소 전파를 자동화한다

`StructuredTaskScope.ShutdownOnFailure`를 쓰면, fork된 하위 작업 중 하나라도 예외를 던지는 순간 스코프에 속한 나머지 모든 작업에 자동으로 취소 신호(인터럽트)가 전파된다. 개발자가 각 작업의 실패를 감지해 다른 작업을 수동으로 취소하는 코드를 작성할 필요가 없다. `join()` 이후 `throwIfFailed()`를 호출하면, 실패한 작업의 원본 예외가 그대로(래핑 없이 원인 체인으로) 다시 던져지므로 스택 트레이스 추적도 훨씬 명확해진다.

| 항목 | CompletableFuture | Structured Concurrency |
|---|---|---|
| 하위 작업 생명주기 | 명시적 관리 필요 (수동 취소) | 스코프 종료 시 자동 정리 |
| 실패 전파 | `exceptionally`/`handle`로 수동 처리 | `ShutdownOnFailure`로 자동 전파 |
| 예외 스택 트레이스 | 원래 호출 흐름과 단절되기 쉬움 | 원인 체인 보존 |
| 가상 스레드와의 결합 | 별도 설정 필요 | 기본적으로 가상 스레드 기반 fork |

## 예제 — 병렬 조회와 실패 시 자동 취소

```java
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    Subtask<User> userTask = scope.fork(() -> fetchUser(userId));
    Subtask<List<Order>> orderTask = scope.fork(() -> fetchOrders(userId));
    Subtask<List<String>> recommendTask = scope.fork(() -> fetchRecommendations(userId));

    scope.join();           // 모든 하위 작업이 끝나거나, 하나가 실패해 전체 취소될 때까지 대기
    scope.throwIfFailed();  // 실패한 작업이 있으면 원본 예외를 그대로 재발생

    // 이 시점에는 세 작업 모두 성공했음이 보장됨
    return new UserPageResponse(userTask.get(), orderTask.get(), recommendTask.get());
}
```

`fetchOrders`에서 예외가 발생하면 `fetchUser`와 `fetchRecommendations`가 아직 진행 중이더라도 즉시 인터럽트 신호를 받고, `join()`이 반환된 뒤 `throwIfFailed()`가 원본 예외를 던진다. 세 작업 중 무엇이 얼마나 진행됐는지 신경 쓰지 않고도 스코프 하나로 전체 생명주기가 정리된다.

## 실무 포인트

- **JDK 버전과 API 안정화 상태를 먼저 확인하라.** 구조화된 동시성은 여러 JDK 버전을 거치며 프리뷰 기능으로 발전해 왔으므로, 프로덕션 도입 전 사용 중인 JDK 버전에서의 API 상태(프리뷰 여부, 패키지 경로)를 반드시 확인해야 한다.
- **가상 스레드와 함께 쓸 때 블로킹 I/O 라이브러리의 스레드 로컬 사용 여부를 점검하라.** 구조화된 동시성은 기본적으로 가상 스레드 기반으로 fork하므로, 커넥션 풀 등 스레드 로컬에 의존하는 라이브러리가 있다면 가상 스레드 피닝 문제와 함께 검토해야 한다.
- **모든 병렬 작업에 무조건 적용하지 마라.** 서로 독립적이지 않고 결과에 순차적 의존성이 있는 로직에 억지로 구조화된 동시성을 적용하면 오히려 코드가 부자연스러워진다. 진짜 "여러 독립 작업을 함께 시작하고 함께 끝내야 하는" 패턴에만 쓰는 것이 적합하다.

## 마무리 요약

- 구조화된 동시성은 하위 작업의 생명주기를 코드 블록 범위에 종속시켜, 스코프를 벗어난 뒤에도 백그라운드에 남는 좀비 작업을 구조적으로 방지한다.
- `ShutdownOnFailure` 정책은 하나의 작업이 실패하면 나머지 작업에 자동으로 취소를 전파하고, 원본 예외를 그대로 재발생시켜 디버깅을 쉽게 한다.
- CompletableFuture의 수동 취소·예외 전파 보일러플레이트를 줄여주지만, 독립적인 병렬 작업 패턴에만 적용하는 것이 코드 가독성에 유리하다.

## 참고 자료

- [JEP 505 - Structured Concurrency](https://openjdk.org/jeps/505)
- [Oracle - Structured Concurrency Guide](https://docs.oracle.com/en/java/javase/21/core/structured-concurrency.html)
