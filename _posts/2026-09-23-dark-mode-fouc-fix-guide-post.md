---
layout: single
title: "웹사이트 다크모드 제대로 구현하기 — 깜빡임(FOUC) 없이 적용하는 법"
date: 2026-09-23 12:30:00 +0530
categories: frontend
tags: ["다크모드", "css변수", "localstorage", "fouc", "웹성능"]
toc: true
toc_sticky: true
excerpt: "다크모드를 켜둔 사용자가 페이지를 새로고침할 때마다 흰 화면이 잠깐 번쩍이는 문제를, prefers-color-scheme과 localStorage, 그리고 초기 스크립트 삽입 순서로 해결하는 방법을 정리했다."
---

## 왜 다크모드를 켰는데 새로고침마다 하얗게 번쩍일까

다크모드 토글 버튼을 만들어 붙였더니, 기능 자체는 잘 동작하는데 페이지를 새로고침하거나 다른 페이지로 이동할 때마다 순간적으로 흰 배경이 번쩍였다가 다크 테마로 바뀌는 현상을 겪게 된다. 이 현상을 FOUC(Flash of Unstyled Content, 정확히는 여기서는 "잘못된 테마의 깜빡임")라고 부른다. 원인은 대부분 **테마를 적용하는 자바스크립트가 너무 늦게 실행되기 때문**이다.

일반적인 React나 Vue 앱에서는 컴포넌트가 마운트된 뒤에야 `useEffect`나 `onMounted` 안에서 localStorage를 읽어 테마 클래스를 적용한다. 하지만 브라우저는 그보다 훨씬 먼저 HTML을 파싱하고 기본(라이트) 스타일로 첫 페인트를 그려버린다. 그 사이의 짧은 순간이 사용자 눈에는 "흰 화면 번쩍임"으로 보이는 것이다.

## 핵심 개념 1 — 테마 결정은 body 렌더링보다 먼저 일어나야 한다

이 문제의 해법은 프레임워크의 생명주기를 기다리지 않고, **HTML의 `<head>` 안에 인라인 스크립트를 넣어 첫 렌더링 전에 테마를 결정**하는 것이다. 브라우저는 `<head>`의 동기 스크립트를 만나면 그 실행이 끝날 때까지 이후 파싱과 렌더링을 멈춘다. 이 짧은 차단 시간을 이용해 테마 클래스를 body(또는 html 태그)에 미리 붙여버리면, 첫 페인트부터 올바른 테마로 그려진다.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <script>
    // 반드시 다른 <link rel="stylesheet">보다 먼저, head 최상단에 위치
    (function () {
      const saved = localStorage.getItem('theme');
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const theme = saved || (prefersDark ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', theme);
    })();
  </script>
  <link rel="stylesheet" href="/styles.css">
</head>
```

이 스크립트가 CSS 파일보다 먼저 실행되고, `<body>`가 파싱되기 전에 `data-theme` 속성이 이미 붙어 있어야 한다. 순서가 뒤바뀌면 여전히 깜빡임이 남는다.

## 핵심 개념 2 — 저장된 선택값과 시스템 설정을 구분해서 다룬다

사용자가 명시적으로 토글 버튼을 눌러 테마를 고른 적이 없다면 시스템 설정(`prefers-color-scheme`)을 따라야 하고, 한 번이라도 직접 선택했다면 그 선택을 시스템 설정보다 우선해야 한다. 이 우선순위를 구분하지 않으면, 사용자가 라이트모드를 명시적으로 골랐는데 OS 설정을 다크로 바꾸는 순간 사이트도 따라 바뀌어버리는 예상 밖의 동작이 생긴다.

<img src="/assets/images/posts/2026-09-23-dark-mode-fouc-fix-guide-1.svg" alt="브라우저가 HTML head의 인라인 스크립트로 테마를 먼저 결정한 뒤 CSS와 body를 렌더링해 깜빡임을 없애는 순서와, 저장된 값과 시스템 설정의 우선순위를 보여주는 다이어그램" style="width:100%;">

## 예제 — CSS 변수와 토글 버튼 연결하기

```css
:root {
  --bg: #ffffff;
  --text: #1a1a1a;
}

[data-theme="dark"] {
  --bg: #121212;
  --text: #e8e8e8;
}

body {
  background-color: var(--bg);
  color: var(--text);
  transition: background-color 0.2s ease;
}
```

```javascript
function toggleTheme() {
  const root = document.documentElement;
  const current = root.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);  // 다음 방문부터도 유지
}
```

## 흔한 실수

| 실수 | 결과 |
|---|---|
| 테마 스크립트를 `<body>` 하단이나 번들 JS 안에 둠 | 렌더링이 먼저 끝나 여전히 깜빡임 발생 |
| `async`/`defer` 속성을 테마 스크립트에 붙임 | 실행 시점이 렌더링과 겹쳐 타이밍이 불안정해짐 |
| CSS에 `transition: all`을 걸어둠 | 테마 전환 시 색상 외에 레이아웃 속성까지 애니메이션되며 어색하게 보임 |
| SSR(Next.js 등)에서 서버가 항상 라이트로 렌더링 | 하이드레이션 후 클라이언트에서 테마가 바뀌며 콘텐츠가 깜빡이는 하이드레이션 미스매치 발생 |

특히 SSR 환경에서는 서버가 사용자의 localStorage를 알 수 없다는 근본적인 제약이 있다. 쿠키에 테마 값을 함께 저장해 서버 렌더링 시점에도 참조하거나, 최초 렌더링에는 테마를 결정하지 않고 클라이언트에서만 렌더링되는 영역으로 분리하는 절충이 필요하다.

## 실무 포인트

- **인라인 스크립트는 최소한으로 압축하라.** head에 들어가는 이 스크립트는 렌더링을 차단하므로, 불필요한 로직 없이 테마 결정 로직만 담아 실행 시간을 최소화해야 한다.
- **`prefers-color-scheme` 미디어쿼리 리스너도 함께 등록하면 좋다.** 사용자가 사이트를 열어둔 채로 OS 설정을 바꾸는 경우, 저장된 값이 없다면 실시간으로 반응하도록 `matchMedia`의 `change` 이벤트를 구독해둔다.
- **CSS 변수 기반 설계가 클래스 기반보다 유지보수하기 쉽다.** 색상마다 `.dark .card`, `.dark .button`처럼 클래스를 일일이 오버라이드하는 대신, 커스텀 프로퍼티 값만 테마별로 바꾸면 컴포넌트 CSS는 그대로 재사용된다.

## 마무리 요약

- 다크모드 깜빡임은 테마 적용 스크립트가 첫 페인트보다 늦게 실행되기 때문이며, head 최상단의 동기 인라인 스크립트로 해결한다.
- 저장된 사용자 선택값이 시스템 설정(prefers-color-scheme)보다 우선해야 예상 밖의 테마 전환을 막을 수 있다.
- SSR 환경에서는 서버가 클라이언트의 localStorage를 모른다는 제약 때문에 쿠키 병행 저장 등 별도 절충이 필요하다.

## 참고 자료

- [MDN - prefers-color-scheme](https://developer.mozilla.org/ko/docs/Web/CSS/@media/prefers-color-scheme)
- [web.dev - Building a color scheme](https://web.dev/articles/prefers-color-scheme)
