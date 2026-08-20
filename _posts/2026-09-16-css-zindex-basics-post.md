---
layout: single
title: "z-index가 뭔가요 — 요소가 겹칠 때 앞뒤 순서 정하기"
date: 2026-09-16 13:30:00 +0530
categories: frontend
tags: ["css", "zindex", "레이어", "쌓임맥락", "입문"]
toc: true
toc_sticky: true
excerpt: "요소가 겹칠 때 누가 위에 보일지 정하는 z-index와 쌓임 맥락(stacking context)의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 모달이 다른 요소 뒤에 숨는다

팝업(모달)을 띄웠는데 다른 요소에 가려 안 보일 때가 있다. 요소가 겹칠 때 "누가 앞(위)에 보일지"는 **z-index**로 정한다. 값이 클수록 앞에 온다. 화면의 깊이(z축) 순서를 정하는 것이다.

## 기본 개념

```css
.back  { z-index: 1; }   /* 뒤 */
.front { z-index: 10; }  /* 앞(위) */
/* 숫자가 클수록 위에 보인다 */
```

주의: z-index는 **position이 static이 아닐 때만**(relative·absolute·fixed 등) 동작한다. position 없이 z-index만 주면 안 먹는다.

## 왜 큰 값을 줘도 안 먹을까

z-index가 항상 전역으로 비교되는 것은 아니다. **쌓임 맥락(stacking context)** 안에서만 비교된다.

```text
부모 A(z-index:1) 안의 자식(z-index:9999)
부모 B(z-index:2)
-> A의 자식이 9999여도 B보다 뒤!
   (자식은 부모 A의 맥락 안에서만 겨룸)
```

## 실무 포인트

- **position을 먼저 확인.** z-index가 안 먹으면 대부분 position이 static이다. `relative` 등을 먼저 준다.
- **z-index 값을 마구 키우지 마라.** `z-index: 99999`로 밀어붙이면 나중에 더 큰 값 경쟁이 벌어진다. 레이어 단계를 정해(예: 모달 1000, 툴팁 1100) 체계적으로 관리한다.
- **쌓임 맥락을 이해하라.** 부모에 `transform`·`opacity`·`z-index` 등이 있으면 새 쌓임 맥락이 생겨, 자식의 z-index가 바깥 요소와 직접 안 겨룬다. 모달이 안 뜨는 흔한 원인이다.

## 마무리 요약

- z-index는 요소가 겹칠 때 앞뒤(z축) 순서를 정하며, 값이 클수록 위에 보인다.
- position이 static이 아니어야 동작하고, 쌓임 맥락 안에서만 값이 비교된다.
- 값을 마구 키우지 말고 레이어 단계를 정하며, 안 먹으면 position·쌓임 맥락을 확인한다.

## 참고 자료

- [MDN - z-index](https://developer.mozilla.org/ko/docs/Web/CSS/z-index)
