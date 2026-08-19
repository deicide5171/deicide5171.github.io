---
layout: single
title: "빌드 모듈을 나눠도 경계는 안 지켜진다 — Spring Modulith로 모듈러 모놀리스 구축하기"
date: 2026-08-25 13:25:00 +0530
categories: backend
tags: ["spring-modulith", "modular-monolith", "spring-boot", "domain-driven-design", "architecture-testing"]
toc: true
toc_sticky: true
excerpt: "Gradle 멀티모듈로 domain·infra를 나눠도 같은 JVM 안에서는 아무 클래스나 자유롭게 참조할 수 있다는 한계를, Spring Modulith의 런타임 모듈 경계 검증과 이벤트 기반 모듈 간 통신으로 보완하는 법을 정리한다."
---

Gradle이나 Maven 멀티모듈로 프로젝트를 `domain`, `infra`, `api` 모듈로 나눠본 사람이라면 한 번쯤 겪는 배신감이 있다. 빌드 설정에서 모듈 간 의존 방향을 아무리 깔끔하게 그려도, 결국 같은 JVM 프로세스 안에서 컴파일되고 실행되는 이상 클래스패스에 올라간 어떤 클래스든 `import` 한 줄이면 자유롭게 참조할 수 있다. 빌드 모듈 분리는 "빌드 시간 최적화"와 "느슨한 경계에 대한 합의"는 만들어주지만, 실제로 그 경계를 넘는 참조를 **강제로 막지는** 못한다.

**Spring Modulith**는 이 틈을 메우는 프레임워크다. Gradle 멀티모듈이 빌드 도구 레벨의 분리라면, Spring Modulith는 애플리케이션 패키지 구조를 기준으로 "모듈"을 정의하고, 그 경계를 테스트 시점에 검증하며, 모듈 간 통신을 이벤트 기반으로 유도해 결합도를 낮추는 런타임/테스트 레벨의 도구다. 이 글에서는 Spring Modulith가 실제로 무엇을 검증하고, 모듈 간 통신을 어떻게 다르게 설계하게 만드는지를 정리한다.

## 핵심 개념 1: 모듈 정의 방식 — 패키지 구조가 곧 모듈 경계

Spring Modulith는 별도의 설정 파일 없이, 애플리케이션의 최상위 패키지 바로 아래 패키지 구조를 모듈 경계로 인식한다. 예를 들어 `com.shop.order`, `com.shop.inventory`, `com.shop.payment`처럼 도메인별로 패키지가 나뉘어 있다면 각각이 하나의 모듈이 된다. 이 관례 기반 접근 덕분에 별도의 모듈 선언 파일을 유지보수할 필요가 없고, 기존 패키지 구조를 그대로 활용해 점진적으로 도입할 수 있다.

각 모듈의 최상위 패키지에 있는 클래스만 다른 모듈에서 접근 가능한 "공개 API"로 취급되고, 하위 패키지(`com.shop.order.internal` 등)의 클래스는 해당 모듈 밖에서 참조하면 위반으로 감지된다. 이 규칙은 헥사고날 아키텍처의 포트-어댑터 분리와 유사하지만, 격리 단위가 레이어(도메인/인프라)가 아니라 **비즈니스 도메인** 단위라는 점이 다르다.

## 핵심 개념 2: ApplicationModules — 경계 위반을 테스트로 검증

Spring Modulith의 핵심 가치는 이 경계가 "문서상의 약속"이 아니라 **테스트 실패로 강제된다**는 점이다. `ApplicationModules.of(Application.class).verify()` 한 줄을 테스트에 넣으면, 모듈 내부 패키지를 다른 모듈이 직접 참조하는 위반이나 순환 의존이 있는지를 컴파일이 아니라 테스트 실행 시점에 검사해 실패시킨다.

이는 ArchUnit 같은 별도 아키텍처 테스트 도구를 처음부터 직접 규칙을 작성해야 하는 것과 달리, Spring 애플리케이션의 관례(빈 등록, 패키지 구조)를 그대로 분석해 규칙을 자동으로 도출한다는 차이가 있다. Gradle 멀티모듈은 빌드 시점에 컴파일 자체를 막지만 같은 모듈 내부에서는 아무 규칙이 없고, Spring Modulith는 빌드 모듈 분리 없이도 도메인 경계 위반을 검출한다는 점에서 상호 보완적이다.

| 구분 | Gradle 멀티모듈 | Spring Modulith |
|---|---|---|
| 격리 단위 | 빌드 아티팩트(jar) | 최상위 도메인 패키지 |
| 위반 감지 시점 | 컴파일 타임(모듈 간만) | 테스트 실행 시점 |
| 같은 모듈 내부 규칙 | 없음 | internal 패키지 접근 차단 |
| 도입 난이도 | 빌드 구조 재편 필요 | 기존 패키지 구조에 점진 적용 가능 |
| 모듈 간 통신 가이드 | 없음(자유로운 직접 호출) | 이벤트 기반 권장, 문서 자동 생성 |

