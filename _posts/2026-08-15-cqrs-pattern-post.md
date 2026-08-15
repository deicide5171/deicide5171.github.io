---
layout: single
title: "CQRS, 읽기와 쓰기 모델을 분리해야 하는 순간"
date: 2026-08-15 20:40:00 +0530
categories: system-design
tags: ["CQRS", "시스템설계", "소프트웨어아키텍처", "이벤트소싱"]
toc: true
toc_sticky: true
excerpt: "명령과 조회 모델을 분리하는 CQRS가 언제 유용하고 언제 과한 설계가 되는지 정리한다."
---

## 왜 지금 CQRS 이야기인가

읽기 트래픽과 쓰기 트래픽의 패턴이 크게 다른 서비스가 늘어나면서 CQRS(Command Query Responsibility Segregation)라는 용어가 다시 자주 언급되는 것으로 보인다. 특히 마이크로서비스 구조에서 한 도메인의 데이터를 여러 형태의 조회 화면(대시보드, 검색, 리포트)으로 보여줘야 하는 상황이 늘면서, 단일 정규화된 모델 하나로 쓰기와 읽기를 모두 처리하는 방식의 한계가 두드러지고 있다.

다만 CQRS는 이벤트소싱과 함께 언급되는 경우가 많다 보니 "이벤트소싱을 써야만 CQRS를 적용할 수 있다"는 오해도 흔하다. 실제로는 두 패턴이 독립적으로 존재하며, 이벤트소싱 없이도 CQRS만 단독으로 도입하는 사례가 많다. 이번 글에서는 CQRS의 핵심 개념과, 이벤트소싱과의 관계, 그리고 언제 이 패턴이 오버엔지니어링이 되는지를 정리한다.

## CQRS 핵심 개념

| 요소 | 전통적인 CRUD 모델 | CQRS 모델 |
|---|---|---|
| 모델 수 | 읽기/쓰기 공용 단일 모델 | 명령(Command) 모델과 조회(Query) 모델 분리 |
| 데이터 형태 | 정규화된 테이블 | 쓰기 측은 정규화, 읽기 측은 비정규화된 전용 스토어 |
| 확장 전략 | 읽기/쓰기가 같은 스케일로 확장 | 읽기와 쓰기를 독립적으로 확장 가능 |
| 일관성 | 강한 일관성이 기본 | 읽기 모델은 최종적 일관성(eventual consistency)을 감수하는 경우가 많음 |
| 적합한 상황 | 단순 CRUD, 트래픽 패턴이 균등 | 읽기/쓰기 패턴이 크게 다르거나 조회 뷰가 다양한 경우 |

CQRS의 핵심은 "쓰기를 위한 모델"과 "읽기를 위한 모델"을 별개의 스키마, 심지어 별개의 저장소로 나누는 것이다. 쓰기 모델은 비즈니스 규칙과 무결성 검증에 최적화되고, 읽기 모델은 화면에 바로 뿌릴 수 있는 형태로 비정규화되어 조회 성능에 최적화된다.

## 이벤트소싱과의 관계

CQRS와 이벤트소싱은 자주 함께 등장하지만 서로 다른 문제를 해결하는 패턴이다. 이벤트소싱은 "상태 변경 이력을 이벤트 로그로 저장한다"는 데이터 저장 방식에 대한 결정이고, CQRS는 "읽기와 쓰기 모델을 나눈다"는 인터페이스/모델 구조에 대한 결정이다.

실무에서는 전통적인 RDBMS로 쓰기 모델을 구성하고, 쓰기가 발생할 때마다 도메인 이벤트나 변경분을 별도의 조회 전용 테이블(또는 검색엔진, 캐시)에 반영해 읽기 모델을 갱신하는 방식으로 CQRS만 단독 적용하는 경우가 흔하다. 이 경우 이벤트소싱 특유의 이벤트 재생(replay)이나 스냅샷 관리 같은 복잡도는 가져가지 않아도 된다.

## 예제

```sql
-- 쓰기 모델: 정규화된 주문 테이블
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- 읽기 모델: 대시보드용 비정규화 뷰 (별도 테이블 또는 문서 스토어)
CREATE TABLE order_summary_view (
    order_id UUID PRIMARY KEY,
    customer_name TEXT,
    order_date DATE,
    status_label TEXT,
    total_amount NUMERIC(12,2),
    item_count INT
);
```

```python
# 쓰기 처리 후 읽기 모델을 비동기로 갱신하는 흐름 (개념 예시)
def handle_order_placed(event):
    write_model.save(event.order)
    read_model_updater.enqueue(
        build_order_summary(event.order)  # 비정규화된 뷰 갱신
    )
```

## 실무 포인트와 주의사항

- CQRS를 도입하면 읽기 모델과 쓰기 모델 사이에 지연(propagation delay)이 생긴다. 화면에 "방금 저장한 데이터가 즉시 보이지 않는" 상황을 사용자에게 어떻게 설명할지 미리 설계해야 한다.
- 소규모 CRUD 서비스, 조회 뷰가 단순하고 트래픽이 크지 않은 경우에는 CQRS 도입이 복잡도만 늘리는 오버엔지니어링이 될 가능성이 높다.
- 읽기 모델 동기화 로직 자체가 새로운 장애 지점이 된다. 동기화 실패 시 재처리(retry)와 모니터링 전략이 필요하다.
- CQRS와 이벤트소싱을 혼동하지 말고, 두 패턴을 각각 필요한 만큼만 독립적으로 적용하는 것이 유지보수 측면에서 유리한 경우가 많다.

## 3줄 요약

- CQRS는 읽기와 쓰기 모델을 분리하는 패턴이며, 이벤트소싱과는 독립적으로 적용할 수 있다.
- 읽기 모델은 조회 성능을 위해 비정규화된 전용 스토어로 구성하는 경우가 많다.
- 트래픽 패턴이 단순하고 조회 뷰가 많지 않다면 CQRS는 과한 설계일 수 있다.

## 참고 자료

- [CQRS pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
- [CQRS - Martin Fowler](https://martinfowler.com/bliki/CQRS.html)
- [Command and Query Responsibility Segregation (CQRS) - Microsoft Learn](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/jj554200(v=pandp.10))
