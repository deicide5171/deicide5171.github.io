---
layout: single
title: "Kotlin Coroutines vs Java Virtual Threads — 동시성, 언어가 짤까 런타임이 짤까"
date: 2026-08-20 13:25:00 +0530
categories: backend
tags: ["kotlin", "coroutines", "virtual-threads", "java", "concurrency", "jvm"]
toc: true
toc_sticky: true
excerpt: "같은 JVM 위에서 Kotlin Coroutines는 언어·컴파일러 차원으로, Java Virtual Threads는 런타임·OS 스케줄링 차원으로 동시성을 다룬다. 두 모델의 구조 차이와 선택 기준을 코드로 정리한다."
---

## 왜 지금 두 모델을 나란히 봐야 하는가

Java Virtual Threads가 JDK 21부터 정식 기능으로 자리 잡으면서, "블로킹 스타일 코드를 그대로 두고도 대규모 동시 요청을 처리할 수 있다"는 선택지가 Java 진영에 생겼다. 한편 Kotlin을 쓰는 백엔드 팀은 그보다 훨씬 전부터 `suspend` 함수와 코루틴으로 비동기 코드를 동기 코드처럼 작성해왔다. 두 접근 모두 "스레드당 요청" 모델의 무거움을 해결하려 한다는 점은 같지만, **문제를 해결하는 층(layer)이 다르다.**

Kotlin Coroutines는 컴파일러가 `suspend` 함수를 상태 머신으로 변환하는 **언어 차원**의 동시성이고, Virtual Threads는 JVM이 스레드를 경량 객체로 스케줄링하는 **런타임 차원**의 동시성이다. Spring Boot 3.2 이후 두 방식이 한 생태계 안에서 공존할 수 있게 되면서, "어느 쪽을 쓸 것인가"가 아니라 "언제 어느 쪽이 자연스러운가"를 판단하는 감각이 필요해졌다.

## 핵심 개념 1: 동시성을 다루는 층이 다르다

| 구분 | Kotlin Coroutines | Java Virtual Threads |
|---|---|---|
| 구현 위치 | 컴파일러(CPS 변환) + 라이브러리 | JVM 런타임 스케줄러 |
| 코드 표시 | `suspend` 키워드로 명시적 | 기존 블로킹 코드와 문법상 동일 |
| 대상 언어 | Kotlin | Java(및 JVM 언어 전반) |
| 실행 위치 | 플랫폼 스레드 위(디스패처가 결정) | 캐리어 스레드 위(런타임이 결정) |
| 취소 방식 | 협력적 취소(suspend 지점에서 확인) | 인터럽트 기반(`Thread.interrupt()`) |

Coroutines는 `suspend fun` 호출부마다 컴파일러가 "여기서 중단하고 나중에 재개할 수 있다"는 지점을 코드에 새겨 넣는다. 개발자가 명시적으로 `suspend`를 붙이지 않으면 그 함수는 코루틴을 중단할 수 없다. 반대로 Virtual Threads는 기존 블로킹 코드(`Thread.sleep`, JDBC 호출 등)를 문법 변경 없이 그대로 실행하면서, 블로킹이 발생하는 순간 JVM이 알아서 캐리어 스레드를 반납한다. 즉 Coroutines는 "무엇이 중단 가능한가"를 타입 시스템 수준에서 드러내고, Virtual Threads는 그 정보를 감춘 채 런타임이 대신 처리한다.

## 핵심 개념 2: 구조적 동시성과 취소 전파

두 모델 모두 "자식 작업은 부모 스코프보다 오래 살 수 없다"는 구조적 동시성 원칙을 따르지만, 이를 구현하는 API 성격이 다르다. Kotlin은 `coroutineScope { }` 같은 언어 내장 빌더로, Java는 `java.util.concurrent`의 `StructuredTaskScope`(아직 프리뷰 단계인 API)로 이 원칙을 구현한다.

<img src="/assets/images/posts/2026-08-20-kotlin-coroutines-vs-virtual-threads-1.svg" alt="Kotlin Coroutines의 coroutineScope와 Java Virtual Threads의 StructuredTaskScope가 자식 작업의 취소를 전파하는 방식 비교" style="width:100%;">

취소가 전파되는 방식도 다르다. Coroutines는 **협력적 취소**를 쓴다. 자식 코루틴이 실패하면 부모 Job이 취소 상태가 되고, 다른 자식은 다음 suspend 지점(체크포인트)에 도달했을 때 비로소 취소를 인지한다. 반면 Virtual Threads 기반 `StructuredTaskScope`는 `shutdown()` 호출 시 나머지 서브태스크에 `Thread.interrupt()`를 걸어 즉시 인터럽트 시그널을 전달한다. 다만 인터럽트를 무시하는 코드(예: 인터럽트를 확인하지 않는 루프)는 실제로는 즉시 멈추지 않을 수 있다는 점은 두 모델 공통의 함정이다.

