---
layout: single
title: "Spring Boot로 gRPC 서비스 만들기 — Protobuf 정의부터 배포까지"
date: 2026-08-20 12:25:00 +0530
categories: backend
tags: ["grpc", "spring-boot", "protobuf", "java", "microservice"]
toc: true
toc_sticky: true
excerpt: "gRPC가 무엇인지, 언제 쓸지는 이미 정리됐다면 이제 남는 질문은 하나다 — 실제로 Spring Boot 프로젝트에 gRPC 서버를 어떻게 붙이는가. proto 정의, 코드 생성, 서버 구현, 배포까지 실습 순서로 정리한다."
---

## 왜 지금 gRPC 실습이 필요한가

gRPC가 REST보다 지연시간과 타입 안전성에서 유리하다는 이야기는 이제 많이 알려져 있다. 문제는 그다음이다. "그래서 실제로 Spring Boot 프로젝트에 gRPC 서버를 어떻게 붙이는가"를 다루는 자료는 상대적으로 드물다. `.proto` 파일을 어디에 두고, 코드는 어떻게 생성하고, Spring Bean으로 어떻게 등록하고, Kubernetes 환경에서는 무엇을 추가로 챙겨야 하는지 — 이 실무적인 배선(wiring) 작업이 실제 진입 장벽의 대부분을 차지한다.

다행히 최근 몇 년 사이 이 배선 비용이 크게 줄었다. 커뮤니티 주도의 `grpc-spring-boot-starter`가 오랫동안 이 자리를 채워왔고, Spring 팀도 별도로 gRPC 공식 지원 프로젝트를 실험적으로 공개하며 생태계에 힘을 보태고 있다. 이 글은 비교론이 아니라, 지금 바로 코드를 작성해 서비스를 띄우는 실습 관점에서 gRPC 서비스를 처음부터 구성하는 과정을 다룬다.

## 핵심 개념 1: gRPC 서비스를 구성하는 세 조각

gRPC 서비스는 크게 세 조각으로 나뉜다. 하나라도 빠지면 빌드 자체가 되지 않으므로, 먼저 전체 그림을 잡고 시작하는 편이 헤매지 않는다.

<img src="/assets/images/posts/2026-08-20-grpc-service-spring-boot-1.svg" alt="Spring Boot gRPC 서비스 구조도 - proto 정의, protobuf-gradle-plugin 코드 생성, 서버/클라이언트 스텁, Spring Boot 서버, Kubernetes 헬스체크 흐름" style="width:100%;">

| 조각 | 역할 | 대표 도구 |
|---|---|---|
| `.proto` 정의 | 서비스 메서드와 메시지 타입을 언어 중립적으로 선언하는 계약 | Protocol Buffers (proto3) |
| 코드 생성 | `.proto`에서 서버 스텁·클라이언트 스텁 Java 코드를 자동 생성 | `protobuf-gradle-plugin` + `protoc` |
| 런타임 통합 | 생성된 서버 스텁을 Spring Bean으로 등록하고 포트·인터셉터 설정 | `grpc-spring-boot-starter`, Spring gRPC |

`.proto` 파일과 생성 코드는 사람이 직접 짜는 부분이 아니라 빌드 과정의 산출물이라는 점이 REST 컨트롤러 작성과 가장 다른 지점이다. 실제로 작성하는 코드는 생성된 추상 클래스를 상속해 비즈니스 로직만 채우는 구현체뿐이다.

## 핵심 개념 2: Spring Boot 통합 방식 비교

Spring Boot에 gRPC 서버를 붙이는 방법은 현재 두 갈래로 정리할 수 있다.

| 통합 방식 | 성격 | 특징 |
|---|---|---|
| `grpc-spring-boot-starter` (devh) | 커뮤니티 오픈소스, 다년간 실무 검증 | `@GrpcService` 어노테이션 하나로 Bean 자동 등록, 문서·예제 풍부 |
| Spring gRPC (Spring 공식 실험 프로젝트) | Spring 팀이 공개한 초기 단계 프로젝트 | Spring Framework의 auto-configuration 방식과 더 긴밀하게 통합하는 방향으로 개발 중 |

Spring 공식 프로젝트는 아직 초기 단계라 프로덕션 도입 전에는 릴리스 노트와 마이그레이션 가이드를 직접 확인하는 것이 안전하다. 이 글의 예제는 실무에서 검증 기간이 긴 `grpc-spring-boot-starter` 기준으로 작성했다. 두 방식 모두 내부적으로는 `grpc-java`(gRPC의 공식 Java 구현체)를 감싸는 형태이므로, 코드 생성 단계와 `.proto` 작성법 자체는 동일하다.

## 예제 1: Protobuf 서비스 정의와 Gradle 코드 생성 설정

`src/main/proto/order_service.proto`에 서비스 계약을 정의한다.

```protobuf
syntax = "proto3";

package order.v1;

option java_multiple_files = true;
option java_package = "com.example.grpc.order";

service OrderService {
  rpc GetOrder (OrderRequest) returns (OrderResponse);
}

message OrderRequest {
  string order_id = 1;
}

message OrderResponse {
  string order_id = 1;
  string status = 2;
  int64 total_amount = 3;
}
```

`build.gradle.kts`에는 코드 생성 플러그인과 실행 시 필요한 의존성을 추가한다.

