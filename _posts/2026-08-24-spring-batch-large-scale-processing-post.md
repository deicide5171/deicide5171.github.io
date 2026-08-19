---
layout: single
title: "수천만 건을 안전하게 — Spring Batch로 설계하는 대용량 배치 처리"
date: 2026-08-24 12:25:00 +0530
categories: backend
tags: ["spring-batch", "java", "batch-processing", "chunk", "partitioning", "spring-boot"]
toc: true
toc_sticky: true
excerpt: "수천만 건 단위 데이터 처리에서 for문 기반 배치 스크립트가 무너지는 지점을 짚고, Spring Batch의 청크 모델·파티셔닝·재시작 설계로 대용량 배치를 안전하게 구성하는 법을 정리한다."
---

"매일 새벽 3시, 전체 주문 테이블을 읽어 정산 파일을 생성한다"는 요구사항을 단순 for문과 JPA로 구현하면 처음 몇 달은 문제없이 돌아간다. 그러다 데이터가 수백만 건을 넘기면 영속성 컨텍스트에 엔티티가 쌓여 메모리가 터지고, 중간에 실패하면 처음부터 다시 돌려야 하고, 어디까지 처리됐는지 추적할 방법도 없다. 대용량 배치는 일반적인 웹 요청 처리와 완전히 다른 설계 원칙을 요구한다.

Spring Batch는 이 문제를 위해 처음부터 설계된 프레임워크다. 청크 단위 처리로 메모리를 제한하고, 실패 지점부터 재시작할 수 있는 메타데이터를 자동 관리하며, 파티셔닝으로 멀티스레드·분산 처리까지 확장할 수 있다. 이 글에서는 핵심 모델과 대규모 처리에서 실제로 마주치는 설계 포인트를 정리한다.

## 핵심 개념 1: Job-Step-Chunk 모델

Spring Batch의 계층 구조는 `Job` → `Step` → (선택적으로) `Chunk`다. 하나의 `Job`은 여러 `Step`으로 구성되고, 각 `Step`은 크게 두 방식으로 구현한다.

- **Tasklet 방식**: 단순 작업(파일 이동, 임시 테이블 정리)을 한 번에 실행. 청크 개념이 없다.
- **Chunk-oriented 방식**: `ItemReader`가 하나씩 읽고, `ItemProcessor`가 변환하고, 지정한 개수(chunk size)만큼 모이면 `ItemWriter`가 한 번에 쓴다. 이 단위로 트랜잭션이 커밋된다.

청크 방식이 대용량 처리의 핵심인 이유는 메모리 사용량이 청크 크기에 비례해 고정되기 때문이다. 1000만 건을 처리하든 100건을 처리하든, 청크 크기를 100으로 두면 메모리에는 항상 최대 100건만 존재한다.

## 핵심 개념 2: 확장 전략 — 멀티스레드, 파티셔닝, 원격 청킹

단일 스레드 청크 처리로는 처리량 한계가 곧 온다. Spring Batch는 세 가지 확장 모델을 제공한다.

| 전략 | 동작 방식 | 적합한 상황 |
|---|---|---|
| Multi-threaded Step | 하나의 Step 내에서 청크 처리를 여러 스레드로 병렬화 | 스레드 안전한 Reader/Writer 확보 가능할 때 |
| Partitioning | 데이터를 범위별로 나눠 각 파티션을 별도 Step 인스턴스(워커)가 처리 | ID 범위·날짜 범위로 자연 분할 가능한 대용량 데이터 |
| Remote Chunking | Reader는 마스터에서, 처리·쓰기는 메시징을 통해 원격 워커에서 수행 | 처리 로직이 무겁고 워커를 별도로 스케일 아웃해야 할 때 |

파티셔닝이 실무에서 가장 널리 쓰이는데, `PartitionHandler`가 각 파티션의 범위(예: `id BETWEEN 1 AND 100000`)를 워커 Step에 나눠주고, 각 워커가 독립적인 트랜잭션과 재시작 상태를 갖는다.

## 예제: 파티셔닝 기반 대용량 정산 배치 (Java)

