---
layout: single
title: "GitHub Actions 빌드가 느릴 때 — 캐시 전략으로 CI 시간 줄이기"
date: 2026-09-21 13:40:00 +0530
categories: infra
tags: ["githubactions", "ci캐시", "빌드최적화", "cicd", "actions-cache"]
toc: true
toc_sticky: true
excerpt: "매 커밋마다 의존성을 처음부터 다시 내려받는 GitHub Actions 워크플로우를, 캐시 키 설계와 레이어별 캐싱으로 실제 빌드 시간을 줄이는 방법을 정리했다."
---

## 왜 지금 CI 캐시를 점검해야 하나

레포지토리 초반에는 CI 파이프라인이 1~2분 안에 끝난다. 의존성이 늘고 테스트 스위트가 커지면서, 어느 순간 PR 하나 올릴 때마다 커피 한 잔 마시고 올 정도로 빌드 시간이 길어진다. 확인해보면 대부분의 시간이 실제 컴파일이나 테스트가 아니라 `npm install`, `./gradlew build`, `pip install -r requirements.txt` 같은 **의존성 설치 단계**에서 소모되고 있다. 매 실행마다 동일한 패키지를 네트워크로 다시 받아오는 것은 명백한 낭비인데도, 워크플로우 파일에 캐시 설정을 아예 하지 않았거나 캐시 키를 잘못 잡아 매번 캐시 미스가 나는 경우가 흔하다.

## 잘못된 캐시 설정과 그 결과

가장 흔한 실수는 캐시 키를 브랜치 이름이나 커밋 SHA처럼 매번 달라지는 값으로 잡는 것이다.

```yaml
# 잘못된 예: 커밋마다 키가 달라져 캐시가 매번 새로 생성됨
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: npm-cache-${{ github.sha }}
```

이렇게 하면 캐시 저장은 되지만 다음 실행에서 정확히 같은 SHA가 다시 나올 일이 없으므로 항상 캐시 미스가 나고, 결국 캐시를 아예 안 쓰는 것과 다를 바 없어진다. 또 다른 실수는 `restore-keys`를 설정하지 않아, 정확히 일치하는 키가 없으면 폴백 없이 바로 빈손으로 시작하는 것이다. 의존성 파일이 아주 조금만 바뀌어도 캐시를 통째로 못 쓰게 되는 셈이다.

## 올바른 캐시 키 설계

핵심 원칙은 **"의존성 정의 파일의 내용이 바뀔 때만 캐시 키가 바뀌게 하는 것"**이다.

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: npm-${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      npm-${{ runner.os }}-
```

`hashFiles('**/package-lock.json')`은 락파일 내용이 바뀌지 않는 한 항상 같은 값을 반환하므로, 같은 의존성 조합이면 커밋이 달라져도 캐시를 그대로 재사용한다. `restore-keys`는 정확한 키가 없을 때 접두사가 일치하는 가장 최근 캐시를 대신 가져오는 폴백 역할을 한다. 락파일이 살짝 바뀌었어도 대부분의 패키지는 겹치므로, 완전히 새로 받는 것보다 훨씬 빠르다.

언어별 대표 패턴은 이렇다.

| 언어/도구 | 캐시 대상 경로 | 키 기준 파일 |
|---|---|---|
| Node.js (npm) | `~/.npm` 또는 `node_modules` | `package-lock.json` |
| Java (Gradle) | `~/.gradle/caches` | `**/*.gradle*`, `gradle-wrapper.properties` |
| Python (pip) | `~/.cache/pip` | `requirements.txt` |
| Go | `~/go/pkg/mod` | `go.sum` |

setup-node, setup-java 같은 공식 액션은 `cache: 'npm'`처럼 옵션 하나만 켜면 위 캐시 설정을 대신 처리해주므로, 직접 `actions/cache`를 조합하기 전에 사용 중인 setup 액션이 내장 캐시를 지원하는지부터 확인하는 것이 좋다.

## 실무 포인트

- **Docker 레이어 캐시도 별도로 챙겨라.** 컨테이너 이미지를 빌드하는 워크플로우라면 `docker/build-push-action`의 `cache-from`/`cache-to`(GitHub Actions 캐시 백엔드, `type=gha`)를 설정해야 매번 베이스 이미지부터 다시 받는 일을 막을 수 있다.
- **모노레포는 캐시 범위를 세분화하라.** 여러 패키지가 섞인 모노레포에서 락파일 하나로 전체 캐시 키를 잡으면, 한 패키지만 바뀌어도 전체 캐시가 무효화된다. 워크스페이스별로 캐시 키를 나누는 편이 유리하다.
- **캐시 크기 상한을 인지하라.** GitHub Actions 캐시는 저장소당 총량 제한이 있어, 오래된 캐시가 자동으로 밀려난다. 캐시 히트율이 갑자기 떨어졌다면 이 제한에 걸린 건 아닌지 Actions 캐시 관리 화면에서 확인한다.
- **테스트 결과 캐싱과 의존성 캐싱을 혼동하지 마라.** 테스트 결과를 캐싱해 건너뛰는 것은 코드 변경을 놓칠 위험이 있으므로, 의존성 캐싱과는 분리해서 신중히 접근한다.

## 마무리 요약

- 대부분의 CI 시간 낭비는 컴파일이 아니라 의존성 재설치에서 발생하며, 원인은 대개 잘못된 캐시 키 설계다.
- `hashFiles()`로 의존성 정의 파일 기준 캐시 키를 잡고 `restore-keys` 폴백을 함께 설정해야 캐시 히트율이 실질적으로 올라간다.
- Docker 레이어 캐시, 모노레포 캐시 범위, 캐시 용량 제한까지 함께 고려해야 CI 시간을 안정적으로 줄일 수 있다.

## 참고 자료

- [GitHub Actions 공식 문서 - Caching dependencies](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [Docker 공식 문서 - GitHub Actions cache backend](https://docs.docker.com/build/cache/backends/gha/)
