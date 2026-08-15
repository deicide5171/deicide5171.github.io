---
layout: single
title: "이벤트 소싱 실전 — 상태 대신 사건을 저장한다는 것의 의미"
date: 2026-08-22 13:45:00 +0530
categories: system-design
tags: ["system-design", "event-sourcing", "cqrs", "event-store", "domain-driven-design"]
toc: true
toc_sticky: true
excerpt: "현재 상태만 덮어써서 저장하는 전통적인 방식 대신, 상태 변화를 일으킨 사건 자체를 순서대로 저장하는 이벤트 소싱의 원리와 실무 적용 시 트레이드오프를 정리한다."
---

은행 계좌 시스템을 떠올려보자. 가장 흔한 구현은 `accounts` 테이블에 `balance`라는 컬럼 하나를 두고, 입금이나 출금이 있을 때마다 그 값을 새 값으로 덮어쓰는 방식이다. 이 방식은 "현재 잔액이 얼마인가"라는 질문에는 즉시 답할 수 있지만, "왜 잔액이 이 값이 되었는가"라는 질문에는 답하지 못한다. 중간에 어떤 입출금이 있었는지, 순서가 어땠는지는 이미 덮어써져 사라진 뒤이기 때문이다. 감사 로그를 별도 테이블에 남기는 임시방편으로 이 문제를 메우는 경우가 많지만, 그 로그는 어디까지나 부가 정보일 뿐 애플리케이션이 실제로 신뢰하는 데이터는 아니다.

이벤트 소싱(event sourcing)은 이 문제를 반대 방향에서 접근한다. 상태 자체를 저장하는 대신, 상태를 변화시킨 사건(이벤트)을 발생한 순서대로 저장하는 것을 시스템의 진실의 원천(source of truth)으로 삼는다. 계좌 개설, 입금, 출금, 이체 하나하나가 각각 독립된 이벤트로 기록되고, "현재 잔액"은 이 이벤트들을 처음부터 순서대로 재생(replay)해서 계산해 낸 결과값에 지나지 않는다. 상태는 저장되는 것이 아니라 유도(derive)되는 것이라는 발상의 전환이 핵심이다.

이 개념이 CQRS(Command Query Responsibility Segregation)와 함께 자주 언급되는 이유도 여기에 있다. 이벤트 로그는 쓰기에는 매우 유리한 구조(그냥 뒤에 이어 붙이면 된다)이지만, 매번 처음부터 재생해서 조회하기에는 비효율적이다. 그래서 조회 전용의 별도 읽기 모델(read model)을 이벤트로부터 미리 만들어두고, 쓰기 경로와 읽기 경로를 분리하는 CQRS 패턴이 이벤트 소싱과 자연스럽게 짝을 이루게 된다.

## 핵심 개념 1: 이벤트 로그를 진실의 원천으로 삼는다는 것

전통적인 방식에서 데이터베이스의 각 행은 "현재 이 엔터티가 어떤 상태인가"를 나타낸다. 이벤트 소싱에서는 이 역할이 뒤바뀐다. 저장되는 단위는 상태가 아니라 `AccountOpened`, `MoneyDeposited`, `MoneyWithdrawn`처럼 과거에 실제로 벌어진 사건이며, 이 이벤트들은 한번 기록되면 수정되거나 삭제되지 않는다(append-only, immutable). 새로운 사실이 생기면 새 이벤트를 뒤에 추가할 뿐, 이미 기록된 이벤트를 고쳐 쓰는 일은 원칙적으로 없다.

이렇게 되면 "현재 상태"는 이벤트 스트림에 대한 하나의 투영(projection)에 불과해진다. 같은 이벤트 스트림으로부터 잔액뿐 아니라 월별 거래 통계, 이상 거래 탐지용 뷰 등 서로 다른 여러 투영을 만들어낼 수 있다는 점도 이 구조의 자연스러운 부산물이다. 이벤트 자체가 도메인에서 실제로 일어난 일을 표현하기 때문에, 도메인 주도 설계(DDD)에서 말하는 도메인 이벤트 개념과도 맞닿아 있다.

## 핵심 개념 2: 현재 상태를 재구성하는 방식 — 이벤트 재생과 스냅샷

가장 단순한 형태의 상태 재구성은 한 엔터티(예: 계좌 하나)에 속한 이벤트를 발생 순서대로 모두 읽어와, 초기 상태에서 시작해 이벤트를 하나씩 적용(fold/reduce)하며 최종 상태를 만드는 것이다. 이벤트 100개짜리 계좌라면 100번의 적용 연산만으로 현재 잔액을 구할 수 있으니 큰 문제가 없다.

문제는 이벤트가 수천, 수만 건으로 쌓였을 때다. 매번 조회할 때마다 처음부터 전체 이벤트를 재생하는 것은 비용이 커진다. 이를 완화하는 대표적인 방법이 스냅샷(snapshot)이다. 특정 시점(예: 이벤트 1000번째)까지 재생한 상태를 별도로 저장해두고, 다음 조회부터는 이 스냅샷을 불러온 뒤 그 이후에 쌓인 이벤트만 추가로 재생하면 된다. 스냅샷은 어디까지나 캐시이며, 손상되거나 사라지더라도 이벤트 로그만 남아 있으면 처음부터 다시 만들어낼 수 있다는 점이 중요하다.

## 핵심 개념 3: 전통적 CRUD 방식과의 비교

