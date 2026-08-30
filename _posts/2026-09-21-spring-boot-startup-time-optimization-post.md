---
layout: single
title: "Spring Boot 애플리케이션 시작이 느릴 때 — 부트 타임 줄이는 법"
date: 2026-09-21 12:25:00 +0530
categories: backend
tags: ["springboot", "부트타임", "지연초기화", "jvm", "성능튜닝"]
toc: true
toc_sticky: true
excerpt: "로컬 개발과 배포 시 Spring Boot 애플리케이션 기동 시간이 계속 늘어날 때, 원인을 진단하고 실제로 시작 시간을 줄이는 설정을 정리했다."
---

## 왜 지금 부트 타임이 문제가 되나

프로젝트 초반에는 애플리케이션이 3~4초 만에 뜨다가, 빈(Bean)이 수백 개로 늘고 라이브러리가 쌓이면서 어느 순간 20초, 30초씩 걸리기 시작한다. 로컬 개발에서는 코드 한 줄 고치고 재시작할 때마다 이 시간이 그대로 낭비되고, 쿠버네티스 환경에서는 새 Pod가 뜨는 시간이 길어질수록 롤링 업데이트와 오토스케일링 반응 속도가 느려진다. `readinessProbe`의 `initialDelaySeconds`를 계속 늘려가며 임시방편으로 버티다 보면, 결국 근본 원인을 짚어야 하는 시점이 온다.

Spring Boot의 시작 시간은 크게 세 구간으로 나뉜다. JVM 프로세스 자체를 띄우는 시간, 클래스패스를 스캔해 빈을 등록하는 시간, 그리고 등록된 빈들을 실제로 초기화(생성자 호출, `@PostConstruct` 실행)하는 시간이다. 문제 진단은 이 세 구간 중 어디가 느린지를 먼저 구분하는 데서 시작한다.

## 어디가 느린지부터 측정하라

```
2026-09-21 12:00:01.234  INFO --- Starting Application using Java 21
2026-09-21 12:00:03.891  INFO --- Started Application in 12.657 seconds (process running for 13.02)
```

Spring Boot 로그에 이미 총 소요 시간이 찍히지만, 어느 빈이 오래 걸리는지는 별도로 확인해야 한다. `--debug` 옵션이나 `spring.boot.admin`, 또는 `ApplicationStartup` API를 활용하면 빈 단위로 초기화 시간을 뽑을 수 있다.

```java
SpringApplication app = new SpringApplication(Application.class);
app.setApplicationStartup(new BufferingApplicationStartup(2048));
app.run(args);
```

이렇게 하면 `ApplicationStartup` 이벤트를 수집해 어떤 빈, 어떤 오토컨피규레이션 클래스가 시간을 많이 쓰는지 실측할 수 있다. 짐작으로 최적화를 시작하면 엉뚱한 곳을 손대고 시간만 낭비하기 쉽다.

## 잘못된 접근: 무작정 컴포넌트 스캔 범위부터 줄이기

흔히 첫 시도로 `@ComponentScan(basePackages = "...")` 범위를 좁히거나 불필요해 보이는 `@Configuration` 클래스를 지우려 한다. 이 방법이 나쁜 것은 아니지만, 대부분의 실제 병목은 컴포넌트 스캔 자체보다 **오토컨피규레이션 조건 평가와 외부 연결(DB 커넥션 풀 초기화, 메시지 브로커 연결, 캐시 워밍업)**에서 발생한다. 스캔 범위만 좁히고 커넥션 풀 초기화 로직은 그대로 두면 체감 개선이 거의 없다.

또 다른 흔한 실수는 측정 없이 `spring-boot-devtools`의 자동 재시작 기능만 켜두고 "빨라졌다"고 착각하는 것이다. devtools의 재시작은 클래스로더를 재사용해 재시작을 빠르게 보일 뿐, 실제 프로덕션 콜드 스타트 시간과는 다른 지표다.

## 올바른 접근

**1) 지연 초기화(Lazy Initialization)를 활성화한다.**

```yaml
spring:
  main:
    lazy-initialization: true
```

빈을 실제로 필요할 때까지 생성하지 않는다. 다만 요청이 처음 들어올 때 초기화 비용이 그쪽으로 옮겨갈 뿐이므로, 첫 요청 지연이 민감한 서비스라면 헬스체크로 워밍업을 별도로 태워야 한다.

**2) 불필요한 오토컨피규레이션을 명시적으로 제외한다.**

```java
@SpringBootApplication(exclude = {
    JmxAutoConfiguration.class
})
```

**3) 커넥션 풀·캐시 초기 크기를 줄인다.** HikariCP의 `minimum-idle`을 필요 이상으로 크게 잡아두면 시작 시점에 커넥션을 미리 여러 개 맺느라 시간이 늘어난다.

**4) GraalVM Native Image나 CDS(Class Data Sharing)를 검토한다.** JVM 프로세스 자체의 뜨는 속도가 병목이라면, `-Xshare:dump`로 클래스 데이터를 사전 생성해두는 AppCDS가 재시작마다 클래스 로딩 시간을 줄여준다. 컨테이너 콜드 스타트가 특히 중요한 서버리스·오토스케일링 환경이라면 Native Image 전환도 고려 대상이다.

## 실무 포인트

- **로컬 개발 환경과 운영 환경의 최적화 목표를 구분하라.** 로컬은 지연 초기화·devtools로 반복 재시작 체감을 줄이고, 운영은 콜드 스타트 자체(오토스케일링 반응성)를 줄이는 데 집중한다.
- **테스트 환경에서 `@SpringBootTest`가 매번 새 컨텍스트를 띄우는지 확인하라.** 컨텍스트 캐싱이 깨지는 설정(프로필, 프로퍼티 조합이 테스트마다 다름)이 있으면 CI 전체 시간이 부트 타임 때문에 크게 늘어난다.
- **지연 초기화는 순환 참조나 초기화 순서에 의존하는 코드에서 예상치 못한 버그를 드러낼 수 있다.** 도입 전에 통합 테스트로 부작용을 확인한다.

## 마무리 요약

- 부트 타임 최적화는 짐작이 아니라 `ApplicationStartup` API 같은 도구로 실측한 뒤 시작해야 한다.
- 지연 초기화, 불필요한 오토컨피규레이션 제외, 커넥션 풀 초기 크기 조정이 즉시 효과를 보는 대표적인 방법이다.
- 콜드 스타트가 핵심 병목이라면 AppCDS나 Native Image 같은 JVM 레벨 해법까지 검토할 필요가 있다.

## 참고 자료

- [Spring Boot 공식 문서 - Application Startup Tracking](https://docs.spring.io/spring-boot/reference/features/spring-application.html#features.spring-application.startup-tracking)
- [Spring Boot 공식 문서 - GraalVM Native Image Support](https://docs.spring.io/spring-boot/reference/packaging/native-image/introducing-graalvm-native-images.html)
