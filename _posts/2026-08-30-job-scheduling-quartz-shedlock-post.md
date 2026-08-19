---
layout: single
title: "@Scheduled를 인스턴스 3대에 붙이면 3번 실행된다 — Quartz vs ShedLock 분산 스케줄링"
date: 2026-08-30 13:25:00 +0530
categories: backend
tags: ["backend", "spring-boot", "quartz", "shedlock", "distributed-lock", "job-scheduling"]
toc: true
toc_sticky: true
excerpt: "Spring @Scheduled는 인스턴스마다 독립적으로 도는 로컬 스케줄러다. 여러 인스턴스로 스케일아웃하는 순간 같은 배치가 중복 실행된다. Quartz의 클러스터 모드와 ShedLock의 경량 분산 락을 비교하고 선택 기준을 정리한다."
---

Spring Boot 애플리케이션에 `@Scheduled(cron = "0 0 3 * * *")`로 새벽 3시 정산 배치를 붙여두고 인스턴스를 1대에서 3대로 스케일아웃하면, 그 배치는 하루아침에 세 번 실행되는 잡이 된다. `@Scheduled`는 애플리케이션 컨텍스트 안의 로컬 스레드 스케줄러일 뿐이라 인스턴스 간에 아무런 조율이 없기 때문이다. 멱등성이 보장된 조회성 배치라면 중복 실행이 큰 문제가 아니지만, 정산·알림 발송·리포트 메일처럼 부작용이 있는 배치는 중복 실행 자체가 장애다.

이 문제를 푸는 접근은 크게 두 갈래다. 스케줄링 자체를 클러스터 인식 구조로 다시 설계하는 **Quartz 클러스터 모드**, 그리고 기존 `@Scheduled` 코드는 그대로 두고 그 실행 앞뒤에 분산 락만 얇게 씌우는 **ShedLock**. 이 글은 두 접근의 동작 원리 차이와 각각이 맞는 상황을 정리한다.

## 핵심 개념 1: Quartz 클러스터 모드 — 스케줄러 자체가 분산을 안다

Quartz는 원래부터 클러스터 환경을 염두에 두고 설계된 엔터프라이즈 스케줄링 프레임워크다. 클러스터 모드에서는 모든 인스턴스가 같은 데이터베이스(JobStore)를 바라보고, 트리거가 발화할 시점이 되면 각 인스턴스가 그 잡을 획득(acquire)하려고 DB 락 경쟁을 벌인다. 락을 획득한 인스턴스만 실제로 잡을 실행하고, 나머지는 자동으로 건너뛴다. 이 메커니즘 덕분에 잡 실행 자체가 클러스터 전체에서 정확히 한 번만 일어난다는 것이 프레임워크 차원에서 보장된다.

대신 이 안정성에는 비용이 따른다. Quartz는 잡, 트리거, 실행 이력을 저장하는 전용 테이블 세트(`QRTZ_*`)를 DB에 만들어야 하고, 잡 정의를 XML이나 코드로 등록하는 방식이 `@Scheduled` 애노테이션 하나 붙이는 것보다 번거롭다. 미스파이어(misfire, 스케줄러가 다운돼 있는 동안 놓친 트리거) 처리 정책, 잡 우선순위, 잡 체이닝처럼 정교한 스케줄링 요구가 있는 조직에는 이 투자가 값어치를 하지만, 단순히 "중복 실행만 막고 싶다"는 요구에는 과할 수 있다.

## 핵심 개념 2: ShedLock — 기존 스케줄러에 분산 락만 얹는다

ShedLock은 접근 자체가 다르다. 스케줄러를 대체하지 않고, 이미 쓰고 있는 `@Scheduled` 메서드 위에 `@SchedulerLock` 애노테이션 하나를 추가하는 방식으로 동작한다. 내부적으로는 각 인스턴스가 여전히 독립적으로 크론 스케줄에 따라 메서드를 호출하려 시도하지만, 실제 실행 직전에 공유 저장소(DB 테이블, Redis, MongoDB 등)에서 락을 획득하는 시도를 하고, 락을 얻은 인스턴스만 실제 로직을 실행한 뒤 락을 해제한다. 나머지 인스턴스는 락 획득에 실패하면 그냥 아무것도 안 하고 넘어간다.

| 구분 | Quartz 클러스터 모드 | ShedLock |
|---|---|---|
| 접근 방식 | 스케줄러 자체를 클러스터 인식으로 교체 | 기존 스케줄러 위에 락만 추가 |
| 기존 코드 변경 | 잡을 Quartz Job 형태로 재작성 | 애노테이션 한 줄 추가 |
| 필요 인프라 | 전용 QRTZ_* 테이블 세트 | 락용 테이블/컬렉션 하나 |
| 미스파이어 처리 | 프레임워크가 정책 제공 | 앱에서 별도 처리 필요 |
| 적합한 상황 | 복잡한 잡 체이닝·우선순위·이력 관리 | 단순 중복 실행 방지가 목적 |

## 핵심 개념 3: 락 획득 실패는 대기가 아니라 스킵이다

