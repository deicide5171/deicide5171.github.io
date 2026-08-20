---
layout: single
title: "자바 equals와 hashCode가 뭔가요 — 같음을 정의하는 규칙"
date: 2026-09-20 13:25:00 +0530
categories: backend
tags: ["java", "equals", "hashcode", "동등성", "입문"]
toc: true
toc_sticky: true
excerpt: "객체가 같은지 판단하는 equals와 해시 기반 자료구조가 쓰는 hashCode를 왜 함께 재정의해야 하는지 처음 배우는 사람 기준으로 정리했다."
---

## "값이 같은 객체인데 다르다고 나온다"

내용이 같은 두 객체를 `==`나 기본 `equals`로 비교하면 `false`가 나온다. 기본 동작은 "같은 메모리 주소인가"를 보기 때문이다. **값으로 같음을 판단**하려면 `equals`를 재정의해야 하고, 그러면 `hashCode`도 함께 재정의해야 한다.

## equals와 hashCode의 역할

| 메서드 | 역할 |
|---|---|
| equals | 두 객체가 논리적으로 같은지 판단 |
| hashCode | 객체를 정수 해시로 요약(HashMap·HashSet이 사용) |

## 왜 함께 재정의하나

```text
규칙: equals가 true면 hashCode도 반드시 같아야 한다.

HashMap/HashSet은 hashCode로 먼저 버킷을 찾고,
그 안에서 equals로 최종 비교한다.

equals만 재정의하고 hashCode를 안 하면 →
같은 값 객체가 다른 버킷으로 가서 "못 찾는" 버그 발생.
```

## 실무 포인트

- **둘은 항상 세트로.** `equals`를 재정의하면 `hashCode`도 반드시 함께 재정의한다. 하나만 하면 컬렉션에서 버그가 난다.
- **같은 필드를 기준으로.** equals에서 비교한 필드로 hashCode도 계산해야 규칙이 지켜진다. `Objects.equals`·`Objects.hash`를 쓰면 간단하다.
- **record·롬복·IDE 생성 활용.** 자바 `record`는 equals·hashCode를 자동 생성한다. 롬복 `@EqualsAndHashCode`나 IDE 자동 생성도 실수를 줄여준다.

## 마무리 요약

- 기본 비교는 주소 기준이라, 값으로 같음을 판단하려면 equals를 재정의한다.
- equals가 true면 hashCode도 같아야 한다는 규칙 때문에 둘을 함께 재정의한다.
- 같은 필드를 기준으로 계산하고, record·롬복·IDE 생성으로 실수를 줄인다.

## 참고 자료

- [Oracle Java 문서 - Object.hashCode](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/Object.html#hashCode())
