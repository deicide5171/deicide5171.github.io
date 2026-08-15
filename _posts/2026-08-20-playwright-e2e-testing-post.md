---
layout: single
title: "Playwright E2E 테스트, 왜 자꾸 플레이키(Flaky)해질까 — 안 흔들리는 테스트 설계하기"
date: 2026-08-20 12:30:00 +0530
categories: frontend
tags: ["playwright", "e2e", "테스트자동화", "typescript", "ci-cd", "flaky-test"]
toc: true
toc_sticky: true
excerpt: "CI에서만 가끔 실패하는 E2E 테스트 때문에 팀이 재실행 버튼만 누르고 있다면, Playwright의 auto-waiting과 locator 전략으로 플레이키 테스트의 근본 원인을 없애는 방법을 정리한다."
---

## 왜 지금 이 이야기인가

E2E 테스트를 도입한 팀이 결국 겪는 문제는 "테스트가 없어서"가 아니라 "테스트를 못 믿어서"다. 로컬에서는 통과하는데 CI에서만 가끔 실패하고, 재실행(re-run)하면 또 통과해버리는 **플레이키 테스트(flaky test)** 가 쌓이면 팀은 자연스럽게 실패를 무시하는 습관을 들이게 된다. 그 순간부터 E2E 스위트는 회귀 버그를 잡는 안전망이 아니라 CI 시간을 잡아먹는 장식품이 된다.

Playwright는 이 문제를 프레임워크 차원에서 다룬다. `sleep`이나 임의의 대기 시간 대신 **auto-waiting**을 기본값으로 삼고, 실패한 테스트를 자동 재시도하면서 트레이스·비디오·스크린샷을 남기는 도구를 갖췄다. 다중 브라우저 엔진(Chromium·Firefox·WebKit)을 하나의 API로 다루면서 병렬 실행과 리포팅까지 기본 제공하는 팀이 늘고 있다. 다만 도구가 좋다고 저절로 안정적인 테스트가 되는 것은 아니다. 같은 Playwright로도 플레이키한 스위트를 만들 수 있고, 몇 가지 원칙만 지키면 오래 돌려도 안 흔들리는 스위트를 만들 수 있다.

## 핵심 개념 1: 플레이키 테스트의 근본 원인

플레이키 테스트는 대부분 "테스트 코드가 실행되는 속도"와 "브라우저/애플리케이션이 실제로 준비되는 속도"가 어긋날 때 발생한다. 원인을 유형별로 나누면 다음과 같다.

| 원인 유형 | 증상 | 대표 해결책 |
|---|---|---|
| 타이밍 경쟁(race condition) | 요소가 DOM에 붙기 전에 클릭 시도 | 고정 `sleep` 대신 조건 기반 auto-wait |
| 네트워크 비동기 응답 | API 응답 전에 검증(assertion) 실행 | `waitForResponse`, 네트워크 인터셉트 |
| 불안정한 선택자 | CSS 클래스·순서 변경에 셀렉터 깨짐 | 역할·텍스트 기반 locator(getByRole 등) |
| 테스트 간 상태 오염 | 이전 테스트의 데이터가 다음 테스트에 영향 | 테스트별 독립 컨텍스트, 격리된 fixture |
| 환경 차이(CI vs 로컬) | 로컬은 통과, CI는 리소스 제약으로 느림 | CI 전용 타임아웃 조정, 재시도 정책 |

실무에서 가장 흔한 원인은 첫 번째와 세 번째다. 요소가 실제로 상호작용 가능한 상태(보이고, 활성화되고, 애니메이션이 끝난 상태)가 되기 전에 클릭을 시도하거나, `div.card:nth-child(3)`처럼 마크업 구조에 강하게 의존하는 셀렉터를 쓰는 경우다.

## 핵심 개념 2: Playwright의 Auto-Waiting과 Locator

Playwright의 `locator` API는 "요소를 지금 찾아서 반환"하는 대신 "요소를 가리키는 질의를 저장해두고, 액션을 수행하는 시점에 다시 찾는다." 그리고 클릭·타이핑 같은 액션 직전에 요소가 실제로 조작 가능한 상태인지(존재·가시성·안정성·활성화 여부) 자동으로 확인한 뒤 실행한다. 이 덕분에 대부분의 경우 명시적인 `waitForSelector`나 `sleep` 호출 없이도 타이밍 문제가 사라진다.

