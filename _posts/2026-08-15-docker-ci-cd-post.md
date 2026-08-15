---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — Docker와 CI/CD 파이프라인"
date: 2026-08-15 13:10:00 +0530
categories: dev-insight
tags: ["docker", "ci-cd", "devops", "github-actions", "학습로드맵"]
toc: true
toc_sticky: true
excerpt: "Flutter 앱, 네이버 클라우드 지도 API, PostGIS 공간 DB, AI 에이전트 프로토콜, 분산 시스템까지 다뤄온 이 블로그의 다음 학습 주제로 Docker와 CI/CD 파이프라인을 추천하는 이유를 정리한다."
---

## 왜 지금 이 주제인가

이 블로그는 지금까지 Flutter 앱 개발, 네이버 클라우드 지도 API 연동, PostGIS 기반 공간 데이터, 그리고 최근에는 AI 에이전트 프로토콜(MCP, A2A)과 분산 시스템(분산 SQL, 캐시 스탬피드)까지 폭넓게 다뤄왔다. 그런데 이 글들을 관통하는 공통 질문이 하나 빠져 있다. "이렇게 만든 것을 어떻게 일관되게, 반복 가능하게, 안전하게 배포할 것인가"이다.

Virtual Threads 도입이나 분산 SQL 마이그레이션처럼 지금까지 다룬 시스템 설계·백엔드 지식이 실제로 힘을 발휘하려면, 그 변경 사항을 안정적으로 검증하고 배포하는 파이프라인이 뒷받침되어야 한다. 코드/인프라 지식이 쌓일수록 "로컬에서는 되는데 배포하면 깨지는" 문제, "테스트를 깜빡하고 배포하는" 문제가 더 아프게 다가온다. 그래서 다음 학습 주제로 **Docker 컨테이너화**와 **CI/CD 파이프라인**을 추천한다.

## 학습 로드맵

| 단계 | 주제 | 왜 필요한가 |
|---|---|---|
| 1 | Dockerfile 작성·멀티스테이지 빌드 | "내 컴퓨터에서는 됐는데" 문제를 근본적으로 없앤다 |
| 2 | docker-compose로 로컬 개발 환경 구성 | DB·캐시·앱을 한 번에 띄워 로컬-운영 환경 격차를 줄인다 |
| 3 | GitHub Actions로 테스트 자동화 | PR마다 자동으로 검증해 리그레션을 조기에 잡는다 |
| 4 | 이미지 빌드·레지스트리 푸시 자동화 | 배포 아티팩트를 재현 가능하게 관리한다 |
| 5 | 배포 전략(블루-그린, 롤링) | 무중단 배포와 빠른 롤백 체계를 갖춘다 |

이 순서대로 학습하면 "코드 작성 → 검증 → 배포"까지 하나의 흐름으로 자동화하는 감각을 자연스럽게 익힐 수 있다.

## 핵심 개념: 멀티스테이지 빌드와 CI 캐시

**멀티스테이지 빌드**는 하나의 Dockerfile 안에서 "빌드용 이미지"와 "실행용 이미지"를 분리해, 최종 이미지에는 빌드 도구·소스 코드 없이 실행에 필요한 산출물만 남기는 기법이다. 이미지 크기가 줄고 공격 표면도 좁아진다.

CI 파이프라인에서는 **캐시 전략**이 속도를 좌우한다. 의존성 설치 단계(예: `npm ci`, Gradle 의존성 다운로드)를 별도 레이어로 분리하고 캐시를 적극 활용하면, 코드만 바뀐 배포에서 전체 빌드 시간을 크게 줄일 수 있다.

## 예제: 멀티스테이지 Dockerfile과 GitHub Actions

```dockerfile
# 1단계: 빌드
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 2단계: 실행
FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
CMD ["node", "dist/main.js"]
```

```yaml
# .github/workflows/ci.yml
name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: 'npm' }
      - run: npm ci
      - run: npm test
```

## 실무 포인트

- **`.dockerignore`를 꼭 작성한다**: `node_modules`, `.git` 같은 불필요한 파일이 빌드 컨텍스트에 포함되면 빌드가 느려지고 이미지가 불필요하게 커진다.
- **환경 변수와 시크릿을 분리한다**: 이미지에 비밀값을 하드코딩하지 말고, CI/CD 플랫폼의 시크릿 관리 기능이나 별도 시크릿 매니저를 사용한다.
- **테스트 실패 시 배포를 반드시 막는다**: 파이프라인에서 테스트 스텝이 실패하면 이후 빌드·배포 스텝이 실행되지 않도록 의존성을 명시한다.
- **작게 시작한다**: 처음부터 완벽한 배포 전략을 짜기보다, "PR마다 테스트 자동 실행" 하나만이라도 먼저 도입해 습관을 들이는 편이 낫다.

## 3줄 요약

- 지금까지 다룬 웹·Flutter·GIS·AI·시스템 설계 지식이 실전에서 힘을 발휘하려면 안정적인 배포 파이프라인이 필요하다.
- Dockerfile 멀티스테이지 빌드로 재현 가능한 이미지를 만들고, GitHub Actions로 테스트·빌드·배포를 자동화하는 것이 다음 학습의 핵심이다.
- `.dockerignore`, 시크릿 분리, 테스트 실패 시 배포 차단부터 작게 시작하는 것을 추천한다.

## 참고 자료

- [Docker — Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [GitHub Actions 공식 문서](https://docs.github.com/actions)
- [The Twelve-Factor App](https://12factor.net/)
