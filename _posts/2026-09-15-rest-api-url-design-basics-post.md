---
layout: single
title: "REST API URL 설계가 뭔가요 — 좋은 엔드포인트 짓는 규칙"
date: 2026-09-15 12:25:00 +0530
categories: backend
tags: ["restapi", "url설계", "엔드포인트", "api", "입문"]
toc: true
toc_sticky: true
excerpt: "REST API에서 예측 가능하고 일관된 URL(엔드포인트)을 짓는 기본 규칙을 처음 배우는 사람 기준으로 정리했다."
---

## URL을 마음대로 지으면 헷갈린다

`/getUser`, `/user_list`, `/deleteUserById`처럼 규칙 없이 URL을 지으면, API를 쓰는 사람이 매번 문서를 봐야 한다. **REST API URL 설계**는 **자원(리소스) 중심의 일관된 규칙**으로 URL을 지어, 예측 가능하고 이해하기 쉽게 만드는 것이다.

## 핵심 규칙

| 규칙 | 좋은 예 | 나쁜 예 |
|---|---|---|
| 명사(자원)로 | `/users` | `/getUsers` |
| 복수형 | `/users/1` | `/user/1` |
| 동작은 HTTP 메서드로 | `DELETE /users/1` | `/deleteUser?id=1` |
| 계층은 경로로 | `/users/1/orders` | `/getUserOrders` |

## 메서드로 동작 표현

```text
GET    /users      목록 조회
GET    /users/1    1번 조회
POST   /users      생성
PUT    /users/1    수정(전체)
DELETE /users/1    삭제

-> URL엔 "무엇(자원)", 메서드엔 "무엇을 할지(동작)"
```

## 실무 포인트

- **동사를 URL에 넣지 마라.** "조회·생성·삭제" 같은 동작은 HTTP 메서드(GET/POST/DELETE)로 표현한다. URL엔 자원 이름(명사)만 둔다. `/createUser`가 아니라 `POST /users`다.
- **필터·정렬·페이징은 쿼리 파라미터로.** `/users?role=admin&sort=name&page=2`처럼 조건은 쿼리스트링에 둔다. 경로는 자원 식별에만 쓴다.
- **일관성이 최고의 문서다.** 규칙을 팀 전체가 일관되게 지키면, 새 엔드포인트도 이름만 보고 동작을 짐작할 수 있다. 예외를 남발하면 규칙의 의미가 사라진다.

## 마무리 요약

- REST API URL 설계는 자원(명사) 중심의 일관된 규칙으로 예측 가능한 엔드포인트를 짓는 것이다.
- URL엔 자원 이름을, 동작은 HTTP 메서드로 표현한다(`POST /users` 등).
- 조건은 쿼리 파라미터로 두고, 팀이 규칙을 일관되게 지키는 것이 가장 좋은 문서다.

## 참고 자료

- [Microsoft - REST API 설계 가이드](https://learn.microsoft.com/ko-kr/azure/architecture/best-practices/api-design)
