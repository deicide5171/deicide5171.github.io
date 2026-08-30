---
layout: single
title: "Speculation Rules API로 다음 페이지 미리 가져오기(Prerendering)"
date: 2026-09-24 13:30:00 +0530
categories: frontend
tags: ["SpeculationRulesAPI", "Prerendering", "웹성능", "MPA", "Prefetch"]
toc: true
toc_sticky: true
excerpt: "링크에 마우스를 올리자마자 클릭할 확률을 계산해 다음 페이지를 미리 렌더링해두는 크롬의 Speculation Rules API가, 기존 rel=prefetch보다 훨씬 적극적으로 체감 속도를 끌어올리는 방식과 오작동을 막는 안전장치를 정리했다."
---

## 왜 지금 Speculation Rules API를 다시 봐야 하는가

전통적인 다중 페이지 애플리케이션(MPA)에서는 링크를 클릭할 때마다 새 페이지를 처음부터 요청하고 렌더링해야 해서, SPA 대비 페이지 전환 체감 속도가 느리다는 인식이 있었다. `<link rel="prefetch">`로 리소스를 미리 받아두는 방법이 있었지만, 이는 파일만 미리 내려받을 뿐 그 파일로 페이지를 실제로 렌더링해두지는 않으므로 체감 속도 개선에는 한계가 있었다. Speculation Rules API는 여기서 한 걸음 더 나아가, 사용자가 실제로 클릭하기 전에 다음 페이지를 백그라운드에서 통째로 미리 렌더링(prerender)해두어, 클릭하는 순간 이미 완성된 페이지를 즉시 보여줄 수 있게 한다. MPA 아키텍처를 유지하면서도 SPA에 준하는 체감 속도를 얻을 수 있다는 점에서, 프레임워크 전환 없이 적용 가능한 성능 개선 수단으로 주목받고 있다.

## 핵심 개념 1 — Prefetch와 Prerender는 완전히 다른 수준의 작업이다

Speculation Rules API는 두 가지 동작 모드를 지원한다. `prefetch`는 다음 페이지의 HTML 문서 자체를 네트워크로 미리 받아두는 것까지만 한다. `prerender`는 여기서 더 나아가 그 HTML을 실제로 파싱하고, CSS를 적용하고, 자바스크립트까지 실행해 완전히 렌더링된 페이지를 백그라운드의 숨겨진 탭 같은 곳에 미리 만들어둔다. 사용자가 실제로 그 링크를 클릭하면, 브라우저는 새로 페이지를 그리는 대신 이미 완성된 프리렌더 결과를 그 자리에서 스왑하듯 보여준다. 이 차이 때문에 `prerender`는 `prefetch`보다 훨씬 체감 속도 개선 효과가 크지만, 그만큼 CPU와 메모리 자원도 더 많이 소모한다.

## 핵심 개념 2 — 예측 규칙과 안전장치로 낭비되는 프리렌더를 줄인다

모든 링크를 무조건 프리렌더하면 사용자가 클릭하지 않을 페이지까지 렌더링하는 낭비가 심해지고, 부작용이 있는 페이지(로그아웃 링크, 결제 확정 페이지)를 실수로 미리 실행시켜버리는 위험도 있다. Speculation Rules API는 이를 막기 위해 몇 가지 안전장치를 둔다. 우선 규칙을 CSS 선택자나 URL 패턴으로 좁혀 지정할 수 있어, "이 목록의 링크들만" 또는 "이 패턴에 맞는 URL만" 프리렌더 대상으로 삼을 수 있다. 또한 브라우저는 `Speculation-Rules` 관련 HTTP 헤더나 `document.prerendering` API로 현재 문서가 프리렌더 상태인지 확인할 수 있게 해줘, 분석 스크립트가 실제 사용자 조회로 잘못 집계하거나 사용자 위치 정보 요청 같은 부작용이 프리렌더 단계에서 실행되는 것을 애플리케이션이 직접 막을 수 있게 한다.

| 모드 | 수행 작업 | 자원 소모 | 체감 속도 개선 |
|---|---|---|---|
| `prefetch` | HTML 문서만 미리 다운로드 | 낮음 | 중간 |
| `prerender` | 다운로드+파싱+렌더링+JS 실행까지 완료 | 높음 | 매우 큼(즉시 표시) |

## 예제 — 문서 규칙과 조건부 실행 코드

```html
<script type="speculationrules">
{
  "prerender": [
    {
      "where": { "selector_matches": ".product-card a" },
      "eagerness": "moderate"
    }
  ],
  "prefetch": [
    {
      "urls": ["/help", "/faq"],
      "eagerness": "conservative"
    }
  ]
}
</script>
```

```javascript
// 프리렌더된 상태에서 실행되면 안 되는 로직은 반드시 이렇게 가드한다
if (document.prerendering) {
  document.addEventListener('prerenderingchange', () => {
    // 실제로 사용자에게 보여지는 시점(activation)에만 실행
    sendAnalyticsPageView();
  }, { once: true });
} else {
  sendAnalyticsPageView();
}
```

`eagerness`는 얼마나 적극적으로 프리렌더를 트리거할지 정하는 값으로, `conservative`는 클릭 의도가 명확할 때(마우스 다운 등)만, `moderate`는 호버 등 좀 더 이른 신호에도 반응하도록 조정한다.

## 실무 포인트

- **분석·로깅 코드는 반드시 `document.prerendering`으로 가드하라.** 이를 빠뜨리면 실제로 사용자가 보지도 않은 프리렌더된 페이지가 페이지뷰로 잘못 집계되는 데이터 오염이 발생한다.
- **부작용이 있는 URL(로그아웃, 결제, 상태를 변경하는 GET 요청)은 프리렌더 규칙에서 명시적으로 제외하라.** GET 요청은 원래 부작용이 없어야 한다는 웹 표준 관례를 어기고 있는 페이지가 있다면, Speculation Rules 도입을 계기로 이 문제부터 먼저 고쳐야 한다.
- **`eagerness` 설정을 트래픽과 서버 부하에 맞춰 조정하라.** 지나치게 적극적인 프리렌더링은 실제로 클릭되지 않는 페이지까지 서버에 요청을 발생시켜 불필요한 트래픽 증가로 이어질 수 있다.

## 마무리 요약

- Speculation Rules API의 `prerender`는 단순 리소스 프리페치를 넘어 다음 페이지를 완전히 렌더링해둬, 클릭 시 즉시 전환되는 체감 속도를 만든다.
- CSS 선택자나 URL 패턴으로 규칙을 좁히고 `eagerness`를 조정해, 낭비되는 프리렌더와 서버 부하를 통제할 수 있다.
- `document.prerendering`으로 분석·부작용 코드를 가드하지 않으면 프리렌더 단계에서 실행된 코드가 잘못된 데이터나 의도치 않은 부작용을 일으킬 수 있다.

## 참고 자료

- [Chrome for Developers - Speculation Rules API](https://developer.chrome.com/docs/web-platform/prerender-pages)
- [MDN - Speculation Rules API](https://developer.mozilla.org/en-US/docs/Web/API/Speculation_Rules_API)
