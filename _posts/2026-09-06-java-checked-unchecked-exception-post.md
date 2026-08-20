---
layout: single
title: "체크 예외 vs 언체크 예외 — 자바 예외 처리 기초"
date: 2026-09-06 12:25:00 +0530
categories: backend
tags: ["예외처리", "checked", "unchecked", "java", "입문"]
toc: true
toc_sticky: true
excerpt: "자바에서 try-catch를 강제하는 체크 예외와 그렇지 않은 언체크 예외의 차이, 그리고 언제 무엇을 써야 하는지 정리했다."
---

## 왜 어떤 예외는 try-catch를 강제하고 어떤 건 안 하나

자바를 배우다 보면 어떤 메서드는 예외를 `try-catch`로 감싸거나 `throws`로 던지지 않으면 컴파일 자체가 안 되고, 어떤 예외는 그런 강제가 없다. 이 차이가 **체크 예외(Checked Exception)**와 **언체크 예외(Unchecked Exception)**의 구분이다.

## 두 예외의 차이

| 항목 | 체크 예외 | 언체크 예외 |
|---|---|---|
| 상위 클래스 | Exception (RuntimeException 제외) | RuntimeException |
| 처리 강제 | 컴파일러가 try-catch/throws 강제 | 강제 안 함 |
| 대표 예시 | IOException, SQLException | NullPointerException, IllegalArgumentException |
| 의미 | 복구 가능성이 있는 예외 | 대부분 프로그래밍 오류 |

## 코드로 보는 차이

```java
// 체크 예외: 반드시 처리하거나 던져야 컴파일됨
public void readFile() {
    try {
        Files.readString(Path.of("file.txt")); // IOException 발생 가능
    } catch (IOException e) {
        // 처리하지 않으면 컴파일 에러
    }
}

// 언체크 예외: 강제하지 않음
public int divide(int a, int b) {
    return a / b; // b가 0이면 ArithmeticException, try-catch 강제 안 됨
}
```

## 언제 무엇을 쓰나

```text
체크 예외:
- 호출자가 복구할 수 있고, 반드시 대응해야 하는 상황
- 예: 파일이 없으면 다른 경로를 시도

언체크 예외:
- 프로그래밍 오류(잘못된 인자, null 등) 또는 복구 불가능한 상황
- 예: 필수 파라미터가 null이면 IllegalArgumentException

실무에서는 언체크 예외를 선호하는 경향이 강하다.
체크 예외는 모든 계층에 throws를 붙여야 해서 코드가 지저분해지기 때문이다.
```

## 실무 포인트

- **최근 프레임워크(Spring 등)는 언체크 예외를 기본으로 삼는다.** Spring은 체크 예외인 SQLException 등을 언체크 예외(DataAccessException)로 감싸서, 비즈니스 로직이 불필요한 try-catch로 지저분해지지 않게 한다.
- **예외를 잡고 아무것도 안 하는 것(빈 catch 블록)은 최악이다.** 예외를 삼켜버리면 문제가 조용히 사라져 나중에 원인을 찾기가 극도로 어려워진다. 최소한 로그라도 남기거나, 처리할 수 없으면 다시 던져야 한다.
- **예외를 잡아 다시 던질 때는 원래 예외를 포함시켜라.** `throw new MyException("메시지", e)`처럼 원인 예외(e)를 함께 넘겨야 스택트레이스가 이어져 진짜 원인을 추적할 수 있다.

## 마무리 요약

- 체크 예외는 컴파일러가 try-catch/throws를 강제하고, 언체크 예외는 강제하지 않는다.
- 체크 예외는 복구 가능한 상황, 언체크 예외는 프로그래밍 오류나 복구 불가 상황에 쓴다.
- 실무와 최신 프레임워크는 코드 간결성을 위해 언체크 예외를 선호하는 경향이 있다.

## 참고 자료

- [Oracle Java 튜토리얼 - 예외](https://docs.oracle.com/javase/tutorial/essential/exceptions/)
