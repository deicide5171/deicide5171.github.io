---
layout: single
title: "JSONB와 관계형의 만남 — PostgreSQL에서 반정형 데이터 다루기"
date: 2026-08-22 13:35:00 +0530
categories: database
tags: ["database", "postgresql", "jsonb", "semi-structured", "gin-index"]
toc: true
toc_sticky: true
excerpt: "스키마가 자주 바뀌는 속성 데이터를 위해 NoSQL을 따로 두는 대신, PostgreSQL의 JSONB 컬럼과 GIN 인덱스로 관계형 테이블 안에서 반정형 데이터를 다루는 방법을 정리한다."
---

이커머스 상품 테이블을 설계하다 보면 금세 한계에 부딪힌다. 의류는 사이즈와 색상이 필요하고, 전자제품은 배터리 용량과 화면 크기가 필요하며, 도서는 저자와 ISBN이 필요하다. 이 모든 속성을 각각의 컬럼으로 만들면 테이블은 대부분의 행에서 NULL로 채워진 열들로 뒤덮이고, 새 카테고리가 추가될 때마다 스키마 마이그레이션이 뒤따른다. 반대로 속성을 별도의 키-값 테이블로 정규화하면 스키마는 유연해지지만, 상품 하나를 조회할 때마다 여러 번의 조인이 필요해지고 쿼리는 점점 복잡해진다.

이런 문제 때문에 팀들은 종종 관계형 데이터베이스 옆에 문서 지향 NoSQL을 별도로 두는 선택을 한다. 하지만 이는 두 개의 데이터 저장소를 동시에 운영하고, 데이터 정합성을 신경 써야 하는 부담을 새로 만든다. PostgreSQL은 이 문제에 대해 다른 답을 제시한다. 관계형 테이블 안에 JSONB라는 타입의 컬럼을 두어, 자주 바뀌지 않는 핵심 필드는 일반 컬럼으로 두고 카테고리마다 달라지는 속성은 JSONB 하나에 담는 하이브리드 접근이다.

이 글에서는 JSON과 JSONB의 차이, GIN 인덱스가 JSONB 검색을 가속하는 원리, 그리고 언제 JSONB를 쓰고 언제 정규화된 컬럼으로 빼야 하는지에 대한 판단 기준을 정리한다.

## 핵심 개념 1: JSON vs JSONB — 저장 방식의 차이

PostgreSQL은 JSON을 저장하는 두 가지 타입을 제공한다. `json` 타입은 입력받은 텍스트를 거의 그대로 저장한다. 즉 공백이나 키의 순서, 중복된 키까지 원본 그대로 보존되며, 대신 쿼리 시점마다 텍스트를 파싱해야 한다. 반면 `jsonb` 타입은 저장할 때 이미 파싱을 마치고 이진(binary) 형태로 분해된 구조로 저장한다. 이 과정에서 공백은 제거되고 키 순서는 내부 저장 순서로 재배치되며, 동일 키가 중복되면 마지막 값만 남는다.

이 차이는 실질적인 트레이드오프로 이어진다. `json`은 입력을 저장하는 시점의 오버헤드가 거의 없지만, 값을 읽거나 특정 키를 조회할 때마다 매번 파싱 비용이 든다. `jsonb`는 저장 시점에 파싱과 이진 변환 비용이 들지만, 이후 조회와 인덱싱에서는 이 구조를 그대로 활용할 수 있어 훨씬 빠르다. 이런 이유로 PostgreSQL 공식 문서도 특별히 원본 텍스트 그대로를 보존해야 하는 경우가 아니라면 대부분의 경우 `jsonb` 사용을 권장한다.

## 핵심 개념 2: GIN 인덱스로 JSONB 내부를 검색하는 원리

일반적인 B-tree 인덱스는 컬럼 전체 값을 기준으로 정렬된 구조를 만들기 때문에, JSONB 컬럼 내부의 특정 키나 값을 찾는 데는 적합하지 않다. 이때 쓰는 것이 GIN(Generalized Inverted Index)이다. GIN은 이름 그대로 역색인 구조로, JSONB 문서 하나를 저장할 때 그 안에 등장하는 키와 값들을 추출해 각각을 색인 항목으로 만들고, 그 항목이 어떤 행에 속하는지를 매핑해둔다.

예를 들어 `{"color": "red", "size": "M"}`이라는 JSONB 값이 있다면, GIN 인덱스는 `color`, `red`, `size`, `M` 같은 개별 요소들을 색인해 나중에 `@>` 연산자로 특정 키-값 쌍을 포함하는 행을 찾을 때 전체 테이블을 스캔하지 않고 인덱스만으로 빠르게 후보 행을 좁힐 수 있게 해준다. PostgreSQL은 기본 연산자 클래스(`jsonb_ops`)와, 색인 크기는 더 작지만 존재 여부 검색(`?`, `?|`, `?&`)에는 쓸 수 없는 대신 포함 연산(`@>`)에 최적화된 `jsonb_path_ops`라는 대안을 함께 제공한다. 어떤 연산자를 주로 쓰느냐에 따라 적합한 연산자 클래스가 달라진다.

## 핵심 개념 3: JSONB를 언제 쓰고 언제 정규화된 컬럼으로 빼야 하는가

JSONB가 유용한 경우는 대체로 두 가지 조건을 같이 만족할 때다. 첫째, 속성의 종류나 개수가 레코드마다(또는 카테고리마다) 크게 달라져 고정된 스키마로 정의하기 어려운 경우. 둘째, 해당 필드가 조회 조건이나 조인 키로 아주 빈번하게 쓰이지는 않는 경우다. 상품의 부가 속성, 사용자 설정값, 외부 API 응답을 그대로 보관하는 로그성 데이터 등이 대표적인 예다.

