---
layout: single
title: "외래키 CASCADE가 뭔가요 — 부모를 지우면 자식도 지울까"
date: 2026-09-16 12:35:00 +0530
categories: database
tags: ["외래키", "cascade", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "외래키로 연결된 데이터에서 부모 행을 지우거나 바꿀 때 자식 행을 어떻게 처리할지 정하는 CASCADE 옵션을 처음 배우는 사람 기준으로 정리했다."
---

## 회원을 지우면 그 회원의 주문은?

주문 테이블이 회원 테이블을 외래키로 참조한다고 하자. 회원을 삭제하면 그 회원의 주문은 어떻게 될까? 그냥 두면 "존재하지 않는 회원을 참조하는 주문"이 생겨 무결성이 깨진다. 외래키의 **ON DELETE / ON UPDATE 옵션**이 이 상황을 어떻게 처리할지 정한다. **CASCADE**는 그중 "부모를 따라 자식도 처리"하는 옵션이다.

## 주요 옵션

| 옵션 | 부모 삭제 시 자식 |
|---|---|
| CASCADE | 자식도 함께 삭제 |
| RESTRICT / NO ACTION | 자식이 있으면 삭제 거부 |
| SET NULL | 자식의 외래키를 NULL로 |

## 설정 예시

```sql
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE
);
-- users에서 회원을 지우면 그 회원의 orders도 자동 삭제
```

## 실무 포인트

- **CASCADE는 편하지만 위험하다.** 부모 하나를 지웠는데 연쇄로 수많은 자식이 삭제될 수 있다. 실수로 큰 데이터가 날아갈 수 있으니, 중요한 데이터엔 RESTRICT로 막고 명시적으로 처리하는 편이 안전할 때가 많다.
- **SET NULL은 관계만 끊는다.** 자식을 지우지 않고 외래키만 NULL로 만들어 "소속 없음" 상태로 둔다. 부모가 사라져도 자식 기록은 남겨야 할 때(작성자 탈퇴해도 글은 유지 등) 쓴다.
- **소프트 삭제도 고려.** 실제로 지우지 않고 `deleted_at` 같은 플래그로 "삭제됨" 표시만 하는 소프트 삭제를 쓰면, CASCADE의 연쇄 삭제 위험 없이 데이터를 보존할 수 있다.

## 마무리 요약

- 외래키의 ON DELETE/UPDATE 옵션은 부모를 지우거나 바꿀 때 자식을 어떻게 처리할지 정한다.
- CASCADE(함께 처리)·RESTRICT(거부)·SET NULL(관계만 끊기)이 대표적이다.
- CASCADE는 편하지만 연쇄 삭제 위험이 있어, 중요한 데이터엔 신중히 쓰고 소프트 삭제도 고려한다.

## 참고 자료

- [PostgreSQL 공식 문서 - Foreign Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)
