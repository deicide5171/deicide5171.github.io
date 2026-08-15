---
layout: single
title: "컨테이너 이미지 최적화 실전 — 멀티스테이지 빌드로 레이어 다이어트하기"
date: 2026-08-16 13:40:00 +0530
categories: infra
tags: ["docker", "container", "multistage-build", "image-optimization", "devops"]
toc: true
toc_sticky: true
excerpt: "빌드 도구와 소스코드가 그대로 남아 비대해진 컨테이너 이미지를, 멀티스테이지 빌드와 베이스 이미지 선택만으로 가볍고 안전하게 줄이는 실전 방법을 정리한다."
---

## 왜 지금 이미지 크기를 신경 써야 하는가

컨테이너 이미지를 처음 만들 때는 대부분 "일단 동작하게" 만드는 데 집중한다. `FROM node:20`이나 `FROM python:3.12`처럼 익숙한 베이스 이미지 위에 소스를 통째로 복사하고 빌드 도구까지 그대로 남겨둔 채 배포하는 경우가 많다. 문제는 이렇게 만들어진 이미지가 실행에 필요 없는 컴파일러, 패키지 캐시, 소스코드, 테스트 파일까지 껴안고 다닌다는 점이다.

이미지가 무거워지면 레지스트리 푸시·풀 시간이 늘어나고, 오토스케일링이나 롤링 배포 시 새 Pod가 뜨는 시간도 함께 늘어난다. 더 중요한 문제는 보안이다. 이미지 안에 셸, 패키지 매니저, 불필요한 라이브러리가 많을수록 취약점 스캐너가 잡아내는 CVE 개수도, 컨테이너가 뚫렸을 때 공격자가 활용할 수 있는 도구도 늘어난다. Docker/CI-CD 파이프라인을 이미 구축한 팀이라면, 다음 단계는 파이프라인을 통과하는 이미지 자체를 가볍고 좁게 다듬는 것이다.

이 글은 Dockerfile 작성이나 CI/CD 개괄이 아니라, **멀티스테이지 빌드를 이용해 실제로 이미지 크기와 공격 표면을 줄이는 구체적인 기법**에 집중한다.

## 핵심 개념 1: 레이어 캐시는 순서가 전부다

Docker 이미지는 Dockerfile의 각 명령이 만드는 레이어를 쌓아 만든다. 레이어는 위에서부터 순서대로 캐시되며, **한 레이어의 내용이 바뀌면 그 아래 모든 레이어의 캐시가 무효화**된다. 그래서 자주 바뀌는 것(소스코드)은 나중에, 잘 안 바뀌는 것(의존성 목록)은 먼저 `COPY`하는 순서가 빌드 속도를 좌우한다.

| 순서 | 안 좋은 예 | 좋은 예 |
|---|---|---|
| 1 | `COPY . .` (전체 복사) | `COPY package*.json ./` (의존성 명세만) |
| 2 | `RUN npm install` | `RUN npm ci` (캐시 재사용 가능) |
| 3 | `RUN npm run build` | `COPY . .` (소스는 마지막에) |
| 결과 | 소스 한 줄만 바뀌어도 의존성 재설치 | 소스만 바뀌면 설치 단계는 캐시 재사용 |

BuildKit을 사용하면 `RUN --mount=type=cache,target=/root/.npm` 같은 **캐시 마운트**로 의존성 다운로드 캐시를 레이어 밖에 별도로 보관할 수도 있다. 레이어 자체에 캐시 파일이 남지 않으면서도 반복 빌드는 빨라진다.

## 핵심 개념 2: 베이스 이미지 선택이 최종 크기를 결정한다

멀티스테이지 빌드를 아무리 잘 써도 마지막 런타임 스테이지의 베이스 이미지가 무거우면 절반의 효과만 얻는다. 상황에 맞는 베이스를 고르는 것이 중요하다.

| 베이스 유형 | 특징 | 디버깅 편의성 | 주로 쓰는 상황 |
|---|---|---|---|
| 풀(full) 이미지 (예: `debian`, `ubuntu`) | 셸·패키지 매니저 포함, 용량 큼 | 높음 | 로컬 개발, 디버깅이 잦은 초기 단계 |
| `-slim` / `-alpine` 계열 | 최소 유틸리티만 포함 | 중간 | 대부분의 운영 배포 |
| `distroless` | OS 유틸리티·셸 자체가 없음 | 낮음(별도 디버그 태그 필요) | 보안 표면을 최소화해야 하는 운영 |
| `scratch` | 완전히 빈 이미지 | 가장 낮음 | Go 등 정적 바이너리 단일 실행 파일 |