반대로 특정 JSONB 내부 필드가 WHERE 절, ORDER BY, 조인 조건에 반복적으로 등장한다면 이는 정규화된 컬럼(또는 별도 테이블)으로 승격하는 것을 고려할 신호다. 관계형 컬럼은 타입 제약과 NOT NULL, 외래 키 같은 무결성 제약을 걸 수 있고, B-tree 인덱스나 통계 정보를 통해 옵티마이저가 더 정확한 실행 계획을 세울 수 있다는 장점이 있다. 즉 JSONB는 "스키마가 아직 안정되지 않았거나 유연성이 정합성보다 중요한 부분"을 위한 도구이지, 관계형 모델링을 완전히 대체하는 수단으로 보기는 어렵다.

## 예제

다음은 상품 테이블에 JSONB 속성 컬럼을 추가하고, GIN 인덱스를 만든 뒤 이를 활용해 조회하는 예시다.

```sql
-- 1. 핵심 필드는 일반 컬럼, 가변 속성은 JSONB 컬럼으로 분리
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 2. JSONB 컬럼에 대한 GIN 인덱스 생성 (포함 연산 @> 위주라면 jsonb_path_ops 사용)
CREATE INDEX idx_products_attributes
    ON products USING GIN (attributes jsonb_path_ops);

-- 3. 예시 데이터 삽입
INSERT INTO products (name, category, price, attributes)
VALUES
    ('러닝화 A', 'shoes', 89000,
     '{"size": "270mm", "color": "black", "waterproof": true}'::jsonb),
    ('노트북 B', 'electronics', 1590000,
     '{"ram_gb": 16, "storage": "512GB SSD", "color": "silver"}'::jsonb);

-- 4. @> 연산자로 특정 키-값 쌍을 포함하는 행 검색 (GIN 인덱스 활용 가능)
SELECT id, name
FROM products
WHERE attributes @> '{"color": "black"}'::jsonb;

-- 5. ->> 연산자로 특정 키의 값을 텍스트로 추출
SELECT id, name, attributes ->> 'ram_gb' AS ram_gb
FROM products
WHERE category = 'electronics';
```

`@>` 연산자는 왼쪽 JSONB가 오른쪽 JSONB를 부분집합으로 포함하는지를 검사하며, GIN 인덱스와 결합되면 인덱스 스캔으로 처리될 수 있다. `->>` 연산자는 지정한 키의 값을 텍스트 타입으로 꺼내오며, 여기에 조건을 걸 때는 필요에 따라 표현식 인덱스(예: `((attributes ->> 'ram_gb'))`에 대한 B-tree 인덱스)를 별도로 고려할 수 있다.

## 실무 포인트

- **JSONB 남용은 쿼리 복잡도를 눈에 띄게 높인다.** 조건이 여러 JSONB 키에 걸쳐 있거나, JSONB 내부 값끼리 비교·집계해야 하는 요구가 늘어나면 SQL은 `->>`와 캐스팅으로 뒤덮이고 가독성과 유지보수성이 떨어진다. 이런 신호가 보이면 해당 부분만이라도 정규화된 구조로 옮기는 것이 낫다.
- **자주 조회하는 필드는 생성 컬럼(generated column)으로 승격하는 것을 고려한다.** PostgreSQL은 `GENERATED ALWAYS AS (...) STORED` 구문으로 JSONB 내부 값을 뽑아 별도 컬럼으로 물리적으로 저장할 수 있고, 이 생성 컬럼에는 일반 B-tree 인덱스를 걸 수 있다. 이렇게 하면 JSONB의 유연성은 유지하면서도 자주 쓰는 조회 경로만 관계형 인덱스의 이점을 누릴 수 있다.
- **인덱스 유형 선택은 실제 쿼리 패턴을 보고 결정해야 한다.** `jsonb_ops`와 `jsonb_path_ops` 중 무엇이 맞는지, 혹은 표현식 인덱스가 더 적합한지는 애플리케이션이 주로 어떤 연산자로 JSONB를 조회하는지에 따라 달라지므로, 실제 쿼리 로그나 실행 계획(`EXPLAIN`)을 확인하고 결정하는 것이 안전하다.

## 3줄 요약

- `json`은 입력 텍스트를 그대로 보존하고 조회 시마다 파싱하는 반면, `jsonb`는 저장 시점에 이진 구조로 변환해두어 이후 조회와 인덱싱이 더 빠르다.
- GIN 인덱스는 JSONB 내부의 키와 값을 역색인으로 추출해두어, `@>` 같은 연산자로 특정 키-값 쌍을 포함하는 행을 인덱스 스캔만으로 찾을 수 있게 해준다.
- JSONB는 스키마가 자주 바뀌는 속성 데이터에 적합하지만, 특정 필드가 조회·정렬·조인에 자주 쓰이기 시작하면 정규화된 컬럼이나 생성 컬럼으로 승격하는 것을 고려해야 한다.

## 참고 자료

- [PostgreSQL Documentation — JSON Types](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostgreSQL Documentation — JSON Functions and Operators](https://www.postgresql.org/docs/current/functions-json.html)
- [PostgreSQL Documentation — GIN Indexes](https://www.postgresql.org/docs/current/gin.html)
- [PostgreSQL Documentation — GIN Indexes for jsonb](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
- [PostgreSQL Documentation — Generated Columns](https://www.postgresql.org/docs/current/ddl-generated-columns.html)
