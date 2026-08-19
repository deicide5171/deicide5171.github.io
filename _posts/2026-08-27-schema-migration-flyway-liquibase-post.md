---
layout: single
title: "스키마도 버전 관리가 필요하다 — Flyway vs Liquibase 비교"
date: 2026-08-27 12:35:00 +0530
categories: database
tags: ["flyway", "liquibase", "schema-migration", "database", "ci-cd", "version-control"]
toc: true
toc_sticky: true
excerpt: "애플리케이션 코드는 Git으로 버전 관리하면서 DB 스키마 변경은 수동 SQL로 처리하는 팀이 아직 많다. Flyway와 Liquibase의 철학 차이와 선택 기준을 정리한다."
---

애플리케이션 코드는 Git으로 버전 관리하고 PR 리뷰를 거치면서, DB 스키마 변경은 누군가 운영 DB에 접속해 수동으로 `ALTER TABLE`을 실행하는 팀이 여전히 많다. 이 방식은 "누가 언제 무엇을 바꿨는지"를 코드처럼 추적할 수 없고, 로컬·스테이징·운영 환경의 스키마가 조금씩 어긋나는 드리프트(drift)를 만든다. 스키마 마이그레이션 도구는 이 문제를 "스키마 변경도 코드처럼 버전 관리하고 순서대로 적용한다"는 원칙으로 해결한다.

Flyway와 Liquibase는 이 분야의 양대 산맥이지만 철학이 다르다. Flyway는 "SQL을 직접 쓰고 그걸 순서대로 실행한다"는 단순함을, Liquibase는 "변경을 DB에 독립적인 형식으로 기술하고 롤백까지 관리한다"는 추상화를 지향한다. 이 글에서는 두 도구의 차이와 선택 기준을 정리한다.

## 핵심 개념 1: 마이그레이션 파일 형식의 철학 차이

Flyway의 마이그레이션은 기본적으로 순수 SQL 파일이다. `V1__create_users_table.sql`처럼 버전 번호가 붙은 파일을 만들고 그 안에 원하는 DDL을 그대로 쓴다. Flyway는 이 파일들을 버전 순서대로 실행하고, 실행 이력을 `flyway_schema_history` 테이블에 기록해 다음 실행 때 이미 적용된 마이그레이션을 건너뛴다. 배운 게 SQL뿐이어도 바로 쓸 수 있다는 게 강점이지만, 롤백 스크립트는 스스로 별도 파일로 작성해야 한다(커뮤니티 버전 기준).

Liquibase는 변경을 changelog(XML, YAML, JSON, 또는 SQL)로 기술한다. `<createTable>`, `<addColumn>` 같은 DB-독립적인 태그로 스키마 변경을 표현하면, Liquibase가 이를 PostgreSQL/MySQL/Oracle 등 대상 DB 방언에 맞는 SQL로 변환해 실행한다. 각 changeSet에는 `rollback` 블록을 함께 정의할 수 있어, 특정 조건에서는 자동 롤백이 가능하다.

## 핵심 개념 2: 기능 비교와 선택 기준

| 구분 | Flyway | Liquibase |
|---|---|---|
| 기본 형식 | SQL 파일 | XML/YAML/JSON changelog (SQL도 가능) |
| DB 독립적 추상화 | 없음(순수 SQL) | 있음(태그가 DB별 SQL로 변환) |
| 자동 롤백 | 커뮤니티 버전엔 제한적(유료 Undo) | changeSet 단위 rollback 정의 가능 |
| 변경 검증(checksum) | 있음(파일 수정 감지) | 있음 |
| 스키마 diff 생성 | 유료 버전 | 커뮤니티에서도 일부 지원 |
| 학습 곡선 | 낮음(SQL만 알면 됨) | 중간(태그 문법 학습 필요) |
| 적합한 팀 | SQL에 익숙한 백엔드 중심 팀 | 멀티 DB 지원·엄격한 변경 이력 관리가 필요한 조직 |

두 도구 모두 "적용된 마이그레이션은 절대 수정하지 않는다"는 원칙을 공유한다. 이미 배포된 마이그레이션 파일의 내용을 바꾸면 체크섬 불일치로 실행이 거부되며, 수정이 필요하면 새로운 마이그레이션을 추가해야 한다.

<img src="/assets/images/posts/2026-08-27-schema-migration-flyway-liquibase-1.svg" alt="Flyway는 SQL 파일을 버전 순서대로 직접 실행하고, Liquibase는 DB 독립적 changelog를 방언별 SQL로 변환해 실행하는 구조 비교도" style="width:100%;">

## 예제: 같은 변경을 각 도구로 표현하기

```sql
-- Flyway: V2__add_email_to_users.sql
ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL DEFAULT '';
CREATE UNIQUE INDEX idx_users_email ON users(email);
```

```yaml
# Liquibase: changelog/002-add-email-to-users.yaml
databaseChangeLog:
  - changeSet:
      id: 002-add-email-to-users
      author: team-db
      changes:
        - addColumn:
            tableName: users
            columns:
              - column:
                  name: email
                  type: varchar(255)
                  defaultValue: ""
                  constraints:
                    nullable: false
        - createIndex:
            indexName: idx_users_email
            tableName: users
            unique: true
            columns:
              - column:
                  name: email
      rollback:
        - dropIndex:
            indexName: idx_users_email
            tableName: users
        - dropColumn:
            tableName: users
            columnName: email
```

Liquibase 쪽은 코드가 길지만 `rollback` 블록이 명시적으로 함께 정의된다는 차이가 눈에 띈다.

## 실무 포인트

- **CI/CD에 마이그레이션 검증 단계를 반드시 넣는다**: PR에서 마이그레이션 파일이 추가되면 임시 DB 컨테이너에 실제로 적용해 보는 CI 잡을 둬야 한다. 문법 오류나 락 충돌 가능성은 로컬에서 놓치기 쉽다.
- **대용량 테이블의 DDL은 별도로 다룬다**: 두 도구 모두 마이그레이션 실행 자체는 순차적이지만, 수억 건짜리 테이블에 `ALTER TABLE ADD COLUMN NOT NULL DEFAULT`를 걸면 잠금 시간이 길어질 수 있다. 이런 경우는 gh-ost·pt-online-schema-change 같은 무중단 DDL 도구와 조합하거나, expand-contract 패턴으로 여러 마이그레이션에 나눠 적용한다.
- **되돌리기 전략을 미리 정한다**: Flyway 커뮤니티 버전은 자동 롤백이 제한적이므로, 되돌려야 할 상황이 오면 "반대 방향 마이그레이션을 새로 추가해 앞으로 감는다(roll forward)"는 원칙을 팀에 미리 합의해 둬야 배포 사고 때 우왕좌왕하지 않는다.

## 3줄 요약

- Flyway는 SQL을 직접 쓰는 단순함을, Liquibase는 DB-독립적 changelog와 롤백 정의라는 추상화를 지향한다.
- 두 도구 모두 이미 적용된 마이그레이션은 수정하지 않고 체크섬으로 변경을 검증한다는 원칙을 공유한다.
- 대용량 테이블 DDL과 롤백 전략은 도구 선택과 별개로 팀이 미리 합의해 둬야 하는 운영 규칙이다.

## 참고 자료

- [Flyway 공식 문서](https://documentation.red-gate.com/fd)
- [Liquibase 공식 문서](https://docs.liquibase.com/)
- [Liquibase: Rollback 작성 가이드](https://docs.liquibase.com/workflows/liquibase-community/using-rollback.html)