## 핵심 개념 3: 무엇을 기준으로 선택할까

| 상황 | Coroutines가 자연스러운 경우 | Virtual Threads가 자연스러운 경우 |
|---|---|---|
| 기존 코드베이스 | 이미 Kotlin + 코루틴 기반 | 기존 Java 블로킹 코드(JDBC, 레거시 라이브러리) 다수 |
| 팀 역량 | `suspend`/구조적 동시성 학습 여유 있음 | 문법 변경 없이 점진 도입하고 싶음 |
| 세밀한 제어 | 취소·타임아웃·디스패처를 코드로 정교하게 제어하고 싶음 | 기존 스레드 기반 사고 방식을 유지하고 싶음 |
| 생태계 | Ktor, 코루틴 친화적 클라이언트 사용 | 동기 JDBC 드라이버, 블로킹 클라이언트 다수 |

## 예제: 세 개의 API를 병렬로 호출하기

Kotlin에서는 `async`/`await`로 병렬 호출을 표현한다.

```kotlin
suspend fun fetchUserDashboard(userId: Long): Dashboard = coroutineScope {
    val profile = async { userService.fetchProfile(userId) }
    val orders = async { orderService.fetchRecentOrders(userId) }
    val notifications = async { notificationService.fetchUnread(userId) }

    Dashboard(
        profile = profile.await(),
        orders = orders.await(),
        notifications = notifications.await(),
    )
}
```

Java에서는 `StructuredTaskScope`(프리뷰 기능, `--enable-preview` 필요)로 같은 구조를 표현한다.

```java
Dashboard fetchUserDashboard(long userId) throws InterruptedException, ExecutionException {
    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        var profile = scope.fork(() -> userService.fetchProfile(userId));
        var orders = scope.fork(() -> orderService.fetchRecentOrders(userId));
        var notifications = scope.fork(() -> notificationService.fetchUnread(userId));

        scope.join();
        scope.throwIfFailed();

        return new Dashboard(profile.get(), orders.get(), notifications.get());
    }
}
```

두 코드 모두 "세 작업 중 하나라도 실패하면 나머지를 취소하고 예외를 던진다"는 동일한 의도를 담고 있다. 차이는 그 의도를 코드가 명시적으로 드러내는 방식(`coroutineScope`의 취소 전파 규칙)과, JVM이 런타임 차원에서 강제하는 방식(`ShutdownOnFailure`의 인터럽트 전파)에 있다.

## 실무 포인트

- **둘은 배타적이지 않다.** Kotlin으로 작성된 서비스도 내부적으로 Virtual Threads를 실행 스레드로 쓸 수 있다. 코루틴 디스패처를 Virtual Thread 기반 Executor로 구성하면, 언어 차원의 구조적 동시성과 런타임의 경량 스레드를 함께 얻을 수 있다.
- **pinning 문제는 여전히 공통 위험이다.** `synchronized` 블록 안에서 블로킹 호출을 하면 Virtual Thread가 캐리어 스레드에 고정(pinning)되어 이점이 사라진다. Kotlin 코드에서도 JVM 레벨 락을 쓰는 라이브러리를 호출하면 동일한 문제가 발생할 수 있다.
- **StructuredTaskScope는 아직 프리뷰 API다.** JDK 버전에 따라 클래스명·메서드 시그니처가 계속 조정되어 왔으므로, 운영 도입 전 사용 중인 JDK 버전의 정확한 API 형태를 문서로 재확인해야 한다.
- **팀의 기존 자산을 우선한다.** 새 프로젝트가 아니라면, 이론적 우수성보다 기존 코드베이스·팀 숙련도에 맞는 모델을 확장하는 편이 현실적인 경우가 많다.

## 3줄 요약

- Kotlin Coroutines는 컴파일러가 `suspend` 함수를 상태 머신으로 바꾸는 언어 차원 동시성이고, Java Virtual Threads는 JVM이 스레드를 경량화해 스케줄링하는 런타임 차원 동시성이다.
- 두 모델 모두 구조적 동시성 원칙(자식은 부모보다 오래 살 수 없음)을 따르지만, 취소 전파 방식은 협력적 취소(코루틴)와 인터럽트 기반(Virtual Threads)으로 갈린다.
- 실무에서는 두 모델을 배타적으로 고르기보다, 기존 코드베이스와 팀 역량에 맞춰 조합하는 것이 현실적이며 pinning 같은 공통 함정은 어느 쪽을 택해도 점검해야 한다.

## 참고 자료

- [Kotlin Coroutines Guide — Coroutine context and dispatchers](https://kotlinlang.org/docs/coroutine-context-and-dispatchers.html)
- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444)
- [Java SE Platform — java.util.concurrent.StructuredTaskScope (Preview API)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/concurrent/StructuredTaskScope.html)
