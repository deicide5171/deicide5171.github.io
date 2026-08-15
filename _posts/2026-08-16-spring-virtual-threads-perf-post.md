---
layout: single
title: "Virtual Threads, 진짜 빠를까? Spring Boot 3.x 부하테스트로 확인한 성능 승부처"
date: 2026-08-16 12:25:00 +0530
categories: backend
tags: ["spring-boot", "virtual-threads", "java", "performance", "benchmark", "concurrency"]
toc: true
toc_sticky: true
excerpt: "Virtual Threads 도입 여부를 논하는 글은 많지만 정작 어떤 조건에서 얼마나 빨라지는지 벤치마크로 확인한 글은 드물다. 벤치마크 설계 변수, 시나리오별 예상 성능 특성, JMH 코드 예제로 성능 비교의 실전 감각을 정리한다."
---

## 왜 지금 "성능 비교"가 필요한가

Spring Boot 3.2부터 Virtual Threads가 정식 지원되기 시작한 뒤, "도입해도 되는가"를 다루는 글은 많이 쌓였다. 하지만 도입을 결정하려면 "우리 트래픽 패턴에서 얼마나 개선되는가"에 숫자로 답해야 한다. Virtual Threads의 효과는 **워크로드 특성에 따라 극단적으로 달라진다**. I/O 대기가 대부분인 API에서는 체감할 만큼 개선되지만, CPU 연산이 많은 배치 작업에서는 거의 차이가 없거나 오히려 오버헤드만 늘 수 있다.

이 글은 도입 여부 판단이 아니라 **어떤 조건을 통제해야 신뢰할 수 있는 벤치마크가 나오는지**, **시나리오별로 어떤 방향의 결과를 기대해야 하는지**에 초점을 맞춘다. Spring Boot 마이너 버전을 거치며 HikariCP·JDBC 드라이버 등 생태계 라이브러리의 pinning 대응도 점차 개선되는 추세라, 결과는 사용하는 라이브러리 버전에 따라서도 달라질 수 있다.

## 벤치마크를 설계할 때 통제해야 할 변수

성능 비교가 의미 있으려면 아래 변수들을 양쪽 실행에서 동일하게 맞춰야 한다. 하나라도 어긋나면 "가상 스레드가 이겼다/졌다"는 결론 자체가 무의미해진다.

| 변수 | 왜 중요한가 |
|---|---|
| 동시 요청 수(concurrency) | 낮은 동시성에서는 두 방식 차이가 거의 드러나지 않는다 |
| I/O 대기시간 비율 | 요청 처리 시간 중 블로킹 I/O가 차지하는 비중이 커질수록 가상 스레드가 유리해진다 |
| 플랫폼 스레드 풀 크기 | 비교 대상 플랫폼 스레드 풀이 너무 작거나 크면 불공정한 비교가 된다 |
| 워밍업(warm-up) | JIT 컴파일이 끝나기 전 측정값은 왜곡되므로 충분한 워밍업 후 측정해야 한다 |
| 커넥션 풀·외부 자원 한도 | DB 커넥션 풀처럼 여전히 유한한 자원이 있으면 그쪽이 먼저 병목이 되어 스레드 모델 차이가 가려진다 |

## 구조 차이가 결과에 어떻게 반영되는가

플랫폼 스레드는 OS 스레드 1:1로 매핑되고 스레드마다 수 MB 단위 스택을 점유해, 동시 처리량이 스레드 풀 크기에 비례해 상한이 생긴다. 가상 스레드는 소수의 **캐리어 스레드** 위에서 스케줄링되다가 블로킹 I/O를 만나면 캐리어를 반납하고, 그 자리를 다른 요청이 이어받는다. 개별 가상 스레드의 메모리 점유가 수백 바이트대로 가벼워 수만 개를 동시에 띄우는 것이 실용적이다.

<img src="/assets/images/posts/2026-08-16-spring-virtual-threads-perf-1.svg" alt="플랫폼 스레드 풀과 가상 스레드+캐리어 스레드 구조 비교, 부하 증가 시 병목 지점 차이" style="width:100%;">

이 구조 차이는 벤치마크에서 아래와 같은 방향성으로 나타나는 경우가 많다. 정확한 수치는 하드웨어·JDK 버전·라이브러리 조합에 따라 달라지므로 자체 환경에서 반드시 재현·측정해야 한다.

