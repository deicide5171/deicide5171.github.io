---
layout: single
title: "도커 컴포즈가 뭔가요 — 여러 컨테이너를 한 번에 실행하기"
date: 2026-09-15 12:40:00 +0530
categories: infra
tags: ["도커컴포즈", "dockercompose", "docker", "컨테이너", "입문"]
toc: true
toc_sticky: true
excerpt: "웹·DB·캐시처럼 여러 컨테이너를 한 파일로 정의해 한 번에 실행하는 도커 컴포즈의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 컨테이너를 매번 하나씩 띄우기 번거롭다

개발 환경에서 웹 서버, DB, Redis를 함께 띄우려면 `docker run`을 각각 실행하고 옵션(포트·볼륨·네트워크)을 일일이 지정해야 한다. **도커 컴포즈(Docker Compose)**는 **여러 컨테이너의 구성을 하나의 YAML 파일에 적어두고, 명령 한 줄로 전부 실행**하게 해준다.

## docker-compose.yml 예시

```text
services:
  web:
    build: .
    ports: ["8080:80"]
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
    volumes: ["dbdata:/var/lib/postgresql/data"]
volumes:
  dbdata:
```

## 명령

| 명령 | 하는 일 |
|---|---|
| `docker compose up` | 모든 서비스 실행 |
| `docker compose up -d` | 백그라운드 실행 |
| `docker compose down` | 전부 중지·삭제 |
| `docker compose logs` | 로그 보기 |

## 실무 포인트

- **로컬 개발 환경에 딱 맞다.** 팀원이 `docker compose up` 한 줄로 동일한 개발 환경(웹+DB+캐시)을 띄울 수 있다. "내 PC에선 됐는데" 문제를 줄이는 데 효과적이다.
- **서비스끼리 이름으로 통신.** 컴포즈가 만든 네트워크 안에서 서비스는 이름으로 서로 부른다. 웹 컨테이너가 DB에 접속할 때 호스트를 `db`(서비스 이름)로 쓰면 된다.
- **운영 배포는 오케스트레이터로.** 컴포즈는 단일 호스트에서 여러 컨테이너를 띄우는 데 적합하다. 여러 서버에 걸친 대규모 운영은 쿠버네티스 같은 오케스트레이터를 쓴다.

## 마무리 요약

- 도커 컴포즈는 여러 컨테이너 구성을 하나의 YAML에 적어 명령 한 줄로 실행하는 도구다.
- `docker compose up`으로 전부 띄우고, 서비스는 이름으로 서로 통신한다.
- 로컬 개발 환경 통일에 유용하며, 대규모 운영은 쿠버네티스로 넘어간다.

## 참고 자료

- [Docker 공식 문서 - Compose](https://docs.docker.com/compose/)