| 셀렉터 전략 | 예시 | 안정성 |
|---|---|---|
| CSS 클래스/구조 의존 | `.btn-primary.mt-2` | 낮음 — 스타일 변경에 깨짐 |
| data-testid | `[data-testid="submit-btn"]` | 중간 — 명시적이지만 접근성과 무관 |
| 역할·접근성 기반 | `getByRole('button', { name: '제출' })` | 높음 — 사용자 관점과 일치, 리팩터링에 강함 |
| 텍스트 기반 | `getByText('장바구니에 담기')` | 높음 — 문구 변경 시에만 깨짐(의도된 변경) |

Playwright 공식 문서는 `getByRole`, `getByLabel`, `getByText` 같은 **사용자 관점 locator**를 CSS 셀렉터보다 우선하도록 권장한다. 사용자가 화면을 "역할과 텍스트"로 인식하는 방식과 테스트가 요소를 찾는 방식을 일치시키면, 마크업 리팩터링에도 테스트가 잘 깨지지 않는다.

## 예제: 안정적인 E2E 테스트 작성 (TypeScript)

```typescript
import { test, expect } from '@playwright/test';

test('로그인 후 대시보드에서 최근 주문 목록을 확인한다', async ({ page }) => {
  await page.goto('/login');

  // 역할 기반 locator — 마크업 구조가 아니라 사용자가 인지하는 방식으로 요소를 찾는다
  await page.getByLabel('이메일').fill('user@example.com');
  await page.getByLabel('비밀번호').fill('password123');
  await page.getByRole('button', { name: '로그인' }).click();

  // 네트워크 응답을 명시적으로 기다려 "화면은 떴지만 데이터는 아직" 상태를 방지
  const ordersResponse = page.waitForResponse(
    (res) => res.url().includes('/api/orders') && res.status() === 200
  );
  await page.getByRole('link', { name: '대시보드' }).click();
  await ordersResponse;

  // auto-waiting: 요소가 나타날 때까지 자동 대기 후 검증
  await expect(page.getByRole('heading', { name: '최근 주문' })).toBeVisible();
  await expect(page.getByTestId('order-row')).toHaveCount(5);
});

// playwright.config.ts 발췌 — 재시도·트레이스 정책은 CI 전용으로 분리
// export default defineConfig({
//   retries: process.env.CI ? 2 : 0,
//   use: { trace: 'retain-on-failure', video: 'retain-on-failure' },
// });
```

## 실무 포인트

- **`sleep`·`waitForTimeout`은 최후의 수단으로만 남긴다.** 고정 대기 시간은 느린 CI에서는 부족하고 빠른 로컬에서는 낭비다. `waitForResponse`, locator의 auto-wait처럼 조건 기반 대기로 대체한다.
- **테스트 간 상태를 공유하지 않는다.** 각 테스트가 자체 계정·데이터로 시작하도록 fixture를 설계하면 실행 순서나 병렬 실행에 영향받지 않는다.
- **재시도는 숨기기가 아니라 신호로 쓴다.** 특정 테스트가 재시도 후에야 통과하는 일이 반복된다면 근본 원인을 찾아야 한다는 신호이며, 재시도 통계를 팀이 볼 수 있게 남겨둔다.
- **트레이스 뷰어를 CI 실패 조사의 기본 루틴으로 삼는다.** 실패 시점의 DOM 스냅샷·네트워크 요청·콘솔 로그를 함께 보여줘 로그만으로 추측하지 않아도 된다.
- **선택자 우선순위를 팀 컨벤션으로 정한다.** `getByRole` → `getByLabel`/`getByText` → `data-testid` → CSS 셀렉터 순으로 정해두면 팀원 모두 일관되게 작성한다.

## 3줄 요약

- 플레이키 테스트의 근본 원인은 대부분 타이밍 경쟁과 불안정한 셀렉터이며, Playwright의 auto-waiting과 역할 기반 locator가 이를 구조적으로 줄여준다.
- `sleep` 대신 `waitForResponse` 등 조건 기반 대기를 쓰고, 테스트 간 상태를 완전히 격리하는 것이 안정성의 핵심이다.
- CI 전용 재시도 정책과 트레이스·비디오 기록을 함께 갖추면, 실패했을 때 원인을 추측이 아니라 근거로 조사할 수 있다.

## 참고 자료

- [Playwright 공식 문서 — Auto-waiting](https://playwright.dev/docs/actionability)
- [Playwright 공식 문서 — Locators](https://playwright.dev/docs/locators)
- [Playwright 공식 문서 — Test Retries](https://playwright.dev/docs/test-retries)
- [Playwright 공식 문서 — Trace Viewer](https://playwright.dev/docs/trace-viewer)
