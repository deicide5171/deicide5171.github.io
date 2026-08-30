---
layout: single
title: "Java ScopedValue (JDK 21) — ThreadLocal을 대체하는 불변 컨텍스트 전달"
date: 2026-09-24 12:25:00 +0530
categories: backend
tags: ["ScopedValue", "ThreadLocal", "JDK21", "가상스레드", "Java"]
toc: true
toc_sticky: true
excerpt: "가상 스레드 수백만 개를 만들 수 있는 시대에 ThreadLocal의 상속·정리 문제가 왜 더 심각해지는지 짚고, 값을 재할당할 수 없는 대신 메모리 누수와 상속 오염 문제를 구조적으로 없앤 ScopedValue의 동작 원리를 정리했다."
---

## 왜 지금 ScopedValue를 다시 봐야 하는가

`ThreadLocal`은 오랫동안 스레드마다 독립된 컨텍스트(요청 ID, 인증 정보, 트랜잭션 상태 등)를 전달하는 표준적인 방법이었다. 문제는 두 가지다. 첫째, `ThreadLocal.remove()`를 명시적으로 호출하지 않으면 스레드 풀 환경에서 이전 요청의 값이 다음 요청에 그대로 남아있는 누수가 발생하기 쉽다. 둘째, `InheritableThreadLocal`로 자식 스레드에 값을 상속시키는 방식은 스레드를 새로 만들 때마다 부모의 모든 값을 복사해야 해서, 가상 스레드처럼 초경량 스레드를 수백만 개 만드는 환경에서는 이 상속 비용 자체가 무시할 수 없는 오버헤드가 된다. ScopedValue는 "값을 한 번 바인딩하면 그 스코프를 벗어날 때까지 변경할 수 없다"는 불변성을 강제해 이 두 문제를 근본적으로 없애도록 설계됐다.

## 핵심 개념 1 — 바인딩은 특정 코드 블록의 실행 범위로 제한된다

`ThreadLocal`은 `set()`을 호출하면 그 값이 스레드가 살아있는 동안, 또는 명시적으로 `remove()`할 때까지 계속 남아있다. ScopedValue는 다르다. `ScopedValue.where(key, value).run(() -> { ... })`처럼 값을 바인딩하는 동시에 그 값이 유효한 코드 블록을 명시적으로 지정한다. 이 블록을 벗어나는 순간 바인딩은 자동으로 해제되며, 개발자가 정리를 깜빡할 여지 자체가 없다. 이 구조는 "이 값이 언제부터 언제까지 유효한가"를 코드만 보고 즉시 알 수 있게 해준다는 점에서도 `ThreadLocal`보다 가독성이 높다.

## 핵심 개념 2 — 불변성 덕분에 가상 스레드로의 상속 비용이 사라진다

`ScopedValue`는 한 번 바인딩되면 그 값을 바꿀 수 없다(재바인딩하려면 새로운 스코프를 열어야 한다). 이 불변성 덕분에, 구조화된 동시성으로 fork된 자식 가상 스레드는 부모의 `ScopedValue` 바인딩 값을 복사할 필요 없이 그냥 부모가 가진 참조를 그대로 공유해도 안전하다 — 어차피 그 값은 아무도 바꿀 수 없기 때문이다. `InheritableThreadLocal`이 자식 스레드마다 부모 값을 복사해야 했던 것과 달리, `ScopedValue`는 복사 없는 공유로 상속 비용 자체를 없앤다. 수백만 개의 가상 스레드를 만드는 환경에서 이 차이는 실질적인 성능 차이로 이어진다.

| 항목 | ThreadLocal | ScopedValue |
|---|---|---|
| 값 변경 | `set()`으로 언제든 재할당 가능 | 바인딩 후 불변 (재바인딩은 새 스코프 필요) |
| 정리 책임 | 개발자가 `remove()` 명시적으로 호출 | 스코프 종료 시 자동 해제 |
| 자식 스레드 전파 비용 | `InheritableThreadLocal`은 값 복사 | 불변이므로 복사 없이 공유 |
| 유효 범위 파악 | 코드 전체를 봐야 알 수 있음 | 바인딩 블록으로 명확히 한정 |

## 예제 — 요청 컨텍스트를 ScopedValue로 전달하기

```java
public class RequestContext {
    public static final ScopedValue<String> REQUEST_ID = ScopedValue.newInstance();
    public static final ScopedValue<String> USER_ID = ScopedValue.newInstance();
}

void handleRequest(HttpRequest request) {
    String requestId = UUID.randomUUID().toString();
    String userId = extractUserId(request);

    ScopedValue.where(RequestContext.REQUEST_ID, requestId)
               .where(RequestContext.USER_ID, userId)
               .run(() -> processBusinessLogic(request));
    // 이 run() 블록을 벗어나는 순간 두 바인딩은 자동으로 사라진다
}

void processBusinessLogic(HttpRequest request) {
    // 깊이 중첩된 호출 안에서도 바인딩된 값을 그대로 읽을 수 있음
    log.info("requestId={}, userId={} 처리 중", 
        RequestContext.REQUEST_ID.get(), RequestContext.USER_ID.get());

    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        scope.fork(() -> callDownstreamService()); // 자식 가상 스레드도 같은 바인딩 값 참조
        scope.join();
    }
}
```

## 실무 포인트

- **요청 스코프 컨텍스트(로깅 MDC, 인증 정보, 트랜잭션 ID)부터 ScopedValue로 옮기는 것을 우선 검토하라.** 이런 값들은 원래도 "요청 처리 동안만 유효하고 재할당이 필요 없는" 성격이라 ScopedValue의 불변성 제약과 자연스럽게 맞아떨어진다.
- **값을 중간에 반드시 바꿔야 하는 로직에는 억지로 적용하지 마라.** ScopedValue는 재할당을 지원하지 않으므로, 누산기처럼 값이 계속 바뀌어야 하는 용도에는 `ThreadLocal`이나 다른 메커니즘이 여전히 적합하다.
- **JDK 버전별 API 상태(프리뷰 여부)를 프로덕션 도입 전 반드시 확인하라.** 구조화된 동시성과 마찬가지로 ScopedValue도 여러 JDK 버전을 거치며 프리뷰 기능으로 다뤄져 왔으므로 사용 중인 버전의 정식 지원 여부를 확인해야 한다.

## 마무리 요약

- ScopedValue는 값을 특정 코드 블록의 실행 범위에서만 유효하도록 바인딩해, ThreadLocal의 수동 정리 누락 문제를 구조적으로 없앤다.
- 바인딩된 값이 불변이기 때문에 가상 스레드로 값을 전파할 때 복사가 필요 없어, 대량의 가상 스레드를 쓰는 환경에서 상속 비용을 줄인다.
- 재할당이 필요한 값에는 적합하지 않으므로, 요청 스코프 컨텍스트처럼 "한 번 정해지면 바뀌지 않는" 값부터 우선적으로 적용하는 것이 실무적으로 합리적이다.

## 참고 자료

- [JEP 506 - Scoped Values](https://openjdk.org/jeps/506)
- [Oracle - ScopedValue API Documentation](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/ScopedValue.html)
