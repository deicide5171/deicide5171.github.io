---
layout: single
title: "블로킹 코드 한 줄이 스레드 풀을 멈춘다 — Spring WebFlux 함정과 디버깅"
date: 2026-08-29 13:25:00 +0530
categories: backend
tags: ["spring-webflux", "reactive-programming", "project-reactor", "netty", "java", "debugging"]
toc: true
toc_sticky: true
excerpt: "WebFlux의 이벤트 루프 모델에서 블로킹 호출 하나가 전체 처리량을 무너뜨리는 이유와, 스택 트레이스가 끊기는 리액티브 디버깅의 함정을 정리한다."
---

Spring MVC에서 WebFlux로 넘어가는 팀이 흔히 겪는 착각이 있다. "리액티브니까 당연히 빠를 것"이라는 기대다. 실제로는 WebFlux를 도입한 뒤 처리량이 오히려 떨어지거나, 알 수 없는 지연이 간헐적으로 발생하는 사례가 드물지 않다. 원인은 대부분 하나로 수렴한다. WebFlux의 논블로킹 모델이 요구하는 규칙, 특히 "이벤트 루프 스레드에서는 절대 블로킹해서는 안 된다"는 규칙을 어딘가에서 어겼기 때문이다.

이 글에서는 WebFlux가 Spring MVC와 근본적으로 다른 스레드 모델을 쓰는 이유, 그 모델에서 블로킹 호출이 왜 치명적인지, 그리고 리액티브 스트림 특유의 디버깅 어려움과 그 대응법을 정리한다.

## 핵심 개념 1: 스레드-per-요청 모델과 이벤트 루프 모델의 차이

Spring MVC(Tomcat 기반)는 요청마다 스레드 하나를 할당하는 스레드-per-요청 모델을 쓴다. 그 스레드가 DB 조회 같은 블로킹 I/O를 기다리는 동안에도 스레드는 점유된 채로 대기하지만, 스레드 풀 크기(보통 수백 개)만큼의 동시 요청을 단순하게 처리할 수 있다는 장점이 있다.

WebFlux(Netty 기반)는 정반대로 접근한다. CPU 코어 수에 맞춘 소수의 이벤트 루프 스레드(기본적으로 코어 수만큼)가 매우 많은 요청을 논블로킹 I/O로 동시에 처리한다. I/O 작업을 시작해두고 결과가 오면 콜백(리액티브 스트림에서는 `Mono`/`Flux`의 구독 체인)으로 이어받는 식이라, 스레드가 I/O를 "기다리며 노는" 시간이 없다. 이 모델은 이벤트 루프 스레드 각각이 매우 많은 요청을 번갈아 처리하기 때문에, 스레드 수 자체는 훨씬 적어도 높은 동시성을 낼 수 있다.

## 핵심 개념 2: 블로킹 호출 하나가 전체를 멈추는 이유

문제는 이 적은 수의 이벤트 루프 스레드 중 하나가 블로킹 호출(동기 JDBC 쿼리, 블로킹 HTTP 클라이언트, `Thread.sleep()` 등)을 만나 멈춰버리면, 그 스레드가 처리하던 **다른 모든 요청까지 함께 멈춘다**는 것이다. 스레드-per-요청 모델에서는 요청 하나가 블로킹돼도 다른 스레드가 다른 요청을 처리하지만, 이벤트 루프 모델에서는 소수의 스레드가 매우 많은 요청을 나눠 처리하고 있어서 그 중 하나가 막히면 파급 효과가 훨씬 크다.

이 문제가 특히 위험한 이유는 겉으로 잘 드러나지 않는다는 데 있다. 개발 환경에서 요청이 하나씩 들어올 때는 블로킹 JDBC 드라이버를 리액티브 코드 안에 섞어 써도 아무 문제가 없어 보인다. 그러다 운영 환경에서 동시 요청이 몰리는 순간, 몇 개의 블로킹 호출이 이벤트 루프 스레드를 차례로 잠식하면서 전체 응답 시간이 갑자기 치솟는 형태로 나타난다. 이런 증상은 일반적인 스레드 덤프나 APM에서 "느린 요청 몇 개"로만 보여 원인 파악이 늦어지기 쉽다.

```java
// 이벤트 루프 스레드에서 블로킹 호출을 실행하는 전형적인 실수
@GetMapping("/legacy-report")
public Mono<Report> getReport(String id) {
    return Mono.fromCallable(() -> legacyJdbcRepository.findById(id))  // 동기 JDBC 호출
               .map(this::toReport);
    // fromCallable만으로는 여전히 이벤트 루프 스레드에서 블로킹 JDBC를 실행한다
}

// 수정 - 블로킹 호출을 별도 스레드 풀로 옮긴다
@GetMapping("/legacy-report")
public Mono<Report> getReportFixed(String id) {
    return Mono.fromCallable(() -> legacyJdbcRepository.findById(id))
               .subscribeOn(Schedulers.boundedElastic())  // 블로킹 전용 스레드 풀에서 실행
               .map(this::toReport);
}
```

