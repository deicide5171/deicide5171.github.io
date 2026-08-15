---
layout: single
title: "HikariCP 커넥션 풀 튜닝 실전 — 커넥션 부족과 누수 잡기"
date: 2026-08-19 13:35:00 +0530
categories: database
tags: ["hikaricp", "connection-pool", "jdbc", "커넥션누수", "spring-boot"]
toc: true
toc_sticky: true
excerpt: "트래픽이 몰릴 때마다 반복되는 HikariCP 타임아웃 예외를 pool size만 키워서 넘기지 않도록, 커넥션 부족과 커넥션 누수를 구분해 진단하고 튜닝하는 방법을 정리한다."
---

## 왜 지금 커넥션 풀 튜닝인가

트래픽이 몰리는 순간 로그에 `HikariPool-1 - Connection is not available, request timed out after 30000ms` 같은 예외가 쏟아지는 경험은 Spring Boot 서비스를 운영해본 사람이라면 한 번쯤 마주친다. Spring Boot 2.x 이후 기본 데이터소스 구현체로 HikariCP가 채택되면서 별도 설정 없이도 커넥션 풀이 동작하지만, 그만큼 기본값을 그대로 둔 채 운영하다 트래픽이 늘어난 뒤에야 문제를 겪는 경우가 많다.

문제는 여기서 pool size를 무작정 키우는 대응이다. 애플리케이션 서버의 스레드 수, DB 서버가 감당 가능한 총 커넥션 수, 각 요청이 커넥션을 붙잡고 있는 시간 사이의 관계를 이해하지 못한 채 숫자만 올리면, 이번엔 DB 서버의 `max_connections`를 초과하거나 느린 쿼리 하나가 커넥션 전체를 잠식하는 새로운 문제로 이어진다.

특히 "커넥션 부족"과 "커넥션 누수"는 겉으로 보이는 증상 — 둘 다 결국 커넥션을 못 구해 타임아웃이 난다 — 이 비슷해 원인을 혼동하기 쉽다. 하지만 해법은 정반대에 가깝다. 이 둘을 구분하는 눈이 튜닝의 출발점이다.

## 핵심 개념 1: HikariCP 주요 파라미터

| 파라미터 | 기본값 | 의미 |
|---|---|---|
| `maximumPoolSize` | 10 | 풀이 유지할 수 있는 최대 커넥션 수(유휴+사용중 합) |
| `minimumIdle` | maximumPoolSize와 동일 | 유휴 상태로 최소한 유지할 커넥션 수 |
| `connectionTimeout` | 30000ms | 커넥션을 못 구했을 때 대기하다 예외를 던지기까지의 시간 |
| `idleTimeout` | 600000ms(10분) | 유휴 커넥션을 풀에서 제거하기까지의 시간(minimumIdle 초과분만 대상) |
| `maxLifetime` | 1800000ms(30분) | 커넥션 하나가 살아있을 수 있는 최대 수명, DB 측 idle timeout보다 짧게 잡는 것이 원칙 |
| `leakDetectionThreshold` | 0(비활성) | 이 시간 이상 반환되지 않은 커넥션을 누수 의심으로 로깅 |

이 값들은 서로 독립적이지 않다. 예를 들어 `maxLifetime`을 DB 서버의 커넥션 타임아웃보다 길게 두면, DB가 먼저 끊어버린 죽은 커넥션을 풀이 살아있다고 착각해 애플리케이션에 넘겨주는 문제가 생길 수 있다.

## 핵심 개념 2: 커넥션 부족 vs 커넥션 누수

| 구분 | 증상 | 주요 원인 | 진단 방법 |
|---|---|---|---|
| 커넥션 부족(Pool exhaustion) | 트래픽 증가 시점에 몰려서 `connectionTimeout` 예외 다발, 트래픽이 줄면 정상화 | 동시 요청 수가 `maximumPoolSize`를 일시적으로 초과, 슬로우 쿼리가 커넥션 점유 시간을 늘림 | 요청량·응답시간 그래프와 예외 발생 시점을 겹쳐 확인 |
| 커넥션 누수(Connection leak) | 트래픽이 줄어도 active 커넥션 수가 회복되지 않고 서서히 누적 | 예외 발생 경로에서 커넥션을 닫지 않음, 트랜잭션이 커밋/롤백 없이 방치됨 | `leakDetectionThreshold` 설정 후 경고 로그의 스택 트레이스 확인, Micrometer의 `hikaricp.connections.active` 추이 관찰 |

