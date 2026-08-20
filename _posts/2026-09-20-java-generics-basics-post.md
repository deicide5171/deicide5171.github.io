---
layout: single
title: "자바 제네릭이 뭔가요 — 타입을 매개변수로 다루기"
date: 2026-09-20 12:25:00 +0530
categories: backend
tags: ["java", "generics", "제네릭", "타입", "입문"]
toc: true
toc_sticky: true
excerpt: "List<String>의 꺾쇠 안에 들어가는 타입 매개변수, 자바 제네릭의 개념과 기본 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "List<String>의 꺾쇠 안은 뭘까?"

`List<String>`처럼 꺾쇠(`<>`) 안에 타입을 적는 것을 자주 본다. 이것이 **제네릭(generics)**이다. 클래스나 메서드가 다룰 타입을 **매개변수처럼 밖에서 지정**하게 해서, 타입 안전성과 재사용성을 동시에 얻는다.

## 제네릭이 없으면

```java
// 제네릭 없이: 꺼낼 때마다 형변환, 실수 위험
List list = new ArrayList();
list.add("hello");
String s = (String) list.get(0);   // 캐스팅 필요

// 제네릭: 타입이 고정돼 캐스팅 불필요
List<String> list = new ArrayList<>();
list.add("hello");
String s = list.get(0);            // 안전
list.add(123);                     // 컴파일 에러로 차단
```

## 직접 정의하기

```java
// 어떤 타입이든 담는 상자
class Box<T> {
    private T value;
    public void set(T value) { this.value = value; }
    public T get() { return value; }
}
Box<Integer> box = new Box<>();
box.set(10);
```

`T`는 "나중에 정할 타입"을 가리키는 자리표시자다.

## 실무 포인트

- **컴파일 시점에 오류를 잡는다.** 잘못된 타입을 넣으면 실행 전에 컴파일 에러로 걸러진다. 런타임 `ClassCastException`을 예방한다.
- **관례적 이름.** `T`(Type), `E`(Element), `K`/`V`(Key/Value)를 관용적으로 쓴다. 의미가 드러나면 좋다.
- **와일드카드(`?`)는 나중에.** `List<? extends Number>` 같은 상·하한 표현은 유연한 API를 만들 때 쓰지만, 처음엔 기본 형태부터 익히면 된다.

## 마무리 요약

- 제네릭은 클래스·메서드가 다룰 타입을 밖에서 지정하게 하는 기능이다.
- 캐스팅을 줄이고, 잘못된 타입을 컴파일 시점에 차단한다.
- `T`, `E`, `K`/`V` 같은 관용 이름을 쓰며, 와일드카드는 이후에 익히면 된다.

## 참고 자료

- [Oracle Java 튜토리얼 - Generics](https://docs.oracle.com/javase/tutorial/java/generics/index.html)
