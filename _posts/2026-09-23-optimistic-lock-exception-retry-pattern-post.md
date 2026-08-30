---
layout: single
title: "OptimisticLockException이 뜰 때 — 낙관적 락 충돌 재시도 처리 실전 패턴"
date: 2026-09-23 13:35:00 +0530
categories: database
tags: ["낙관적락", "optimisticlock", "jpa", "재시도", "동시성제어"]
toc: true
toc_sticky: true
excerpt: "재고 차감이나 포인트 적립처럼 동시 수정이 잦은 로직에서 OptimisticLockException이 사용자 화면에 그대로 노출되는 문제를, 재시도 로직과 예외 처리 경계 설계로 해결하는 방법을 정리했다."
---

## 왜 가끔씩 500 에러가 뜰까

재고 차감이나 포인트 적립처럼 여러 요청이 같은 행을 동시에 수정할 가능성이 있는 로직에 `@Version` 필드로 낙관적 락을 걸어뒀는데, 트래픽이 몰리는 시간대에만 간헐적으로 500 에러 로그가 쌓인다. 로그를 열어보면 `ObjectOptimisticLockingFailureException`이 원인으로 찍혀 있다. 낙관적 락을 건 것 자체는 올바른 설계인데, 이 예외를 만났을 때 그대로 사용자에게 에러 화면을 보여주는 것이 문제다.

낙관적 락은 "충돌이 나면 예외를 던진다"까지가 라이브러리의 역할이고, "그 충돌을 어떻게 처리할지"는 애플리케이션 코드의 몫이다. 이 경계를 놓치면 실제로는 몇 밀리초 뒤 재시도하면 성공할 수 있는 일시적 충돌을, 사용자에게는 영구적인 실패처럼 보여주게 된다.

## 핵심 개념 1 — 낙관적 락 충돌은 실패가 아니라 재시도 신호다

낙관적 락은 데이터를 읽을 때 함께 읽은 버전 값을, 수정해서 저장할 때 다시 확인해 그 사이 다른 트랜잭션이 먼저 바꾸지 않았는지 검증하는 방식이다. 검증에 실패했다는 것은 데이터가 손상됐다는 뜻이 아니라, 단지 "내가 읽은 시점의 데이터가 이미 낡았다"는 뜻이다. 최신 데이터를 다시 읽어서 같은 로직을 다시 시도하면 대부분 성공한다. 그래서 이 예외는 catch해서 로그만 남기고 끝낼 것이 아니라, 정해진 횟수만큼 재시도하는 로직으로 감싸는 것이 정석이다.

<img src="/assets/images/posts/2026-09-23-optimistic-lock-exception-retry-pattern-1.svg" alt="두 트랜잭션이 같은 버전의 행을 동시에 읽고 수정을 시도할 때, 먼저 커밋한 트랜잭션은 성공하고 나중에 커밋하려는 트랜잭션은 버전 불일치로 실패해 최신 데이터를 다시 읽고 재시도하는 흐름을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 무조건 재시도하면 안 되고 트랜잭션 경계를 새로 열어야 한다

여기서 흔히 놓치는 부분이 있다. 실패한 트랜잭션 안에서 그냥 다시 같은 엔티티로 저장을 시도하면 안 된다. 이미 실패한 트랜잭션의 영속성 컨텍스트는 낡은 버전 정보를 들고 있으므로, **완전히 새로운 트랜잭션을 열어 엔티티를 다시 조회하는 것부터** 재시도해야 한다. 이 때문에 재시도 로직은 보통 트랜잭션 경계보다 한 단계 바깥, 즉 트랜잭션을 시작하는 서비스 메서드를 감싸는 형태로 구현한다.

## 예제 — Spring Retry로 재시도 로직 감싸기