| 구분 | 전통적 CRUD | 이벤트 소싱 |
|---|---|---|
| 저장 대상 | 엔터티의 현재 상태 | 상태를 변화시킨 이벤트 시퀀스 |
| 이력 추적 | 별도 감사 로그를 추가로 구현해야 함 | 이벤트 로그 자체가 이력 |
| 과거 시점 상태 재현 | 어려움(스냅샷/버전 관리 없이는 불가능) | 해당 시점까지 이벤트만 재생하면 자연스럽게 가능 |
| 데이터 수정 방식 | UPDATE로 이전 값을 덮어씀 | 새 이벤트를 추가(과거 이벤트는 불변) |
| 조회 성능 | 단순 조회에 유리 | 별도 읽기 모델(투영) 없이는 불리할 수 있음 |
| 구현/운영 복잡도 | 상대적으로 낮음 | 이벤트 스토어, 투영, 스키마 진화 등 추가 고려사항 필요 |

두 방식 중 어느 쪽이 절대적으로 우월한 것은 아니다. 감사·재현 가능성이 중요하지 않은 단순한 CRUD 화면이라면 전통적 방식이 훨씬 단순하고 저렴하다. 이벤트 소싱은 "무슨 일이 있었는지"가 비즈니스적으로 중요한 도메인(결제, 재고, 주문 상태 변화 등)에서 그 값어치가 드러난다.

## 예제

다음은 계좌 도메인을 예로 든 의사코드다. 이벤트를 정의하고, 이벤트 목록을 재생해 현재 잔액 상태를 재구성하는 흐름을 보여준다.

```
// 이벤트 정의 (모두 불변, 과거에 실제로 일어난 사실을 표현)
event AccountOpened { accountId, openedAt }
event MoneyDeposited { accountId, amount, occurredAt }
event MoneyWithdrawn { accountId, amount, occurredAt }

// 이벤트 재생을 통한 상태 재구성
function replay(events):
    state = { balance: 0, opened: false }

    for event in events (in order):
        match event.type:
            case "AccountOpened":
                state.opened = true
            case "MoneyDeposited":
                state.balance += event.amount
            case "MoneyWithdrawn":
                state.balance -= event.amount

    return state

// 스냅샷을 활용한 재구성 (이벤트가 많이 쌓였을 때)
function replayWithSnapshot(accountId):
    snapshot = loadLatestSnapshot(accountId)      // 없으면 null
    baseState = snapshot ? snapshot.state : { balance: 0, opened: false }
    fromVersion = snapshot ? snapshot.version + 1 : 0

    remainingEvents = loadEvents(accountId, fromVersion)
    return replay(remainingEvents, startingFrom=baseState)
```

실제 이벤트 스토어(EventStoreDB, Kafka를 이벤트 로그로 활용하는 구성, 혹은 관계형 DB 위에 직접 구현한 이벤트 테이블 등)에서는 이벤트마다 버전 번호나 시퀀스 번호를 함께 저장해 동시성 제어(낙관적 잠금)에 활용하는 경우가 많다.

## 실무 포인트

- **이벤트 스키마 진화를 처음부터 염두에 두어야 한다.** 한번 저장된 이벤트는 원칙적으로 수정하지 않으므로, 시간이 지나 이벤트 필드를 추가하거나 이름을 바꾸고 싶어질 때 과거에 저장된 옛 버전의 이벤트와 새 버전의 이벤트가 공존하게 된다. 이벤트에 버전 필드를 두고, 오래된 버전의 이벤트를 읽을 때 최신 스키마로 변환해주는 업캐스팅(upcasting) 계층을 두는 방식이 흔히 쓰인다.
- **이벤트가 많이 쌓였을 때는 스냅샷 전략을 설계해야 한다.** 몇 개의 이벤트마다 스냅샷을 찍을지(예: N개 이벤트마다, 혹은 일정 시간 간격마다)는 도메인별 이벤트 발생 빈도와 조회 성능 요구사항에 따라 달라진다. 스냅샷은 성능 최적화를 위한 파생 데이터일 뿐이므로, 스냅샷 로직에 버그가 있어도 이벤트 로그를 재생해 정합성을 다시 확인할 수 있다는 전제를 지켜야 한다.
- **도입 난이도를 과소평가해서는 안 된다.** 이벤트 소싱은 데이터 모델링, 조회 경로(CQRS 읽기 모델), 트랜잭션 경계, 팀의 사고방식까지 함께 바꿔야 하는 결정이다. 시스템 전체를 한 번에 이벤트 소싱으로 전환하기보다, 감사·이력 추적이 실제로 중요한 특정 애그리거트(aggregate)에 국한해 부분적으로 도입하고 효과를 확인한 뒤 범위를 넓히는 접근이 안전하다.

## 3줄 요약

- 이벤트 소싱은 현재 상태를 직접 저장하는 대신, 상태를 변화시킨 이벤트를 순서대로 저장하고 이를 재생해 현재 상태를 유도해내는 방식이다.
- 이벤트가 쌓일수록 매번 처음부터 재생하는 비용이 커지므로, 특정 시점까지의 상태를 스냅샷으로 캐싱해두고 그 이후 이벤트만 재생하는 전략이 함께 쓰인다.
- 감사·이력 추적이 중요한 도메인에서 강점을 발휘하지만, 스키마 진화·CQRS 읽기 모델 구축 등 추가 복잡도를 감수해야 하므로 전면 도입보다는 필요한 애그리거트에 한정해 점진적으로 적용하는 편이 안전하다.

## 참고 자료

- [Martin Fowler — Event Sourcing (bliki)](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Martin Fowler — CQRS (bliki)](https://martinfowler.com/bliki/CQRS.html)
- [EventStoreDB 공식 사이트](https://www.eventstore.com/)
- [microservices.io — Pattern: Event sourcing](https://microservices.io/patterns/data/event-sourcing.html)
- [Microsoft Azure Architecture Center — Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
