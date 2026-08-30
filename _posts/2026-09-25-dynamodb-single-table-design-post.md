---
layout: single
title: "DynamoDB 싱글 테이블 설계 — 관계형 사고를 버리고 접근 패턴으로 모델링하기"
date: 2026-09-25 13:35:00 +0530
categories: database
tags: ["DynamoDB", "싱글테이블설계", "NoSQL모델링", "접근패턴", "GSI"]
toc: true
toc_sticky: true
excerpt: "RDB처럼 엔티티마다 테이블을 나눠 DynamoDB를 설계했다가 조회 한 번에 여러 테이블을 오가며 비용과 지연이 폭발하는 문제를, 서로 다른 엔티티를 의도적으로 한 테이블에 몰아넣는 싱글 테이블 설계로 해결하는 원리를 정리했다."
---

## 왜 지금 싱글 테이블 설계를 다시 봐야 하는가

DynamoDB를 처음 접하는 팀은 대개 RDB에서 하던 대로 `Users`, `Orders`, `Products`처럼 엔티티마다 별도 테이블을 만든다. 문제는 DynamoDB에 JOIN이 없다는 것이다. "이 주문에 포함된 상품 정보까지 함께" 같은 조회가 필요해지는 순간, 애플리케이션 코드에서 여러 테이블에 여러 번 요청을 보내고 그 결과를 직접 조립해야 한다. 요청이 늘어날수록 지연시간과 비용(RCU/WCU)이 함께 늘어나는 구조다. 싱글 테이블 설계는 이 문제를 정반대 방향에서 접근한다 — 서로 다른 종류의 엔티티를 의도적으로 하나의 테이블에 함께 저장해, 관련된 데이터를 한 번의 쿼리로 몰아서 가져올 수 있게 만드는 것이다. 이는 "정규화를 깨는 나쁜 설계"가 아니라, DynamoDB가 원래 그렇게 쓰이도록 설계된 파티션 키·정렬 키 기반 접근 방식에 맞춘 정공법이다.

## 핵심 개념 1 — 스키마가 아니라 접근 패턴부터 설계한다

RDB 설계는 보통 데이터 구조(정규화된 엔티티 관계)를 먼저 정의하고, 쿼리는 나중에 그 구조 위에서 자유롭게 짠다. DynamoDB 싱글 테이블 설계는 순서가 반대다. "이 애플리케이션이 실제로 어떤 조회를 얼마나 자주 하는가"를 먼저 전부 나열한 뒤(예: "고객 ID로 그 고객의 모든 주문 조회", "주문 ID로 주문과 배송 상태 함께 조회"), 그 접근 패턴들을 파티션 키(PK)와 정렬 키(SK) 설계 하나로 전부 커버할 수 있도록 데이터를 배치한다. 이 접근 방식에서는 나중에 예상 못 한 새로운 조회 패턴이 추가되면 테이블 구조 자체를 다시 설계해야 할 수도 있다는 것을 의미하며, 이것이 DynamoDB 도입 전에 접근 패턴을 최대한 철저히 뽑아내야 하는 이유다.

## 핵심 개념 2 — 오버로딩된 키와 GSI로 여러 엔티티·관계를 한 테이블에

싱글 테이블 설계의 핵심 기법은 PK와 SK를 "고정된 의미의 컬럼"이 아니라 "여러 엔티티 타입이 공유하는 범용 문자열 필드"로 오버로딩하는 것이다. 예를 들어 고객 정보는 `PK=CUSTOMER#123, SK=CUSTOMER#123`으로, 그 고객의 주문들은 `PK=CUSTOMER#123, SK=ORDER#456`, `PK=CUSTOMER#123, SK=ORDER#789`로 저장한다. 이렇게 하면 `PK=CUSTOMER#123`으로 한 번의 Query 요청만 보내도 그 고객 정보와 모든 주문을 정렬 키 순서대로 한꺼번에 받아올 수 있다. 반대 방향의 조회(예: "이 주문이 어느 배송 상태인지 주문 ID로 바로 찾기")를 위해서는 Global Secondary Index(GSI)를 추가해, GSI의 파티션 키를 `ORDER#456`처럼 다른 접근 경로로 재배치한다. 결국 하나의 물리적 아이템(행)이 기본 테이블에서는 "이 고객의 주문 목록"의 일부로, GSI에서는 "이 주문 ID로 직접 조회"의 대상으로 동시에 두 가지 역할을 하게 된다.

