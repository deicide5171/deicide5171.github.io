---
layout: single
title: "도커 네트워크가 뭔가요 — 컨테이너끼리 통신하기"
date: 2026-09-19 13:40:00 +0530
categories: infra
tags: ["docker", "network", "컨테이너", "통신", "입문"]
toc: true
toc_sticky: true
excerpt: "컨테이너끼리 어떻게 서로를 찾고 통신하는지, 도커 네트워크의 기본 개념과 bridge 네트워크 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## "앱 컨테이너가 DB 컨테이너에 연결이 안 된다"

앱과 DB를 각각 컨테이너로 띄웠는데 `localhost:5432`로 붙으면 연결이 안 된다. 컨테이너는 저마다 격리된 네트워크를 가져서, 한 컨테이너의 `localhost`는 다른 컨테이너가 아니다. 이때 필요한 게 **도커 네트워크**다.

## 같은 네트워크에 묶기

```bash
# 사용자 네트워크 생성
docker network create myapp-net

# 두 컨테이너를 같은 네트워크에
docker run --network myapp-net --name db postgres
docker run --network myapp-net --name app myapp

# app에서 DB 주소는 localhost가 아니라 "db"
#   → postgres://db:5432
```

같은 사용자 정의 bridge 네트워크에 있으면, **컨테이너 이름이 곧 호스트명**이 되어 서로를 찾을 수 있다.

## 네트워크 종류

| 종류 | 특징 |
|---|---|
| bridge | 기본. 같은 호스트 안 컨테이너끼리 통신 |
| host | 호스트 네트워크를 그대로 공유(격리 없음) |
| none | 네트워크 없음(완전 격리) |

## 실무 포인트

- **사용자 네트워크를 만들어 붙여라.** 기본 bridge에서는 이름으로 서로를 못 찾는다. `docker network create`로 만든 네트워크에 함께 넣어야 이름 기반 통신이 된다.
- **연결 주소는 컨테이너 이름.** 앱 설정에서 DB 주소를 `localhost`가 아니라 컨테이너 이름(`db`)으로 적는다.
- **docker compose는 자동으로 묶는다.** compose로 여러 서비스를 정의하면 같은 네트워크에 자동 배치돼, 서비스 이름으로 바로 통신된다.

## 마무리 요약

- 컨테이너는 격리돼 있어 `localhost`로는 다른 컨테이너에 못 붙는다.
- 같은 사용자 정의 네트워크에 넣으면 컨테이너 이름으로 서로를 찾는다.
- compose는 서비스들을 자동으로 한 네트워크에 묶어준다.

## 참고 자료

- [Docker 공식 문서 - Networking](https://docs.docker.com/network/)