```java
@Configuration
public class SettlementBatchConfig {

    @Bean
    public Job settlementJob(JobRepository jobRepository, Step partitionStep) {
        return new JobBuilder("settlementJob", jobRepository)
                .start(partitionStep)
                .build();
    }

    @Bean
    public Step partitionStep(JobRepository jobRepository,
                               Step workerStep,
                               Partitioner rangePartitioner) {
        return new StepBuilder("partitionStep", jobRepository)
                .partitioner("workerStep", rangePartitioner)
                .step(workerStep)
                .gridSize(8) // 8개 파티션으로 분할
                .taskExecutor(new SimpleAsyncTaskExecutor("partition-"))
                .build();
    }

    @Bean
    public Step workerStep(JobRepository jobRepository,
                            PlatformTransactionManager txManager,
                            ItemReader<Order> reader,
                            ItemProcessor<Order, Settlement> processor,
                            ItemWriter<Settlement> writer) {
        return new StepBuilder("workerStep", jobRepository)
                .<Order, Settlement>chunk(500, txManager) // 청크 크기 500
                .reader(reader)
                .processor(processor)
                .writer(writer)
                .faultTolerant()
                .skip(DataIntegrityViolationException.class)
                .skipLimit(100) // 개별 레코드 오류는 100건까지 건너뛰고 계속 진행
                .build();
    }
}
```

`reader`는 `JdbcPagingItemReader`처럼 `StepExecutionContext`에 주입된 파티션 범위(`minId`, `maxId`)를 조회 조건으로 사용하도록 구성한다.

## 실무 포인트

- **재시작 가능성을 처음부터 설계에 넣는다**: `JobRepository`가 각 Step의 처리 커밋 지점을 메타데이터 테이블(`BATCH_STEP_EXECUTION` 등)에 기록하므로, 실패한 Job을 재실행하면 이미 커밋된 청크는 건너뛰고 실패 지점부터 재개된다. 단, `ItemWriter`가 멱등하지 않으면(같은 레코드를 다시 써도 안전하지 않으면) 재시작 시 중복 처리가 발생하므로 UPSERT 또는 처리 여부 플래그로 멱등성을 확보해야 한다.
- **Reader는 커서보다 페이징 방식을 기본으로 고려한다**: `JdbcCursorItemReader`는 연결을 오래 점유하고 네트워크 문제에 취약하며, 파티셔닝과의 조합에서 스레드 안전성 문제가 생기기 쉽다. `JdbcPagingItemReader`나 커서 기반이라도 파티션 단위로 독립 연결을 쓰는 구성이 안전하다.
- **skip과 retry 정책을 명확히 분리한다**: 일시적 오류(데드락, 타임아웃)는 `retry`로 재시도하고, 데이터 자체의 결함(제약 조건 위반)은 `skip`으로 건너뛰며 별도 실패 로그 테이블에 기록해야 한다. 두 정책을 뒤섞으면 진짜 데이터 문제가 재시도 루프에 묻혀 배치가 무한정 느려질 수 있다.

## 3줄 요약

- 대용량 배치는 청크 단위 처리로 메모리 사용량을 고정 크기로 제한하는 것이 출발점이며, Spring Batch의 Job-Step-Chunk 모델이 이를 기본 제공한다.
- 처리량 확장은 멀티스레드 Step, 파티셔닝, 원격 청킹 중 데이터 분할 가능성과 워커 확장 요구에 맞춰 선택하며, 파티셔닝이 가장 널리 쓰인다.
- 재시작 시 멱등성 확보, 페이징 기반 Reader, skip/retry 정책 분리가 실무에서 배치의 안정성을 좌우하는 핵심 설계 포인트다.

## 참고 자료

- [Spring Batch 공식 문서: Chunk-oriented Processing](https://docs.spring.io/spring-batch/reference/step/chunk-oriented-processing.html)
- [Spring Batch 공식 문서: Scaling and Parallel Processing](https://docs.spring.io/spring-batch/reference/scalability.html)
- [Spring Batch 공식 문서: Configuring a Step for Restart](https://docs.spring.io/spring-batch/reference/step/restart.html)
