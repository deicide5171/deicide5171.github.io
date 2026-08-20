---
layout: single
title: "HTTP 압축이 뭔가요 — gzip으로 응답을 작게 보내기"
date: 2026-09-16 12:45:00 +0530
categories: system-design
tags: ["http압축", "gzip", "brotli", "성능", "입문"]
toc: true
toc_sticky: true
excerpt: "서버 응답을 gzip·brotli로 압축해 전송량을 줄여 페이지를 빠르게 만드는 HTTP 압축의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 응답을 그대로 보내면 무겁다

HTML·CSS·JS·JSON은 텍스트라 반복이 많아 잘 압축된다. 압축 없이 그대로 보내면 전송량이 커 페이지가 느리다. **HTTP 압축**은 **서버가 응답을 gzip·brotli 등으로 압축해 보내고, 브라우저가 받아서 푸는** 방식이다. 전송량이 크게 줄어 로딩이 빨라진다.

## 어떻게 협상하나

```text
1. 브라우저: 요청 헤더에 "나 gzip/brotli 풀 수 있어"
   Accept-Encoding: gzip, br
2. 서버: 압축해서 응답 + 헤더로 방식 알림
   Content-Encoding: br
3. 브라우저: 받아서 압축을 풀어 화면에 표시
```

## 대표 방식

| 방식 | 특징 |
|---|---|
| gzip | 널리 지원, 무난 |
| brotli(br) | 압축률 더 좋음(정적 파일에 유리) |

## 실무 포인트

- **텍스트에 크게 효과, 이미지엔 무의미.** HTML·JS·CSS·JSON 같은 텍스트는 60~80%까지 줄기도 한다. 반면 JPG·PNG·MP4는 이미 압축돼 있어 다시 압축해도 이득이 없고 CPU만 쓴다. 텍스트에만 켠다.
- **정적 파일은 미리 압축.** 매 요청마다 압축하면 CPU가 든다. 자주 안 바뀌는 정적 파일은 미리 압축본을 만들어두면(precompress) 서버 부하가 준다. CDN이 이를 대신 해주기도 한다.
- **보통 서버/프록시가 처리.** 애플리케이션 코드에서 직접 압축하기보다, Nginx·리버스 프록시·CDN 설정으로 켜는 경우가 많다. 설정 한 줄로 전체 응답에 적용된다.

## 마무리 요약

- HTTP 압축은 서버가 응답을 gzip·brotli로 압축해 전송량을 줄여 로딩을 빠르게 한다.
- 브라우저가 `Accept-Encoding`으로 지원을 알리고 서버가 압축해 보내며, 받아서 푼다.
- 텍스트에 효과가 크고 이미지엔 무의미하며, 정적 파일은 미리 압축하고 보통 프록시/CDN에서 켠다.

## 참고 자료

- [MDN - HTTP 압축](https://developer.mozilla.org/ko/docs/Web/HTTP/Guides/Compression)
