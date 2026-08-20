---
layout: single
title: "저장 프로시저가 뭔가요 — DB 안에 저장해두는 SQL 묶음"
date: 2026-09-08 13:35:00 +0530
categories: database
tags: ["저장프로시저", "storedprocedure", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "여러 SQL 문을 DB 안에 미리 저장해두고 호출하는 저장 프로시저의 개념과 장단점을 처음 배우는 사람 기준으로 정리했다."
---

## 자주 쓰는 SQL을 매번 짜야 하나

"주문을 넣고, 재고를 줄이고, 로그를 남기는" 여러 SQL 문을 매번 애플리케이션에서 하나씩 보내야 할까? **저장 프로시저(stored procedure)**는 이런 **여러 SQL 문을 DB 안에 하나의 이름으로 미리 저장해두고, 필요할 때 이름만 불러서 실행**하는 기능이다. 함수처럼 파라미터를 받아 동작할 수도 있다.

## 일반 SQL과 저장 프로시저

| 구분 | 일반 SQL | 저장 프로시저 |
|---|---|---|
| 위치 | 애플리케이션 코드 | DB 안에 저장 |
| 실행 | 매번 SQL 전송 | 이름으로 호출 |
| 재사용 | 코드에 반복 | 한 번 만들고 재호출 |
| 로직 | 앱에서 처리 | DB 안에서 처리 가능 |

## 만들고 쓰기

```sql
-- 정의: 특정 고객의 주문 수를 세는 프로시저
CREATE PROCEDURE count_orders(IN customer_id INT)
BEGIN
    SELECT COUNT(*) FROM orders WHERE cust_id = customer_id;
END;

-- 호출
CALL count_orders(42);
```

이렇게 한 번 정의해두면, 애플리케이션은 긴 SQL 대신 `CALL count_orders(42)`만 보내면 된다.

## 실무 포인트

- **네트워크 왕복을 줄일 수 있다.** 여러 SQL을 한 번의 호출로 DB 안에서 처리하므로, 앱과 DB 사이를 여러 번 오가는 것보다 빠를 수 있다. 대량 배치 처리에서 유리할 때가 있다.
- **로직이 DB에 숨어 관리가 어려워진다.** 비즈니스 로직이 애플리케이션 코드와 DB 프로시저로 나뉘면, 코드만 봐선 전체 흐름을 알기 어렵다. 버전 관리(git)도 코드보다 번거롭다. 요즘은 로직을 앱에 두는 경우가 많다.
- **DB마다 문법이 다르다.** MySQL, PostgreSQL, Oracle의 프로시저 문법이 제각각이라, 다른 DB로 옮길 때 프로시저를 다시 짜야 할 수 있다. 이식성이 중요하면 신중히 선택한다.

## 마무리 요약

- 저장 프로시저는 여러 SQL 문을 DB 안에 이름으로 저장해두고 호출하는 기능이다.
- 네트워크 왕복을 줄이고 재사용이 쉬운 장점이 있다.
- 로직이 DB에 숨고 버전 관리·이식성이 어려워, 요즘은 앱에 로직을 두는 경우가 많다.

## 참고 자료

- [MySQL 공식 문서 - Stored Procedures](https://dev.mysql.com/doc/refman/8.0/en/stored-routines.html)
