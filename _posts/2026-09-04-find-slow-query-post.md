---
layout: single
title: "느린 쿼리 찾기 — 어떤 쿼리가 DB를 느리게 하는지 잡아내기"
date: 2026-09-04 12:35:00 +0530
categories: database
tags: ["느린쿼리", "slow query", "쿼리튜닝", "트러블슈팅", "입문"]
toc: true
toc_sticky: true
excerpt: "서비스가 느려졌을 때 어떤 쿼리가 범인인지 찾는 방법을, 슬로우 쿼리 로그와 실행 계획 관점에서 처음 배우는 사람 기준으로 정리했다."
---

## "DB가 느려요"에서 시작하기

서비스가 느려졌다는 신고가 들어오면 막연하다. 코드가 문제인지, 네트워크인지, DB인지부터 좁혀야 한다. DB가 원인이라면 대부분 **특정 쿼리 몇 개가 유독 느려서** 전체 응답을 끌어내리는 경우다. 그 범인 쿼리를 찾는 것이 튜닝의 첫걸음이다.

## 1단계: 느린 쿼리 로그 켜기

DB에는 "일정 시간 이상 걸린 쿼리를 기록하는" 기능이 있다.

```sql
-- MySQL: 1초 이상 걸린 쿼리를 로그에 기록
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- 1초 기준

-- PostgreSQL: postgresql.conf 또는 세션 설정
-- log_min_duration_statement = 1000  (1000ms 이상 기록)
```

이렇게 해두면 느린 쿼리만 로그 파일에 쌓여, 어떤 쿼리가 문제인지 목록으로 확인할 수 있다.

## 2단계: 실행 계획 보기

범인 쿼리를 찾았다면 `EXPLAIN`으로 그 쿼리가 어떻게 실행되는지 들여다본다.

```sql
EXPLAIN ANALYZE
SELECT * FROM orders WHERE user_id = 123 AND status = 'PAID';
```

| 봐야 할 것 | 의미 |
|---|---|
| Full Table Scan (type: ALL) | 인덱스를 못 타고 전체를 훑음 → 인덱스 후보 |
| 예상 행 수 vs 실제 행 수 | 크게 다르면 통계 정보가 오래됐을 수 있음 |
| 정렬(Sort)·임시 테이블 | 메모리·디스크 부담. 인덱스로 개선 가능한지 검토 |

## 3단계: 흔한 원인과 처방

```text
- WHERE 조건 컬럼에 인덱스가 없음 -> 인덱스 추가
- 인덱스가 있는데도 안 탐 -> 함수를 씌우거나(WHERE DATE(col)=...) 타입 불일치
- 너무 많은 데이터를 가져옴 -> 필요한 컬럼만 SELECT, 페이지네이션
- N+1 문제로 쿼리가 반복됨 -> JOIN이나 일괄 조회로 묶기
```

## 실무 포인트

- **`SELECT *`를 습관적으로 쓰지 마라.** 필요 없는 컬럼(특히 큰 텍스트·BLOB)까지 가져오면 네트워크와 메모리 부담이 커진다. 실제로 쓰는 컬럼만 명시하는 것이 기본이다.
- **인덱스를 걸었는데도 안 타는 대표적 원인은 컬럼에 함수를 씌우는 것이다.** `WHERE DATE(created_at) = '2026-09-04'`는 인덱스를 못 타지만, `WHERE created_at >= '2026-09-04' AND created_at < '2026-09-05'`로 바꾸면 인덱스를 탈 수 있다.
- **운영 DB에서 무거운 `EXPLAIN ANALYZE`를 함부로 돌리지 마라.** `ANALYZE`는 실제로 쿼리를 실행하므로, `UPDATE`/`DELETE`에 붙이면 데이터가 진짜 바뀐다. 조회 쿼리에만, 가능하면 복제본에서 확인하는 것이 안전하다.

## 마무리 요약

- 느린 쿼리 로그를 켜서 어떤 쿼리가 느린지 먼저 목록으로 확인하는 것이 시작점이다.
- 범인 쿼리는 `EXPLAIN`으로 실행 계획을 보고, Full Table Scan 여부부터 확인한다.
- 인덱스 누락, 컬럼에 함수 씌우기, `SELECT *` 남용이 초보자가 만드는 대표적인 느린 쿼리 원인이다.

## 참고 자료

- [MySQL 공식 문서 - 슬로우 쿼리 로그](https://dev.mysql.com/doc/refman/8.0/en/slow-query-log.html)
- [PostgreSQL 공식 문서 - EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
