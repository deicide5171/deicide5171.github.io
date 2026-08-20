---
layout: single
title: "도커 볼륨이 뭔가요 — 컨테이너 데이터 영구 저장하기"
date: 2026-09-19 12:40:00 +0530
categories: infra
tags: ["docker", "volume", "데이터", "영속성", "입문"]
toc: true
toc_sticky: true
excerpt: "컨테이너를 지워도 데이터가 남게 해주는 도커 볼륨(volume)의 개념과 bind mount와의 차이를 처음 배우는 사람 기준으로 정리했다."
---

## "컨테이너를 지웠더니 DB 데이터가 사라졌다"

컨테이너 안에 저장한 파일은 컨테이너를 삭제하면 같이 사라진다. DB 컨테이너를 재생성했더니 데이터가 날아간 경험이 여기서 온다. 컨테이너와 **분리해서 데이터를 남기는 방법**이 도커 볼륨(volume)이다.

## 볼륨과 bind mount

```bash
# 볼륨: 도커가 관리하는 저장소
docker volume create mydata
docker run -v mydata:/var/lib/mysql mysql

# bind mount: 호스트의 특정 경로를 직접 연결
docker run -v /home/user/data:/var/lib/mysql mysql
```

| 방식 | 저장 위치 | 쓰임 |
|---|---|---|
| volume | 도커가 관리하는 영역 | 운영 데이터(권장) |
| bind mount | 호스트의 지정 경로 | 개발 중 소스 코드 연결 |

## 왜 볼륨을 쓰나

컨테이너의 파일 시스템은 컨테이너 수명과 함께한다. 볼륨은 컨테이너 밖에 있어서, 컨테이너를 지우고 새로 만들어도 같은 볼륨을 붙이면 데이터가 그대로 남는다.

## 실무 포인트

- **DB·업로드 파일은 반드시 볼륨에.** 재배포 때마다 데이터가 날아가지 않으려면 상태가 있는 데이터는 볼륨에 저장한다.
- **개발엔 bind mount가 편하다.** 호스트의 소스 폴더를 컨테이너에 연결하면 코드 수정이 즉시 반영돼 개발 반복이 빨라진다.
- **`docker volume ls`로 관리.** 안 쓰는 볼륨이 쌓여 디스크를 잡아먹을 수 있으니 `docker volume prune`으로 정리한다(삭제 전 사용 여부 확인).

## 마무리 요약

- 컨테이너 안 파일은 컨테이너와 함께 사라지므로, 남길 데이터는 볼륨에 저장한다.
- 볼륨은 도커가 관리하는 영역, bind mount는 호스트 경로 직접 연결이다.
- 운영 데이터는 볼륨, 개발 중 소스 연결은 bind mount가 어울린다.

## 참고 자료

- [Docker 공식 문서 - Volumes](https://docs.docker.com/storage/volumes/)
