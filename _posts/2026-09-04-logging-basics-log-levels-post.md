---
layout: single
title: "로그 레벨이 뭔가요 — DEBUG, INFO, WARN, ERROR 제대로 쓰기"
date: 2026-09-04 12:25:00 +0530
categories: backend
tags: ["로깅", "logging", "로그레벨", "백엔드기초", "입문"]
toc: true
toc_sticky: true
excerpt: "System.out.println 대신 로거를 써야 하는 이유와, DEBUG·INFO·WARN·ERROR 로그 레벨을 상황에 맞게 구분하는 기준을 정리했다."
---

## 왜 println 대신 로거를 쓰나

디버깅할 때 `System.out.println`(또는 `console.log`)으로 값을 찍어보는 것은 편하지만, 운영 코드에 그대로 남기면 문제가 된다. 출력을 끄고 켤 수 없고, 언제·어디서 찍혔는지 정보가 없으며, 파일로 저장하거나 중요도별로 거르기도 어렵다. **로거(Logger)**는 이 모든 것을 관리 가능하게 해준다. 그 핵심이 **로그 레벨**이다.

## 로그 레벨과 그 의미

| 레벨 | 언제 쓰나 | 예시 |
|---|---|---|
| ERROR | 즉시 대응이 필요한 오류 | 결제 실패, DB 연결 끊김 |
| WARN | 문제는 아니지만 주의가 필요 | 재시도 발생, 사용량 임계치 근접 |
| INFO | 정상 동작의 주요 흐름 기록 | 서버 시작, 주문 생성 완료 |
| DEBUG | 개발 중 상세 추적용 | 변수 값, 분기 진입 여부 |

레벨은 위에서 아래로 갈수록 덜 심각하고 더 상세하다. 로거는 "이 레벨 이상만 출력"하도록 설정할 수 있어, 운영에서는 INFO 이상만 남기고 개발에서는 DEBUG까지 보는 식으로 조절한다.

## 코드 예제

```java
private static final Logger log = LoggerFactory.getLogger(OrderService.class);

public void createOrder(Order order) {
    log.debug("주문 생성 시작, 요청 데이터={}", order); // 개발 중 상세 추적
    try {
        paymentService.pay(order);
        log.info("주문 생성 완료, orderId={}", order.getId()); // 정상 흐름
    } catch (PaymentException e) {
        log.error("결제 실패, orderId={}", order.getId(), e); // 예외는 스택트레이스와 함께
    }
}
```

## 로그를 잘 남기는 원칙

```text
- 예외는 반드시 스택트레이스와 함께 (log.error("메시지", e))
  -> e를 빼먹으면 어디서 터졌는지 알 수 없다

- 민감정보(비밀번호, 카드번호, 토큰)는 절대 로그에 남기지 않기
  -> 로그가 유출되면 그대로 정보 유출이 된다

- 문자열 연결 대신 파라미터 방식 사용 (log.info("id={}", id))
  -> 성능과 가독성 모두 유리
```

## 실무 포인트

- **로그 레벨을 운영에서 DEBUG로 켜두면 로그가 폭증한다.** 디스크가 순식간에 차거나 로그 시스템 비용이 커지므로, 운영은 보통 INFO 이상으로 유지하고 문제 조사 시에만 일시적으로 낮춘다.
- **모든 것을 INFO로 남기면 정작 중요한 로그가 묻힌다.** "정상 흐름의 핵심 이정표"만 INFO로 남기고, 세부 추적은 DEBUG로 내리는 구분이 로그를 유용하게 만든다.
- **구조화된 로깅(JSON 형태)을 쓰면 나중에 검색·분석이 쉬워진다.** 로그를 사람이 눈으로만 보는 게 아니라 로그 수집 시스템(ELK 등)에서 쿼리한다면, 처음부터 구조화된 형식으로 남기는 것이 좋다.

## 마무리 요약

- 로거는 println과 달리 출력 제어·시간·위치 정보·파일 저장·레벨별 필터링을 가능하게 한다.
- ERROR·WARN·INFO·DEBUG를 상황의 심각도와 상세함에 맞게 구분해 쓰는 것이 핵심이다.
- 예외는 스택트레이스와 함께 남기고, 민감정보는 절대 로그에 남기지 않아야 한다.

## 참고 자료

- [SLF4J 공식 매뉴얼](https://www.slf4j.org/manual.html)
- [Logback 공식 문서](https://logback.qos.ch/documentation.html)
