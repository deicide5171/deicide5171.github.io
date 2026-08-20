---
layout: single
title: "Java Optional이 뭔가요 — null을 안전하게 다루기"
date: 2026-09-18 13:25:00 +0530
categories: backend
tags: ["optional", "java", "null", "nullpointer", "입문"]
toc: true
toc_sticky: true
excerpt: "값이 있을 수도 없을 수도 있음을 명시적으로 표현해 NullPointerException을 줄이는 Java Optional의 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## null이 어디서 튀어나올지 모른다

메서드가 `null`을 반환할 수 있으면, 받는 쪽이 null 체크를 잊고 `.method()`를 호출해 `NullPointerException`이 터진다. **Optional**은 **"값이 있을 수도, 없을 수도 있다"를 타입으로 명시**해, 받는 쪽이 없는 경우를 강제로 다루게 한다.

## 사용법

```java
// 없을 수 있음을 Optional로 표현
Optional<User> findUser(Long id) { ... }

// 받는 쪽: 없는 경우를 다뤄야 함
User user = findUser(1L)
    .orElse(defaultUser);           // 없으면 기본값

findUser(1L).ifPresent(u -> print(u)); // 있을 때만 실행

String name = findUser(1L)
    .map(User::getName)
    .orElse("이름 없음");            // 변환하며 처리
```

## 주요 메서드

| 메서드 | 하는 일 |
|---|---|
| `orElse(x)` | 없으면 x 반환 |
| `orElseThrow()` | 없으면 예외 |
| `ifPresent(fn)` | 있을 때만 실행 |
| `map(fn)` | 있으면 변환 |

## 실무 포인트

- **`get()`을 함부로 쓰지 마라.** `optional.get()`은 값이 없으면 예외를 던진다. null 체크 안 하고 쓰는 것과 다를 바 없다. `orElse`·`orElseThrow`·`ifPresent`로 없는 경우를 명시적으로 다룬다.
- **반환 타입에만 쓰는 게 좋다.** Optional은 "결과가 없을 수 있는 반환값"을 표현하는 용도다. 메서드 파라미터나 클래스 필드에 Optional을 쓰는 것은 권장되지 않는다.
- **컬렉션엔 빈 컬렉션을.** 리스트가 비어 있을 수 있으면 `Optional<List>`가 아니라 그냥 빈 리스트를 반환한다. Optional은 "단일 값이 없을 수 있는" 경우에 쓴다.

## 마무리 요약

- Optional은 "값이 있을 수도 없을 수도 있음"을 타입으로 명시해 NPE를 줄인다.
- `orElse`·`orElseThrow`·`ifPresent`·`map`으로 없는 경우를 명시적으로 처리한다.
- `get()` 남용을 피하고, 반환 타입에만 쓰며, 컬렉션엔 빈 컬렉션을 반환한다.

## 참고 자료

- [Oracle Java 문서 - Optional](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Optional.html)
