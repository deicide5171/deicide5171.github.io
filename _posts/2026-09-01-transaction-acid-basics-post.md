---
layout: single
title: "트랜잭션이 뭔가요 — ACID 개념부터 예제까지"
date: 2026-09-01 12:35:00 +0530
categories: database
tags: ["트랜잭션", "acid", "데이터베이스기초", "입문", "sql"]
toc: true
toc_sticky: true
excerpt: "데이터베이스를 배우면 가장 먼저 나오는 트랜잭션과 ACID가 무엇을 보장하는 개념인지, 계좌 이체 예제로 처음부터 정리했다."
---

## 왜 이체 도중 서버가 죽으면 돈이 사라지면 안 되는가

계좌 이체는 "A 계좌에서 빼고, B 계좌에 더한다"는 두 개의 작업으로 이뤄진다. 만약 A에서 돈을 뺀 직후 서버가 죽어버리면 B는 돈을 못 받았는데 A의 돈만 사라지는 사고가 난다. **트랜잭션(transaction)**은 여러 작업을 "전부 성공하거나 전부 실패하는 하나의 단위"로 묶어 이런 사고를 막는 개념이다.

## ACID란 무엇인가

| 속성 | 의미 | 이체 예제로 보면 |
|---|---|---|
| Atomicity(원자성) | 전부 성공하거나 전부 실패 | 출금과 입금 둘 다 되거나, 둘 다 안 된다 |
| Consistency(일관성) | 트랜잭션 전후로 데이터 규칙이 유지됨 | 이체 후에도 전체 계좌 잔액 합은 그대로다 |
| Isolation(고립성) | 동시 실행되는 트랜잭션끼리 서로 간섭하지 않음 | 다른 사람이 동시에 이체해도 잔액이 꼬이지 않는다 |
| Durability(지속성) | 커밋된 데이터는 장애가 나도 사라지지 않음 | 이체 완료 직후 정전이 나도 결과는 남아있다 |

## 코드 예제: 트랜잭션으로 묶은 이체

```sql
BEGIN;  -- 트랜잭션 시작

UPDATE accounts SET balance = balance - 10000 WHERE id = 'A';
UPDATE accounts SET balance = balance + 10000 WHERE id = 'B';

COMMIT;  -- 여기까지 문제없으면 확정
-- 중간에 오류가 나면 ROLLBACK으로 둘 다 취소
```

`BEGIN`과 `COMMIT` 사이의 두 UPDATE는 하나의 단위로 묶인다. 두 번째 UPDATE 실행 중 에러가 나면 `ROLLBACK`으로 첫 번째 UPDATE도 함께 취소해야 A의 잔액만 줄어드는 사고를 막을 수 있다.

## 애플리케이션 코드에서의 트랜잭션

```java
@Transactional
public void transfer(String fromId, String toId, BigDecimal amount) {
    Account from = accountRepository.findById(fromId);
    Account to = accountRepository.findById(toId);

    from.withdraw(amount);
    to.deposit(amount);
    // 메서드가 예외 없이 끝나면 자동 커밋, 예외 발생 시 자동 롤백
}
```

Spring의 `@Transactional`처럼 대부분의 프레임워크는 메서드 단위로 트랜잭션 경계를 선언적으로 지정할 수 있게 해준다.

## 실무 포인트

- **트랜잭션이 너무 길면 락을 오래 잡고 있어 다른 요청이 대기하게 된다.** 외부 API 호출처럼 느린 작업을 트랜잭션 안에 넣지 않는 것이 기본 원칙이다.
- **`@Transactional`을 붙였다고 항상 동작하는 것은 아니다.** 같은 클래스 내부에서 메서드를 직접 호출(self-invocation)하면 프록시를 거치지 않아 트랜잭션이 적용되지 않는 흔한 함정이 있다.
- **격리 수준(Isolation Level)에 따라 동시성 문제를 어디까지 허용할지가 달라진다.** 기본값을 그대로 쓰기보다, 어떤 이상 현상(더티 리드, 반복 불가능한 읽기 등)을 막아야 하는지 먼저 파악하는 것이 좋다.

## 마무리 요약

- 트랜잭션은 여러 작업을 하나의 성공/실패 단위로 묶어 데이터 일관성을 지키는 개념이다.
- ACID(원자성·일관성·고립성·지속성)는 트랜잭션이 지켜야 할 네 가지 성질이다.
- 트랜잭션은 짧게 유지하고, 느린 외부 호출은 트랜잭션 밖으로 빼는 것이 기본 원칙이다.

## 참고 자료

- [PostgreSQL 공식 문서 - 트랜잭션](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [Spring 공식 문서 - @Transactional](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html)
