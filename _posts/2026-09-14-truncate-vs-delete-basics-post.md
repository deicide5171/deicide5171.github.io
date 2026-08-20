---
layout: single
title: "TRUNCATE와 DELETE 차이가 뭔가요 — 데이터를 지우는 두 방법"
date: 2026-09-14 13:35:00 +0530
categories: database
tags: ["truncate", "delete", "sql", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "테이블 데이터를 지우는 TRUNCATE와 DELETE의 동작 차이와 언제 무엇을 써야 하는지 처음 배우는 사람 기준으로 정리했다."
---

## 데이터를 다 지우는데 왜 두 가지인가

테이블의 데이터를 지우는 방법에는 **DELETE**와 **TRUNCATE**가 있다. 둘 다 데이터를 없애지만, 동작 방식과 속도, 되돌릴 수 있는지가 다르다. 특히 "전체 삭제"에서 차이가 크다.

## DELETE vs TRUNCATE

| 구분 | DELETE | TRUNCATE |
|---|---|---|
| 방식 | 행을 하나씩 삭제 | 테이블을 통째로 비움 |
| 조건(WHERE) | 가능 | 불가(전체만) |
| 속도 | 느림(행 수만큼) | 매우 빠름 |
| 롤백 | 트랜잭션 내 가능 | 보통 불가·제한적 |
| auto increment | 유지 | 초기화되기도 함 |

## 예시

```sql
-- 조건부 삭제: DELETE만 가능
DELETE FROM logs WHERE created_at < '2025-01-01';

-- 전체 비우기: TRUNCATE가 훨씬 빠름
TRUNCATE TABLE temp_data;
```

## 실무 포인트

- **일부만 지울 땐 DELETE.** 조건에 맞는 행만 지우려면 `WHERE`가 필요하니 DELETE를 쓴다. TRUNCATE는 조건을 걸 수 없다.
- **전체 삭제는 TRUNCATE가 빠르다.** 수백만 행을 DELETE하면 행마다 로그를 남겨 매우 느리고 부하가 크다. 전체를 비울 거면 TRUNCATE가 훨씬 빠르고 가볍다.
- **되돌리기 어려움에 주의.** TRUNCATE는 대부분 롤백이 안 되거나 제한적이라, 실행하면 사실상 복구가 어렵다. 운영 테이블에선 백업을 확인하고 매우 신중히 쓴다. 외래키가 걸린 테이블은 TRUNCATE가 막히기도 한다.

## 마무리 요약

- DELETE는 조건에 맞는 행을 하나씩 지우고(WHERE 가능, 롤백 가능), TRUNCATE는 테이블을 통째로 빠르게 비운다.
- 일부만 지울 땐 DELETE, 전체를 비울 땐 TRUNCATE가 빠르다.
- TRUNCATE는 롤백이 어렵고 외래키 제약에 걸릴 수 있어 운영에서 매우 신중히 써야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 - TRUNCATE](https://www.postgresql.org/docs/current/sql-truncate.html)
