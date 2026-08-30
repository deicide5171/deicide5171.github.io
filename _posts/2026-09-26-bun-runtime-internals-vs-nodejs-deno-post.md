---
layout: single
title: "Bun 런타임 내부 구조 — Node.js·Deno와 다른 설계가 만드는 성능 차이"
date: 2026-09-26 13:25:00 +0530
categories: backend
tags: ["Bun", "JavaScript런타임", "JavaScriptCore", "Nodejs비교", "콜드스타트"]
toc: true
toc_sticky: true
excerpt: "서버리스 함수의 콜드 스타트 시간이 응답 속도를 좌우하는 상황에서, Node.js의 V8·libuv 조합과 근본적으로 다른 JavaScriptCore·Zig 기반 설계로 시작 시간을 한 자릿수 밀리초까지 줄인 Bun 런타임의 내부 아키텍처를 정리했다."
---

## 왜 지금 자바스크립트 런타임을 다시 봐야 하는가

Node.js가 오랫동안 서버 사이드 자바스크립트의 사실상 표준이었지만, 서버리스·엣지 컴퓨팅 환경이 늘면서 런타임 시작 시간 자체가 병목이 되는 워크로드가 많아졌다. Node.js는 V8 엔진을 초기화하고, libuv 이벤트 루프를 띄우고, 모듈 시스템(CommonJS/ESM)을 해석하는 데 수십~수백 밀리초가 걸린다. 요청마다 새 컨테이너를 띄우는 서버리스 함수라면 이 시작 비용이 매 요청에 그대로 전가된다. Bun은 이 문제를 자바스크립트 엔진 선택부터 런타임 전체 구현 언어까지 다시 설계해 접근한 프로젝트다.

## 핵심 개념 1 — V8 대신 JavaScriptCore, libuv 대신 자체 이벤트 루프

Bun의 가장 근본적인 차이는 자바스크립트 엔진으로 Chrome/Node.js의 V8이 아니라 Safari의 JavaScriptCore(JSC)를 채택했다는 점이다. JSC는 시작 시간과 메모리 사용량 최적화에 강점이 있는 엔진으로 알려져 있으며, Bun 팀은 이를 서버 워크로드에 맞게 추가로 튜닝했다. 런타임 자체도 Node.js처럼 C++이 아니라 Zig 언어로 작성됐는데, Zig는 가비지 컬렉션이 없고 컴파일 타임 최적화가 강력해 저수준 시스템 프로그래밍에 적합하다는 평가를 받는다. 이벤트 루프 역시 libuv를 그대로 쓰는 대신 리눅스의 io_uring을 적극 활용하는 자체 I/O 계층을 구현해, 시스템 콜 오버헤드를 줄이는 방향으로 설계됐다.

## 핵심 개념 2 — 번들러·테스트 러너·패키지 매니저의 런타임 통합

Node.js 생태계에서는 런타임(Node.js), 번들러(webpack/esbuild), 테스트 러너(Jest), 패키지 매니저(npm/yarn/pnpm)가 각각 독립적인 도구로 존재하고 사용자가 직접 조합해야 한다. Bun은 이 네 가지 역할을 하나의 바이너리 안에 네이티브로 통합했다. `bun install`은 npm보다 훨씬 빠른 병렬 다운로드와 전역 캐시 하드링크를 사용하고, `bun build`는 별도 설정 없이도 즉시 번들링을 수행하며, `bun test`는 Jest 호환 API를 자체 구현으로 제공한다. 이 통합은 단순히 편의성 문제가 아니라, 각 도구 사이의 프로세스 경계와 파일 I/O 왕복을 줄여 개발 워크플로 전체의 지연시간을 낮추는 효과로 이어진다.

| 항목 | Node.js | Deno | Bun |
|---|---|---|---|
| JS 엔진 | V8 | V8 | JavaScriptCore |
| 구현 언어 | C++ | Rust | Zig |
| 콜드 스타트 | 상대적으로 느림 | 중간 | 매우 빠름(수~수십ms) |
| 번들러/테스트 통합 | 별도 도구 필요 | 일부 내장 | 완전 네이티브 통합 |

## 코드 예제 — Bun 네이티브 API로 HTTP 서버 띄우기

```javascript
// Bun.serve()는 별도 프레임워크 없이 고성능 HTTP 서버를 즉시 제공한다
Bun.serve({
  port: 3000,
  fetch(req) {
    const url = new URL(req.url);
    if (url.pathname === "/health") {
      return new Response("OK", { status: 200 });
    }
    return new Response("Not Found", { status: 404 });
  },
});

// package.json 스크립트 없이 바로 실행: bun run server.ts (TypeScript 트랜스파일 내장)
```

Bun은 TypeScript 파일을 별도 트랜스파일 단계 없이 바로 실행할 수 있고, Web 표준 `fetch`/`Request`/`Response` API를 서버 사이드에서도 그대로 제공해 브라우저 코드와의 API 일관성을 높인다.

## 실무 포인트

- **Node.js API 호환성은 대부분이지 전부가 아니다.** Bun은 Node.js 코어 모듈 대부분을 구현했지만, 일부 네이티브 애드온(N-API)이나 드물게 쓰이는 API는 완전히 동작하지 않을 수 있으므로 마이그레이션 전 실제 의존성 목록으로 호환성을 검증해야 한다.
- **생태계 성숙도와 속도를 함께 저울질해야 한다.** Bun의 성능 이점은 명확하지만, 대규모 프로덕션에서의 검증 사례는 Node.js보다 아직 적으므로 트래픽이 큰 핵심 서비스에는 점진적 도입이 안전하다.
- **콜드 스타트가 중요한 워크로드(서버리스, CLI 도구)에서 이점이 가장 크다.** 반대로 이미 장시간 실행되는 상시 서버라면 시작 시간 차이의 체감 효과가 크지 않을 수 있다.

## 마무리 요약

- Bun은 V8 대신 JavaScriptCore를, C++ 대신 Zig를 선택하고 자체 I/O 계층을 구현해 Node.js 대비 콜드 스타트 시간을 극적으로 줄인 런타임이다.
- 런타임·번들러·테스트 러너·패키지 매니저를 하나의 바이너리로 네이티브 통합해, 여러 도구 사이의 프로세스 경계로 인한 오버헤드를 없앴다.
- Node.js API 호환성이 대부분이라도 완전하지 않으므로, 콜드 스타트 이점이 큰 워크로드부터 점진적으로 도입하며 실제 의존성 호환성을 검증하는 것이 안전하다.

## 참고 자료

- [Bun 공식 문서](https://bun.sh/docs)
- [Bun 공식 블로그 — Bun is a fast JavaScript runtime](https://bun.sh/blog)
