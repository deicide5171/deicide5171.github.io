---
layout: single
title: "@PostConstruct가 뭔가요 — 빈 생성 후 초기화 코드 실행하기"
date: 2026-09-16 13:25:00 +0530
categories: backend
tags: ["postconstruct", "빈생명주기", "spring", "초기화", "입문"]
toc: true
toc_sticky: true
excerpt: "스프링 빈이 만들어진 뒤 초기화 작업을 실행하고 소멸 전 정리 작업을 하는 생명주기 콜백을 처음 배우는 사람 기준으로 정리했다."
---

## 빈이 준비된 직후에 뭔가 하고 싶다

의존성이 다 주입된 뒤 캐시를 미리 채우거나, 설정을 검증하거나, 연결을 준비하고 싶을 때가 있다. 생성자에서 하기엔 아직 의존성 주입이 안 끝났을 수 있다. **`@PostConstruct`**는 **빈이 만들어지고 의존성 주입이 끝난 직후 자동으로 실행**되는 초기화 메서드를 지정한다.

## 생명주기 콜백

| 시점 | 애너테이션 | 용도 |
|---|---|---|
| 초기화 | `@PostConstruct` | 의존성 주입 후 준비 작업 |
| 소멸 전 | `@PreDestroy` | 종료 전 정리 작업 |

## 예시

```java
@Service
public class CacheService {
    private final Repo repo;
    public CacheService(Repo repo) { this.repo = repo; }

    @PostConstruct
    public void init() {
        // 주입된 repo로 캐시 미리 로드 (앱 시작 시 1회)
    }

    @PreDestroy
    public void cleanup() {
        // 종료 전 자원 정리
    }
}
```

## 실무 포인트

- **생성자 대신 `@PostConstruct`에 초기화를.** 생성자 시점엔 아직 주입이 다 안 됐을 수 있고, 무거운 작업을 생성자에 넣으면 빈 생성이 느려진다. 주입 완료 후 실행되는 `@PostConstruct`가 초기화에 적합하다.
- **무거운 작업은 신중히.** `@PostConstruct`는 앱 시작 시 실행되므로, 여기서 오래 걸리는 작업을 하면 시작이 느려진다. 정말 시작 시 필요한 것만 넣는다.
- **`@PreDestroy`로 자원 정리.** 스레드 풀·커넥션·파일 핸들 등을 앱 종료 시 정리하지 않으면 누수가 생긴다. `@PreDestroy`에서 닫아준다(그레이스풀 셧다운과 연계).

## 마무리 요약

- `@PostConstruct`는 빈이 만들어지고 의존성 주입이 끝난 직후 실행되는 초기화 메서드다.
- `@PreDestroy`는 빈 소멸 전 정리 작업에 쓴다.
- 초기화는 생성자보다 `@PostConstruct`에 두되 무거운 작업은 신중히 하고, 자원은 `@PreDestroy`에서 정리한다.

## 참고 자료

- [Spring 공식 문서 - Lifecycle Callbacks](https://docs.spring.io/spring-framework/reference/core/beans/factory-nature.html#beans-factory-lifecycle)
