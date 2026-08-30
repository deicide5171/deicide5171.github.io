---
layout: single
title: "@WebMvcTest vs @DataJpaTest vs @SpringBootTest — 스프링 테스트 슬라이스 제대로 고르기"
date: 2026-09-22 12:25:00 +0530
categories: backend
tags: ["스프링테스트", "webmvctest", "datajpatest", "테스트슬라이스", "springboottest"]
toc: true
toc_sticky: true
excerpt: "테스트마다 매번 전체 스프링 컨텍스트를 띄우느라 테스트 스위트가 몇 분씩 걸리는 문제를, 목적에 맞는 테스트 슬라이스 애노테이션을 골라 로딩 범위를 줄이는 방법으로 정리했다."
---

## 왜 테스트가 갈수록 느려지는가

프로젝트 초반에는 테스트 몇 개를 돌리는 데 몇 초면 충분했는데, 컨트롤러·서비스·리포지토리가 늘어날수록 테스트 스위트 전체를 실행하는 데 걸리는 시간이 점점 길어진다. 원인을 찾아보면 대부분의 테스트 클래스가 `@SpringBootTest`를 붙여 **애플리케이션 전체 컨텍스트**를 매번 새로 띄우고 있다는 사실을 발견한다.

`@SpringBootTest`는 실제 운영 환경과 가장 비슷한 조건에서 검증할 수 있어 편리하지만, 컨트롤러 하나의 URL 매핑만 확인하고 싶은 테스트에서까지 DB 커넥션, 시큐리티 필터, 메시지 브로커 연결 같은 애플리케이션 전체 빈을 매번 로딩하는 것은 명백한 낭비다. 스프링은 이 문제를 위해 목적별로 필요한 빈만 로딩하는 **테스트 슬라이스(Test Slice)** 애노테이션을 여러 개 제공한다.

## @WebMvcTest — 컨트롤러 레이어만 검증하기

`@WebMvcTest`는 MVC 관련 빈(컨트롤러, `@ControllerAdvice`, 컨버터, 필터 등)만 로딩하고, `@Service`나 `@Repository` 빈은 로딩하지 않는다. 컨트롤러가 요청을 올바르게 매핑하고, 상태 코드와 응답 형식을 올바르게 반환하는지만 검증하고 싶을 때 적합하다.

```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private OrderService orderService;

    @Test
    void 주문_조회_성공() throws Exception {
        given(orderService.findById(1L)).willReturn(new OrderResponse(1L, "PAID"));

        mockMvc.perform(get("/orders/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("PAID"));
    }
}
```

`OrderService`는 실제 빈이 아니라 `@MockBean`으로 대체된다. 이 테스트는 서비스 로직이 맞는지가 아니라, **컨트롤러가 그 서비스를 올바르게 호출하고 결과를 올바른 HTTP 응답으로 변환하는지**만 확인한다.

## @DataJpaTest — 리포지토리 레이어만 검증하기

`@DataJpaTest`는 반대로 JPA 관련 빈(엔티티 매니저, 리포지토리)만 로딩하고, 기본적으로 내장 인메모리 DB(H2 등)를 사용하도록 자동 구성한다. 컨트롤러나 서비스 빈은 전혀 로딩되지 않는다.

```java
@DataJpaTest
class OrderRepositoryTest {

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void 상태별_주문_조회() {
        entityManager.persist(new Order("PAID"));
        entityManager.persist(new Order("CANCELLED"));

        List<Order> paidOrders = orderRepository.findByStatus("PAID");

        assertThat(paidOrders).hasSize(1);
    }
}
```

`@DataJpaTest`는 기본적으로 각 테스트 메서드를 트랜잭션으로 감싸고 종료 시 롤백하기 때문에, 테스트 간 데이터가 서로 오염되지 않는다는 것도 중요한 특징이다. 다만 실제 운영 DB(MySQL, PostgreSQL)와 인메모리 DB(H2) 사이에 SQL 문법이나 제약조건 동작 차이가 있을 수 있으므로, 이 차이가 우려된다면 Testcontainers로 실제 DB를 띄워 검증하는 편이 안전하다.

<img src="/assets/images/posts/2026-09-22-spring-test-slice-webmvctest-datajpatest-1.svg" alt="SpringBootTest가 전체 애플리케이션 컨텍스트를 로딩하는 것과 달리 WebMvcTest와 DataJpaTest가 각각 필요한 레이어의 빈만 로딩하는 범위를 비교하는 다이어그램" style="width:100%;">

## @SpringBootTest — 통합 시나리오를 검증할 때만

`@SpringBootTest`는 실제 애플리케이션과 동일하게 전체 컨텍스트를 로딩하므로, 여러 레이어가 함께 맞물려 동작하는 것을 확인해야 하는 통합 테스트에 적합하다. 다만 이 애노테이션을 모든 테스트에 습관적으로 붙이면 테스트 스위트 전체가 느려지는 원인이 된다.

| 애노테이션 | 로딩 범위 | 적합한 용도 | 속도 |
|---|---|---|---|
| `@WebMvcTest` | 컨트롤러 관련 빈만 | URL 매핑, 요청/응답 검증 | 빠름 |
| `@DataJpaTest` | JPA 관련 빈만 | 쿼리 메서드, 연관관계 매핑 검증 | 빠름 |
| `@SpringBootTest` | 전체 애플리케이션 컨텍스트 | 여러 레이어가 얽힌 통합 시나리오 | 느림 |

## 실무 포인트

- **테스트 슬라이스는 스프링 컨텍스트를 캐싱한다는 점을 활용하라.** 같은 슬라이스 설정(같은 애노테이션·같은 구성)을 쓰는 테스트 클래스가 여러 개면 스프링은 컨텍스트를 재사용해 로딩 시간을 줄인다. 반대로 클래스마다 `@MockBean` 조합이 다르면 컨텍스트가 매번 새로 만들어져 테스트가 느려진다.
- **테스트 피라미드 관점에서 비율을 의식하라.** 단위 테스트(순수 자바 객체, 스프링 컨텍스트 없이)를 가장 많이, `@WebMvcTest`·`@DataJpaTest` 같은 슬라이스 테스트를 중간 정도, `@SpringBootTest` 통합 테스트는 핵심 시나리오 몇 개로 최소화하는 구성이 빠르고 안정적인 테스트 스위트를 만든다.
- **@WebMvcTest에서 시큐리티 설정을 빼먹지 마라.** Spring Security가 적용된 프로젝트라면 `@WebMvcTest`도 기본적으로 시큐리티 필터를 함께 로딩하므로, 인증이 필요한 엔드포인트를 테스트할 때는 `@WithMockUser` 같은 애노테이션으로 인증 컨텍스트를 채워줘야 한다.

## 마무리 요약

- 모든 테스트에 `@SpringBootTest`를 습관적으로 붙이면 불필요한 빈까지 매번 로딩되어 테스트 스위트 전체가 느려진다.
- `@WebMvcTest`는 컨트롤러 레이어만, `@DataJpaTest`는 리포지토리 레이어만 로딩해 각 레이어를 빠르고 독립적으로 검증할 수 있다.
- 슬라이스 테스트로 대부분을 커버하고, 여러 레이어가 얽힌 핵심 시나리오만 `@SpringBootTest` 통합 테스트로 남기는 것이 실전에서 균형 잡힌 전략이다.

## 참고 자료

- [Spring Boot 공식 문서 - Testing](https://docs.spring.io/spring-boot/reference/testing/spring-boot-applications.html)
- [Spring Boot 공식 문서 - Auto-configured Tests](https://docs.spring.io/spring-boot/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.autoconfigured-tests)