`Schedulers.boundedElastic()`은 블로킹 작업을 위해 별도로 마련된, 요청량에 따라 늘어나는 스레드 풀이다. 이벤트 루프 스레드가 아니라 이 풀에서 블로킹 코드를 실행하도록 명시적으로 옮겨야, 블로킹이 발생해도 이벤트 루프는 다른 요청을 계속 처리할 수 있다.

## 핵심 개념 3: 끊긴 스택 트레이스와 리액티브 디버깅

리액티브 스트림 특유의 또 다른 함정은 디버깅이다. 명령형 코드에서 예외가 발생하면 스택 트레이스가 호출 경로를 그대로 보여주지만, 리액티브 체인에서는 연산자마다 실행 스레드가 바뀌고 콜백이 비동기로 실행되기 때문에 스택 트레이스가 "이 예외가 원래 어디서 조립된 체인에서 발생했는지"를 보여주지 못하고 리액터 내부 구현 세부사항만 나열하는 경우가 흔하다.

Project Reactor는 이를 보완하기 위해 `Hooks.onOperatorDebug()`나 리액터 3.5 이상의 경량 버전인 `ReactorDebugAgent`를 제공한다. 이를 활성화하면 각 연산자 체인이 조립된 위치를 스택 트레이스에 덧붙여, 예외가 어느 코드 라인에서 조립된 체인에서 발생했는지 추적할 수 있다. 다만 이 기능은 성능 오버헤드가 있으므로 프로덕션에 상시 켜두기보다 문제 재현 시 임시로 활성화하거나, 개발 환경에서 기본으로 켜두는 방식이 일반적이다.

| 구분 | Spring MVC(Tomcat) | Spring WebFlux(Netty) |
|---|---|---|
| 스레드 모델 | 요청당 스레드 할당 | 소수 이벤트 루프 + 논블로킹 I/O |
| 블로킹 호출 영향 | 해당 요청만 지연 | 이벤트 루프 전체 요청 지연 가능 |
| 동시성 확보 방식 | 스레드 풀 크기 확장 | 논블로킹 I/O + 콜백 체인 |
| 블로킹 코드 처리 | 기본 동작과 자연스럽게 호환 | 별도 스케줄러(boundedElastic)로 명시적 격리 필요 |
| 디버깅 | 스택 트레이스가 호출 경로 그대로 반영 | 연산자 조립 위치 추적에 별도 도구 필요 |

## 실무 포인트

- **레거시 블로킹 라이브러리 경계를 명확히 표시한다**: 팀에서 관습적으로 JDBC 드라이버나 블로킹 HTTP 클라이언트를 리액티브 코드에 섞어 쓰는 경우, 코드 리뷰 단계에서 "이 호출은 블로킹인가"를 체크리스트화하고 반드시 `subscribeOn(Schedulers.boundedElastic())`으로 격리시킨다.
- **BlockHound 같은 도구로 블로킹 호출을 자동 탐지한다**: 개발자가 모든 블로킹 지점을 눈으로 찾아내기는 현실적으로 어렵다. Reactor의 BlockHound는 이벤트 루프 스레드에서 블로킹 호출이 발생하면 즉시 예외를 던져주는 계측 도구로, 테스트 환경에 통합해두면 배포 전에 이런 실수를 자동으로 잡아낼 수 있다.
- **WebFlux 전면 도입 전에 I/O 스택 전체를 점검한다**: 컨트롤러만 리액티브로 바꾸고 그 아래 레포지토리·외부 API 클라이언트가 여전히 블로킹이라면, WebFlux 도입 효과는 거의 없고 오히려 디버깅 난이도만 올라간다. R2DBC, WebClient 같은 논블로킹 대응 라이브러리로 전체 스택을 일관되게 맞추는 것이 전제조건이다.

## 3줄 요약

- WebFlux는 소수의 이벤트 루프 스레드가 논블로킹 I/O로 많은 요청을 동시에 처리하는 모델이라, 그 중 한 스레드가 블로킹되면 그 스레드가 담당하던 모든 요청이 함께 지연된다.
- 블로킹 호출은 반드시 `Schedulers.boundedElastic()` 같은 별도 스케줄러로 명시적으로 옮겨야 하며, 이를 놓치면 저부하 환경에서는 안 보이다가 고부하에서만 드러나는 문제가 된다.
- 리액티브 체인은 스택 트레이스가 끊기기 쉬워, `Hooks.onOperatorDebug()`나 BlockHound 같은 도구로 문제를 재현·탐지하는 것이 명령형 코드보다 훨씬 중요해진다.

## 참고 자료

- [Project Reactor 공식 문서: Debugging Reactor](https://projectreactor.io/docs/core/release/reference/#debugging)
- [Spring 공식 문서: WebFlux Concurrency Model](https://docs.spring.io/spring-framework/reference/web/webflux.html)
- [Reactor BlockHound GitHub](https://github.com/reactor/BlockHound)
