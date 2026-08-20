---
layout: single
title: "로컬에선 되는데 빌드는 실패할 때 — npm run build 에러 잡기"
date: 2026-09-03 13:30:00 +0530
categories: frontend
tags: ["빌드에러", "npm", "트러블슈팅", "배포", "프론트엔드"]
toc: true
toc_sticky: true
excerpt: "개발 서버(npm run dev)에서는 잘 되는데 프로덕션 빌드(npm run build)만 실패하는 흔한 원인을 유형별로 정리했다."
---

## 왜 dev는 되는데 build만 깨지나

"내 컴퓨터에서 `npm run dev`로는 잘 돌아가는데 `npm run build`나 CI에서만 실패한다"는 것은 프론트엔드 개발자가 자주 겪는 상황이다. 개발 서버는 관대하게 동작하지만, 프로덕션 빌드는 타입 검사와 최적화를 더 엄격하게 수행하기 때문에 개발 중에는 넘어갔던 문제가 빌드에서 드러난다.

## 흔한 원인 유형

| 유형 | 증상 | 원인 |
|---|---|---|
| 타입 에러 | `Type error: ...` | dev는 타입 검사를 건너뛰지만 build는 엄격히 검사 |
| 대소문자 파일명 | `Module not found` | 맥/윈도우는 대소문자 무시, 리눅스 CI는 구분 |
| 환경변수 누락 | `undefined`로 빌드됨 | CI에 `.env` 값이 없음 |
| 사용하지 않는 변수 | `error ... is defined but never used` | 린트 규칙이 빌드에서 에러로 취급 |

## 가장 악명 높은 함정: 대소문자

```javascript
// 파일명은 Button.tsx인데
import Button from './components/button'; // 소문자 button

// 맥/윈도우: 파일시스템이 대소문자를 구분하지 않아 통과
// 리눅스 CI: 대소문자를 구분해서 "Module not found" 에러!
```

로컬(맥/윈도우)에서는 파일시스템이 대소문자를 구분하지 않아 잘 되지만, 대부분의 CI 서버(리눅스)는 대소문자를 엄격히 구분한다. import 경로의 대소문자가 실제 파일명과 정확히 일치하는지 확인해야 한다.

## 진단 순서

```bash
# 1. 로컬에서 프로덕션 빌드를 직접 실행해 재현
npm run build

# 2. 에러 메시지의 파일·줄 번호 확인
#    -> 타입 에러인지, 모듈 못 찾음인지, 린트 에러인지 유형 파악

# 3. CI에서만 난다면 Node 버전과 환경변수를 로컬과 비교
node -v          # CI의 Node 버전과 같은지
cat .env.example # 필요한 환경변수가 CI에 다 등록됐는지
```

핵심은 **로컬에서 `npm run dev`가 아니라 `npm run build`를 직접 실행해 문제를 재현하는 것**이다. dev로만 확인하면 빌드 전용 문제는 절대 재현되지 않는다.

## 실무 포인트

- **환경변수는 빌드 시점에 코드에 박히는 경우가 많다.** 프론트엔드 빌드는 `.env` 값을 최종 번들에 포함시키므로, CI에 환경변수를 등록하지 않으면 `undefined`가 그대로 빌드된다. 런타임이 아니라 빌드 시점에 값이 필요하다는 점을 기억해야 한다.
- **CI와 로컬의 Node 버전을 맞춰라.** Node 버전이 다르면 특정 문법이나 패키지가 한쪽에서만 동작할 수 있다. `.nvmrc`나 `package.json`의 `engines` 필드로 버전을 고정하는 것이 좋다.
- **빌드가 메모리 부족으로 죽는 경우도 있다.** 큰 프로젝트는 CI 컨테이너의 메모리 제한에 걸려 `JavaScript heap out of memory`로 실패할 수 있으므로, 이 경우 Node의 메모리 할당량을 늘리는 옵션이 필요하다.

## 마무리 요약

- 개발 서버는 관대하지만 프로덕션 빌드는 타입·최적화를 엄격히 검사해 숨어있던 문제가 드러난다.
- import 경로의 대소문자 불일치는 맥/윈도우에서는 통과하지만 리눅스 CI에서 깨지는 대표적 함정이다.
- 반드시 로컬에서 `npm run build`를 직접 실행해 재현하고, CI와 Node 버전·환경변수를 맞춰야 한다.

## 참고 자료

- [Vite 공식 문서 - 프로덕션 빌드](https://vitejs.dev/guide/build.html)
- [Node.js 공식 문서 - 환경변수](https://nodejs.org/api/process.html#processenv)
