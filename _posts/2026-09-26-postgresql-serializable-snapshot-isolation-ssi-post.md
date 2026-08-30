---
layout: single
title: "PostgreSQL Serializable Snapshot Isolation — Predicate Lock으로 진짜 직렬성 잡아내기"
date: 2026-09-26 12:35:00 +0530
categories: database
tags: ["PostgreSQL", "SSI", "직렬화가능격리", "PredicateLock", "동시성제어"]
toc: true
toc_sticky: true
excerpt: "REPEATABLE READ로도 잡히지 않는 write skew 이상현상이 재고 관리·예약 시스템에서 실제 데이터 오류로 이어지는 문제를, PostgreSQL이 Serializable 격리수준에서 실제로 무엇을 추가로 검사하는지 SIREAD 예측 락 메커니즘으로 정리했다."
---

## 왜 지금 SERIALIZABLE을 다시 봐야 하는가

REPEATABLE READ(PostgreSQL 기준 스냅샷 격리)는 대부분의 이상현상을 막아주지만, write skew라 부르는 특정 패턴은 여전히 통과시킨다. 병원 당직 시스템을 예로 들면, 규칙이 "최소 1명은 당직을 서야 한다"일 때 당직 의사 두 명이 동시에 "다른 한 명이 남아있으니 나는 빠져도 된다"고 각자 트랜잭션에서 확인하고 둘 다 당직을 취소하면, 각 트랜잭션은 자기 스냅샷 안에서는 완벽하게 정합적으로 보였지만 결과적으로 당직자가 0명이 되는 상황이 발생한다. 두 트랜잭션이 서로 다른 행을 쓰기 때문에 락 기반의 단순 충돌 감지로는 잡히지 않는다. PostgreSQL 9.1부터 도입된 진짜 SERIALIZABLE 격리수준은 이런 패턴까지 잡아내기 위해 스냅샷 격리 위에 추가 감시 계층을 얹은 것이다.

## 핵심 개념 1 — SIREAD 락은 잠그지 않는다

일반적인 락은 다른 트랜잭션의 접근을 차단하지만, PostgreSQL의 SSI(Serializable Snapshot Isolation)가 사용하는 SIREAD 락(predicate lock)은 실제로 아무것도 차단하지 않는다. 이는 순전히 "이 트랜잭션이 이 조건(predicate)으로 이 데이터를 읽었다"는 기록일 뿐이다. 트랜잭션이 커밋을 시도할 때, PostgreSQL은 이 읽기 기록들을 모아 위험한 구조(dangerous structure)가 형성됐는지 검사한다. 구체적으로는 세 개의 동시 실행 트랜잭션 사이에 "T1이 읽은 것을 T2가 쓰고, T2가 읽은 것을 T3이 쓰는" 형태의 상호 의존 사이클(rw-antidependency 두 개가 연쇄된 형태)이 발견되면, 그 순간 나중에 커밋을 시도하는 트랜잭션이 직렬화 실패 오류로 롤백된다.

## 핵심 개념 2 — 2단계 락(2PL)과 무엇이 다른가

전통적인 직렬성 보장 방식인 Strict 2-Phase Locking은 읽기·쓰기 시점에 실제로 락을 걸어 충돌하는 트랜잭션을 대기시킨다. 반대로 SSI는 스냅샷 격리처럼 낙관적으로 모두 진행시킨 뒤, 커밋 시점에만 사후적으로 위험 패턴을 검사하는 낙관적 동시성 제어다. 이 차이 덕분에 SSI는 순수 읽기 트랜잭션 사이에서는 어떤 대기도 발생시키지 않고, 실제 쓰기 충돌이 있는 소수의 트랜잭션 조합에서만 롤백 비용을 지불한다. 대신 트래픽이 몰리면 재시도 로직이 필수라는 실무 부담이 따른다 — SERIALIZABLE 격리수준에서는 애플리케이션이 "40001 serialization_failure" 오류를 받으면 반드시 트랜잭션을 처음부터 재시도해야 한다.

| 격리수준/기법 | write skew 방지 | 차단 방식 | 실무 부담 |
|---|---|---|---|
| REPEATABLE READ(스냅샷 격리) | 방지 못함 | 없음(낙관적) | write skew 이상현상 잔존 |
| Strict 2PL | 방지함 | 실제 락으로 대기 | 대기·데드락 관리 |
| SERIALIZABLE(SSI) | 방지함 | 커밋 시점 사후 검사 | 재시도 로직 필수 |

## 코드 예제 — write skew 재현과 재시도 처리

```sql
-- 두 세션이 동시에 실행: 각자 스냅샷 안에서는 "다른 한 명이 있다"고 판단
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT count(*) FROM on_call WHERE shift = 'night';  -- 결과: 2
-- 조건 만족(2명 이상)으로 판단해 자신을 제외
DELETE FROM on_call WHERE doctor_id = 101 AND shift = 'night';
COMMIT;  -- SSI가 위험 구조를 감지하면 여기서 40001 오류 발생
```

```python
# 애플리케이션 재시도 루프 (의사코드)
for attempt in range(3):
    try:
        run_transaction()
        break
    except SerializationFailure:
        if attempt == 2:
            raise
        backoff_and_retry()
```

## 실무 포인트

- **SERIALIZABLE은 무료가 아니다.** SIREAD 락 기록과 사이클 검사에 CPU·메모리 오버헤드가 있으므로, write skew 위험이 실제로 있는 트랜잭션에만 선택적으로 적용하고 나머지는 READ COMMITTED를 유지하는 것이 일반적이다.
- **재시도 로직 없이 SERIALIZABLE을 쓰면 안 된다.** 40001 오류는 버그가 아니라 정상 동작이므로, 애플리케이션 레벨에서 지수 백오프 재시도를 반드시 구현해야 한다.
- **읽기 전용 트랜잭션은 `DEFERRABLE`과 조합해 락 오버헤드를 줄일 수 있다.** `READ ONLY DEFERRABLE`로 선언하면 스냅샷을 안전한 시점까지 지연시켜 직렬화 실패 없이 일관된 읽기를 보장받을 수 있다.

## 마무리 요약

- write skew는 서로 다른 행을 쓰는 트랜잭션들이 각자 스냅샷 안에서는 정합적으로 보이지만 결과적으로 비즈니스 규칙을 깨는 이상현상으로, 일반 스냅샷 격리로는 잡히지 않는다.
- PostgreSQL의 SERIALIZABLE은 SIREAD 예측 락으로 읽기 기록을 추적하고, 커밋 시점에 위험한 의존 사이클을 검사해 사후적으로 트랜잭션을 실패시키는 낙관적 방식(SSI)으로 이를 방지한다.
- SERIALIZABLE 도입 시 재시도 로직은 선택이 아니라 필수이며, 오버헤드를 고려해 write skew 위험이 있는 트랜잭션에만 선택적으로 적용하는 것이 실무적이다.

## 참고 자료

- [PostgreSQL 공식 문서 — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [Serializable Isolation for Snapshot Databases 논문](https://drkp.net/papers/ssi-vldb12.pdf)