두 방식 모두에서 반드시 이해해야 할 공통점이 있다. 락을 획득하지 못한 인스턴스는 "락이 풀릴 때까지 기다렸다가 실행"하는 게 아니라 **그 회차 실행 자체를 건너뛴다**는 점이다. 이는 일반적인 상호 배제 락(뮤텍스)과는 다른 의미론이다 — 스케줄링 락의 목적은 "여러 인스턴스가 순서대로 다 실행하게 하는 것"이 아니라 "여러 인스턴스 중 정확히 하나만 이번 회차를 실행하게 하는 것"이기 때문이다. ShedLock에서는 `lockAtLeastFor`(락을 최소 이 시간 동안은 유지, 실행이 너무 빨리 끝나 다른 인스턴스가 곧바로 재획득하는 것을 방지)와 `lockAtMostFor`(락을 쥔 인스턴스가 죽었을 때 락이 영원히 안 풀리는 것을 막는 안전장치)라는 두 파라미터로 이 시간 창을 명시적으로 설정해야 한다.

<img src="/assets/images/posts/2026-08-30-job-scheduling-quartz-shedlock-1.svg" alt="세 개의 애플리케이션 인스턴스가 같은 크론 스케줄로 스케줄러를 호출하지만 공유 락 저장소에서 하나의 인스턴스만 락을 획득해 실제 작업을 실행하고 나머지는 건너뛰는 ShedLock 동작 흐름도" style="width:100%;">

## 예제: ShedLock 설정과 lockAtMostFor 안전장치

```java
// SchedulerConfig.java — JDBC 기반 락 프로바이더 등록
@Configuration
@EnableScheduling
@EnableSchedulerLock(defaultLockAtMostFor = "10m")
public class SchedulerConfig {

    @Bean
    public LockProvider lockProvider(DataSource dataSource) {
        return new JdbcTemplateLockProvider(
                JdbcTemplateLockProvider.Configuration.builder()
                        .withJdbcTemplate(new JdbcTemplate(dataSource))
                        .usingDbTime() // 인스턴스 간 시계 오차 영향 제거
                        .build());
    }
}
```

```java
// SettlementJob.java — 중복 실행 방지가 필요한 배치에 락 적용
@Component
@RequiredArgsConstructor
public class SettlementJob {

    private final SettlementService settlementService;

    @Scheduled(cron = "0 0 3 * * *")
    @SchedulerLock(
        name = "dailySettlement",
        lockAtLeastFor = "5m",   // 실행이 빨리 끝나도 최소 5분은 락 유지
        lockAtMostFor = "30m"    // 인스턴스 다운 시 30분 후 자동 해제
    )
    public void runDailySettlement() {
        // 락을 획득한 단 하나의 인스턴스만 이 블록을 실행한다
        settlementService.processDailySettlement();
    }
}
```

```sql
-- ShedLock이 요구하는 락 테이블 (JDBC 프로바이더 사용 시)
CREATE TABLE shedlock (
    name       VARCHAR(64)  NOT NULL PRIMARY KEY,
    lock_until TIMESTAMP(3) NOT NULL,
    locked_at  TIMESTAMP(3) NOT NULL,
    locked_by  VARCHAR(255) NOT NULL
);
```

## 실무 포인트

- **`lockAtMostFor`는 실제 작업 소요 시간보다 넉넉히 잡아야 한다.** 이 값을 실제 작업 시간보다 짧게 설정하면, 아직 작업이 끝나지 않았는데 락이 만료돼 다른 인스턴스가 같은 작업을 동시에 시작하는 최악의 상황이 생긴다. 작업 소요 시간의 최대치를 실측한 뒤 여유를 더해 설정해야 한다.
- **`usingDbTime()`으로 인스턴스 간 시계 오차를 제거하라.** 락 만료 판정을 각 인스턴스의 로컬 시계로 하면, 인스턴스 간 시계가 몇 초라도 어긋날 때 락 판정이 꼬일 수 있다. DB 서버의 시각을 기준으로 삼는 옵션을 켜두면 이 문제를 원천적으로 없앤다.
- **락 저장소 자체가 단일 장애점이 되지 않게 하라.** ShedLock의 락 테이블이 있는 DB가 다운되면 모든 스케줄 작업이 락 획득 실패로 전부 스킵될 수 있다. 락 저장소로 이미 고가용성이 확보된 인프라(운영 중인 메인 DB, 관리형 Redis 클러스터)를 재사용하는 것이 별도 인프라를 새로 구축하는 것보다 실무적으로 안전하다.

## 3줄 요약

- `@Scheduled`는 인스턴스별 로컬 스케줄러라서 스케일아웃하면 부작용이 있는 배치가 중복 실행되며, 이를 막으려면 클러스터 인식 스케줄러(Quartz)나 기존 스케줄러 위의 분산 락(ShedLock) 중 하나가 필요하다.
- Quartz 클러스터 모드는 스케줄링 자체를 프레임워크 차원에서 안전하게 만들지만 전용 인프라와 재작성 비용이 크고, ShedLock은 기존 코드에 애노테이션만 추가해 단순 중복 실행 방지 목적에 가볍게 대응한다.
- 락 획득 실패는 대기가 아니라 스킵을 의미하며, `lockAtLeastFor`와 `lockAtMostFor`를 실제 작업 시간과 인스턴스 장애 가능성을 고려해 신중히 설정해야 한다.

## 참고 자료

- [ShedLock 공식 GitHub](https://github.com/lukas-krecan/ShedLock)
- [Quartz Scheduler 공식 문서: Clustering](https://www.quartz-scheduler.org/documentation/quartz-2.3.0/configuration/ConfigJDBCJobStoreClustering.html)
- [Spring Framework 공식 문서: Task Execution and Scheduling](https://docs.spring.io/spring-framework/reference/integration/scheduling.html)
