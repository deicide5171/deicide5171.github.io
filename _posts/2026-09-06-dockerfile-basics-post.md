---
layout: single
title: "Dockerfile 처음 써보기 — 내 앱을 컨테이너 이미지로 만들기"
date: 2026-09-06 13:40:00 +0530
categories: infra
tags: ["dockerfile", "docker", "컨테이너이미지", "입문", "빌드"]
toc: true
toc_sticky: true
excerpt: "내 애플리케이션을 어디서든 똑같이 실행되는 컨테이너 이미지로 만드는 Dockerfile의 기본 명령과 작성법을 처음 배우는 사람 기준으로 정리했다."
---

## "내 컴퓨터에선 되는데"를 없애는 법

"내 컴퓨터에선 되는데 서버에선 안 돼요"는 환경 차이(OS, 버전, 라이브러리) 때문에 생긴다. **Dockerfile**은 앱을 실행하는 데 필요한 모든 것(코드, 런타임, 의존성)을 하나의 이미지로 굳혀, 어디서든 똑같이 실행되게 만드는 설계도다. 이 이미지로 컨테이너를 띄우면 내 컴퓨터든 서버든 동일한 환경이 재현된다.

## 자주 쓰는 Dockerfile 명령

| 명령 | 역할 |
|---|---|
| FROM | 베이스 이미지 지정(출발점) |
| WORKDIR | 작업 디렉터리 설정 |
| COPY | 파일을 이미지 안으로 복사 |
| RUN | 이미지 빌드 중 명령 실행(의존성 설치 등) |
| EXPOSE | 컨테이너가 사용하는 포트 명시 |
| CMD | 컨테이너 시작 시 실행할 명령 |

## 예제: Node.js 앱 Dockerfile

```dockerfile
# 1. 베이스 이미지 (Node.js가 설치된 리눅스)
FROM node:20-alpine

# 2. 작업 디렉터리
WORKDIR /app

# 3. 의존성 먼저 복사·설치 (캐시 활용)
COPY package*.json ./
RUN npm ci

# 4. 나머지 소스 복사
COPY . .

# 5. 포트 명시
EXPOSE 3000

# 6. 시작 명령
CMD ["node", "server.js"]
```

## 빌드와 실행

```bash
# 이미지 빌드 (-t로 이름 태그)
docker build -t my-app .

# 컨테이너 실행 (호스트 8080 -> 컨테이너 3000)
docker run -p 8080:3000 my-app
```

## 실무 포인트

- **의존성 설치와 소스 복사를 분리하면 빌드 캐시가 잘 먹는다.** 위 예제에서 `package.json`을 먼저 복사해 `npm ci`를 하고, 그 뒤에 나머지 소스를 복사한 이유가 이것이다. 소스만 바뀌면 의존성 설치 단계는 캐시를 재사용해 빌드가 빨라진다.
- **`.dockerignore`로 불필요한 파일을 제외하라.** `node_modules`, `.git` 등을 이미지에 넣으면 크기가 커지고 빌드가 느려진다. `.gitignore`처럼 `.dockerignore`를 작성해 제외한다.
- **가벼운 베이스 이미지와 멀티스테이지 빌드를 검토하라.** `alpine` 같은 경량 이미지를 쓰고, 빌드용과 실행용 스테이지를 나누면(멀티스테이지) 최종 이미지 크기를 크게 줄일 수 있다.

## 마무리 요약

- Dockerfile은 앱 실행에 필요한 모든 것을 이미지로 굳혀 어디서든 같은 환경을 재현하는 설계도다.
- FROM·WORKDIR·COPY·RUN·CMD 등의 명령으로 이미지를 층층이 쌓아 만든다.
- 의존성과 소스 복사를 분리해 캐시를 활용하고, `.dockerignore`와 경량 이미지로 크기를 줄이는 것이 실무 포인트다.

## 참고 자료

- [Docker 공식 문서 - Dockerfile 작성](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
