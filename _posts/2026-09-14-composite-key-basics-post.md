---
layout: single
title: "복합키가 뭔가요 — 여러 컬럼을 묶어 기본키로 쓰기"
date: 2026-09-14 12:35:00 +0530
categories: database
tags: ["복합키", "compositekey", "기본키", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "두 개 이상의 컬럼을 묶어 하나의 기본키로 삼는 복합키의 개념과 언제 쓰는지 처음 배우는 사람 기준으로 정리했다."
---

## 컬럼 하나로 고유하게 못 구분할 때

수강신청 테이블에서 "학생 A가 과목 1을 신청"한 행을 고유하게 구분하려면 어떻게 할까? `student_id`만으로는 한 학생이 여러 과목을 신청하니 안 되고, `course_id`만으로도 안 된다. **복합키(composite key)**는 **두 개 이상의 컬럼을 묶어 하나의 기본키로 삼는** 것이다. `(student_id, course_id)` 조합이 유일하면 기본키가 된다.

## 단일키 vs 복합키

| 구분 | 단일 기본키 | 복합키 |
|---|---|---|
| 구성 | 컬럼 1개 | 컬럼 2개 이상 |
| 예 | user_id | (student_id, course_id) |
| 유일성 | 그 컬럼만으로 | 컬럼 조합으로 |

## 예시

```sql
CREATE TABLE enrollments (
    student_id BIGINT,
    course_id  BIGINT,
    enrolled_at TIMESTAMP,
    PRIMARY KEY (student_id, course_id)
);
-- (학생, 과목) 조합이 유일 -> 같은 학생이 같은 과목 중복 신청 불가
```

## 실무 포인트

- **다대다 연결 테이블에 자주 쓴다.** 학생-과목, 사용자-역할처럼 다대다 관계를 잇는 중간 테이블에서 두 외래키를 묶어 복합키로 삼는 것이 자연스럽다.
- **대리키(surrogate key)와 비교하라.** 복합키 대신 무의미한 단일 `id`(auto increment)를 기본키로 두고, 조합엔 UNIQUE 제약을 거는 방식도 많이 쓴다. 다른 테이블에서 이 행을 참조하기 쉬워 실무에서 선호되기도 한다.
- **순서가 인덱스에 영향.** 복합키는 인덱스로도 동작하는데, 컬럼 순서가 중요하다. `(A, B)` 인덱스는 A 조건엔 잘 쓰이지만 B만으로 조회하면 못 탄다. 자주 조회하는 컬럼을 앞에 둔다.

## 마무리 요약

- 복합키는 두 개 이상의 컬럼을 묶어 하나의 기본키로 삼는 것이다.
- `(student_id, course_id)`처럼 조합이 유일할 때 쓰며, 다대다 연결 테이블에 자주 등장한다.
- 대리키+UNIQUE 방식과 비교해 선택하고, 복합키 컬럼 순서가 인덱스 활용에 영향을 준다.

## 참고 자료

- [PostgreSQL 공식 문서 - Primary Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)
