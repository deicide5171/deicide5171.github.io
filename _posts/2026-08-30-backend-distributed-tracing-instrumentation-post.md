---
layout: single
title: "스팬 하나가 끊기면 추적도 끊긴다 — 백엔드 분산 트레이싱 계측 실무"
date: 2026-08-30 12:25:00 +0530
categories: backend
tags: ["backend", "distributed-tracing", "opentelemetry", "micrometer-tracing", "observability", "spring-boot"]
toc: true
toc_sticky: true
excerpt: "메트릭 대시보드가 갖춰져 있어도 스팬 컨텍스트가 비동기 경계에서 끊기면 트레이스는 조각난다. Micrometer Tracing과 OpenTelemetry Java로 컨텍스트 전파를 실제로 붙이는 계측 실무를 정리한다."
---

분산 트레이싱을 "그냥 라이브러리 붙이면 되는 것"으로 여기다가 실제로 붙여보면 예상 밖의 지점에서 트레이스가 끊긴다. `@Async` 메서드로 넘어가는 순간, `CompletableFuture`의 콜백 스레드로 넘어가는 순간, 메시지 큐에 이벤트를 발행하고 다른 프로세스가 소비하는 순간 — 이런 경계마다 "지금 이 작업이 어느 트레이스에 속하는지"를 나타내는 컨텍스트가 스레드 로컬을 벗어나며 유실되기 쉽다. 계측 라이브러리를 넣는 것 자체는 몇 줄이지만, 이 컨텍스트 전파(context propagation)를 코드베이스 전체의 비동기 경계마다 빠짐없이 이어주는 것이 실제 작업의 8할이다.

이 글은 트레이싱 개념 소개보다, Spring Boot 3.x 기준 Micrometer Tracing(+ OpenTelemetry) 조합으로 실제 코드에 계측을 붙일 때 마주치는 문제와 해법에 집중한다. 샘플링 전략 자체는 별도 주제이므로, 여기서는 "스팬을 어떻게 정확하게 만들고 끊기지 않게 이어가는가"를 다룬다.

## 핵심 개념 1: 트레이스, 스팬, 컨텍스트 전파의 관계

하나의 요청이 여러 서비스를 거치는 흐름 전체가 **트레이스(trace)**이고, 그 안에서 개별 작업 단위(HTTP 핸들러 실행, DB 쿼리, 외부 API 호출)가 **스팬(span)**이다. 각 스팬은 자신의 부모 스팬 ID를 가져서 트리 구조를 이루고, 이 부모-자식 관계를 다음 작업에 전달하는 것이 컨텍스트 전파다. HTTP 경계를 넘을 때는 W3C Trace Context 표준의 `traceparent` 헤더로 전파되고, 같은 프로세스 안에서는 스레드 로컬(또는 리액티브 환경의 `Context`)에 담겨 전파된다.

문제는 스레드 로컬이 스레드 경계를 자동으로 넘지 못한다는 점이다. `ExecutorService`에 작업을 제출하면 그 작업은 다른 스레드에서 실행되므로, 별도 처리 없이는 원래 스레드의 트레이스 컨텍스트가 새 스레드로 전달되지 않는다. Micrometer의 `ContextPropagation` API나 OpenTelemetry의 `Context.wrap()`은 정확히 이 문제, 즉 스레드 경계를 넘을 때 컨텍스트를 캡처하고 복원하는 역할을 한다.

## 핵심 개념 2: Spring Boot에서 실제로 끊기는 지점들

| 경계 유형 | 기본 동작 | 계측 필요 조치 |
|---|---|---|
| 동기 HTTP 호출(RestClient/WebClient) | Micrometer가 자동 계측 | 별도 조치 보통 불필요 |
| `@Async` 메서드 | 스레드 풀 전환 시 컨텍스트 유실 | `ContextExecutorService`로 래핑된 Executor 빈 등록 |
| `CompletableFuture.supplyAsync` | 지정 Executor에 따라 유실 | Micrometer가 감싼 Executor 사용 |
| 리액티브 체인(WebFlux) | 스레드가 계속 바뀜 | Reactor Context에 트레이스 컨텍스트를 심는 `ContextPropagation.WITH_ASYNC_BOUNDARIES` |
| Kafka/RabbitMQ 발행-구독 | 프로세스 경계라 전파 불가능 | 메시지 헤더에 `traceparent` 수동 주입/추출 |
| 배치 잡, 스케줄러(`@Scheduled`) | 새 루트 트레이스로 시작 | 의도된 동작(별도 트레이스가 맞음) — 상위 업무 ID를 태그로만 연결 |

가장 자주 놓치는 것이 Kafka 같은 메시지 큐 경계다. 발행자 프로세스와 소비자 프로세스는 완전히 분리돼 있으므로 컨텍스트를 자동으로 이어줄 방법이 없고, 발행 시점에 현재 트레이스 컨텍스트를 메시지 헤더에 직접 써넣고, 소비 시점에 그 헤더를 읽어 새 스팬의 부모로 지정해야 한다. Spring Kafka는 최근 버전에서 `KafkaTemplate`과 `@KafkaListener`에 이 작업을 자동화하는 계측을 제공하지만, 커스텀 프로듀서/컨슈머 코드나 다른 메시징 시스템에서는 직접 구현해야 한다.

## 핵심 개념 3: 로그와 트레이스를 잇는 MDC 연동

