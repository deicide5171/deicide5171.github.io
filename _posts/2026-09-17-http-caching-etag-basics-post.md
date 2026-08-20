---
layout: single
title: "ETag가 뭔가요 — 안 바뀌었으면 다시 안 받게 하기"
date: 2026-09-17 13:45:00 +0530
categories: system-design
tags: ["etag", "http캐싱", "조건부요청", "성능", "입문"]
toc: true
toc_sticky: true
excerpt: "리소스가 바뀌지 않았으면 다시 내려받지 않게 하는 HTTP 캐싱의 ETag와 조건부 요청을 처음 배우는 사람 기준으로 정리했다."
---

## 안 바뀐 데이터를 매번 다시 받는 건 낭비

같은 이미지·API 응답을 매번 통째로 다시 받으면 대역폭과 시간이 낭비된다. **ETag**는 리소스의 **버전을 나타내는 식별자(지문)**다. 브라우저가 이 값을 갖고 있다가, 다음 요청에 "내가 가진 게 이거인데 바뀌었나?"라고 물어 안 바뀌었으면 다시 안 받는다.

## 조건부 요청 흐름

```text
1. 첫 응답: 서버가 ETag를 함께 보냄
   ETag: "abc123"
2. 다음 요청: 브라우저가 가진 ETag를 보냄
   If-None-Match: "abc123"
3. 서버 판단:
   - 안 바뀜 -> 304 Not Modified (본문 없이, 캐시 사용)
   - 바뀜   -> 200 + 새 본문 + 새 ETag
```

## 실무 포인트

- **304는 본문이 없어 가볍다.** 리소스가 그대로면 서버는 `304 Not Modified`만 보내고 본문은 안 보낸다. 브라우저는 캐시된 것을 쓴다. 전송량이 크게 줄어든다.
- **Last-Modified와 비슷하다.** 시간 기반 `Last-Modified`/`If-Modified-Since`도 비슷한 역할을 한다. ETag는 내용 기반이라 더 정확할 수 있다. 둘을 함께 쓰기도 한다.
- **Cache-Control과 역할이 다르다.** `Cache-Control`은 "얼마나 오래 캐시할지"를 정해 아예 요청을 안 보내게 할 수 있고, ETag는 "요청은 하되 안 바뀌었으면 본문은 안 받기"다. 둘을 조합해 캐싱 전략을 짠다.

## 마무리 요약

- ETag는 리소스의 버전을 나타내는 지문으로, 조건부 요청에 쓰인다.
- 브라우저가 `If-None-Match`로 물으면 서버는 안 바뀌었을 때 `304`만 보내 본문 전송을 아낀다.
- `Last-Modified`와 비슷하고 `Cache-Control`과 역할이 달라, 조합해 캐싱 전략을 만든다.

## 참고 자료

- [MDN - ETag](https://developer.mozilla.org/ko/docs/Web/HTTP/Reference/Headers/ETag)
