---
layout: single
title: "instanceof 캐스팅은 이제 그만 — 자바 레코드와 패턴 매칭으로 코드 현대화하기"
date: 2026-08-29 12:25:00 +0530
categories: backend
tags: ["java", "record", "pattern-matching", "sealed-interface", "switch-expression", "jvm"]
toc: true
toc_sticky: true
excerpt: "레코드·레코드 패턴·sealed 인터페이스·switch 패턴 매칭이 함께 맞물려 자바의 데이터 모델링과 분기 처리 코드를 어떻게 단순화하는지 정리한다."
---

자바에서 "데이터만 담는 불변 클래스"를 만들려면 오랫동안 필드·생성자·getter·`equals`/`hashCode`/`toString`을 손으로 다 채워야 했다. Lombok 같은 라이브러리가 보일러플레이트를 줄여줬지만 그건 언어가 아니라 애노테이션 프로세서에 의존한 우회로였다. 자바 16의 레코드(record)부터 최근 버전의 레코드 패턴, sealed 인터페이스, switch 패턴 매칭까지 몇 개 버전에 걸쳐 추가된 기능들이 합쳐지면서, 이제는 언어 차원에서 대수적 데이터 타입(ADT)에 가까운 모델링과 분기 처리가 가능해졌다.

이 기능들은 따로따로 봐도 유용하지만, 함께 쓸 때 진가가 드러난다. 이 글에서는 레코드, sealed 인터페이스, 레코드 패턴, switch 패턴 매칭이 각각 무엇을 해결하고, 이들을 조합했을 때 기존의 `instanceof` 캐스팅 코드가 어떻게 바뀌는지를 정리한다.

## 핵심 개념 1: 레코드 — 불변 데이터 홀더의 보일러플레이트 제거

레코드는 "이 클래스는 필드 몇 개를 그대로 담는 불변 데이터"라는 의도를 한 줄로 선언하게 해준다. `record Point(int x, int y) {}`라고 쓰면 컴파일러가 `x()`, `y()` 접근자, `equals`/`hashCode`/`toString`, 그리고 필드 그대로를 받는 표준 생성자(canonical constructor)를 자동 생성한다. 필드는 자동으로 `final`이라 불변성이 보장되고, 필요하면 표준 생성자에 검증 로직만 압축해서 넣는 컴팩트 생성자(compact constructor) 문법도 제공한다.

```java
record Point(int x, int y) {
    Point {  // 컴팩트 생성자 - 필드 대입 없이 검증만
        if (x < 0 || y < 0) throw new IllegalArgumentException("음수 좌표 불가");
    }
}
```

레코드는 상속을 지원하지 않고(암묵적으로 `final`), 상태 없는 동작을 얹고 싶으면 인터페이스 구현이나 정적/인스턴스 메서드 추가로 확장한다. DTO, 값 객체(value object), 이벤트 페이로드처럼 "데이터가 곧 정체성"인 타입에 적합하다.

## 핵심 개념 2: sealed 인터페이스 — 허용된 하위 타입을 컴파일러가 안다

sealed 인터페이스(또는 클래스)는 "이 타입을 상속·구현할 수 있는 타입은 여기 나열한 것뿐"이라고 컴파일러에 선언하는 기능이다. 결제 결과처럼 "성공 아니면 몇 가지 실패 사유 중 하나"라는 것이 명확한 도메인에서, sealed 인터페이스와 레코드를 결합하면 다른 언어의 대수적 데이터 타입(ADT)과 거의 동일한 모델링이 된다.

```java
sealed interface PaymentResult permits Approved, Declined, NetworkError {}
record Approved(String transactionId, long amountCents) implements PaymentResult {}
record Declined(String reasonCode) implements PaymentResult {}
record NetworkError(int httpStatus) implements PaymentResult {}
```

`permits` 절 덕분에 컴파일러는 `PaymentResult`의 하위 타입이 정확히 세 가지뿐임을 안다. 이 정보는 다음 개념인 switch 패턴 매칭에서 "모든 경우를 다뤘는지"를 컴파일 타임에 검증하는 데 그대로 쓰인다.

## 핵심 개념 3: 레코드 패턴과 switch 패턴 매칭 — 분해와 분기를 한 번에

기존 자바에서 타입에 따라 분기하며 내부 필드까지 꺼내 쓰려면 `instanceof` 캐스팅과 접근자 호출을 반복해야 했다. 레코드 패턴은 `instanceof`나 `switch`의 case 자체에서 레코드를 "타입 검사 + 필드 분해"를 동시에 할 수 있게 한다.

