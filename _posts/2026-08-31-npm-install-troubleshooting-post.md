---
layout: single
title: "npm install이 자꾸 실패할 때 — 캐시와 lock 파일 문제 해결"
date: 2026-08-31 14:30:00 +0530
categories: frontend
tags: ["npm", "트러블슈팅", "패키지매니저", "package-lock", "입문"]
toc: true
toc_sticky: true
excerpt: "npm install이 원인 모를 에러로 실패할 때, 캐시 손상과 lock 파일 충돌을 구분해서 해결하는 순서를 정리했다."
---

## 왜 어제까지 되던 install이 갑자기 안 될까

`npm install`이 갑자기 실패하기 시작하면 대부분 코드 문제가 아니라 **로컬 환경 상태**의 문제다. Node 버전이 바뀌었거나, 캐시가 손상됐거나, 다른 브랜치의 `package-lock.json`과 충돌하는 경우가 대부분을 차지한다. 에러 메시지를 하나하나 검색하기보다 아래 순서대로 좁혀가는 것이 빠르다.

## 흔한 에러와 원인

| 에러 메시지 | 주된 원인 |
|---|---|
| `ERESOLVE unable to resolve dependency tree` | 패키지 간 버전 충돌(peer dependency) |
| `EINTEGRITY` / `Integrity checksum failed` | npm 캐시 손상 |
| `ENOENT: no such file or directory` | node_modules가 반쯤 삭제된 상태 |
| `gyp ERR! build error` | 네이티브 모듈 빌드 실패(빌드 도구 미설치) |

## 진단 및 해결 순서

```bash
# 1. Node/npm 버전 확인 (프로젝트가 요구하는 버전과 다른지)
node -v
npm -v
cat package.json | grep '"engines"' -A 3

# 2. 캐시 손상 의심 시 캐시 정리
npm cache clean --force

# 3. 확실한 초기화 (가장 흔한 해결책)
rm -rf node_modules package-lock.json
npm install

# 4. 그래도 안 되면 ERESOLVE 임시 우회 (근본 해결 아님, 최후 수단)
npm install --legacy-peer-deps
```

3번(완전 초기화)만으로 대부분의 이상 증상은 해결된다. 다만 `--legacy-peer-deps`는 버전 충돌을 강제로 무시하는 것이므로, 팀 프로젝트에서는 왜 충돌이 났는지 원인 패키지를 찾아 버전을 맞추는 것이 더 안전하다.

## 실무 포인트

- **`package-lock.json`을 git에 커밋하지 않으면 팀원마다 다른 버전의 의존성이 설치돼 "내 컴퓨터에서는 되는데" 문제가 생긴다.** 반드시 커밋해야 한다.
- **Node 버전 관리자(nvm, fnm 등)로 프로젝트별 Node 버전을 고정하면** 팀원 간 Node 버전 불일치로 인한 문제를 크게 줄일 수 있다. `.nvmrc` 파일을 프로젝트 루트에 두는 것이 관례다.
- **CI 환경에서는 `npm install` 대신 `npm ci`를 써야 한다.** `npm ci`는 lock 파일을 그대로 신뢰해 설치하므로 재현 가능한 빌드를 보장하고 속도도 더 빠르다.

## 마무리 요약

- 원인 모를 install 실패는 대부분 캐시 손상이나 lock 파일 상태 문제이며, `node_modules`와 `package-lock.json`을 지우고 재설치하면 대부분 해결된다.
- `--legacy-peer-deps`는 임시 우회일 뿐이므로 팀 프로젝트에서는 근본 원인(버전 충돌 패키지)을 찾는 것이 낫다.
- CI에서는 재현성을 위해 `npm install`이 아니라 `npm ci`를 사용해야 한다.

## 참고 자료

- [npm 공식 문서 - npm ci](https://docs.npmjs.com/cli/v10/commands/npm-ci)
- [npm 공식 문서 - 캐시](https://docs.npmjs.com/cli/v10/commands/npm-cache)
