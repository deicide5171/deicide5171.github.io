---
layout: single
title: "2026년 최신 JS 문법 정리, 실무에 바로 쓰는 기능들"
date: 2026-08-15 18:30:00 +0530
categories: web-dev
tags: ["JavaScript", "ECMAScript", "TC39", "신규문법"]
toc: true
toc_sticky: true
excerpt: "Temporal API, Object.groupBy, 데코레이터 등 최근 표준화 단계가 진전된 JS 문법의 지원 현황과 실무 활용 예제를 정리한다."
---

## 왜 지금 이 이야기인가

JavaScript는 매년 TC39를 통해 새 문법이 표준화되지만, 실무에서는 "이게 브라우저/Node에서 실제로 쓸 수 있는 단계인지"를 확인하는 일이 은근히 번거롭다. 제안(proposal) 단계별로 Stage 0부터 Stage 4까지 있고, Stage 4에 도달해야 다음 ECMAScript 연례 개정판에 실제로 포함되는데, 이 진행 상황은 계속 바뀌기 때문에 특정 시점의 정보를 그대로 믿기보다는 실제 배포 환경에서 지원 여부를 다시 확인하는 습관이 필요하다.

이 글에서는 최근 표준화가 진전된 대표적인 문법 몇 가지를 정리한다. 다만 TC39 제안의 스테이지는 회의마다 갱신되므로, 아래 내용 중 최신 상태는 반드시 TC39 공식 저장소나 MDN에서 재확인하는 것을 권장한다.

## 핵심 개념

| 제안/기능 | 대략적 상태 (확인 시점 기준, 변동 가능) | 한 줄 설명 |
|---|---|---|
| Object.groupBy / Map.groupBy | Baseline로 표기되어 주요 브라우저와 최신 Node에서 사용 가능한 것으로 보인다 | 배열 요소를 조건에 따라 그룹핑 |
| Temporal | Stage 4에 도달했다는 보도가 있으나, 런타임별 실제 지원 시점은 별도로 확인 필요 | Date를 대체하는 불변 날짜/시간 API |
| Decorators | Stage 3 단계로 TypeScript, Babel 등 트랜스파일러에서는 이미 널리 쓰이는 것으로 보인다 | 클래스/메서드에 메타 동작을 부여하는 문법 |
| Pipeline operator (`|>`) | 여러 차례 논의됐지만 아직 초기 스테이지에 머물러 있는 것으로 보이며 문법 확정까지는 시간이 걸릴 수 있다 | 함수 호출 체이닝을 가독성 있게 표현 |
| Explicit Resource Management (`using`) | Stage 3 전후로 논의되어 온 것으로 보이며 런타임 지원은 확인이 필요하다 | 리소스 자동 해제를 위한 선언 문법 |

Node/브라우저 지원 여부는 caniuse.com이나 각 런타임 릴리스 노트에서 버전별로 확인하는 것이 가장 정확하다.

## 예제

```javascript
// Object.groupBy — 배열을 조건별로 그룹핑 (Baseline로 표기된 것으로 보임, 실행 환경에서 재확인 권장)
const orders = [
  { id: 1, status: "paid" },
  { id: 2, status: "pending" },
  { id: 3, status: "paid" },
];

const grouped = Object.groupBy(orders, (order) => order.status);
console.log(grouped);
// { paid: [{id:1,...}, {id:3,...}], pending: [{id:2,...}] }
```

```javascript
// Temporal — Date보다 명확한 날짜/시간 연산 (지원 여부는 런타임별 확인 필요)
// 폴리필: @js-temporal/polyfill 등을 사용해 먼저 테스트해보는 것을 권장
import { Temporal } from "@js-temporal/polyfill";

const now = Temporal.Now.zonedDateTimeISO("Asia/Seoul");
const deadline = now.add({ days: 7 });

console.log(deadline.toString());
```

## 실무 포인트와 주의사항

- 새 문법을 도입하기 전에 타겟 브라우저/Node 버전에서의 실제 지원 여부를 caniuse나 공식 릴리스 노트로 반드시 재확인한다.
- Stage 3 이하 제안은 사양이 바뀔 수 있으므로, 프로덕션 코드에 직접 쓰기보다는 폴리필/트랜스파일 여부와 함께 신중히 검토한다.
- Temporal처럼 기존 Date API를 대체하는 기능은 마이그레이션 범위가 크므로 신규 코드부터 점진적으로 도입하는 편이 안전하다.
- 데코레이터처럼 TypeScript/Babel에서 먼저 널리 쓰이던 문법은 트랜스파일러 버전에 따라 동작 방식이 미묘하게 다를 수 있어 표준 사양과의 차이를 인지하고 있어야 한다.

## 3줄 요약

- Object.groupBy/Map.groupBy는 Baseline로 표기되어 실무에 바로 활용할 수 있는 단계로 보인다.
- Temporal, 데코레이터, 파이프라인 연산자 등은 스테이지가 계속 바뀌므로 도입 전 최신 상태 재확인이 필요하다.
- 새 문법 도입 여부는 타겟 런타임의 실제 지원 현황을 기준으로 판단해야 한다.

## 참고 자료

- [TC39 proposals 저장소](https://github.com/tc39/proposals)
- [MDN - Object.groupBy()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/groupBy)
- [MDN - Temporal](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Temporal)