```java
// 기존 방식 - 캐스팅 후 접근자 호출 반복
if (result instanceof Approved) {
    Approved approved = (Approved) result;
    log.info("승인: {} / {}원", approved.transactionId(), approved.amountCents());
}

// 레코드 패턴 - 타입 검사와 필드 분해를 한 번에
if (result instanceof Approved(String txId, long amount)) {
    log.info("승인: {} / {}원", txId, amount);
}
```

switch 패턴 매칭과 결합하면 sealed 타입의 모든 경우를 다루는 분기가 더 선언적으로 바뀌고, 컴파일러는 `permits`에 나열된 하위 타입 중 하나라도 처리하지 않으면 컴파일 오류를 낸다(exhaustiveness 검사). 이는 새 하위 타입을 sealed 계층에 추가했을 때, 기존 switch 문 중 그 타입을 놓친 곳을 컴파일 타임에 바로 찾아준다는 뜻이다.

```java
String message = switch (result) {
    case Approved(String txId, long amount) ->
        "승인: " + txId + " / " + amount + "원";
    case Declined(String reason) ->
        "거절: " + reason;
    case NetworkError(int status) when status >= 500 ->  // 가드 조건
        "서버 오류(" + status + ") - 재시도 가능";
    case NetworkError(int status) ->
        "네트워크 오류(" + status + ")";
};
// PaymentResult에 새 하위 타입을 추가하면, 이 switch가 모든 경우를 안 다룰 시 컴파일 에러
```

## 핵심 비교: 이전 방식과 현대화된 방식

| 구분 | 이전 방식 | 레코드 + 패턴 매칭 |
|---|---|---|
| 데이터 클래스 정의 | 필드·생성자·getter·equals 수동 작성(또는 Lombok) | `record` 한 줄 |
| 타입 분기 | if-else + instanceof 캐스팅 | switch 패턴 매칭 |
| 필드 추출 | 캐스팅 후 접근자 호출 | 레코드 패턴으로 즉시 분해 |
| 누락된 분기 감지 | 런타임에야 발견(default 분기로 숨겨짐) | 컴파일 타임 exhaustiveness 검사 |
| 도메인 표현력 | 클래스 계층 + 수동 타입 체크 | sealed 계층으로 "가능한 경우의 수"를 타입으로 표현 |

## 실무 포인트

- **모든 클래스를 레코드로 바꾸려 하지 않는다**: 레코드는 불변 데이터에 적합하다. 가변 상태나 복잡한 생명주기를 가진 객체(엔티티, 서비스 클래스)까지 레코드로 바꾸면 오히려 설계가 어색해진다.
- **sealed 계층은 도메인이 실제로 닫혀 있을 때 쓴다**: "앞으로도 새 결제 실패 사유가 계속 추가될 것"이라면 sealed보다 열린 확장이 더 맞을 수 있다. sealed는 "이 경우의 수는 우리가 다 안다"는 도메인 지식이 확실할 때 가치가 크다.
- **exhaustiveness 검사를 리팩터링 안전망으로 적극 활용한다**: sealed 인터페이스에 새 구현체를 추가했을 때 컴파일 에러가 나는 switch 문들을 그대로 "고쳐야 할 곳 목록"으로 쓸 수 있다. `default` 분기를 습관적으로 넣으면 이 안전망이 무력화되므로 꼭 필요한 경우가 아니면 지양한다.

## 3줄 요약

- 레코드는 불변 데이터 클래스의 보일러플레이트(생성자·getter·equals)를 언어 차원에서 제거하고, sealed 인터페이스는 허용된 하위 타입을 컴파일러가 알게 한다.
- 레코드 패턴은 `instanceof`/`switch`에서 타입 검사와 필드 분해를 동시에 수행해 기존의 캐스팅 반복 코드를 없앤다.
- sealed 타입과 switch 패턴 매칭을 결합하면 모든 경우를 다뤘는지 컴파일 타임에 검증(exhaustiveness)할 수 있어, 새 케이스 추가 시 놓친 분기를 즉시 찾아낼 수 있다.

## 참고 자료

- [OpenJDK JEP 395: Records](https://openjdk.org/jeps/395)
- [OpenJDK JEP 409: Sealed Classes](https://openjdk.org/jeps/409)
- [OpenJDK JEP 440: Record Patterns](https://openjdk.org/jeps/440)
- [OpenJDK JEP 441: Pattern Matching for switch](https://openjdk.org/jeps/441)
