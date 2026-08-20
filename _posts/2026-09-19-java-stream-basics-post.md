---
layout: single
title: "자바 Stream이 뭔가요 — 컬렉션을 선언적으로 다루기"
date: 2026-09-19 12:25:00 +0530
categories: backend
tags: ["java", "stream", "람다", "컬렉션", "입문"]
toc: true
toc_sticky: true
excerpt: "for 반복문 대신 filter·map·collect로 데이터를 선언적으로 처리하는 자바 Stream의 기본을 처음 배우는 사람 기준으로 정리했다."
---

## "for 반복문이 길고 읽기 어렵다"

리스트를 걸러 변환하고 모으는 작업을 for 문으로 짜면, 임시 리스트와 조건문이 얽혀 길어진다. 자바 **Stream**은 "무엇을 할지"를 `filter`·`map`·`collect`로 선언해, 같은 일을 짧고 읽기 쉽게 표현한다.

## for 문 vs Stream

```java
// for 문
List<String> result = new ArrayList<>();
for (User u : users) {
    if (u.getAge() >= 20) {
        result.add(u.getName());
    }
}

// Stream: "20세 이상의 이름을 모아라"
List<String> result = users.stream()
    .filter(u -> u.getAge() >= 20)
    .map(User::getName)
    .collect(Collectors.toList());
```

## 자주 쓰는 연산

| 연산 | 하는 일 |
|---|---|
| filter | 조건에 맞는 것만 남김 |
| map | 각 요소를 변환 |
| sorted | 정렬 |
| collect | 결과를 리스트·맵 등으로 모음 |
| count / sum | 개수·합계 집계 |

## 중간 연산과 최종 연산

`filter`·`map`은 **중간 연산**이라 결과를 바로 만들지 않고 지연된다. `collect`·`count` 같은 **최종 연산**이 호출될 때 비로소 파이프라인이 한 번에 실행된다.

## 실무 포인트

- **가독성을 위해 쓴다.** "무엇을"에 집중해 로직이 한눈에 읽히는 게 Stream의 최대 장점이다. 짧은 단순 반복은 그냥 for 문이 나을 때도 있다.
- **최종 연산이 없으면 아무 일도 안 한다.** `filter`만 쓰고 `collect`를 빼먹으면 실행조차 되지 않는다.
- **한 번 쓰면 끝.** Stream은 최종 연산 후 재사용할 수 없다. 다시 쓰려면 새로 `stream()`을 만든다.

## 마무리 요약

- Stream은 `filter`·`map`·`collect`로 컬렉션 처리를 선언적으로 표현한다.
- 중간 연산은 지연되고, 최종 연산이 호출돼야 실행된다.
- 가독성이 목적이며, 최종 연산 없이는 동작하지 않고 재사용도 안 된다.

## 참고 자료

- [Oracle Java 문서 - Stream](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/stream/Stream.html)
