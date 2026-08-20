---
layout: single
title: "N+1 문제가 뭔가요 — 쿼리가 갑자기 수백 번 나가는 이유"
date: 2026-09-03 13:35:00 +0530
categories: database
tags: ["n+1문제", "orm", "쿼리성능", "데이터베이스기초", "입문"]
toc: true
toc_sticky: true
excerpt: "ORM을 쓰면 나도 모르게 발생하는 N+1 문제가 왜 성능을 망치는지, 코드 예제로 원인과 해결의 기본 아이디어를 정리했다."
---

## 리스트 하나 조회했을 뿐인데 쿼리가 수백 번

게시글 목록 10개를 조회했을 뿐인데 DB 로그를 보니 쿼리가 11번, 100개를 조회하니 101번 나가는 경우가 있다. 이것이 **N+1 문제**다. 목록을 가져오는 쿼리 1번 + 각 항목의 연관 데이터를 가져오는 쿼리 N번이 따로 나가서, 데이터가 많아질수록 쿼리 수가 선형으로 폭증한다.

## 왜 발생하는가

```java
// 게시글 목록을 가져오는 쿼리 1번
List<Post> posts = postRepository.findAll();

// 각 게시글의 작성자 이름에 접근할 때마다 쿼리가 추가로 나간다
for (Post post : posts) {
    System.out.println(post.getAuthor().getName());
    // -> 게시글마다 SELECT * FROM users WHERE id = ? 가 한 번씩!
}
```

게시글이 100개면 `getAuthor()`에 접근하는 순간마다 작성자 조회 쿼리가 100번 나가서, 총 1(목록) + 100(작성자) = 101번의 쿼리가 실행된다. ORM이 연관 데이터를 "실제로 쓸 때 가져오는(지연 로딩)" 특성 때문에 코드만 봐서는 눈치채기 어렵다.

## 해결의 기본 아이디어: 한 번에 가져오기

```java
// JPA: Fetch Join으로 게시글과 작성자를 한 번의 쿼리로 함께 조회
@Query("SELECT p FROM Post p JOIN FETCH p.author")
List<Post> findAllWithAuthor();
// -> 쿼리 1번으로 끝난다
```

핵심 아이디어는 "필요한 연관 데이터를 처음부터 JOIN해서 한 번에 가져오는 것"이다. 각 프레임워크마다 이름은 다르지만(Fetch Join, eager loading, includes 등) 발상은 같다.

## 프레임워크별 해결 키워드

| 프레임워크 | 해결 방법 |
|---|---|
| JPA/Hibernate | Fetch Join, `@EntityGraph`, batch size |
| Django ORM | `select_related`, `prefetch_related` |
| Rails ActiveRecord | `includes` |
| Sequelize(Node) | `include` 옵션 |

## 실무 포인트

- **N+1은 개발 단계에서는 데이터가 적어 잘 안 보이다가, 운영에서 데이터가 쌓이면 갑자기 느려진다.** 개발 중에 ORM이 실제로 날리는 SQL 로그를 켜두고 확인하는 습관이 중요하다.
- **무조건 다 JOIN하는 것도 답이 아니다.** 연관 데이터를 항상 즉시 로딩(eager)하도록 설정하면, 그 데이터가 필요 없는 화면에서도 불필요한 JOIN이 발생한다. "이 화면에서 실제로 쓰는 데이터"만 함께 가져오도록 쿼리별로 조절하는 것이 좋다.
- **연관관계가 여러 단계로 깊으면 Fetch Join만으로 부족할 수 있다.** 이 경우 batch size 설정이나 별도 쿼리로 나눠 가져오는 전략을 조합해야 한다.

## 마무리 요약

- N+1 문제는 목록 조회 1번 + 각 항목의 연관 데이터 조회 N번이 따로 나가 쿼리가 폭증하는 현상이다.
- ORM의 지연 로딩 특성 때문에 코드만 봐서는 눈치채기 어렵고, SQL 로그로 확인해야 한다.
- Fetch Join 등으로 필요한 연관 데이터를 한 번에 가져오는 것이 기본 해결책이며, 화면별로 필요한 만큼만 조절하는 것이 좋다.

## 참고 자료

- [Hibernate 공식 문서 - Fetch 전략](https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html#fetching)
- [Django 공식 문서 - select_related/prefetch_related](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related)