```java
@Service
public class InventoryService {

    @Retryable(
        retryFor = ObjectOptimisticLockingFailureException.class,
        maxAttempts = 3,
        backoff = @Backoff(delay = 50, multiplier = 2)
    )
    @Transactional
    public void decreaseStock(Long itemId, int quantity) {
        // 매 재시도마다 새 트랜잭션으로 최신 버전을 다시 조회한다
        Item item = itemRepository.findById(itemId)
                .orElseThrow(() -> new ItemNotFoundException(itemId));

        if (item.getStock() < quantity) {
            throw new InsufficientStockException(itemId);
        }
        item.decreaseStock(quantity);  // @Version 필드가 저장 시 자동 검증됨
    }

    @Recover
    public void recover(ObjectOptimisticLockingFailureException e, Long itemId, int quantity) {
        // 재시도를 다 소진해도 실패하면 여기서 최종 처리
        throw new StockUpdateFailedException(itemId);
    }
}
```

`@Retryable`이 재시도 자체를 관리하고, 매 시도가 새로운 프록시 호출이 되도록 만들어 트랜잭션도 새로 시작된다. `@Recover`는 최대 재시도 횟수를 다 써도 실패했을 때 호출되는 최종 처리 지점으로, 이 지점에서만 사용자에게 실질적인 실패를 알려야 한다.

## 흔한 실수와 함정

| 실수 | 결과 | 대응 |
|---|---|---|
| 같은 트랜잭션 안에서 재시도 | 낡은 영속성 컨텍스트로 재시도해도 계속 실패 | 새 트랜잭션에서 엔티티 재조회부터 시작 |
| 재시도 횟수를 무제한으로 둠 | 충돌이 심한 상황에서 응답 지연 누적 | 최대 3~5회로 제한, 백오프 간격 적용 |
| 백오프 없이 즉시 재시도 | 같은 타이밍에 계속 충돌할 확률이 높음 | 지수 백오프로 재시도 간격을 점차 늘림 |
| 낙관적 락과 비관적 락을 같은 로직에 혼용 | 두 메커니즘이 서로 상쇄되며 예상 밖 동작 | 경합이 심한 부분은 처음부터 비관적 락 검토 |

마지막 항목도 실무에서 자주 헷갈린다. 재시도로 해결이 안 될 만큼 동시 요청이 극심하게 몰리는 지점(예: 선착순 이벤트의 재고 차감)이라면, 애초에 낙관적 락으로 재시도를 반복하는 것보다 `SELECT ... FOR UPDATE` 같은 비관적 락이나 Redis 원자적 연산으로 설계를 바꾸는 것이 더 적절할 수 있다.

## 실무 포인트

- **재시도 대상 예외를 정확히 지정하라.** 모든 예외를 재시도 대상으로 잡으면 재고 부족처럼 재시도해도 절대 성공할 수 없는 비즈니스 예외까지 불필요하게 반복 실행된다.
- **백오프 간격에 지터(jitter)를 섞는 것도 고려하라.** 여러 요청이 동시에 충돌했다면 정확히 같은 간격으로 재시도할 때 다시 충돌할 확률이 높아지므로, 약간의 무작위성을 섞으면 충돌 확률을 더 낮출 수 있다.
- **재시도 소진 시의 사용자 메시지를 구체적으로 설계하라.** "잠시 후 다시 시도해주세요"처럼 일시적 상황임을 알려주는 것이, 그냥 "오류가 발생했습니다"보다 사용자 경험 면에서 훨씬 낫다.

## 마무리 요약

- OptimisticLockException은 데이터 손상이 아니라 낡은 버전으로 수정을 시도했다는 신호이므로, 최신 데이터를 다시 읽어 재시도하면 대부분 해결된다.
- 재시도는 반드시 새로운 트랜잭션에서 엔티티를 재조회하는 것부터 시작해야 하며, 같은 실패한 트랜잭션 안에서 반복해서는 안 된다.
- 충돌이 극심한 구간은 재시도만으로 감당이 안 될 수 있으므로 비관적 락이나 다른 동시성 제어 방식으로의 전환도 함께 검토해야 한다.

## 참고 자료

- [Spring Retry 공식 GitHub](https://github.com/spring-projects/spring-retry)
- [Spring Data JPA 공식 문서 - Optimistic Locking](https://docs.spring.io/spring-data/jpa/reference/jpa/locking.html)
