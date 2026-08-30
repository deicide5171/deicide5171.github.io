---
layout: single
title: "Java FFM API — JNI를 대체하는 Foreign Function & Memory 연동"
date: 2026-09-26 12:25:00 +0530
categories: backend
tags: ["Java", "FFMAPI", "ProjectPanama", "JNI대체", "네이티브연동"]
toc: true
toc_sticky: true
excerpt: "네이티브 라이브러리 하나 호출하려고 C 헤더 파일과 javah, 별도 빌드 체인까지 갖춰야 했던 JNI의 부담을, 순수 자바 코드만으로 네이티브 함수를 직접 호출하고 오프힙 메모리를 안전하게 다루는 JDK 22 FFM API 표준화 버전으로 정리했다."
---

## 왜 지금 네이티브 연동 방식을 다시 봐야 하는가

이미지 처리, 암호화, 하드웨어 가속 라이브러리처럼 C/C++로 작성된 고성능 코드를 자바에서 호출해야 하는 상황은 꾸준히 있었지만, JNI(Java Native Interface)는 그 대가로 상당한 복잡도를 요구했다. 자바 쪽에 `native` 메서드를 선언하고, `javah`로 C 헤더를 생성하고, C 코드에서 JNI 함수 시그니처를 손으로 맞추고, 별도의 네이티브 빌드 체인(cmake, gcc)까지 준비해야 겨우 함수 하나를 호출할 수 있었다. 게다가 JNI 코드에서 포인터를 잘못 다루면 JVM이 세그멘테이션 폴트로 통째로 죽어버리는데, 스택 트레이스만으로는 원인을 추적하기 어려웠다. Project Panama의 결과물인 FFM(Foreign Function & Memory) API는 JDK 22에서 정식(Final) 기능으로 자리 잡으며, 순수 자바 코드만으로 네이티브 함수를 호출하고 네이티브 메모리를 안전하게 관리하는 길을 열었다.

## 핵심 개념 1 — 링커와 심볼 조회로 네이티브 함수 호출하기

FFM API의 핵심 축은 `Linker`다. `Linker.nativeLinker()`로 플랫폼 기본 링커를 얻고, `SymbolLookup`으로 공유 라이브러리(.so/.dll)에서 함수 심볼을 찾은 뒤, `FunctionDescriptor`로 그 함수의 C 시그니처(인자·반환 타입)를 자바 쪽에 선언하면, `Linker.downcallHandle()`이 그 함수를 호출 가능한 `MethodHandle`로 만들어준다. 컴파일 타임에 별도의 C 스텁 코드를 생성할 필요가 없고, 실행 중에 동적으로 어떤 네이티브 함수든 연결할 수 있다는 점이 JNI와의 근본적인 차이다.

## 핵심 개념 2 — MemorySegment와 Arena로 오프힙 메모리 안전하게 다루기

네이티브 함수는 대부분 자바 힙 바깥의 메모리(오프힙)를 포인터로 주고받는다. FFM API는 이를 `MemorySegment`라는 타입 안전한 핸들로 감싸고, 그 수명을 `Arena`가 명시적으로 관리하게 한다. `Arena.ofConfined()`로 만든 아레나는 생성한 스레드에서만 접근 가능하고 `close()` 시점에 관련된 모든 세그먼트가 한꺼번에 해제되며, 이미 닫힌 아레나의 세그먼트에 접근하면 예외가 발생한다(JVM 크래시가 아니라 자바 예외로 처리된다는 점이 핵심이다). 이는 `try-with-resources`와 자연스럽게 맞물려, 네이티브 리소스의 수명을 자바의 스코프 규칙 안으로 끌어들인다.

| 항목 | JNI | FFM API |
|---|---|---|
| 바인딩 생성 방식 | javah로 헤더 생성 + C 스텁 작성 | 런타임에 MethodHandle 동적 연결 |
| 빌드 요구사항 | 별도 네이티브 컴파일러 필요 | 순수 자바만으로 충분 |
| 메모리 접근 오류 시 | JVM 크래시(세그폴트) 위험 | 자바 예외로 처리(경계 검사) |
| 코드 유지보수 | C/자바 양쪽 동기화 필요 | 자바 단일 코드베이스 |

## 코드 예제 — libc의 strlen 호출하기

```java
import java.lang.foreign.*;
import java.lang.invoke.MethodHandle;

public class StrlenExample {
    public static void main(String[] args) throws Throwable {
        Linker linker = Linker.nativeLinker();
        SymbolLookup stdlib = linker.defaultLookup();

        MethodHandle strlen = linker.downcallHandle(
            stdlib.find("strlen").orElseThrow(),
            FunctionDescriptor.of(ValueLayout.JAVA_LONG, ValueLayout.ADDRESS)
        );

        try (Arena arena = Arena.ofConfined()) {
            MemorySegment cString = arena.allocateUtf8String("Hello, FFM!");
            long length = (long) strlen.invoke(cString);
            System.out.println("길이: " + length); // 11
        } // 아레나가 닫히며 cString 메모리 자동 해제
    }
}
```

## 실무 포인트

- **`Arena.ofConfined()`와 `Arena.ofShared()`를 상황에 맞게 골라야 한다.** 단일 스레드에서만 쓰는 리소스는 confined로 빠르게, 여러 스레드가 공유해야 하는 장기 리소스는 shared로 선언해야 한다.
- **JNI에서 마이그레이션할 때는 성능 프로파일링을 반드시 다시 해야 한다.** downcall 호출도 완전히 공짜는 아니며, `Linker.Option.critical()` 같은 옵션으로 안전 검사를 줄여 초저지연 경로를 만들 수 있지만 그만큼 안전성과 맞바꾸는 것이다.
- **기존 JNI 코드를 당장 걷어낼 필요는 없다.** FFM API는 신규 네이티브 연동부터 우선 적용하고, 안정성이 검증된 기존 JNI 모듈은 점진적으로 이관하는 편이 리스크가 적다.

## 마무리 요약

- FFM API는 JDK 22에서 정식화된 기능으로, C 헤더 생성과 별도 빌드 체인 없이 순수 자바 코드만으로 네이티브 함수를 동적으로 링크·호출할 수 있게 한다.
- `MemorySegment`와 `Arena`가 오프힙 메모리의 수명을 자바 스코프 규칙에 편입시켜, 메모리 접근 오류가 JVM 크래시 대신 자바 예외로 처리되도록 만든다.
- JNI 대비 유지보수 부담이 크게 줄지만, downcall 호출 오버헤드와 아레나 종류 선택은 실제 적용 전에 반드시 검증해야 한다.

## 참고 자료

- [JEP 454: Foreign Function & Memory API](https://openjdk.org/jeps/454)
- [OpenJDK 공식 문서 — java.lang.foreign 패키지](https://docs.oracle.com/en/java/javase/22/docs/api/java.base/java/lang/foreign/package-summary.html)
