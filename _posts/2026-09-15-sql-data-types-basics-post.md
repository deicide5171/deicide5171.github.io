---
layout: single
title: "데이터 타입 고르기 — VARCHAR, TEXT, INT 뭘 써야 하나"
date: 2026-09-15 13:35:00 +0530
categories: database
tags: ["데이터타입", "varchar", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "테이블 컬럼의 데이터 타입을 고를 때 자주 헷갈리는 문자·숫자·날짜 타입 선택 기준을 처음 배우는 사람 기준으로 정리했다."
---

## 컬럼 타입을 대충 정하면 나중에 고생한다

테이블을 만들 때 각 컬럼의 데이터 타입을 정한다. "그냥 다 문자열로" 하면 정렬·계산·용량에서 문제가 생긴다. 적절한 타입을 고르면 저장 공간을 아끼고, DB가 값을 올바르게 정렬·비교하며, 잘못된 데이터를 막을 수 있다.

## 자주 쓰는 타입

| 종류 | 타입 | 용도 |
|---|---|---|
| 문자 | VARCHAR(n) | 길이 제한 있는 문자열(이름 등) |
| 문자 | TEXT | 긴 글(본문·설명) |
| 숫자 | INT / BIGINT | 정수(개수·ID) |
| 숫자 | DECIMAL | 정확한 소수(돈) |
| 날짜 | DATE / TIMESTAMP | 날짜 / 날짜+시간 |
| 참거짓 | BOOLEAN | 예/아니오 |

## 선택 기준

```text
- 이름·이메일: VARCHAR(길이 제한)
- 게시글 본문: TEXT
- 가격·금액: DECIMAL (FLOAT는 오차 있음!)
- 생성 시각: TIMESTAMP (타임존 고려)
- 활성 여부: BOOLEAN
```

## 실무 포인트

- **돈에는 FLOAT 말고 DECIMAL.** FLOAT/DOUBLE은 소수를 근사값으로 저장해 `0.1 + 0.2 ≠ 0.3` 같은 오차가 난다. 금액·정산처럼 정확해야 하는 값은 반드시 DECIMAL을 쓴다.
- **숫자 같아도 문자면 문자로.** 전화번호·우편번호는 숫자로 보이지만 앞의 0이 사라지거나 계산할 일이 없으니 문자(VARCHAR)로 저장하는 것이 안전하다.
- **날짜는 타임존을 정하라.** 여러 지역 사용자가 있으면 UTC로 저장하고 표시할 때 변환하는 것이 표준이다. 타임존 없는 타입을 쓰면 시간이 뒤섞일 수 있다.

## 마무리 요약

- 데이터 타입을 잘 고르면 공간을 아끼고 정렬·비교가 올바르며 잘못된 데이터를 막는다.
- 문자는 VARCHAR/TEXT, 정수는 INT/BIGINT, 정확한 소수는 DECIMAL, 날짜는 TIMESTAMP를 쓴다.
- 돈엔 FLOAT 대신 DECIMAL, 전화번호는 문자, 날짜는 타임존(UTC)을 고려한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Data Types](https://www.postgresql.org/docs/current/datatype.html)