`alpine`은 `musl libc`를 쓰기 때문에 `glibc` 기반으로 컴파일된 바이너리나 일부 네이티브 애드온과 호환성 문제가 생길 수 있다는 점은 감안해야 한다. 무조건 가장 작은 베이스를 고르기보다, 팀의 디버깅 요구 수준과 런타임 호환성을 먼저 따진 뒤 선택하는 편이 안전하다.

## 예제: 캐시 마운트 + distroless 멀티스테이지 Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# 1단계: 의존성 설치 (레이어 캐시 극대화)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# 2단계: 빌드 (풀 의존성 + 소스)
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .
RUN npm run build

# 3단계: 실행 (distroless, 최소 산출물만)
FROM gcr.io/distroless/nodejs20-debian12 AS runtime
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
USER nonroot
EXPOSE 3000
CMD ["dist/main.js"]
```

`deps`와 `build` 스테이지를 분리한 이유는, 운영에 필요한 `node_modules`(devDependencies 제외)와 빌드에만 필요한 전체 의존성을 구분하기 위해서다. 최종 `runtime` 스테이지는 `distroless` 이미지를 베이스로 써서 셸조차 없앴고, `USER nonroot`로 실행해 컨테이너가 침해당하더라도 루트 권한으로 확장되지 않도록 했다.

## 실무 포인트

- **`.dockerignore`를 반드시 관리한다**: `node_modules`, `.git`, 테스트 픽스처처럼 빌드 컨텍스트에 들어갈 필요 없는 파일을 제외하면 빌드 컨텍스트 전송 자체가 빨라진다.
- **이미지 레이어를 직접 눈으로 확인한다**: `dive` 같은 도구나 `docker history <image>`로 어느 레이어가 용량을 많이 차지하는지 확인하는 습관을 들이면, 어떤 `RUN` 명령을 합치거나 뒷정리해야 할지 바로 보인다.
- **RUN 명령을 논리적으로 묶는다**: `apt-get update && apt-get install ... && rm -rf /var/lib/apt/lists/*`처럼 설치와 캐시 삭제를 한 레이어 안에서 끝내야 실제로 용량이 줄어든다. 별도 `RUN`으로 나누면 이전 레이어에 이미 남은 캐시는 지워지지 않는다.
- **버전을 태그로 고정한다**: `latest` 태그는 재현성을 깨뜨린다. `node:20.x-alpine`처럼 구체적인 버전을 명시해 빌드마다 다른 이미지가 섞여 들어가는 상황을 막는다.
- **distroless·scratch 전환 전 디버깅 경로부터 확보한다**: 셸이 없는 이미지는 운영 중 문제가 생겼을 때 `docker exec`로 들어가 확인하는 것이 불가능하다. 구조화 로깅과 별도 디버그용 이미지 태그를 함께 준비해두는 편이 안전하다.

## 3줄 요약

- 레이어는 위에서부터 캐시되므로, 자주 바뀌지 않는 의존성 설치를 먼저, 소스 복사를 나중에 배치하는 순서 하나만으로도 빌드 속도가 달라진다.
- 멀티스테이지 빌드로 빌드 도구·소스·캐시를 최종 이미지에서 걷어내고, `distroless`나 `scratch`처럼 좁은 런타임 베이스를 선택하면 이미지 크기와 공격 표면을 함께 줄일 수 있다.
- 셸이 없는 최소 이미지로 전환하기 전에는 `dive` 등으로 레이어를 직접 점검하고, 디버깅 경로(로깅, 디버그 태그)를 먼저 마련해두는 것이 안전하다.

## 참고 자료

- [Docker — Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker — BuildKit cache mounts](https://docs.docker.com/build/cache/optimize/)
- [Google — Distroless container images (GitHub)](https://github.com/GoogleContainerTools/distroless)
- [dive — 이미지 레이어 분석 도구 (GitHub)](https://github.com/wagoodman/dive)
