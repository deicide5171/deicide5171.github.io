---
layout: single
title: "자바 NullPointerException, 원인 찾고 예방하기"
date: 2026-09-03 13:25:00 +0530
categories: backend
tags: ["java", "nullpointerexception", "npe", "트러블슈팅", "입문"]
toc: true
toc_sticky: true
excerpt: "자바에서 가장 흔한 예외인 NullPointerException이 왜 나는지, 최신 자바의 개선된 에러 메시지 읽는 법과 예방 패턴을 정리했다."
---

## 가장 흔하지만 가장 자주 당황하는 예외

`NullPointerException`(NPE)은 자바 개발자가 가장 많이 마주치는 예외다. `null`인 참조로 무언가를 하려 할 때 발생한다. 예를 들어 `user.getName()`을 호출했는데 `user`가 `null`이면, 없는 객체의 메서드를 부르려 한 것이므로 NPE가 터진다.

## NPE가 나는 전형적인 상황

```java
String name = getUserName(); // null을 반환할 수 있음
int length = name.length();  // name이 null이면 여기서 NPE

Map<String, User> users = ...;
users.get("없는키").getEmail(); // get이 null을 반환 -> NPE

List<Order> orders = user.getOrders(); // 초기화 안 된 컬렉션이 null
for (Order o : orders) { ... }         // null을 순회 -> NPE
```

## 최신 자바의 친절해진 에러 메시지

Java 14부터 Helpful NullPointerException 기능이 기본 활성화되어, **정확히 무엇이 null이었는지** 알려준다.

```text
과거:
Exception in thread "main" java.lang.NullPointerException
  (어느 변수가 null인지 알 수 없어 추측해야 했다)

Java 14+:
Cannot invoke "String.length()" because "name" is null
  (name이 null이었다는 것을 정확히 알려준다)
```

이 메시지만 잘 읽어도 어느 변수가 null인지 바로 알 수 있어 디버깅 시간이 크게 줄어든다.

## 예방하는 패턴

```java
// 1. Optional로 "값이 없을 수 있음"을 명시
public Optional<User> findUser(Long id) { ... }
findUser(1L).map(User::getName).orElse("이름 없음");

// 2. 컬렉션은 null 대신 빈 컬렉션을 반환
public List<Order> getOrders() {
    return orders != null ? orders : Collections.emptyList();
}

// 3. 외부 입력은 조기에 검증
Objects.requireNonNull(param, "param은 null일 수 없습니다");
```

핵심 원칙은 **"null을 반환하지 않기"**다. 메서드가 값이 없을 수 있음을 표현할 때는 `null` 대신 `Optional`이나 빈 컬렉션을 반환하면, 호출하는 쪽에서 NPE를 걱정할 일이 크게 줄어든다.

## 실무 포인트

- **`Optional`을 필드나 메서드 매개변수에 쓰는 것은 권장되지 않는다.** `Optional`은 주로 메서드의 반환 타입으로, "값이 없을 수 있다"를 표현할 때 쓰는 것이 원래 의도다.
- **외부(API 응답, DB 조회, 사용자 입력)에서 들어오는 값은 항상 null 가능성을 의심해야 한다.** 반대로 내가 통제하는 내부 코드까지 과도하게 null 체크로 도배하면 코드가 지저분해지므로, 경계에서 검증하는 것이 좋다.
- **롬복(Lombok)의 `@NonNull`이나 정적 분석 도구를 활용하면** 컴파일·분석 단계에서 잠재적 NPE를 미리 잡을 수 있다.

## 마무리 요약

- NPE는 null인 참조로 메서드 호출이나 필드 접근을 시도할 때 발생하는 가장 흔한 자바 예외다.
- Java 14부터는 정확히 어떤 변수가 null이었는지 알려주므로 에러 메시지를 잘 읽는 것이 첫걸음이다.
- null을 반환하지 않고 Optional·빈 컬렉션을 쓰며, 외부 입력은 경계에서 검증하는 것이 예방의 핵심이다.

## 참고 자료

- [Oracle - Helpful NullPointerExceptions (JEP 358)](https://openjdk.org/jeps/358)
- [Java 공식 문서 - Optional](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Optional.html)