트레이스 ID만으로는 부족하다 — 실제 장애 조사는 트레이스 뷰어(Jaeger, Tempo 등)와 로그(ELK, Loki 등)를 오가며 진행되는데, 로그 라인에 `traceId`가 찍혀 있어야 이 둘을 연결할 수 있다. Micrometer Tracing은 SLF4J MDC에 자동으로 `traceId`, `spanId`를 심어주는 브리지를 제공하므로, 로그 포맷에 `%X{traceId}`를 넣는 것만으로 모든 로그 라인에서 트레이스로 바로 점프할 수 있는 상관관계(correlation)가 생긴다. 단, 이 역시 비동기 경계를 넘으면 MDC가 스레드 로컬이라 함께 끊긴다는 점은 스팬 컨텍스트와 동일하다.

<img src="/assets/images/posts/2026-08-30-backend-distributed-tracing-instrumentation-1.svg" alt="HTTP 요청이 컨트롤러, Async 메서드, Kafka 발행-구독 경계를 지나며 트레이스 컨텍스트가 스레드 로컬 전파와 메시지 헤더 전파로 이어지거나 끊기는 지점을 보여주는 다이어그램" style="width:100%;">

## 예제: Spring Boot 계측 설정

```java
// AsyncConfig.java — @Async 실행기에 컨텍스트 전파 래핑
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {

    private final ContextPropagator contextPropagator;

    @Override
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor delegate = new ThreadPoolTaskExecutor();
        delegate.setCorePoolSize(8);
        delegate.initialize();
        // 컨텍스트를 캡처해 작업 제출 시점 스레드 상태를 새 스레드에 복원
        return ContextExecutorService.wrap(delegate.getThreadPoolExecutor(),
                () -> ContextSnapshot.captureAll());
    }
}
```

```java
// KafkaTracingPropagation.java — 발행 시 traceparent를 메시지 헤더에 주입
@Service
@RequiredArgsConstructor
public class OrderEventPublisher {

    private final KafkaTemplate<String, OrderEvent> kafkaTemplate;
    private final Tracer tracer;
    private final Propagator propagator;

    public void publish(OrderEvent event) {
        ProducerRecord<String, OrderEvent> record =
                new ProducerRecord<>("order-events", event.orderId(), event);

        // 현재 스팬 컨텍스트를 W3C traceparent 형식으로 헤더에 직접 기록
        propagator.inject(tracer.currentTraceContext().context(),
                record.headers(),
                (carrier, key, value) ->
                        carrier.add(key, value.getBytes(StandardCharsets.UTF_8)));

        kafkaTemplate.send(record);
    }
}
```

## 실무 포인트

- **계측 도입 초기엔 "끊긴 트레이스"부터 찾아라.** 새로 계측을 붙이면 처음엔 트레이스 그래프가 여러 조각으로 나뉘어 보이는 게 정상이다. 각 조각의 시작 스팬이 어느 경계(스레드 풀, 메시지 큐, 스케줄러) 직후에 생기는지를 먼저 찾고, 그 경계부터 하나씩 컨텍스트 전파를 붙여나가는 순서로 접근해야 한다.
- **커스텀 스팬은 비즈니스 의미 단위로 만든다.** 프레임워크가 자동으로 만들어주는 HTTP·DB 스팬만으로는 "재고 확인 로직이 왜 느린지"를 구분하기 어렵다. `@Observed` 애노테이션이나 `Tracer.spanBuilder()`로 의미 있는 비즈니스 경계(재고 확인, 할인 계산 등)에 커스텀 스팬을 명시적으로 추가해야 트레이스가 실제로 디버깅에 쓸모 있어진다.
- **컨텍스트 전파 누락은 조용히 실패한다.** 전파가 끊겨도 애플리케이션은 정상 동작하고 에러도 나지 않는다 — 다만 트레이스가 새 루트로 시작될 뿐이다. 이 때문에 코드 리뷰에서 새로운 비동기 경계(신규 `ExecutorService`, 신규 메시징 통합)가 추가될 때마다 컨텍스트 전파 처리 여부를 체크리스트 항목으로 명시하지 않으면 계속 재발한다.

## 3줄 요약

- 분산 트레이싱 계측의 실제 작업량 대부분은 라이브러리 도입이 아니라, 스레드 풀·리액티브 체인·메시지 큐 같은 비동기 경계마다 컨텍스트 전파를 빠짐없이 이어주는 데 있다.
- Micrometer Tracing은 대부분의 Spring 통합(RestClient, `@Async`)에 자동 계측을 제공하지만, 메시지 큐 발행-구독처럼 프로세스 경계를 넘는 구간은 `traceparent`를 헤더에 직접 주입·추출해야 한다.
- MDC 브리지로 로그에 traceId를 심어 로그-트레이스 상관관계를 만들고, 비즈니스 의미 단위의 커스텀 스팬을 추가해야 트레이스가 실제 디버깅 도구로서 값어치를 한다.

## 참고 자료

- [Micrometer Tracing 공식 문서](https://docs.micrometer.io/tracing/reference/index.html)
- [OpenTelemetry Java 공식 문서: Context Propagation](https://opentelemetry.io/docs/languages/java/instrumentation/#context-propagation)
- [W3C Trace Context 표준](https://www.w3.org/TR/trace-context/)
- [Spring Framework 공식 문서: Observability](https://docs.spring.io/spring-framework/reference/integration/observability.html)