## 핵심 개념 3: 이벤트 기반 모듈 간 통신

Spring Modulith는 경계를 검증하는 데서 그치지 않고, 모듈 간 결합을 낮추는 통신 방식도 제시한다. 한 모듈(`order`)이 다른 모듈(`inventory`)의 서비스를 직접 호출하는 대신, 스프링의 `ApplicationEventPublisher`로 도메인 이벤트(`OrderPlaced`)를 발행하고 `inventory` 모듈이 `@ApplicationModuleListener`로 이를 구독하는 방식이다.

이 패턴의 이점은 두 가지다. 첫째, `order` 모듈은 `inventory` 모듈의 존재 자체를 몰라도 되므로 결합도가 낮아진다. 둘째, Spring Modulith는 이벤트 발행과 리스너 실행을 같은 트랜잭션 커밋 이후(`@TransactionalEventListener` 기반)로 처리해, 향후 이 로직을 별도 마이크로서비스로 분리할 때 이벤트를 메시지 브로커로 그대로 옮기기만 하면 되는 이행 경로도 마련해준다.

## 예제: 모듈 경계 검증과 이벤트 기반 통신

```java
// 아키텍처 테스트: 모듈 경계 위반과 순환 의존을 검사
class ModularityTests {
    ApplicationModules modules = ApplicationModules.of(ShopApplication.class);

    @Test
    void verifiesModularStructure() {
        modules.verify(); // 위반 시 상세 리포트와 함께 테스트 실패
    }

    @Test
    void writesDocumentation() {
        new Documenter(modules).writeDocumentation(); // 모듈 구조 다이어그램 자동 생성
    }
}

// order 모듈: 인벤토리 모듈을 직접 호출하지 않고 이벤트만 발행
package com.shop.order;

@Service
class OrderService {
    private final ApplicationEventPublisher events;

    void placeOrder(Order order) {
        orderRepository.save(order);
        events.publishEvent(new OrderPlaced(order.getId(), order.getItems()));
    }
}

// inventory 모듈: 이벤트를 구독, 트랜잭션 커밋 이후 비동기 처리
package com.shop.inventory;

@Component
class InventoryEventListener {
    @ApplicationModuleListener
    void on(OrderPlaced event) {
        inventoryService.reserve(event.items());
    }
}
```

## 실무 포인트

- **기존 레거시 모놀리스에 점진적으로 도입한다**: 처음부터 완벽한 모듈 경계를 요구하지 않고, `verify()` 테스트를 우선 추가해 현재 위반 목록을 파악한 뒤 우선순위가 높은 도메인부터 하나씩 정리하는 방식이 현실적이다.
- **이벤트 리스너의 실패 처리를 명시적으로 설계한다**: `@ApplicationModuleListener`는 기본적으로 트랜잭션 커밋 이후 실행되므로, 리스너가 실패했을 때 재시도나 보상 처리를 어떻게 할지(Spring Modulith의 이벤트 발행 로그 테이블 활용 등) 별도로 설계해야 한다.
- **마이크로서비스 전환의 리허설로 활용한다**: 모듈 경계가 잘 지켜지고 이벤트 기반 통신으로 결합이 낮아진 모듈러 모놀리스는, 실제로 서비스를 분리해야 할 필요가 생겼을 때 어떤 모듈을 먼저 떼어낼지 판단하는 근거 자체가 된다. Spring Modulith가 자동 생성하는 모듈 의존 다이어그램이 이 판단에 실질적으로 도움이 된다.

## 3줄 요약

- Gradle 멀티모듈은 빌드 아티팩트 수준의 분리이고, Spring Modulith는 도메인 패키지 수준의 경계를 테스트 시점에 강제한다는 점에서 상호 보완적이다.
- `ApplicationModules.verify()`로 모듈 경계 위반과 순환 의존을 테스트 실패로 검출할 수 있고, 위반 여부를 사람이 리뷰로 걸러낼 필요가 없어진다.
- 모듈 간 통신을 이벤트 기반으로 유도하면 결합도가 낮아지고, 향후 마이크로서비스로 분리할 때 이벤트를 메시지 브로커로 옮기는 이행 경로도 자연스럽게 마련된다.

## 참고 자료

- [Spring Modulith 공식 문서](https://docs.spring.io/spring-modulith/reference/)
- [Spring Blog: Introducing Spring Modulith](https://spring.io/blog/2022/10/21/introducing-spring-modulith)
- [Spring Modulith GitHub 저장소](https://github.com/spring-projects/spring-modulith)
