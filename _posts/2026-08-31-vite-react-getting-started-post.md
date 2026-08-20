---
layout: single
title: "Vite로 React 프로젝트 시작하기 — CRA 대신 Vite를 쓰는 이유"
date: 2026-08-31 12:30:00 +0530
categories: frontend
tags: ["vite", "react", "입문", "튜토리얼", "빌드도구"]
toc: true
toc_sticky: true
excerpt: "Create React App이 아니라 Vite로 React 프로젝트를 시작해야 하는 이유와, 설치부터 첫 화면 렌더링까지 따라 하는 실전 가이드."
---

## 왜 지금 Vite인가

몇 년 전까지만 해도 React 프로젝트를 시작하면 `create-react-app`이 정석이었다. 하지만 CRA는 유지보수가 사실상 중단됐고, 개발 서버 구동과 HMR(Hot Module Replacement) 속도가 프로젝트가 커질수록 눈에 띄게 느려진다는 문제가 있었다. Vite는 개발 중에는 번들링 없이 브라우저의 네이티브 ES 모듈을 그대로 활용하고, 배포 시에만 Rollup으로 번들링하는 구조라 체감 속도 차이가 크다.

## CRA와 Vite 핵심 차이

| 항목 | Create React App | Vite |
|---|---|---|
| 개발 서버 시작 속도 | 프로젝트 크기에 비례해 느려짐 | 거의 즉시 (ESM 기반) |
| HMR 속도 | 파일이 많아지면 지연 발생 | 변경된 모듈만 갱신, 빠름 |
| 유지보수 상태 | 사실상 중단 | 활발히 개발 중 |
| 설정 커스터마이징 | eject 필요(비가역적) | `vite.config.js`로 간단히 확장 |

## 코드 예제: 프로젝트 생성부터 실행까지

```bash
# 1. 프로젝트 생성 (React + TypeScript 템플릿)
npm create vite@latest my-app -- --template react-ts

# 2. 의존성 설치
cd my-app
npm install

# 3. 개발 서버 실행
npm run dev
```

`npm run dev`를 실행하면 몇 초 안에 로컬 서버가 뜬다. `src/App.tsx`를 수정하고 저장하면 브라우저가 새로고침 없이 즉시 반영되는 것을 확인할 수 있다.

## 자주 막히는 설정 한 가지: 환경변수

CRA는 `REACT_APP_` 접두사를 요구했지만, Vite는 `VITE_` 접두사를 써야 하고 접근 방식도 다르다.

```javascript
// .env
VITE_API_URL=https://api.example.com

// 코드에서 사용
const apiUrl = import.meta.env.VITE_API_URL;
```

`process.env`가 아니라 `import.meta.env`를 쓴다는 점을 놓치면 값이 `undefined`로 나와 한참 헤매게 된다.

## 실무 포인트

- **기존 CRA 프로젝트를 억지로 Vite로 마이그레이션할 필요는 없다.** 안정적으로 돌아가는 프로젝트라면 신규 프로젝트부터 Vite를 적용하는 것이 현실적이다.
- **절대경로 import(`@/components/...`)를 쓰려면 `vite.config.js`의 `resolve.alias`와 `tsconfig.json`의 `paths`를 함께 맞춰야 한다.** 둘 중 하나만 설정하면 에디터에서는 되는데 빌드가 실패하는 상황이 생긴다.
- **Vitest**를 함께 쓰면 Vite 설정을 그대로 재사용해 테스트 환경을 별도로 구성할 필요가 없다.

## 마무리 요약

- Vite는 개발 중 네이티브 ESM을 활용해 CRA보다 체감 속도가 훨씬 빠르다.
- 환경변수는 `VITE_` 접두사와 `import.meta.env`로 접근해야 한다.
- 절대경로 alias는 vite.config와 tsconfig 양쪽에 동일하게 설정해야 빌드 에러를 피할 수 있다.

## 참고 자료

- [Vite 공식 문서](https://vitejs.dev/)
- [Vite 공식 문서 - 환경변수](https://vitejs.dev/guide/env-and-mode.html)
