---
layout: single
title: "로그만으로는 부족하다 — Spring Boot Micrometer/Actuator 옵저버빌리티 실무"
date: 2026-08-27 13:25:00 +0530
categories: backend
tags: ["spring-boot", "micrometer", "actuator", "observability", "prometheus"]
toc: true
toc_sticky: true
excerpt: "장애가 나면 로그를 grep하는 것으로는 한계가 있다. Micrometer와 Actuator로 메트릭·트레이스를 표준화하고 카디널리티 함정을 피하는 법을 정리한다."
---

장애가 발생했을 때 로그를 `grep`으로 뒤지는 것은 "무슨 일이 일어났는지"는 알려주지만 "얼마나 자주, 어느 정도 심각하게 일어나는지"는 알려주지 않는다. 이 간극을 메우는 것이 메트릭이고, Spring 생태계에서는 Micrometer가 사실상 표준 계측 라이브러리 역할을 한다. Micrometer는 여러 모니터링 시스템(Prometheus, Datadog, CloudWatch 등)에 대한 벤더 중립적 파사드로, 애플리케이션 코드는 Micrometer API로만 계측하고 실제 백엔드는 설정으로 바꿀 수 있다.

Spring Boot Actuator는 이 위에 `/actuator/health`, `/actuator/metrics`, `/actuator/prometheus` 같은 관리용 HTTP 엔드포인트를 얹어준다. 최근에는 분산 트레이싱도 Micrometer Tracing(과거 Spring Cloud Sleuth를 대체)이 담당하게 되면서, 메트릭과 트레이스를 같은 계측 축으로 다룰 수 있게 됐다. 이 글에서는 Micrometer/Actuator 실무 적용과 흔히 빠지는 카디널리티 함정을 정리한다.

## 핵심 개념 1: Micrometer의 세 가지 계측 프리미티브

Micrometer는 세 가지 기본 계측 타입을 제공한다.

- **Counter**: 누적 증가만 하는 값. 요청 수, 에러 수처럼 "몇 번 일어났는가"를 센다.
- **Timer**: 이벤트의 지속시간과 발생 빈도를 함께 기록한다. HTTP 요청 처리 시간, DB 쿼리 시간 등에 쓴다.
- **Gauge**: 특정 시점의 순간값. 커넥션 풀의 현재 사용 중인 커넥션 수, 큐 대기 길이처럼 오르내리는 값을 표현한다.

Spring Boot는 `@Timed` 애노테이션이나 `MeterRegistry`를 통해 이 세 프리미티브를 애플리케이션 코드에 쉽게 붙일 수 있게 해준다. HTTP 요청 처리량, 응답 시간 분포 같은 것은 Spring MVC 자동 계측으로 이미 기본 제공되므로, 커스텀 계측은 비즈니스 로직에서 의미 있는 값(주문 처리 건수, 결제 실패율 등)에 집중하는 것이 효율적이다.

## 핵심 개념 2: 카디널리티 — 조용히 시스템을 무너뜨리는 함정

메트릭에 태그(레이블)를 붙이면 그룹별로 값을 나눠 볼 수 있어 유용하다. 문제는 태그 값의 종류(카디널리티)가 커지면 시계열 개수가 태그 값의 곱만큼 폭발한다는 것이다. `user_id`나 `request_id`처럼 사실상 무한한 값을 갖는 필드를 태그로 붙이면, 메트릭 백엔드(Prometheus 등)의 메모리와 쿼리 성능이 감당 불가능해진다.

| 태그 예시 | 카디널리티 | 적합성 |
|---|---|---|
| `http.method` (GET, POST...) | 낮음(수개) | 안전 |
| `http.status` (200, 404, 500...) | 낮음(수십개) | 안전 |
| `endpoint` (경로 패턴, `/users/{id}` 등) | 중간(수백개) | 대체로 안전 — 단, 파라미터 미치환 시 위험 |
| `user_id`, `order_id` | 매우 높음(무한) | 위험 — 태그 대신 로그/트레이스로 |

Spring MVC는 기본적으로 URL 경로를 패턴(`/users/{id}`)으로 계측하지만, 커스텀 계측을 추가할 때 실수로 실제 값(`/users/12345`)을 태그에 넣는 실수가 흔하다.

