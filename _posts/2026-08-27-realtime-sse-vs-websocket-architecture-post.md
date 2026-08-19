---
layout: single
title: "실시간 기능, 소켓부터 열 필요는 없다 — SSE vs WebSocket vs 롱폴링 아키텍처 결정"
date: 2026-08-27 12:45:00 +0530
categories: system-design
tags: ["sse", "websocket", "long-polling", "realtime", "architecture", "scalability"]
toc: true
toc_sticky: true
excerpt: "실시간 알림, 채팅, 대시보드 업데이트를 만들 때 SSE·WebSocket·롱폴링 중 무엇을 고를지, 그리고 각각을 어떻게 스케일아웃할지 정리한다."
---

"실시간 기능이 필요하다"는 요구가 들어오면 반사적으로 WebSocket을 꺼내는 팀이 많다. 하지만 실제로는 서버가 클라이언트에게 데이터를 흘려주기만 하면 되는 경우(알림, 대시보드 갱신, 진행률 표시)가 대부분이고, 이런 경우 WebSocket은 필요 이상의 복잡도를 끌고 온다. 양방향 통신이 필요 없다면 더 단순한 선택지가 있고, 반대로 채팅이나 협업 편집처럼 양방향이 필수라면 WebSocket이 맞는 선택이다.

이 글에서는 SSE(Server-Sent Events), WebSocket, 롱폴링(Long Polling) 세 가지를 통신 모델, 인프라 호환성, 스케일아웃 난이도 기준으로 비교한다.

## 핵심 개념 1: 세 방식의 근본적인 차이

**롱폴링**은 일반 HTTP 요청을 서버가 응답할 데이터가 생길 때까지 붙잡아두는 방식이다. 프로토콜적으로는 평범한 HTTP라서 어떤 프록시·로드밸런서와도 마찰이 없지만, 매 응답마다 연결을 다시 맺어야 하고 서버는 대기 중인 요청 수만큼 스레드/커넥션을 붙잡고 있어야 한다.

**SSE**는 HTTP 위에서 서버가 하나의 연결을 계속 열어둔 채 `text/event-stream` 형식으로 이벤트를 계속 흘려보내는 단방향(서버→클라이언트) 프로토콜이다. `EventSource` 브라우저 API가 재연결과 마지막으로 받은 이벤트 ID(`Last-Event-ID`) 추적을 자동으로 해준다.

**WebSocket**은 HTTP 핸드셰이크로 시작해 별도의 양방향 프로토콜로 업그레이드된다. 클라이언트도 언제든 서버로 메시지를 보낼 수 있고, 텍스트뿐 아니라 바이너리 프레임도 지원한다.

| 구분 | 롱폴링 | SSE | WebSocket |
|---|---|---|---|
| 통신 방향 | 서버→클라 (요청마다) | 서버→클라 (단방향) | 양방향 |
| 프로토콜 | 순수 HTTP | HTTP (event-stream) | 별도 프로토콜(업그레이드) |
| 자동 재연결 | 직접 구현 | 브라우저 내장 | 직접 구현 |
| 프록시/방화벽 호환성 | 매우 좋음 | 좋음 | 일부 구형 프록시에서 문제 |
| 바이너리 지원 | 가능(응답 바디) | 불가(텍스트만) | 가능 |
| 서버 리소스 | 요청당 커넥션 | 커넥션 유지 | 커넥션 유지 |

## 핵심 개념 2: 인프라 호환성과 로드밸런서 문제

WebSocket은 L7 로드밸런서가 업그레이드 핸드셰이크를 올바르게 처리해야 하고, 일부 사내망 프록시나 오래된 CDN은 여전히 WebSocket 업그레이드를 막거나 유휴 타임아웃을 짧게 잡아 연결을 끊는다. SSE와 롱폴링은 순수 HTTP이므로 이런 문제에서 훨씬 자유롭다. 반대로 SSE는 브라우저의 동시 연결 수 제한(HTTP/1.1 기준 도메인당 6개)에 걸릴 수 있는데, HTTP/2를 쓰면 이 제한이 사실상 사라진다.

로드밸런서의 유휴 타임아웃(idle timeout)은 SSE·WebSocket 모두의 공통 함정이다. 로드밸런서 기본 타임아웃(흔히 60초)이 애플리케이션의 하트비트 주기보다 짧으면, 아무 이벤트도 없는 조용한 연결이 중간에서 끊긴다. SSE는 주기적으로 주석(`: heartbeat\n\n`) 이벤트를 보내 연결을 살아있게 유지해야 한다.

<img src="/assets/images/posts/2026-08-27-realtime-sse-vs-websocket-architecture-1.svg" alt="롱폴링, SSE, WebSocket 세 가지 통신 방식의 연결 유지 구조와 데이터 흐름 방향 비교도" style="width:100%;">

## 예제: SSE 엔드포인트와 재연결 대응(Node.js/Express)

```javascript
app.get('/events', (req, res) => {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });
  res.flushHeaders();

  // Last-Event-ID로 재연결 시 놓친 이벤트부터 재전송
  const lastId = req.headers['last-event-id'];
  const backlog = lastId ? getEventsAfter(lastId) : [];
  backlog.forEach(sendEvent);

  const heartbeat = setInterval(() => res.write(': heartbeat\n\n'), 25000);
  const unsubscribe = subscribeToChannel(req.params.channel, (event) => sendEvent(event));

  function sendEvent(event) {
    res.write(`id: ${event.id}\n`);
    res.write(`data: ${JSON.stringify(event.payload)}\n\n`);
  }

  req.on('close', () => { clearInterval(heartbeat); unsubscribe(); });
});
```

## 실무 포인트

- **스케일아웃은 세 방식 모두 pub/sub 백플레인이 필요하다**: 서버 인스턴스가 여러 대면, A 인스턴스에 연결된 클라이언트에게 B 인스턴스가 받은 이벤트를 전달할 방법이 필요하다. Redis Pub/Sub이나 Kafka를 백플레인으로 두고, 각 인스턴스는 거기서 받은 메시지를 자신에게 연결된 클라이언트에게만 릴레이하는 구조가 표준적이다.
- **연결 수는 서버의 실제 병목이다**: SSE·WebSocket 모두 연결 하나당 파일 디스크립터와 메모리를 소비한다. 동시 접속 10만을 노린다면 스레드-per-connection 모델보다 이벤트 루프 기반(Node.js, Netty, Vert.x) 서버가 유리하고, WebSocket 게이트웨이를 별도 서비스로 분리해 비즈니스 로직 서버와 부하를 나누는 것도 흔한 패턴이다.
- **양방향이 필요 없다면 WebSocket을 선택하지 않는다**: WebSocket은 재연결·백프레셔·프레이밍을 직접 관리해야 하는 복잡도를 감수하는 대신 양방향성을 얻는다. 서버→클라이언트 단방향 알림이 전부라면 SSE로 이 복잡도를 대부분 피할 수 있다.

## 3줄 요약

- 서버→클라이언트 단방향이면 SSE, 양방향이 필수면 WebSocket, 인프라 호환성이 최우선이면 롱폴링을 우선 고려한다.
- 로드밸런서 유휴 타임아웃은 SSE·WebSocket 공통 함정이며 하트비트로 방어해야 한다.
- 어떤 방식이든 여러 서버 인스턴스로 확장하려면 Redis/Kafka 같은 pub/sub 백플레인으로 인스턴스 간 이벤트를 릴레이해야 한다.

## 참고 자료

- [MDN: Server-Sent Events 사용하기](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [MDN: The WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [RFC 6455: The WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
