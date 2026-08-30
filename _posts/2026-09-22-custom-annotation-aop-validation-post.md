---
layout: single
title: "커스텀 어노테이션 만들기 — @interface와 AOP로 검증 로직 재사용하기"
date: 2026-09-22 13:25:00 +0530
categories: backend
tags: ["커스텀어노테이션", "aop", "annotation", "spring", "코드재사용"]
toc: true
toc_sticky: true
excerpt: "여러 컨트롤러 메서드마다 똑같은 권한 체크·로깅 코드를 복붙하던 문제를, 직접 커스텀 어노테이션을 만들고 AOP로 공통 로직을 한곳에 모으는 방법을 예제 코드와 함께 정리했다."
---

## 왜 매번 같은 코드를 복붙하게 되나

여러 API 메서드에 "이 요청은 관리자만 호출 가능", "이 메서드는 실행 시간을 로그로 남긴다" 같은 공통 요구사항이 반복적으로 등장한다. 처음에는 각 메서드 맨 앞에 검증 코드 몇 줄을 그대로 복사해 넣는 것으로 시작하지만, 이런 코드가 수십 개의 메서드에 흩어지면 검증 로직 하나를 수정할 때마다 관련된 모든 메서드를 찾아다니며 고쳐야 하는 유지보수 부담이 커진다.

스프링에서 이미 익숙하게 쓰는 `@Transactional`, `@PreAuthorize`, `@Cacheable` 같은 애노테이션도 사실 이 문제를 해결하기 위한 같은 패턴을 쓴다. 메서드에 애노테이션 하나만 붙이면, 실제 로직은 별도의 공통 처리기(Aspect)가 대신 실행해주는 구조다. 이 원리를 이해하면 프레임워크가 제공하지 않는 우리 프로젝트만의 공통 로직도 같은 방식으로 직접 만들 수 있다.

## 1단계: 커스텀 애노테이션 정의하기

먼저 자바의 `@interface` 키워드로 애노테이션 자체를 정의한다.

```java
import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface RequireAdmin {
    String message() default "관리자 권한이 필요합니다.";
}
```

`@Target(ElementType.METHOD)`는 이 애노테이션을 메서드에만 붙일 수 있다는 뜻이고, `@Retention(RetentionPolicy.RUNTIME)`은 컴파일 이후에도 이 애노테이션 정보가 실행 시점까지 유지되어야 한다는 뜻이다. **AOP로 애노테이션을 감지하려면 반드시 `RUNTIME` 유지 정책이 필요하다.** 이 부분을 `CLASS`나 `SOURCE`로 잘못 설정하면, 애노테이션을 아무리 메서드에 붙여도 실행 시점에 인식되지 않아 아무 일도 일어나지 않는다.

## 2단계: AOP Aspect로 실제 동작 구현하기

```java
@Aspect
@Component
public class AdminCheckAspect {

    @Around("@annotation(requireAdmin)")
    public Object checkAdmin(ProceedingJoinPoint joinPoint, RequireAdmin requireAdmin) throws Throwable {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();

        boolean isAdmin = auth.getAuthorities().stream()
            .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));

        if (!isAdmin) {
            throw new AccessDeniedException(requireAdmin.message());
        }

        return joinPoint.proceed();
    }
}
```

`@Around` 어드바이스는 대상 메서드 실행 전후를 모두 감싸는 가장 강력한 형태의 AOP 어드바이스다. `joinPoint.proceed()`를 호출하는 시점이 실제 원본 메서드가 실행되는 순간이며, 이 호출 전에 조건을 검사해 실패하면 예외를 던지고 `proceed()`를 아예 호출하지 않는 방식으로 실행을 가로챌 수 있다.

## 3단계: 실제 사용

```java
@RestController
public class AdminController {

    @RequireAdmin(message = "이 작업은 관리자만 수행할 수 있습니다.")
    @DeleteMapping("/users/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable Long id) {
        userService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
```

컨트롤러 메서드는 이제 권한 검사 코드를 전혀 신경 쓰지 않고, 순수하게 "사용자를 삭제한다"는 본연의 로직만 담당한다. 권한 검사 로직이 바뀌어야 한다면 `AdminCheckAspect` 한 곳만 수정하면 된다.

<img src="/assets/images/posts/2026-09-22-custom-annotation-aop-validation-1.svg" alt="컨트롤러 메서드에 붙은 커스텀 애노테이션을 AOP Aspect가 프록시 계층에서 감지해 실제 메서드 실행 전후로 공통 로직을 끼워 넣는 흐름도" style="width:100%;">

## 잘못된 접근: 애노테이션만 만들고 아무것도 연결하지 않기

애노테이션을 처음 만들어보는 사람이 자주 저지르는 실수는, `@interface`로 애노테이션을 정의하는 것 자체가 자동으로 어떤 동작을 실행시켜줄 것이라고 착각하는 것이다. 애노테이션은 그 자체로는 **메타데이터, 즉 표시일 뿐** 아무 동작도 하지 않는다. 반드시 이 표시를 읽어서 실제로 무언가를 하는 별도의 처리기(AOP Aspect, 리플렉션 기반 검사기, 스프링의 `HandlerMethodArgumentResolver` 등)가 함께 있어야 한다.

## 실무 포인트

- **AOP는 스프링 빈으로 등록된 객체에만 적용된다.** `new`로 직접 생성한 객체나 `private` 메서드, 같은 클래스 내부에서 `this.method()`로 호출하는 경우에는 프록시를 거치지 않아 AOP가 동작하지 않는다는 점을 반드시 기억해야 한다.
- **포인트컷 표현식은 필요한 범위로만 좁혀라.** `@annotation(...)` 대신 패키지 전체를 대상으로 하는 광범위한 포인트컷을 쓰면 의도하지 않은 메서드까지 어드바이스가 적용되어 예상치 못한 부작용이 생길 수 있다.
- **여러 애노테이션이 겹칠 때 실행 순서를 명시하라.** `@Transactional`과 커스텀 애노테이션이 같은 메서드에 함께 있으면 어떤 Aspect가 먼저 실행되는지가 중요해질 수 있다. `@Order` 애노테이션으로 Aspect 간 실행 순서를 명시적으로 정할 수 있다.

## 마무리 요약

- 커스텀 애노테이션은 `@interface`로 정의하고 `@Retention(RetentionPolicy.RUNTIME)`을 지정해야 실행 시점에 AOP가 이를 감지할 수 있다.
- 애노테이션 자체는 메타데이터일 뿐이며, `@Around` 같은 AOP 어드바이스로 실제 동작을 구현해야 한다.
- 반복되는 권한 검사·로깅·검증 로직을 커스텀 애노테이션과 AOP로 분리하면, 비즈니스 로직 코드가 훨씬 단순해지고 공통 로직 수정이 한 곳으로 집중된다.

## 참고 자료

- [Spring 공식 문서 - Aspect Oriented Programming](https://docs.spring.io/spring-framework/reference/core/aop.html)
- [Oracle Java 튜토리얼 - Annotations](https://docs.oracle.com/javase/tutorial/java/annotations/)