```kotlin
plugins {
    id("com.google.protobuf") version "0.9.4"
}

dependencies {
    implementation("net.devh:grpc-spring-boot-starter:3.1.0.RELEASE")
    implementation("io.grpc:grpc-protobuf:1.68.1")
    implementation("io.grpc:grpc-stub:1.68.1")
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.5" }
    plugins {
        create("grpc") { artifact = "io.grpc:protoc-gen-java-grpc:1.68.1" }
    }
    generateProtoTasks {
        all().forEach { task -> task.plugins { create("grpc") {} } }
    }
}
```

버전은 사용하는 스타터·`grpc-java` 릴리스에 맞춰 확인 후 조정해야 한다. `./gradlew build`를 실행하면 `build/generated/source/proto`에 `OrderServiceGrpc`, `OrderRequest`, `OrderResponse` 등 자바 클래스가 생성된다.

## 예제 2: 서버 구현체와 애플리케이션 설정

생성된 `OrderServiceGrpc.OrderServiceImplBase`를 상속해 비즈니스 로직을 채운다.

```java
@GrpcService
public class OrderGrpcServer extends OrderServiceGrpc.OrderServiceImplBase {

    private final OrderQueryService orderQueryService;

    public OrderGrpcServer(OrderQueryService orderQueryService) {
        this.orderQueryService = orderQueryService;
    }

    @Override
    public void getOrder(OrderRequest request,
                          StreamObserver<OrderResponse> responseObserver) {
        try {
            Order order = orderQueryService.find(request.getOrderId());

            OrderResponse response = OrderResponse.newBuilder()
                .setOrderId(order.getId())
                .setStatus(order.getStatus().name())
                .setTotalAmount(order.getTotalAmount())
                .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();
        } catch (OrderNotFoundException e) {
            responseObserver.onError(
                Status.NOT_FOUND
                    .withDescription("주문을 찾을 수 없습니다: " + request.getOrderId())
                    .asRuntimeException()
            );
        }
    }
}
```

`application.yml`에서는 gRPC 서버 포트와 리플렉션(reflection) 서비스 활성화 여부를 설정한다.

```yaml
grpc:
  server:
    port: 9090
    reflection-service-enabled: true   # 개발 환경에서 grpcurl 등으로 탐색할 때만 켠다
```

`@GrpcService` 어노테이션이 붙은 Bean은 스타터가 자동으로 별도 gRPC 서버(기본적으로 HTTP 서버와 다른 포트)에 등록한다. REST 컨트롤러처럼 `@RestController`를 붙이는 감각과 크게 다르지 않지만, 실행 중인 서버가 논리적으로 두 개(HTTP + gRPC)라는 점은 배포 설정에서 반드시 반영해야 한다.

## 실무 포인트

- **예외를 그대로 던지지 않는다.** gRPC는 HTTP 상태 코드 대신 자체 `Status` 코드 체계(`NOT_FOUND`, `INVALID_ARGUMENT`, `INTERNAL` 등)를 쓴다. 일반 Java 예외를 그대로 흘려보내면 클라이언트에는 의미 없는 `UNKNOWN` 코드로 전달되므로, 인터셉터나 서비스 구현체에서 도메인 예외를 gRPC `Status`로 명시적으로 변환해야 한다.
- **리플렉션 서비스는 운영 환경에서 기본적으로 끈다.** 개발 중 `grpcurl`로 서비스 목록을 조회할 때는 유용하지만, 운영 환경에 그대로 켜두면 서비스 스키마 전체가 외부에 노출될 수 있다.
- **Kubernetes 헬스체크는 `grpc.health.v1` 프로토콜을 별도로 구현해야 한다.** HTTP 기반 `/actuator/health`와 달리 gRPC는 표준 Health Checking Protocol을 지원하는 별도 서비스를 등록해야 `grpc_health_probe` 같은 도구로 readiness/liveness를 검사할 수 있다.
- **인증은 인터셉터에서 메타데이터로 처리한다.** REST의 Authorization 헤더에 대응하는 것이 gRPC의 메타데이터(Metadata)이며, `ServerInterceptor`에서 토큰을 검증하는 패턴이 표준적이다.
- **메시지 크기·keepalive 설정을 트래픽 특성에 맞게 조정한다.** 기본 최대 메시지 크기를 넘는 대용량 페이로드나, 커넥션이 오래 유지되는 스트리밍 API를 쓴다면 서버·클라이언트 양쪽의 관련 옵션을 함께 점검해야 한다.

## 3줄 요약

- gRPC 서비스는 `.proto` 계약, 코드 생성, Spring 통합이라는 세 조각으로 구성되며, 실제로 손으로 작성하는 코드는 생성된 추상 클래스를 상속한 구현체뿐이다.
- `grpc-spring-boot-starter`의 `@GrpcService`를 쓰면 REST 컨트롤러 작성과 비슷한 감각으로 서버를 등록할 수 있지만, HTTP 서버와 별개의 gRPC 서버가 함께 뜬다는 점은 배포 설계에 반영해야 한다.
- 예외의 `Status` 코드 변환, 헬스체크 프로토콜 구현, 리플렉션 서비스 비활성화는 실제 운영 배포 전 반드시 챙겨야 할 항목이다.

## 참고 자료

- [gRPC 공식 문서 — Java Quick Start](https://grpc.io/docs/languages/java/quickstart/)
- [grpc-spring-boot-starter (devh) GitHub](https://github.com/grpc-ecosystem/grpc-spring)
- [gRPC Health Checking Protocol](https://github.com/grpc/grpc/blob/master/doc/health-checking.md)
- [Protocol Buffers 공식 문서 — Java Generated Code](https://protobuf.dev/reference/java/java-generated/)
