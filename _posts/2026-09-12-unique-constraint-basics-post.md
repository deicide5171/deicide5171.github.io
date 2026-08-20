---
layout: single
title: "UNIQUE 제약이 뭔가요 — 중복 값을 DB가 막게 하기"
date: 2026-09-12 12:35:00 +0530
categories: database
tags: ["unique", "제약조건", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "이메일·아이디 같은 값의 중복을 데이터베이스 차원에서 막는 UNIQUE 제약의 개념과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 애플리케이션에서만 중복을 막으면 위험하다

"이미 가입된 이메일인지"를 애플리케이션 코드에서 조회로 확인한 뒤 저장한다고 하자. 조회와 저장 사이에 동시 요청이 끼면 같은 이메일이 두 번 저장될 수 있다. **UNIQUE 제약**은 이런 중복을 **데이터베이스가 직접 막아**, 어떤 상황에서도 중복 값이 들어가지 못하게 한다.

## 무엇을 하나

| 상황 | UNIQUE 없을 때 | UNIQUE 있을 때 |
|---|---|---|
| 같은 이메일 두 번 저장 | 둘 다 들어감 | 두 번째는 오류로 거부 |
| 동시 요청 중복 | 앱 검사만으론 뚫림 | DB가 원자적으로 차단 |

## 설정하기

```sql
-- 테이블 만들 때
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) UNIQUE
);

-- 여러 컬럼 조합의 유일성(복합 UNIQUE)
ALTER TABLE enrollments
  ADD CONSTRAINT uq_student_course UNIQUE (student_id, course_id);
```

복합 UNIQUE는 "한 학생이 같은 과목을 두 번 신청 못 하게"처럼 컬럼 조합의 중복을 막는다.

## 실무 포인트

- **앱 검사와 DB 제약을 함께 써라.** 앱에서 미리 확인하면 사용자에게 친절한 메시지를 줄 수 있지만, 최종 방어선은 DB의 UNIQUE 제약이다. 둘 다 두면 편의성과 안전성을 모두 얻는다.
- **NULL은 보통 중복으로 안 본다.** 대부분의 DB에서 UNIQUE 컬럼의 NULL 값 여러 개는 허용된다("모름"은 서로 같다고 보지 않기 때문). 정책이 DB마다 다르니 확인한다.
- **위반 오류를 처리하라.** 중복 저장을 시도하면 DB가 오류를 던진다. 이 오류를 잡아 "이미 사용 중인 이메일입니다" 같은 안내로 바꿔줘야 사용자가 이해할 수 있다.

## 마무리 요약

- UNIQUE 제약은 특정 컬럼(또는 컬럼 조합)에 중복 값이 들어가지 못하게 DB가 막는다.
- 앱 검사만으론 동시 요청에 뚫릴 수 있어, DB 제약이 최종 방어선이다.
- NULL 처리 정책을 확인하고, 위반 오류를 잡아 친절한 메시지로 바꿔 처리한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