<img src="/assets/images/posts/2026-08-27-spring-boot-observability-micrometer-1.svg" alt="애플리케이션 코드가 Micrometer API로 계측하면 MeterRegistry를 거쳐 Prometheus 같은 백엔드로 내보내지고, 동시에 Micrometer Tracing이 trace id를 로그 MDC에 심어 메트릭과 로그와 트레이스가 연결되는 구조도" style="width:100%;">

## 예제: 커스텀 메트릭과 트레이스 상관관계 설정

```java
@Service
public class OrderService {
    private final Counter orderFailureCounter;
    private final Timer orderProcessingTimer;

    public OrderService(MeterRegistry registry) {
        this.orderFailureCounter = Counter.builder("orders.failed")
            .tag("reason", "unspecified") // 낮은 카디널리티 태그만 사용
            .register(registry);
        this.orderProcessingTimer = Timer.builder("orders.processing.time")
            .publishPercentiles(0.5, 0.95, 0.99) // P50/P95/P99 히스토그램 발행
            .register(registry);
    }

    public void processOrder(Order order) {
        orderProcessingTimer.record(() -> {
            try {
                doProcess(order);
            } catch (OrderException e) {
                orderFailureCounter.increment(); // user_id는 태그 아닌 로그에만
                log.error("order processing failed order_id={}", order.getId(), e);
                throw e;
            }
        });
    }
}
```

```yaml
# application.yml — Micrometer Tracing으로 trace id를 로그에 자동 삽입
management:
  tracing:
    sampling:
      probability: 0.1
  endpoints:
    web:
      exposure:
        include: health, metrics, prometheus
logging:
  pattern:
    level: "%5p [%X{traceId:-},%X{spanId:-}]"
```

`logging.pattern.level`에 MDC 값(`traceId`, `spanId`)을 넣으면, 로그 한 줄만으로 해당 요청의 분산 트레이스를 역추적할 수 있다.

## 실무 포인트

- **`/actuator` 엔드포인트는 반드시 접근 제어를 건다**: `/actuator/env`, `/actuator/heapdump` 같은 엔드포인트는 민감 정보나 메모리 덤프를 노출할 수 있다. `management.endpoints.web.exposure.include`로 노출 범위를 최소화하고, 별도 포트/네트워크 정책으로 외부 접근을 차단해야 한다.
- **히스토그램 버킷은 실제 SLO 경계에 맞춘다**: `publishPercentiles`만으로는 임의의 백분위를 나중에 재계산할 수 없다. SLO 판정에 쓸 정확한 임계값(예: 200ms)이 있다면 `serviceLevelObjectives()`로 해당 버킷을 명시적으로 추가해야 알람 조건을 정확히 만들 수 있다.
- **샘플링 비율은 트래픽 규모에 맞춰 조정한다**: 트레이싱 샘플링 확률을 100%로 두면 고트래픽 서비스에서 트레이싱 백엔드에 과부하가 걸린다. 초기값은 낮게(1~10%) 잡고, 에러 트레이스는 별도 정책으로 100% 포착하는 구조를 검토한다.

## 3줄 요약

- Micrometer는 Counter·Timer·Gauge라는 벤더 중립 계측 API로 여러 모니터링 백엔드에 동일한 코드로 값을 보낼 수 있게 한다.
- `user_id`처럼 카디널리티가 높은 값을 메트릭 태그로 쓰면 모니터링 백엔드가 감당 못 하므로, 그런 값은 로그·트레이스에만 남긴다.
- Micrometer Tracing으로 trace id를 로그 MDC에 심으면 메트릭에서 이상 신호를 포착한 뒤 로그·트레이스로 바로 이어서 조사할 수 있다.

## 참고 자료

- [Micrometer 공식 문서](https://docs.micrometer.io/micrometer/reference/)
- [Spring Boot 공식 문서: Actuator](https://docs.spring.io/spring-boot/reference/actuator/index.html)
- [Micrometer Tracing 공식 문서](https://docs.micrometer.io/tracing/reference/)
