---
layout: single
title: "axe-core로 완성하는 웹 접근성(A11y) 자동화 테스트 파이프라인"
date: 2026-08-17 12:30:00 +0530
categories: frontend
tags: ["a11y", "accessibility", "axe-core", "playwright", "wcag", "frontend"]
toc: true
toc_sticky: true
excerpt: "WCAG 자동 탐지의 한계를 이해하고 axe-core·Playwright·Lighthouse CI를 조합해 접근성 회귀를 PR 단계에서 잡아내는 테스트 파이프라인을 구축하는 방법을 정리한다."
---

## 왜 지금 웹 접근성 자동화인가

유럽 접근성법(European Accessibility Act, EAA)이 시행되면서 EU 시장을 대상으로 하는 서비스는 접근성 준수가 "권장"이 아니라 법적 의무 영역으로 넘어갔다. 국내에서도 공공기관 웹사이트에 이어 일부 민간 서비스까지 웹 접근성 인증 요구가 확대되는 흐름이 이어지고 있다. 이제 접근성은 출시 직전 QA 체크리스트의 한 항목이 아니라, 매 PR마다 검증해야 하는 **회귀 테스트 대상**으로 다뤄야 한다.

문제는 수동 접근성 감사가 시간과 비용이 크고, 하루에도 여러 번 배포하는 요즘 릴리스 주기와는 속도가 맞지 않는다는 점이다. 반면 axe-core 같은 자동화 도구는 코드가 바뀔 때마다 몇 초 안에 실행할 수 있어, CI 파이프라인에 넣어두면 "접근성 회귀"를 커밋 단위로 잡아낼 수 있다.

최근에는 Playwright가 접근성 트리 스냅샷과 axe-core 결합(`@axe-core/playwright`)을 공식 지원 범위로 다루고, Storybook의 a11y addon과 `eslint-plugin-jsx-a11y` 같은 정적 분석 도구까지 생태계가 성숙해지면서, 개발 초기 단계부터 접근성을 검증하는 "시프트 레프트(shift-left)" 접근이 프론트엔드 팀의 표준 관행으로 자리 잡는 중이다.

## 핵심 개념 1: 자동화가 잡아낼 수 있는 것과 없는 것

자동화 도구를 도입하기 전에 가장 먼저 정리해야 할 것은 기대치다. axe-core 같은 도구는 마크업에 드러나는 정적 규칙 위반은 정확히 잡지만, "의미가 맞는지"는 판단하지 못한다.

| 구분 | 자동 탐지 | 예시 |
|---|---|---|
| 정적 규칙 위반 | 가능 | `alt` 속성 누락, 폼 라벨 누락, 색상 대비 비율 미달, 중복 `id` |
| ARIA 오용 패턴 | 부분적 | 잘못된 `role` 지정, 필수 `aria-*` 속성 누락 |
| 논리적 흐름·문맥 | 수동 필요 | 탭 순서가 시각적 순서와 일치하는지, 안내 문구가 맥락상 자연스러운지 |
| 실제 보조기술 호환성 | 수동 필요 | 실제 스크린리더(NVDA, VoiceOver)로 읽었을 때 이해가 되는지 |

정확한 비율은 도구·측정 기준마다 다르지만, axe-core 등 자동화 도구 개발사들은 대체로 "자동화만으로는 전체 WCAG 이슈 중 일부만 탐지할 수 있다"는 점을 공통으로 안내한다. 즉 자동화는 접근성 검증을 대체하는 것이 아니라, 반복적으로 재발하는 이슈를 저비용으로 걸러내는 1차 방어선으로 이해하는 것이 정확하다.

## 핵심 개념 2: 테스트 레벨별 접근성 검증 도구

접근성 테스트도 일반적인 테스트 피라미드처럼 레벨을 나눠 배치하는 것이 효율적이다.

| 레벨 | 대표 도구 | 검증 대상 |
|---|---|---|
| 정적 분석(커밋 전) | `eslint-plugin-jsx-a11y` | JSX 마크업 규칙(`alt`, 라벨 연결 등) 위반을 편집 시점에 즉시 경고 |
| 단위/컴포넌트 | `jest-axe`, `vitest-axe` | 컴포넌트 렌더 결과에 axe 규칙을 적용해 회귀 방지 |
| E2E | `@axe-core/playwright` | 실제 라우팅·상태가 반영된 페이지 전체를 스캔 |
| 품질 게이트 | Lighthouse CI | 접근성 점수 임계값을 CI에서 강제, 성능·SEO와 함께 관리 |

각 레벨은 서로 다른 실패 지점을 잡는다. 정적 분석은 컴포넌트를 작성하는 순간의 실수를 막고, 단위 테스트는 컴포넌트 단위 회귀를 잡으며, E2E는 여러 컴포넌트가 조합된 실제 페이지에서만 드러나는 문제(포커스 순서, 동적으로 삽입된 콘텐츠 등)를 잡는다.

