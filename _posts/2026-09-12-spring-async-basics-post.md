---
layout: single
title: "@Async 입문 — 스프링에서 오래 걸리는 작업 비동기로 돌리기"
date: 2026-09-12 13:25:00 +0530
categories: backend
tags: ["async", "비동기", "spring", "스레드", "입문"]
toc: true
toc_sticky: true
excerpt: "이메일 발송·알림처럼 오래 걸리는 작업을 응답과 분리해 처리하는 스프링 @Async의 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 이메일 보내느라 응답이 느려진다

회원가입 후 환영 이메일을 보내는데 3초가 걸린다면, 사용자는 그 3초 동안 화면이 멈춘 것처럼 기다린다. 이메일 발송은 응답과 별개로 백그라운드에서 처리하면 된다. 스프링의 **`@Async`**는 **메서드를 별도 스레드에서 비동기로 실행**해, 호출한 쪽은 기다리지 않고 바로 다음으로 넘어가게 한다.

## 동기 vs 비동기

```text
[동기] 가입 처리 -> 이메일 발송(3초 대기) -> 응답  (총 3초+)
[비동기] 가입 처리 -> 응답(즉시)
                  \-> 이메일 발송은 백그라운드에서 따로
```

## 사용법

```java
@EnableAsync   // 설정 클래스에 한 번
@Configuration
public class AsyncConfig {}

@Service
public class MailService {
    @Async
    public void sendWelcome(String email) {
        // 오래 걸리는 이메일 발송 (별도 스레드)
    }
}
```

`@EnableAsync`로 기능을 켜고, 비동기로 돌릴 메서드에 `@Async`를 붙인다.

## 실무 포인트

- **같은 클래스 내부 호출은 동작 안 한다.** `@Async`는 프록시로 동작해, 같은 클래스 안의 다른 메서드가 직접 호출하면 비동기가 적용되지 않는다. 다른 빈(bean)을 통해 호출해야 한다.
- **전용 스레드 풀을 설정하라.** 기본 설정이면 스레드가 무한정 생기거나 부족할 수 있다. `TaskExecutor`로 스레드 풀 크기·큐를 정해, 폭주나 자원 고갈을 막는다.
- **예외 처리에 주의.** 비동기 메서드에서 던진 예외는 호출한 쪽으로 전달되지 않는다. 내부에서 잡아 로그를 남기거나, 결과가 필요하면 `CompletableFuture`를 반환해 처리한다.

## 마무리 요약

- `@Async`는 메서드를 별도 스레드에서 비동기로 실행해, 오래 걸리는 작업을 응답과 분리한다.
- `@EnableAsync`로 켜고 대상 메서드에 `@Async`를 붙이며, 이메일·알림 발송 등에 유용하다.
- 같은 클래스 내부 호출은 안 되고, 전용 스레드 풀 설정과 예외 처리를 함께 해야 한다.

## 참고 자료

- [Spring 공식 문서 - @Async](https://docs.spring.io/spring-framework/reference/integration/scheduling.html#scheduling-annotation-support-async)
