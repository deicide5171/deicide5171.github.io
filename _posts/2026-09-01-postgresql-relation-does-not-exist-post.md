---
layout: single
title: "PostgreSQL 'relation does not exist' 에러 해결하기"
date: 2026-09-01 13:35:00 +0530
categories: database
tags: ["postgresql", "트러블슈팅", "sql에러", "schema", "데이터베이스"]
toc: true
toc_sticky: true
excerpt: "테이블이 분명히 있는데도 PostgreSQL이 relation does not exist를 내뱉을 때, 스키마와 검색 경로 문제를 확인하는 순서를 정리했다."
---

## 분명히 만든 테이블인데 왜 없다고 하는가

`\dt`로 확인하면 테이블이 분명히 존재하는데도 쿼리에서 `relation "users" does not exist` 에러가 난다면, 대부분 테이블 이름 자체의 문제가 아니라 **어느 스키마에서 찾고 있는지**의 문제다. PostgreSQL은 MySQL과 달리 하나의 데이터베이스 안에 여러 스키마(namespace)를 가질 수 있고, 명시하지 않으면 `search_path`에 지정된 스키마 순서대로 찾는다.

## 원인 후보

| 원인 | 확인 방법 |
|---|---|
| 다른 스키마에 테이블이 있음 | `SELECT * FROM information_schema.tables WHERE table_name = 'users';` |
| 대소문자 문제 | 큰따옴표로 테이블을 만들면 대소문자를 그대로 구분하게 됨 |
| 다른 DB에 연결되어 있음 | `SELECT current_database();` |
| 트랜잭션 커밋 전 다른 세션에서 조회 | 커밋 여부 확인 |

## 대소문자 문제, 가장 흔한 함정

```sql
-- 큰따옴표로 테이블을 만들면 대소문자가 그대로 유지된다
CREATE TABLE "Users" (id serial primary key);

-- 이렇게 조회하면 실패한다 (PostgreSQL이 소문자로 변환해서 찾기 때문)
SELECT * FROM Users;  -- ERROR: relation "users" does not exist

-- 큰따옴표로 정확히 감싸야 성공한다
SELECT * FROM "Users";
```

PostgreSQL은 큰따옴표 없이 쓴 식별자를 자동으로 소문자로 변환한다. 테이블을 만들 때 실수로 대문자가 섞인 이름을 큰따옴표로 감싸 만들었다면, 이후 모든 쿼리에서도 큰따옴표로 감싸야 하는 번거로움이 생긴다. 그래서 실무에서는 테이블·컬럼명을 처음부터 소문자+언더스코어로 통일하는 컨벤션을 권장한다.

## 스키마 문제 확인 및 해결

```sql
-- 현재 search_path 확인
SHOW search_path;

-- 테이블이 실제로 어느 스키마에 있는지 확인
SELECT schemaname, tablename FROM pg_tables WHERE tablename = 'users';

-- 스키마를 명시해서 조회 (근본 해결)
SELECT * FROM my_schema.users;

-- 또는 search_path에 해당 스키마를 추가
SET search_path TO my_schema, public;
```

## 실무 포인트

- **마이그레이션 도구(Flyway, Liquibase)가 다른 스키마에 테이블을 만들도록 설정되어 있는 경우가 있다.** 로컬에서는 `public` 스키마를 쓰는데 운영 환경 설정이 다르면 이런 에러가 환경별로 다르게 나타난다.
- **커넥션 풀을 쓰는 경우, 세션마다 `search_path`가 다르게 설정될 수 있다.** 애플리케이션 시작 시 명시적으로 `search_path`를 고정하는 것이 안전하다.
- **ORM(JPA, Hibernate 등)을 쓸 때도 엔티티에 스키마를 명시하지 않으면 기본 `search_path`를 따른다.** 여러 스키마를 쓰는 프로젝트라면 `@Table(schema = "...")` 같은 명시적 설정이 필요하다.

## 마무리 요약

- `relation does not exist`는 대부분 테이블이 없는 게 아니라 다른 스키마에 있거나 search_path가 다른 문제다.
- 큰따옴표로 만든 대소문자 혼용 테이블명은 조회할 때도 항상 큰따옴표로 감싸야 한다.
- `search_path`와 `information_schema.tables`로 실제 위치를 확인하는 것이 가장 빠른 진단 방법이다.

## 참고 자료

- [PostgreSQL 공식 문서 - 스키마](https://www.postgresql.org/docs/current/ddl-schemas.html)
- [PostgreSQL 공식 문서 - 식별자와 키워드](https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS)
