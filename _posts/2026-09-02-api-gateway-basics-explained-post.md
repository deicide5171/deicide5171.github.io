---
layout: single
title: "API Gateway가 뭔가요 — 처음 이해하는 개념과 역할"
date: 2026-09-02 12:45:00 +0530
categories: system-design
tags: ["api gateway", "마이크로서비스", "시스템설계기초", "입문", "api"]
toc: true
toc_sticky: true
excerpt: "마이크로서비스 아키텍처를 공부하면 반드시 등장하는 API Gateway가 정확히 무슨 역할을 하는지 개념부터 예제까지 정리했다."
---

## 왜 클라이언트가 서비스마다 직접 호출하면 안 되는가

마이크로서비스로 시스템을 나누면 주문 서비스, 결제 서비스, 회원 서비스처럼 여러 개의 독립된 서버가 생긴다. 클라이언트(앱, 웹)가 이 서비스들을 하나하나 직접 호출하게 만들면, 각 서비스의 주소가 바뀔 때마다 클라이언트 코드를 수정해야 하고 인증도 서비스마다 따로 구현해야 한다. **API Gateway**는 클라이언트와 여러 백엔드 서비스 사이에 놓여, 이 모든 요청을 받아 적절한 서비스로 전달해주는 단일 진입점이다.

## API Gateway가 하는 일

| 역할 | 설명 |
|---|---|
| 라우팅 | 요청 경로에 따라 알맞은 백엔드 서비스로 전달 |
| 인증/인가 | 토큰 검증을 게이트웨이에서 한 번에 처리 |
| 레이트 리밋 | 서비스별로 반복 구현하지 않고 게이트웨이에서 공통 적용 |
| 응답 조합 | 여러 서비스의 응답을 하나로 합쳐 클라이언트에 전달(BFF와 유사한 역할) |
| 로깅·모니터링 | 모든 요청이 거쳐가는 지점이라 관측성 확보가 쉬움 |

## 그림으로 보는 구조 차이

```text
게이트웨이 없음:
클라이언트 -> 주문 서비스 (인증 로직 각각 구현)
클라이언트 -> 결제 서비스 (인증 로직 각각 구현)
클라이언트 -> 회원 서비스 (인증 로직 각각 구현)

게이트웨이 있음:
클라이언트 -> API Gateway (인증·라우팅 한 곳에서 처리)
                 ├─> 주문 서비스
                 ├─> 결제 서비스
                 └─> 회원 서비스
```

## 코드로 보는 간단한 라우팅 설정 예제

```yaml
# Spring Cloud Gateway 설정 예시
spring:
  cloud:
    gateway:
      routes:
        - id: order-service
          uri: http://order-service:8080
          predicates:
            - Path=/api/orders/**
        - id: payment-service
          uri: http://payment-service:8081
          predicates:
            - Path=/api/payments/**
```

`/api/orders`로 오는 요청은 주문 서비스로, `/api/payments`로 오는 요청은 결제 서비스로 자동 라우팅된다. 클라이언트는 게이트웨이 주소 하나만 알면 되고, 뒤에서 서비스 주소가 바뀌어도 클라이언트 코드는 그대로다.

## 실무 포인트

- **API Gateway 자체가 단일 장애점(SPOF)이 될 수 있다.** 게이트웨이가 죽으면 모든 서비스로 가는 길이 막히므로, 반드시 여러 인스턴스로 이중화해야 한다.
- **게이트웨이에 비즈니스 로직을 넣기 시작하면 관리가 어려워진다.** 라우팅·인증·공통 정책 같은 횡단 관심사만 게이트웨이에 두고, 비즈니스 로직은 각 서비스에 남겨야 한다.
- **서비스 메시(Service Mesh)와 혼동하지 말아야 한다.** API Gateway는 외부(클라이언트)에서 들어오는 트래픽(North-South)을 다루고, 서비스 메시는 내부 서비스 간 통신(East-West)을 다룬다는 점에서 역할이 다르다.

## 마무리 요약

- API Gateway는 클라이언트와 여러 백엔드 서비스 사이의 단일 진입점 역할을 한다.
- 라우팅, 인증, 레이트 리밋 같은 공통 관심사를 한 곳에서 처리해 각 서비스의 중복 구현을 줄여준다.
- 게이트웨이 자체의 이중화와, 비즈니스 로직을 넣지 않는 것이 실무에서 중요한 원칙이다.

## 참고 자료

- [Spring Cloud Gateway 공식 문서](https://docs.spring.io/spring-cloud-gateway/reference/)
- [AWS 공식 문서 - API Gateway 개념](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html)
