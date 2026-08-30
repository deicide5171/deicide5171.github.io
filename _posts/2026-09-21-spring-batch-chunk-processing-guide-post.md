---
layout: single
title: "Spring Batch로 대용량 배치 작업 처리하기 — Chunk 기반 처리 입문"
date: 2026-09-21 12:25:00 +0530
categories: backend
tags: ["springbatch", "배치처리", "chunk", "대용량데이터처리", "스프링"]
toc: true
toc_sticky: true
excerpt: "매일 밤 수백만 건의 정산 데이터를 처리해야 하는 배치 작업을 for문과 스케줄러만으로 짜다가 실패 복구가 불가능해지는 문제를, Spring Batch의 Chunk 기반 처리로 해결하는 방법을 정리했다."
---

## 왜 @Scheduled와 for문만으로는 한계가 오나

"매일 자정에 그날 발생한 거래 내역을 집계해서 정산 테이블에 반영한다" 같은 배치성 작업은 처음엔 `@Scheduled` 애노테이션과 반복문으로 충분히 처리된다.

```java
@Scheduled(cron = "0 0 0 * * *")
public void settleTransactions() {
    List<Transaction> transactions = transactionRepository.findAllByDate(today());
    for (Transaction t : transactions) {
        settlementService.process(t);
    }
}
```

데이터가 수천 건일 때는 문제없이 돌아간다. 그런데 건수가 수백만 건으로 늘어나면 여러 문제가 동시에 터진다. 전체 데이터를 한 번에 메모리에 올리면 `OutOfMemoryError`가 나고, 처리 도중 서버가 재시작되면 어디까지 처리했는지 알 방법이 없어 처음부터 다시 돌려야 한다. 실패한 건만 재처리하고 싶어도 성공/실패 이력을 관리하는 로직을 직접 다 짜야 한다.

## 잘못된 접근: 재시도 로직을 직접 누더기로 짜기

이 문제를 마주친 팀은 보통 "실패하면 다시 시도하는 로직"을 직접 추가하는 식으로 대응한다.

```java
for (Transaction t : transactions) {
    int retryCount = 0;
    while (retryCount < 3) {
        try {
            settlementService.process(t);
            break;
        } catch (Exception e) {
            retryCount++;
            log.error("재시도 {}회", retryCount);
        }
    }
}
```

이 방식은 재시도는 되지만, 서버가 배치 도중 완전히 죽어버리면 여전히 "어디서부터 다시 시작해야 하는지"를 알 수 없다. 처리 상태를 어딘가에 기록해야 하는데, 이걸 매번 새 배치 작업마다 직접 설계하고 구현하는 것은 반복 노동이자 버그의 온상이 된다.

## 올바른 접근: Spring Batch의 Chunk 기반 처리

Spring Batch는 이런 배치 작업의 공통 문제(메모리 관리, 실패 복구, 진행 상태 추적)를 프레임워크 레벨에서 해결해준다. 핵심 개념은 **Chunk**다. 전체 데이터를 한 번에 처리하지 않고, 일정 크기(chunk)만큼 읽고(Read) → 가공하고(Process) → 쓰는(Write) 작업을 트랜잭션 단위로 반복한다.

```java
@Bean
public Step settlementStep(JobRepository jobRepository,
                            PlatformTransactionManager transactionManager) {
    return new StepBuilder("settlementStep", jobRepository)
        .<Transaction, Settlement>chunk(1000, transactionManager)
        .reader(transactionReader())
        .processor(settlementProcessor())
        .writer(settlementWriter())
        .faultTolerant()
        .retryLimit(3)
        .retry(TransientDataAccessException.class)
        .skipLimit(10)
        .skip(InvalidDataException.class)
        .build();
}
```

`chunk(1000, ...)`은 1000건씩 묶어 하나의 트랜잭션으로 처리한다는 뜻이다. 1000건 중 하나에서 예외가 나면 그 청크만 롤백되고, 이미 커밋된 이전 청크들은 영향을 받지 않는다. `retryLimit`과 `skipLimit`을 지정하면 일시적 오류(네트워크 타임아웃 등)는 재시도하고, 특정 건의 데이터 자체 문제는 건너뛰고 계속 진행하도록 세밀하게 제어할 수 있다.

## 진행 상태는 어떻게 추적되나

Spring Batch는 `JobRepository`라는 메타데이터 저장소(보통 DB 테이블)에 Job과 Step의 실행 이력, 처리된 건수, 마지막 커밋 지점을 자동으로 기록한다. 배치 도중 서버가 죽어도, 같은 Job을 다시 실행하면 이미 완료된 Step은 건너뛰고 실패한 지점부터 재시작할 수 있다. 이 복구 능력이 직접 짠 for문 방식과 가장 큰 차이다.

## 실무 포인트

- **Reader/Processor/Writer 책임을 명확히 분리하라.** Reader는 데이터를 읽어오는 역할만, Processor는 변환·검증만, Writer는 저장만 담당하게 하면 각 단계를 독립적으로 테스트하고 교체하기 쉬워진다.
- **JpaPagingItemReader처럼 페이징 기반 Reader를 쓸 때는 정렬 기준을 명시하라.** 정렬 기준이 없으면 페이지 경계에서 데이터가 중복되거나 누락될 수 있다.
- **재시작 가능성을 전제로 Writer를 멱등하게 설계하라.** 같은 청크가 재시도로 두 번 쓰여도 결과가 같아야 한다(upsert 방식 등).
- **Chunk 크기는 무작정 크게 잡지 마라.** 너무 크면 하나의 트랜잭션이 오래 걸리고 실패 시 롤백 비용도 커진다. 데이터 특성에 맞춰 수백~수천 단위로 실측하며 조정한다.

## 마무리 요약

- 배치 작업을 `@Scheduled`와 단순 반복문으로만 짜면 대량 데이터에서 메모리 문제와 실패 복구 불가능 문제가 동시에 터진다.
- Spring Batch의 Chunk 기반 처리는 일정 단위로 트랜잭션을 나누고, 재시도·건너뛰기 정책을 선언적으로 설정할 수 있게 해준다.
- JobRepository가 진행 상태를 자동으로 기록해, 중간에 실패해도 처음부터 다시 돌리지 않고 이어서 재시작할 수 있다.

## 참고 자료

- [Spring Batch 공식 문서 - Chunk-oriented Processing](https://docs.spring.io/spring-batch/reference/step/chunk-oriented-processing.html)
- [Spring Batch 공식 문서 - Configuring a Step](https://docs.spring.io/spring-batch/reference/step.html)
