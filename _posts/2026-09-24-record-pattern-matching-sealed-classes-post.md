---
layout: single
title: "Java Record Pattern Matching과 Sealed Classes 심화 (JDK 21)"
date: 2026-09-24 12:25:00 +0530
categories: backend
tags: ["RecordPattern", "SealedClasses", "PatternMatching", "JDK21", "Java"]
toc: true
toc_sticky: true
excerpt: "instanceof와 캐스팅을 반복하던 분기 로직이나 switch의 default 분기가 놓치는 케이스를 컴파일 타임에 잡아내지 못하던 문제를, Java의 Sealed Classes와 Record Pattern이 어떻게 함께 해결하는지 정리했다."
---

## 왜 지금 Record Pattern과 Sealed Classes를 다시 봐야 하는가

여러 종류의 하위 타입을 분기 처리하는 로직은 전통적으로 `instanceof` 체크와 캐스팅을 나열하거나, `switch`문에 `default` 분기를 두는 방식으로 작성해왔다. 두 방식 모두 근본적인 약점이 있다. `instanceof` 체이닝은 새로운 하위 타입이 추가됐을 때 그 분기를 빠뜨려도 컴파일러가 알려주지 않는다. `switch`의 `default` 분기는 "혹시 모를 경우"를 처리한다는 명목으로 존재하지만, 실제로는 새 타입이 추가됐는데 그 타입에 대한 처리를 깜빡했다는 사실을 숨겨버리는 역할을 하기 쉽다. Sealed Classes는 "이 타입의 하위 타입은 여기 나열한 것이 전부다"라고 컴파일러에게 선언하고, Record Pattern은 그 하위 타입이 레코드일 때 필드까지 한 번에 분해(destructure)하며 매칭할 수 있게 해준다. 이 둘이 결합되면 컴파일러가 "모든 경우의 수를 다뤘는지"를 검증해주는 완전성 검사(exhaustiveness check)가 가능해진다.

## 핵심 개념 1 — Sealed Classes: 하위 타입의 닫힌 집합을 선언한다

`sealed` 키워드로 선언한 클래스나 인터페이스는 `permits` 절에 명시한 타입만 하위 타입이 될 수 있다. 이는 단순한 접근 제어가 아니라, 컴파일러에게 "이 타입 계층의 전체 목록을 나는 이미 다 알고 있다"는 정보를 제공하는 것이다. 이 정보 덕분에 `switch` 문에서 sealed 타입의 모든 하위 타입을 분기 처리하면, `default` 분기가 없어도 컴파일러가 "모든 경우를 다뤘다"는 것을 확인하고 컴파일을 통과시킨다. 반대로 하나라도 빠뜨리면 컴파일 에러가 발생해, 새로운 하위 타입을 추가했는데 기존 분기 로직에 반영하는 것을 잊는 버그를 원천적으로 막을 수 있다.

## 핵심 개념 2 — Record Pattern: 타입 검사와 필드 분해를 한 번에

레코드는 필드 구성 자체가 타입 시그니처이므로, Record Pattern은 `instanceof`나 `switch`의 케이스 라벨에서 "이 타입이면서 동시에 필드를 이런 변수로 분해해서 꺼내라"는 것을 한 문장으로 표현할 수 있게 해준다. 중첩된 레코드도 패턴을 중첩해서 한 번에 분해할 수 있어, 기존이라면 여러 단계의 `instanceof`와 getter 호출로 풀어써야 했던 코드가 하나의 `switch` 케이스로 압축된다. 여기에 가드 조건(`when` 절)을 추가하면 타입 매칭과 값 조건을 함께 표현할 수 있어 표현력이 한층 더 올라간다.

| 항목 | 기존 방식 (instanceof + switch default) | Sealed + Record Pattern |
|---|---|---|
| 새 하위 타입 추가 시 | 기존 분기 누락을 컴파일러가 못 잡음 | 완전성 검사로 컴파일 에러 발생 |
| 필드 접근 | getter 호출을 별도로 나열 | 패턴 안에서 즉시 분해 |
| 중첩 구조 처리 | 여러 단계의 중첩 instanceof | 중첩 패턴으로 한 번에 표현 |
| 조건부 매칭 | 타입 매칭 후 별도 if | `when` 가드로 한 문장에 결합 |

## 예제 — Sealed 계층과 Record Pattern으로 결제 이벤트 처리하기

```java
sealed interface PaymentEvent permits PaymentApproved, PaymentFailed, PaymentRefunded {}

record PaymentApproved(String orderId, long amountCents) implements PaymentEvent {}
record PaymentFailed(String orderId, String reason) implements PaymentEvent {}
record PaymentRefunded(String orderId, long amountCents, String refundReason) implements PaymentEvent {}

String describe(PaymentEvent event) {
    return switch (event) {
        case PaymentApproved(String orderId, long amount) when amount > 1_000_000 ->
            "고액 결제 승인: " + orderId;
        case PaymentApproved(String orderId, long amount) ->
            "결제 승인: " + orderId + ", " + amount + "원";
        case PaymentFailed(String orderId, String reason) ->
            "결제 실패: " + orderId + " (" + reason + ")";
        case PaymentRefunded(String orderId, long amount, String reason) ->
            "환불 처리: " + orderId + ", " + amount + "원 (" + reason + ")";
        // default 없이도 컴파일 통과 — 세 타입을 모두 다뤘기 때문
    };
}
```

`PaymentEvent`에 새로운 하위 타입(예: `PaymentDisputed`)을 추가하면, 이 `switch` 문은 그 케이스를 다루지 않았다는 이유로 즉시 컴파일 에러를 낸다. 새 이벤트 타입을 처리하는 로직을 빠뜨리는 실수를 배포 전에 강제로 잡아낼 수 있다.

## 실무 포인트

- **도메인 이벤트나 API 응답처럼 "종류가 유한하고 앞으로도 이 파일 안에서만 늘어나는" 타입 계층에 sealed를 우선 적용하라.** 반대로 외부 라이브러리 사용자가 자유롭게 구현체를 추가해야 하는 인터페이스에는 적합하지 않다.
- **레코드가 아닌 일반 클래스 계층에도 sealed는 적용할 수 있지만, Record Pattern의 필드 분해 이점을 온전히 누리려면 하위 타입을 레코드로 설계하는 것이 자연스럽다.**
- **기존 `instanceof` 체이닝 코드를 한 번에 다 바꾸려 하지 말고, 새로 추가하는 도메인 이벤트·명령 계층부터 sealed + record pattern으로 설계하며 점진적으로 넓혀가는 편이 리스크가 적다.**

## 마무리 요약

- Sealed Classes는 하위 타입의 전체 목록을 컴파일러에게 알려줘, `switch`에서 완전성 검사를 가능하게 한다.
- Record Pattern은 타입 검사와 필드 분해를 한 문장으로 표현해, 중첩된 조건 분기를 간결한 `switch` 케이스로 압축한다.
- 이 둘을 결합하면 새로운 하위 타입 추가 시 처리 누락을 컴파일 타임에 강제로 잡아낼 수 있어, 런타임에야 발견되던 버그의 상당수를 배포 전에 차단할 수 있다.

## 참고 자료

- [JEP 440 - Record Patterns](https://openjdk.org/jeps/440)
- [JEP 409 - Sealed Classes](https://openjdk.org/jeps/409)