| 항목 | RDB 다중 테이블 | DynamoDB 싱글 테이블 |
|---|---|---|
| 설계 시작점 | 엔티티 관계(정규화) | 접근 패턴(쿼리) 목록 |
| 관계 조회 | JOIN으로 실행 시점에 결합 | PK/SK 설계로 저장 시점에 미리 결합 |
| 새 쿼리 패턴 추가 | 대체로 유연(SQL로 즉석 대응) | 기존 키 설계로 못 커버하면 재설계 필요 |
| 대표 조회 수단 | JOIN, 서브쿼리 | Query(PK 지정) + GSI |

## 예제 — 고객·주문을 한 테이블에 오버로딩

```python
import boto3
table = boto3.resource('dynamodb').Table('AppTable')

# 고객 프로필 저장
table.put_item(Item={
    'PK': 'CUSTOMER#123', 'SK': 'CUSTOMER#123',
    'type': 'Customer', 'name': '김민준', 'email': 'minjun@example.com'
})

# 그 고객의 주문 저장 — 같은 PK, 다른 SK
table.put_item(Item={
    'PK': 'CUSTOMER#123', 'SK': 'ORDER#456',
    'type': 'Order', 'status': 'SHIPPED', 'total': 45000,
    'GSI1PK': 'ORDER#456', 'GSI1SK': 'ORDER#456'  # 주문 ID로 직접 조회용
})

# 한 번의 Query로 고객 정보 + 모든 주문을 정렬 키 순서로 함께 조회
response = table.query(
    KeyConditionExpression='PK = :pk',
    ExpressionAttributeValues={':pk': 'CUSTOMER#123'}
)
```

## 실무 포인트

- **모든 워크로드에 싱글 테이블 설계가 정답은 아니다.** 접근 패턴이 자주 바뀌는 초기 단계의 서비스이거나, 분석·임시 쿼리가 잦은 워크로드라면 오히려 여러 테이블로 나누고 필요시 RDB나 별도 분석 스토리지를 병행하는 것이 유연하다. Rick Houlihan의 강연에서 강조되듯, 이는 "성숙하고 접근 패턴이 안정된 고트래픽 서비스"에 특히 유리한 기법이다.
- **엔티티 타입을 구분하는 `type` 속성과 일관된 키 네이밍 규칙(`ENTITY#id`)을 처음부터 강제하라.** 시간이 지나 여러 개발자가 참여하면 이 규칙이 흐트러지기 쉬운데, 규칙이 깨지면 싱글 테이블의 장점인 예측 가능한 쿼리가 무너진다.
- **GSI 개수와 프로젝션(어떤 속성을 GSI에 복제할지) 설계는 비용에 직접 영향을 준다.** 필요 이상으로 많은 속성을 GSI에 프로젝션하면 쓰기 비용이 늘어나므로, 실제 그 GSI로 조회할 때 필요한 속성만 최소한으로 선택해야 한다.

## 마무리 요약

- DynamoDB 싱글 테이블 설계는 JOIN이 없는 제약을 받아들이고, 관련 엔티티를 같은 파티션에 미리 배치해 한 번의 Query로 가져오는 방식으로 접근 비용을 줄인다.
- 설계는 데이터 구조가 아니라 애플리케이션의 실제 접근 패턴 목록에서 출발하며, PK/SK를 여러 엔티티 타입이 공유하는 범용 필드로 오버로딩하고 GSI로 역방향 조회를 지원한다.
- 접근 패턴이 안정된 고트래픽 서비스에 유리한 기법이며, 패턴이 자주 바뀌는 초기 서비스나 분석 워크로드에는 오히려 유연성을 해칠 수 있다.

## 참고 자료

- [AWS 공식 문서 - Best Practices for Designing and Using Partition Keys Effectively](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html)
- [AWS re:Invent - Advanced Design Patterns for DynamoDB (Rick Houlihan)](https://www.youtube.com/watch?v=6yqfmXiZTlM)