부족은 "잠깐 몰렸다 풀리는" 패턴을, 누수는 "시간이 갈수록 쌓이기만 하는" 패턴을 보인다는 점이 가장 실용적인 구분 기준이다.

## 예제: application.yml 설정과 누수 탐지

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 10
      connection-timeout: 3000
      idle-timeout: 600000
      max-lifetime: 1800000
      leak-detection-threshold: 60000
```

누수는 대부분 커넥션(또는 그 위의 트랜잭션 리소스)을 명시적으로 닫지 않는 코드 경로에서 발생한다.

```java
// 누수 위험: 예외 발생 시 conn.close()가 실행되지 않는다
Connection conn = dataSource.getConnection();
PreparedStatement ps = conn.prepareStatement(sql);
ps.executeUpdate(); // 여기서 예외가 나면 conn이 반환되지 않는다

// 안전한 패턴: try-with-resources로 예외 발생 여부와 무관하게 반환 보장
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql)) {
    ps.executeUpdate();
}
```

`leakDetectionThreshold`를 60초로 설정하면, 커넥션이 60초 넘게 반환되지 않을 때 아래와 같은 경고가 찍혀 누수 지점의 스택 트레이스를 바로 확인할 수 있다.

```
2026-08-19 13:20:11 WARN HikariPool-1 - Connection leak detection triggered for
com.zaxxer.hikari.pool.ProxyConnection@... on thread http-nio-8080-exec-7,
stack trace follows
```

## 실무 포인트

- **pool size는 "많을수록 좋다"가 아니다.** HikariCP 위키는 `((core_count * 2) + effective_spindle_count)` 같은 계산식을 출발점으로 제시하지만, 이는 워크로드에 따라 크게 달라지는 값이라 실제 운영 수치를 그대로 적용하기보다 부하 테스트로 검증하는 편이 안전하다.
- **애플리케이션 인스턴스 수를 곱해서 생각한다.** 인스턴스 3대가 각각 `maximumPoolSize=20`이면 DB에는 최대 60개의 커넥션이 동시에 열릴 수 있다는 뜻이다. DB의 `max_connections` 설정과 다른 서비스가 쓰는 몫까지 함께 계산해야 한다.
- **connectionTimeout을 지나치게 낮추면 순간적인 트래픽 스파이크에도 예외가 폭증하고, 지나치게 높이면 스레드가 대기 상태로 쌓여 전체 응답 지연으로 번진다.** 서비스의 허용 가능한 응답 시간 범위 안에서 값을 잡아야 한다.
- **leakDetectionThreshold는 오탐 가능성을 함께 고려한다.** 배치 작업처럼 원래 커넥션을 오래 점유하는 로직이 있으면 오탐이 반복될 수 있으므로, 임계값을 실제 정상 쿼리의 최대 소요 시간보다 여유 있게 잡는다.
- **Micrometer 등으로 active/idle/pending 지표를 상시 관찰한다.** 예외가 터지기 전에 pending(대기 스레드) 수가 늘어나는 추세를 먼저 포착할 수 있다.

<img src="/assets/images/posts/2026-08-19-hikaricp-connection-pool-tuning-1.svg" alt="HikariCP 커넥션 풀 상태 흐름도 - 유휴 풀, 대여, 사용 중, 반환과 대기열/누수 탐지 분기" style="width:100%;">

## 3줄 요약

- 커넥션 예외가 터지면 pool size부터 키우기 전에, 트래픽에 따라 일시적으로 몰리는 "부족"인지 시간이 갈수록 누적되는 "누수"인지부터 구분한다.
- 누수는 try-with-resources로 반환을 보장하고 `leakDetectionThreshold`로 미반환 커넥션의 스택 트레이스를 확인하는 방식으로 잡는다.
- pool size는 애플리케이션 인스턴스 수와 DB의 `max_connections`를 함께 고려해 계산하고, 확정적인 공식 수치보다는 부하 테스트로 검증한 값을 신뢰한다.

## 참고 자료

- [HikariCP GitHub — About Pool Sizing](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [HikariCP GitHub — Configuration (README)](https://github.com/brettwooldridge/HikariCP#configuration-knobs-baby)
- [Spring Boot 공식 문서 — Configure a DataSource](https://docs.spring.io/spring-boot/reference/data/sql.html#data.sql.datasource)
