---
layout: single
title: "SQL JOIN 기초 — INNER, LEFT, RIGHT 헷갈리지 않기"
date: 2026-09-03 12:35:00 +0530
categories: database
tags: ["sql", "join", "데이터베이스기초", "입문", "쿼리"]
toc: true
toc_sticky: true
excerpt: "SQL을 배울 때 가장 헷갈리는 INNER JOIN, LEFT JOIN, RIGHT JOIN의 차이를 예제 데이터로 명확하게 정리했다."
---

## JOIN이 왜 필요한가

관계형 데이터베이스는 데이터를 여러 테이블에 나눠 저장한다. 예를 들어 회원 정보는 `users` 테이블에, 주문 정보는 `orders` 테이블에 따로 있다. "각 회원이 주문한 내역을 함께 보고 싶다"면 두 테이블을 연결해야 하는데, 이 연결을 담당하는 것이 **JOIN**이다.

## 예제 데이터

```text
users 테이블            orders 테이블
id | name              id | user_id | item
1  | 김철수            1  | 1       | 노트북
2  | 이영희            2  | 1       | 마우스
3  | 박민수            3  | 2       | 키보드
                       (박민수는 주문 내역 없음)
```

## INNER / LEFT / RIGHT JOIN 차이

| 종류 | 결과 | 위 예제 결과 |
|---|---|---|
| INNER JOIN | 양쪽 모두에 매칭되는 행만 | 김철수·이영희의 주문만 (박민수 제외) |
| LEFT JOIN | 왼쪽(users) 전부 + 매칭되는 오른쪽 | 박민수도 포함(주문은 NULL) |
| RIGHT JOIN | 오른쪽(orders) 전부 + 매칭되는 왼쪽 | 모든 주문 + 해당 회원 |

```sql
-- INNER JOIN: 주문이 있는 회원만
SELECT u.name, o.item
FROM users u
INNER JOIN orders o ON u.id = o.user_id;
-- 결과: 김철수-노트북, 김철수-마우스, 이영희-키보드 (박민수 없음)

-- LEFT JOIN: 주문이 없는 회원도 포함
SELECT u.name, o.item
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;
-- 결과: 위 3건 + 박민수-NULL
```

핵심 차이는 **"매칭이 안 되는 행을 결과에 포함할 것인가"**다. INNER는 매칭된 것만, LEFT는 왼쪽 테이블을 기준으로 매칭이 없어도 다 살린다.

## 어떤 JOIN을 언제 쓰나

```text
- "주문한 적 있는 회원 목록" -> INNER JOIN (주문 없는 회원 제외)
- "모든 회원과 각자의 주문(없으면 없는 대로)" -> LEFT JOIN
- "주문이 하나도 없는 회원 찾기" -> LEFT JOIN + WHERE o.id IS NULL
```

마지막 패턴(LEFT JOIN 후 `IS NULL` 필터)은 "한쪽에만 있고 다른 쪽엔 없는 데이터"를 찾는 아주 유용한 기법이다.

## 실무 포인트

- **RIGHT JOIN은 실무에서 거의 쓰이지 않는다.** LEFT JOIN으로 테이블 순서만 바꾸면 같은 결과를 얻을 수 있어, 가독성을 위해 LEFT JOIN으로 통일하는 팀이 많다.
- **JOIN 조건(`ON`)에 인덱스가 없으면 데이터가 많을 때 매우 느려진다.** 연결 키(위 예제의 `user_id`)에는 인덱스를 걸어두는 것이 기본이다.
- **여러 테이블을 JOIN할 때 결과 행이 예상보다 많아지면(중복) 조인 관계가 1:N인지 N:M인지 확인해야 한다.** 한 회원에 주문이 여러 개면 회원 정보가 주문 수만큼 반복되어 나오는 것이 정상이다.

## 마무리 요약

- JOIN은 여러 테이블에 나뉜 데이터를 연결해 함께 조회하는 방법이다.
- INNER는 매칭된 행만, LEFT는 왼쪽 테이블을 기준으로 매칭이 없어도 모두 살린다.
- LEFT JOIN + `IS NULL`은 한쪽에만 있는 데이터를 찾는 유용한 패턴이며, 연결 키에는 인덱스를 걸어야 한다.

## 참고 자료

- [MySQL 공식 문서 - JOIN](https://dev.mysql.com/doc/refman/8.0/en/join.html)
- [PostgreSQL 공식 문서 - 테이블 조인](https://www.postgresql.org/docs/current/tutorial-join.html)
