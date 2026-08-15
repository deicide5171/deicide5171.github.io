---
layout: single
title: "TypeScript가 이겼다는 지금, 남은 논쟁은 무엇인가"
date: 2026-08-15 16:30:00 +0530
categories: web-dev
tags: ["typescript", "javascript", "strict-mode", "type-safety", "tsconfig"]
toc: true
toc_sticky: true
excerpt: "TypeScript 채택이 사실상 보편화된 2026년, 이제 실무에서 남은 쟁점은 문법이 아니라 strict 수준, 타입 우선 설계, 빌드 없는 실행, 컴파일 성능이다."
---

## 왜 지금 이 이야기인가

몇 해 전만 해도 "TypeScript를 도입할 것인가"는 프로젝트 초기에 진지하게 토론할 주제였습니다. 하지만 최근 개발자 설문들을 보면 신규 JavaScript 프로젝트 대다수가 TypeScript로 시작한다는 응답이 반복적으로 나오고 있고, 커뮤니티에서는 이미 "TypeScript가 사실상 승리했다"는 표현까지 등장했습니다. 정확한 채택 비율은 설문마다 편차가 있어 단정하기 어렵지만, 방향성 자체는 뚜렷합니다.

문제는 도입 여부가 논쟁의 종착점이 아니라는 점입니다. TypeScript를 쓰기로 한 이후에도 팀마다 방식이 크게 갈립니다. strict 모드를 얼마나 엄격하게 켤 것인가, 타입을 먼저 설계하고 구현을 따라가야 하는가, 빌드 단계 없이 TypeScript를 바로 실행해도 괜찮은가, 대형 프로젝트의 컴파일 속도는 어떻게 관리할 것인가 같은 질문들이 새로운 실무 논쟁으로 자리 잡았습니다. 이 글에서는 이 네 가지 쟁점을 정리합니다.

## strict 모드, 어디까지 켤 것인가

`strict: true`는 이제 신규 프로젝트의 기본값처럼 여겨지지만, 그 안에 포함된 세부 옵션(`noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess` 등)을 전부 동일한 강도로 적용할지는 팀마다 다릅니다. 레거시 코드베이스를 마이그레이션하는 경우 한 번에 전체를 켜기보다 옵션을 단계적으로 켜는 접근이 흔히 권장됩니다.

| 접근 | 장점 | 단점 |
|---|---|---|
| 처음부터 strict 전체 적용 | 타입 안전성 최대화, 런타임 버그 조기 발견 | 신규 팀원 진입 장벽, 초기 작성 속도 저하 |
| 단계적 strict 적용 | 기존 코드 마이그레이션 용이 | 과도기 동안 타입 커버리지 불균일 |
| strict 최소화 | 빠른 프로토타이핑 | any 남용, 타입 이점 상실 위험 |

## 타입 우선 설계 vs 점진적 타이핑

"타입 우선(type-first)" 접근은 도메인 모델과 인터페이스를 먼저 정의하고 구현을 채워나가는 방식이고, "점진적 타이핑(gradual typing)"은 기존 JavaScript 코드에 타입을 나중에 덧입히는 방식입니다. 신규 프로젝트에서는 타입 우선 설계가 API 계약을 명확히 하는 데 유리하다는 의견이 많지만, 기존 대형 코드베이스에서는 점진적 타이핑이 현실적인 선택지로 남아 있습니다. 두 접근을 이분법으로 볼 필요는 없고, 핵심 도메인 로직은 타입 우선으로, 주변부 유틸리티는 점진적으로 타입을 붙이는 혼합 전략도 널리 쓰입니다.

## 빌드 없이 TypeScript 실행하기

Node.js가 실험적으로 지원하기 시작한 native type stripping은 별도의 트랜스파일 빌드 단계 없이 `.ts` 파일을 바로 실행할 수 있게 해줍니다. 다만 이는 타입을 "제거"만 할 뿐 타입 검사를 수행하지는 않으므로, 타입 오류를 잡으려면 여전히 `tsc --noEmit` 같은 별도 검사 단계가 필요합니다. 프로덕션 빌드 파이프라인 전체를 대체하기보다는 로컬 개발이나 스크립트 실행 편의성을 높이는 용도로 먼저 도입하는 편이 안전합니다.

```json
// tsconfig.json — 점진적으로 strict를 켜는 예시
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "skipLibCheck": true
  }
}
```

```ts
// native type stripping 환경에서의 실행 예시 (개념 코드)
// 실행: node --experimental-strip-types app.ts
interface User {
  id: string;
  name: string;
}

function greet(user: User): string {
  return `안녕하세요, ${user.name}님`;
}

console.log(greet({ id: "1", name: "지연" }));
```

## 실무 포인트와 주의사항

`any`는 여전히 가장 흔한 함정입니다. 외부 라이브러리 타입이 부실하거나 마감이 급할 때 `any`로 임시 봉합하는 경우가 많은데, 이렇게 들어온 `any`는 시간이 지나며 코드베이스 전반으로 조용히 퍼지는 경향이 있습니다. `unknown`으로 대체하고 타입 가드를 작성하는 습관, ESLint의 `no-explicit-any` 규칙을 CI에 걸어두는 방식이 실무에서 자주 쓰입니다. 또한 대형 모노레포에서는 컴파일·타입 검사 속도 자체가 개발 경험을 좌우하므로, 프로젝트 레퍼런스(`project references`) 분리나 증분 빌드 캐시 활용도 함께 검토할 만합니다.

## 3줄 요약

- TypeScript 도입 자체는 더 이상 논쟁거리가 아니며, 논쟁은 strict 수준·설계 순서·실행 방식·성능으로 옮겨갔습니다.
- native type stripping은 빌드 단계를 줄여주지만 타입 검사를 대체하지 않으므로 별도 검사 단계가 여전히 필요합니다.
- `any` 남용을 막고 타입 커버리지를 유지하려면 ESLint 규칙, 단계적 strict 적용, 프로젝트 레퍼런스 같은 장치를 실무 규칙으로 못박아 두는 것이 중요합니다.

## 참고 자료

- [TypeScript 공식 문서 — tsconfig 컴파일러 옵션](https://www.typescriptlang.org/tsconfig/)
- [TypeScript 공식 릴리스 노트](https://www.typescriptlang.org/docs/handbook/release-notes/overview.html)
- [Node.js 공식 문서 — TypeScript 지원](https://nodejs.org/en/learn/typescript/run-natively)
- [State of JS 설문](https://stateofjs.com/)
