---
layout: single
title: "SQL HAVING과 WHERE 차이가 뭔가요 — 헷갈리는 조건절 정리"
date: 2026-09-19 12:35:00 +0530
categories: database
tags: ["sql", "having", "where", "groupby", "입문"]
toc: true
toc_sticky: true
excerpt: "집계 결과에 조건을 걸 때 WHERE가 안 먹히는 이유와 HAVING을 써야 하는 경우를 처음 배우는 사람 기준으로 정리했다."
---

## "GROUP BY 결과에 조건을 걸었더니 에러가 났다"

`WHERE COUNT(*) > 5` 같은 조건을 걸면 에러가 난다. 집계 함수 결과에는 WHERE를 쓸 수 없기 때문이다. 이럴 때 쓰는 게 **HAVING**이다. WHERE와 HAVING은 조건을 거는 **시점**이 다르다.

## 언제 무엇을 쓰나

```sql
-- WHERE: 그룹으로 묶기 "전" 개별 행을 거른다
-- HAVING: 그룹으로 묶은 "후" 집계 결과를 거른다

SELECT dept, COUNT(*) AS cnt
FROM employee
WHERE salary >= 3000        -- 개별 행 필터 (묶기 전)
GROUP BY dept
HAVING COUNT(*) > 5;        -- 집계 결과 필터 (묶은 후)
```

## 실행 순서로 이해하기

| 순서 | 절 | 하는 일 |
|---|---|---|
| 1 | WHERE | 개별 행을 먼저 거른다 |
| 2 | GROUP BY | 남은 행을 그룹으로 묶는다 |
| 3 | HAVING | 묶인 그룹을 집계 결과로 거른다 |

WHERE는 묶기 전이라 `COUNT(*)` 같은 집계값을 아직 모른다. 그래서 집계 조건은 HAVING에서만 쓸 수 있다.

## 실무 포인트

- **가능하면 WHERE로 먼저 걸러라.** WHERE가 행을 미리 줄이면 그룹으로 묶을 대상이 적어져 더 빠르다. HAVING은 묶은 뒤라 이미 계산이 끝난 상태다.
- **집계 조건만 HAVING으로.** `HAVING dept = 'sales'`처럼 집계가 아닌 조건을 HAVING에 넣으면 비효율적이다. 이런 건 WHERE로 옮긴다.
- **둘 다 쓸 수 있다.** WHERE로 개별 행을 거르고, HAVING으로 그룹 결과를 거르는 조합이 흔하다.

## 마무리 요약

- WHERE는 그룹으로 묶기 전 개별 행을, HAVING은 묶은 후 집계 결과를 거른다.
- `COUNT(*) > 5` 같은 집계 조건은 HAVING에서만 쓸 수 있다.
- 성능을 위해 가능한 조건은 WHERE로 먼저 걸러 대상을 줄인다.

## 참고 자료

- [PostgreSQL 문서 - GROUP BY and HAVING](https://www.postgresql.org/docs/current/tutorial-agg.html)
