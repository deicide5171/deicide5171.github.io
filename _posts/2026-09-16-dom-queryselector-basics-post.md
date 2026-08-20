---
layout: single
title: "querySelector가 뭔가요 — 자바스크립트로 HTML 요소 찾기"
date: 2026-09-16 12:30:00 +0530
categories: frontend
tags: ["queryselector", "dom", "자바스크립트", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "CSS 선택자로 HTML 요소를 찾아 조작하는 querySelector의 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## HTML 요소를 코드로 어떻게 집나

버튼을 클릭했을 때 반응하게 하거나 텍스트를 바꾸려면, 먼저 그 HTML 요소를 자바스크립트로 "찾아야" 한다. **querySelector**는 **CSS 선택자로 요소를 찾는** 메서드다. CSS에서 스타일을 줄 때 쓰던 선택자를 그대로 쓴다.

## 기본 사용

```javascript
// 하나 찾기 (첫 번째 매칭)
const title = document.querySelector('.title');   // class
const box = document.querySelector('#box');        // id
const firstLi = document.querySelector('ul li');   // 자손

// 여러 개 찾기
const items = document.querySelectorAll('.item');  // NodeList
items.forEach(el => el.classList.add('active'));
```

## querySelector vs querySelectorAll

| 메서드 | 반환 |
|---|---|
| querySelector | 첫 번째 매칭 요소 1개(없으면 null) |
| querySelectorAll | 매칭 요소 전부(NodeList) |

## 실무 포인트

- **없으면 null이 반환된다.** 찾는 요소가 없으면 `querySelector`는 `null`을 준다. 여기에 바로 `.textContent` 등을 쓰면 "null의 속성 읽기" 오류가 난다. 요소가 있을 때만 조작하도록 확인하거나 옵셔널 체이닝(`?.`)을 쓴다.
- **로드 시점을 조심하라.** 스크립트가 HTML보다 먼저 실행되면 아직 요소가 없어 못 찾는다. 스크립트를 `<body>` 끝에 두거나 `defer`를 쓰거나, `DOMContentLoaded` 이후에 실행한다.
- **자주 쓰면 변수에 저장.** 같은 요소를 반복해서 `querySelector`로 찾으면 매번 DOM을 탐색해 비효율적이다. 한 번 찾아 변수에 담아 재사용한다.

## 마무리 요약

- querySelector는 CSS 선택자로 HTML 요소를 찾는 메서드로, CSS 선택자를 그대로 쓴다.
- 하나는 `querySelector`(첫 매칭, 없으면 null), 여러 개는 `querySelectorAll`(NodeList)이다.
- 없으면 null이니 확인 후 조작하고, 로드 시점과 반복 탐색 성능에 주의한다.

## 참고 자료

- [MDN - querySelector](https://developer.mozilla.org/ko/docs/Web/API/Document/querySelector)
