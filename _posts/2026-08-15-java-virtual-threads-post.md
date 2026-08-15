---
layout: single
title: "가상 스레드 실전 도입 — Spring Boot에서 Virtual Threads 써도 될까"
date: 2026-08-15 13:30:00 +0530
categories: web-dev
tags: ["java", "virtual-threads", "spring-boot", "concurrency", "backend"]
toc: true
toc_sticky: true
excerpt: "JDK의 Virtual Threads가 실무 적용 사례를 넓혀가는 가운데, 플랫폼 스레드와의 차이, Spring Boot에서의 활성화 방법, pinning 같은 실전 함정을 정리한다."
---

## 왜 지금 Virtual Threads인가

Project Loom을 통해 JDK에 정식으로 들어온 **Virtual Threads**는 "스레드 하나당 요청 하나"라는 익숙한 프로그래밍 모델을 유지하면서도, 수만 개의 동시 요청을 감당할 수 있게 해주는 기능이다. 그동안 대규모 동시성을 다루려면 리액티브 스택(WebFlux, RxJava)으로 전환해 콜백·연산자 체인을 배워야 했는데, Virtual Threads는 "블로킹 코드를 그대로 써도 확장이 된다"는 다른 접근을 제시한다.

Spring Boot가 Virtual Threads를 정식 지원하고, Tomcat·Jetty 같은 서블릿 컨테이너도 이를 활용하는 옵션을 내놓으면서, "리액티브로 재작성할 것인가, 기존 블로킹 코드에 Virtual Threads만 얹을 것인가"는 백엔드 설계에서 실질적인 선택지가 됐다.

이미 React Compiler 같은 프론트엔드 변화를 다뤘으니, 이번엔 백엔드에서 가장 화제가 된 동시성 모델 변화를 짚어본다.

## 플랫폼 스레드 vs 가상 스레드

| 항목 | 플랫폼 스레드 | 가상 스레드 |
|---|---|---|
| 생성 비용 | OS 스레드 1:1, 무거움(수 MB 스택) | JVM이 관리, 매우 가벼움(수백 바이트~) |
| 동시 개수 | 보통 수백~수천 개 한계 | 수십만 개까지 실용적 |
| 블로킹 I/O | OS 스레드 점유, 스레드풀 고갈 위험 | 블로킹 시 caller 스레드(carrier)를 반납 |
| 프로그래밍 모델 | 동기 코드 그대로 | 동기 코드 그대로(코드 변경 거의 없음) |
| 대체 대상 | 스레드풀 기반 블로킹 서버 | 리액티브 스택의 대안(일부 시나리오) |

핵심은 "코드를 리액티브 스타일로 바꾸지 않고도" 동시성 확장을 얻을 수 있다는 점이다. 다만 모든 시나리오에서 리액티브를 완전히 대체하는 것은 아니다.

## 핵심 개념: Carrier Thread와 Pinning

가상 스레드는 실제로는 소수의 **캐리어 스레드(Carrier Thread)** 위에서 스케줄링된다. 가상 스레드가 블로킹 I/O를 만나면 캐리어 스레드에서 내려가고, 그 캐리어 스레드는 다른 가상 스레드를 실행하러 간다. 이 덕분에 적은 수의 OS 스레드로 수많은 가상 스레드를 처리할 수 있다.

문제는 **pinning**이다. `synchronized` 블록 안에서 블로킹 I/O를 수행하면 가상 스레드가 캐리어 스레드를 내려놓지 못하고 그대로 점유해버려, 가상 스레드의 장점이 사라진다. 레거시 코드에 `synchronized`가 많다면 이 부분을 `ReentrantLock` 등으로 교체하는 작업이 선행되어야 한다.

## 예제: Spring Boot에서 Virtual Threads 활성화

```yaml
# application.yml
spring:
  threads:
    virtual:
      enabled: true
```

```java
@RestController
class OrderController {

    @GetMapping("/orders/{id}")
    public Order getOrder(@PathVariable String id) {
        // 기존과 동일한 블로킹 코드
        return orderRepository.findById(id);
    }
}
```

설정 한 줄만 추가하면 서블릿 컨테이너의 요청 처리 스레드가 가상 스레드로 바뀌며, 컨트롤러 코드는 전혀 수정할 필요가 없다.

## 실무 포인트

- **synchronized 사용처를 점검한다**: pinning이 발생하는 지점을 미리 찾아 `ReentrantLock`으로 바꾸거나, JDK 최신 패치로 완화된 부분인지 확인한다.
- **커넥션 풀 크기를 재검토한다**: 가상 스레드는 동시 요청 수를 크게 늘리므로, DB 커넥션 풀처럼 여전히 유한한 자원의 병목이 먼저 드러날 수 있다.
- **CPU 바운드 작업에는 큰 이득이 없다**: Virtual Threads는 I/O 대기 구간을 효율화하는 것이지, 연산 자체를 빠르게 하지 않는다. CPU 집약적 작업은 별도 전략이 필요하다.
- **점진적으로 전환한다**: 전체 스택을 한 번에 바꾸기보다, I/O 대기 비중이 높은 엔드포인트부터 적용해 효과를 확인하며 넓혀간다.

## 3줄 요약

- Virtual Threads는 기존 블로킹 코드를 그대로 두고도 대규모 동시 요청을 처리할 수 있게 해준다.
- 캐리어 스레드 위에서 스케줄링되며, synchronized 블록 안 블로킹은 pinning을 유발해 이점을 없앨 수 있다.
- Spring Boot는 설정 한 줄로 도입 가능하지만, 커넥션 풀 등 다른 병목은 별도로 재검토해야 한다.

## 참고 자료

- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444)
- [Spring Boot — Virtual Threads 공식 가이드](https://docs.spring.io/spring-boot/reference/features/task-execution-and-scheduling.html)