## 예제 1: Playwright + axe-core로 E2E 접근성 스캔

```typescript
// a11y.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('상품 목록 페이지는 심각한 접근성 위반이 없어야 한다', async ({ page }) => {
  await page.goto('/products');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag22aa']) // WCAG 2.2 AA 기준까지 포함
    .exclude('#third-party-widget')              // 통제 불가한 외부 위젯은 제외
    .analyze();

  // impact가 critical/serious인 위반만 우선 실패 처리
  const blocking = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );

  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
});
```

`withTags`로 검사 기준을 WCAG 버전·레벨 단위로 명시할 수 있고, `exclude`로 자사가 통제할 수 없는 외부 위젯 영역을 스캔에서 제외할 수 있다. 처음부터 모든 위반을 실패로 처리하면 팀의 반발이 크므로, `impact` 값으로 critical/serious만 우선 게이트에 걸고 moderate/minor는 리포트로만 축적하는 전략이 현실적이다.

## 예제 2: GitHub Actions에서 접근성 게이트 구성

```yaml
# .github/workflows/a11y.yml
name: Accessibility Gate

on:
  pull_request:
    branches: [main]

jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npm run build && npm run start &
      - run: npx wait-on http://localhost:3000
      - run: npx playwright test a11y.spec.ts
      - name: Lighthouse CI 접근성 점수 게이트
        run: npx lhci autorun --config=./lighthouserc.json
```

`lighthouserc.json`의 assertion에 `categories:accessibility` 최소 점수를 지정해두면, axe-core로 잡지 못하는 색상 대비·랜드마크 구조 같은 항목까지 별도 점수 지표로 함께 관리할 수 있다.

<img src="/assets/images/posts/2026-08-17-web-a11y-automation-testing-1.svg" alt="코드 작성부터 정적 분석, 단위 테스트, E2E 스캔, CI 게이트를 거쳐 PR이 머지되는 흐름과, 이와 별개로 릴리스 주기마다 병행되는 스크린리더 수동 감사를 함께 보여주는 웹 접근성 자동화 테스트 파이프라인 개념도" style="width:100%;">

## 실무 포인트

- **게이트 정책은 단계적으로 강화한다.** 처음부터 모든 위반을 빌드 실패로 처리하면 기존 코드베이스의 누적 이슈 때문에 파이프라인이 곧바로 막힌다. critical/serious부터 실패 처리하고, moderate/minor는 리포트로 추적하며 점진적으로 기준을 올린다.
- **동적 콘텐츠·색상 대비는 오탐·누락 가능성을 염두에 둔다.** 그라디언트 배경이나 이미지 위에 겹쳐진 텍스트는 자동 계산이 부정확할 수 있어, 디자인 시스템 단계에서 대비 기준을 미리 확정해두는 편이 안전하다.
- **키보드 내비게이션은 Playwright로 일부 자동화할 수 있지만 전부는 아니다.** `Tab` 키 시퀀스나 포커스 이동은 스크립트로 검증 가능하지만, 포커스 트랩이나 논리적 탐색 순서가 사용자 입장에서 자연스러운지는 여전히 수동 리뷰가 필요하다.
- **스크린리더 실사용 테스트는 자동화가 대체하지 못한다.** NVDA·VoiceOver 같은 실제 보조기술로 주기적으로 점검하는 수동 감사를 릴리스 사이클에 별도로 포함시켜야 한다.
- **WCAG 버전을 명시적으로 관리한다.** 자동화 도구의 규칙 세트는 WCAG 2.2 등 최신 버전을 계속 반영하고 있으므로, 팀의 목표 준수 레벨(예: AA)을 설정에 명시해 시간이 지나도 기준이 흔들리지 않게 한다.

## 3줄 요약

- 자동화 도구는 정적 규칙 위반은 정확히 잡지만 논리적 흐름이나 실제 보조기술 호환성까지는 판단하지 못하므로, 자동화와 수동 감사를 함께 운영해야 한다.
- `eslint-plugin-jsx-a11y`(정적 분석) → `jest-axe`(단위) → `@axe-core/playwright`(E2E) → Lighthouse CI(품질 게이트) 순으로 레벨을 나눠 배치하면 서로 다른 실패 지점을 효율적으로 잡을 수 있다.
- CI 게이트는 처음부터 전체 실패 처리하지 말고 `impact`가 critical/serious인 위반부터 단계적으로 강제해야 팀의 저항 없이 정착시킬 수 있다.

## 참고 자료

- [Deque — axe-core GitHub Repository](https://github.com/dequelabs/axe-core)
- [W3C — Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/)
- [Playwright — Accessibility testing](https://playwright.dev/docs/accessibility-testing)
- [eslint-plugin-jsx-a11y](https://github.com/jsx-eslint/eslint-plugin-jsx-a11y)
