---
layout: single
title: "개발·운영 설정 분리하기 — Spring 프로파일 기초"
date: 2026-09-07 12:25:00 +0530
categories: backend
tags: ["spring", "profile", "설정관리", "환경분리", "입문"]
toc: true
toc_sticky: true
excerpt: "로컬·개발·운영 환경마다 다른 설정을 어떻게 분리해 관리할지, Spring 프로파일의 기본 개념과 사용법을 정리했다."
---

## 로컬 DB와 운영 DB 주소가 다른데

로컬에서는 로컬 DB에, 운영에서는 운영 DB에 연결해야 한다. 로그 레벨도 개발은 DEBUG, 운영은 INFO로 다르게 하고 싶다. 이 설정들을 코드에 하드코딩하거나 배포할 때마다 바꾸면 실수가 생긴다. **Spring 프로파일(Profile)**은 환경별 설정을 파일로 분리해두고, 실행 시 어느 환경인지만 지정하면 알맞은 설정이 적용되게 하는 기능이다.

## 프로파일별 설정 파일

```text
application.yml          # 공통 설정
application-local.yml    # 로컬 전용
application-dev.yml      # 개발 서버 전용
application-prod.yml     # 운영 전용

실행 시 활성 프로파일만 지정하면
공통 설정 + 해당 프로파일 설정이 합쳐져 적용된다.
```

## 예제

```yaml
# application-local.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb
logging:
  level:
    root: DEBUG

# application-prod.yml
spring:
  datasource:
    url: jdbc:mysql://prod-db.internal:3306/mydb
logging:
  level:
    root: INFO
```

## 프로파일 활성화 방법

```bash
# 실행 시 활성 프로파일 지정
java -jar app.jar --spring.profiles.active=prod

# 또는 환경변수로
export SPRING_PROFILES_ACTIVE=prod
```

`prod`를 활성화하면 `application-prod.yml`이 공통 설정 위에 덮여 적용된다. 코드는 그대로 두고 실행 옵션만 바꾸면 환경이 전환된다.

## 실무 포인트

- **운영 비밀번호·키는 설정 파일에 넣지 말고 환경변수나 시크릿 매니저로 주입하라.** `application-prod.yml`에 DB 비밀번호를 적어 저장소에 올리면 유출된다. 민감한 값은 파일이 아니라 실행 환경에서 주입받는 것이 안전하다.
- **`@Profile` 애노테이션으로 특정 환경에서만 동작하는 빈을 만들 수 있다.** 예를 들어 로컬에서만 쓰는 목(mock) 구현이나 개발용 초기 데이터 로더를 `@Profile("local")`로 지정하면 운영에서는 로드되지 않는다.
- **활성 프로파일을 실수로 안 지정하면 기본(default)으로 뜬다.** 운영 배포 시 프로파일 지정을 빠뜨리면 개발 설정으로 운영 서버가 뜨는 사고가 날 수 있으므로, 배포 스크립트에서 프로파일 지정을 반드시 확인해야 한다.

## 마무리 요약

- Spring 프로파일은 환경별 설정을 파일로 분리하고 실행 시 활성 프로파일만 지정해 전환하는 기능이다.
- 공통 설정에 프로파일별 설정이 덮여 적용되며, 코드 변경 없이 실행 옵션만으로 환경을 바꿀 수 있다.
- 비밀번호·키는 파일이 아니라 환경변수·시크릿 매니저로 주입하고, 배포 시 프로파일 지정을 반드시 확인해야 한다.

## 참고 자료

- [Spring 공식 문서 - 프로파일](https://docs.spring.io/spring-boot/reference/features/profiles.html)