| 시나리오 | 예상되는 경향 |
|---|---|
| I/O 대기 비율 높음(외부 API 호출, 느린 DB 쿼리) + 높은 동시성 | 가상 스레드 쪽 처리량 우위가 뚜렷해지는 경향 |
| I/O 대기 비율 낮음(캐시 히트 위주) + 낮은 동시성 | 두 방식 차이가 거의 없거나 오차 범위 수준 |
| CPU 바운드 연산 위주(암복호화, 이미지 처리 등) | 가상 스레드가 연산 자체를 빠르게 하지 않으므로 유의미한 개선 없음 |
| DB 커넥션 풀이 요청 수보다 훨씬 작은 혼합 시나리오 | 커넥션 풀 대기가 먼저 병목이 되어 가상 스레드 효과가 가려짐 |

## 예제: JMH로 두 실행 모델의 처리량 비교하기

아래는 동일한 블로킹 작업(`Thread.sleep`로 I/O 대기를 흉내)을 플랫폼 스레드 풀과 가상 스레드 실행기로 각각 처리시켜 처리량을 비교하는 최소 예제다. 실제 측정에는 JMH 같은 도구로 워밍업·반복 횟수를 통제하는 것이 바람직하다.

```java
public class ThreadModelBenchmark {

    static final int TASK_COUNT = 10_000;
    static final int SIMULATED_IO_MS = 50;

    public static void main(String[] args) throws InterruptedException {
        long platform = run(Executors.newFixedThreadPool(200));
        long virtual = run(Executors.newVirtualThreadPerTaskExecutor());
        System.out.printf("플랫폼 스레드 풀(200개): %dms%n", platform);
        System.out.printf("가상 스레드: %dms%n", virtual);
    }

    static long run(ExecutorService executor) throws InterruptedException {
        long start = System.currentTimeMillis();
        try (executor) {
            var latch = new CountDownLatch(TASK_COUNT);
            for (int i = 0; i < TASK_COUNT; i++) {
                executor.submit(() -> {
                    try {
                        Thread.sleep(SIMULATED_IO_MS); // 블로킹 I/O 흉내
                    } catch (InterruptedException ignored) {
                    } finally {
                        latch.countDown();
                    }
                });
            }
            latch.await();
        }
        return System.currentTimeMillis() - start;
    }
}
```

동시 작업 수(`TASK_COUNT`)와 대기시간(`SIMULATED_IO_MS`)을 바꿔가며 실행해보면, 풀 크기가 동시 작업 수보다 훨씬 작을 때 차이가 벌어지고, 동시 작업 수가 풀 크기보다 작을 때는 차이가 거의 없다는 경향을 직접 확인할 수 있다.

## 실무 포인트

- **불공정한 비교를 피한다**: 플랫폼 스레드 풀 크기를 기본값 그대로 둔 채 비교하면 가상 스레드가 항상 이기는 것처럼 보인다. 실제 운영 설정과 동일한 크기로 맞춰야 한다.
- **워밍업 없이 1회 측정하지 않는다**: JIT 컴파일·클래스 로딩 비용이 섞이면 첫 실행이 유독 느리게 나온다. JMH의 `@Warmup`, `@Measurement`로 이를 분리한다.
- **API 레벨도 함께 확인한다**: JMH는 마이크로벤치마크용이고, 실제 서비스 시나리오는 k6·Gatling·wrk로 엔드포인트 단위 처리량·지연시간(p50/p95/p99)을 함께 봐야 한다.
- **외부 자원 한도를 모니터링한다**: DB 커넥션 풀이나 외부 API rate limit이 더 좁은 병목이면 개선 폭이 기대만큼 나오지 않는다.
- **pinning 여부를 벤치마크에 포함한다**: `synchronized` 블록 안 블로킹은 캐리어 스레드를 점유해 가상 스레드의 이점을 없앤다. 대상 코드에 이런 지점이 있는지 사전에 점검한다.

## 3줄 요약

- Virtual Threads의 성능 개선 폭은 I/O 대기 비율과 동시 요청 수에 크게 좌우되며, CPU 바운드 작업에서는 유의미한 차이가 없다.
- 신뢰할 수 있는 벤치마크는 플랫폼 스레드 풀 크기, 워밍업, 커넥션 풀 한도 같은 변수를 동일하게 통제해야 하며, 확인되지 않은 수치를 그대로 단정해서는 안 된다.
- JMH로 마이크로벤치마크를, k6·Gatling 같은 도구로 API 레벨 부하테스트를 병행해 자신의 서비스 워크로드에서 직접 재현해보는 것이 유일하게 신뢰할 수 있는 방법이다.

## 참고 자료

- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444)
- [JEP 425: Virtual Threads (Preview)](https://openjdk.org/jeps/425)
- [Spring Boot Reference — Task Execution and Scheduling (Virtual Threads)](https://docs.spring.io/spring-boot/reference/features/task-execution-and-scheduling.html)
- [JMH (Java Microbenchmark Harness) 공식 문서](https://github.com/openjdk/jmh)
