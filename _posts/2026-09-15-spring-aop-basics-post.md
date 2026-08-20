---
layout: single
title: "AOP가 뭔가요 — 로깅·트랜잭션 같은 공통 관심사 분리하기"
date: 2026-09-15 13:25:00 +0530
categories: backend
tags: ["aop", "spring", "관점지향", "횡단관심사", "입문"]
toc: true
toc_sticky: true
excerpt: "로깅·트랜잭션·권한 검사처럼 여러 곳에 흩어지는 공통 코드를 한곳으로 모으는 AOP의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 로깅 코드가 모든 메서드에 반복된다

메서드마다 "시작 로그 남기고, 실행하고, 끝 로그 남기고" 하는 코드가 반복되면, 핵심 로직이 로깅 코드에 파묻힌다. 이렇게 **여러 곳에 흩어지는 공통 관심사(로깅·트랜잭션·권한 등)**를 **횡단 관심사(cross-cutting concern)**라 한다. **AOP(관점 지향 프로그래밍)**는 이 공통 코드를 **한곳에 모아 필요한 지점에 자동으로 끼워 넣는** 방식이다.

## 핵심 용어

| 용어 | 의미 |
|---|---|
| Aspect | 공통 기능을 모은 모듈(로깅 등) |
| Advice | 실제 실행되는 부가 코드 |
| Pointcut | 어디에 적용할지(대상 지정) |
| JoinPoint | 적용될 수 있는 지점(메서드 실행 등) |

## 예시 (로깅 Aspect)

```java
@Aspect
@Component
public class LoggingAspect {
    @Around("execution(* com.app.service..*(..))")
    public Object log(ProceedingJoinPoint pjp) throws Throwable {
        System.out.println("시작: " + pjp.getSignature());
        Object result = pjp.proceed(); // 실제 메서드 실행
        System.out.println("끝");
        return result;
    }
}
// service 패키지의 모든 메서드에 로깅이 자동 적용됨
```

## 실무 포인트

- **`@Transactional`도 AOP다.** 스프링의 트랜잭션 처리는 내부적으로 AOP로 동작한다. 메서드 앞뒤에 "트랜잭션 시작·커밋/롤백"을 자동으로 끼워 넣는 것이다. 익숙한 기능이 AOP였던 셈이다.
- **프록시 기반이라 제약이 있다.** 스프링 AOP는 프록시로 동작해, 같은 클래스 내부에서 자기 메서드를 직접 호출하면 적용되지 않는다. `@Transactional`이 안 먹는 흔한 원인이 이것이다.
- **공통 관심사에만 써라.** 로깅·트랜잭션·권한·성능 측정처럼 여러 곳에 공통으로 필요한 것에 쓴다. 핵심 비즈니스 로직까지 AOP로 숨기면 흐름이 안 보여 오히려 이해가 어려워진다.

## 마무리 요약

- AOP는 로깅·트랜잭션 같은 횡단 관심사를 한곳에 모아 필요한 지점에 자동으로 끼워 넣는다.
- Aspect·Advice·Pointcut 개념으로 "어디에 어떤 부가 기능을" 적용할지 정한다.
- `@Transactional`도 AOP이며, 프록시 기반이라 내부 호출엔 안 먹는 점에 주의한다.

## 참고 자료

- [Spring 공식 문서 - AOP](https://docs.spring.io/spring-framework/reference/core/aop.html)
