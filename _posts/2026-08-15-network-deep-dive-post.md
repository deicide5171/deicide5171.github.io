---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — TCP/TLS와 네트워크 심화"
date: 2026-08-15 15:10:00 +0530
categories: dev-insight
tags: ["tcp", "tls", "http2", "http3", "네트워크", "학습로드맵"]
toc: true
toc_sticky: true
excerpt: "Flutter 앱, 네이버 클라우드 지도 API, PostGIS, AI 에이전트 프로토콜, 분산 시스템까지 다뤄온 이 블로그의 다음 학습 주제로 TCP 3-way handshake, TLS 핸드셰이크, HTTP/2·HTTP/3, 커넥션 풀링 같은 네트워크 심화 지식을 추천하는 이유를 정리한다."
---

## 왜 지금 이 주제인가

이 블로그는 지금까지 Flutter 앱 개발, 네이버 클라우드 지도 API 연동, PostGIS 기반 공간 데이터, AI 에이전트 프로토콜(MCP, A2A), 그리고 분산 SQL과 캐시 스탬피드 같은 분산 시스템 문제, Postgres 기반 워크플로우 오케스트레이션, Docker/CI-CD 파이프라인까지 다양한 층위를 다뤄왔다. 그런데 이 모든 글에서 "요청은 결국 어떻게 상대 서버까지 도달하는가"라는 가장 아래층의 질문은 아직 다루지 않았다.

MCP나 A2A로 에이전트끼리 통신하든, 네이버 클라우드 지도 API를 호출하든, 분산 SQL 노드끼리 데이터를 주고받든, 그 모든 통신은 결국 TCP 연결 위에서 TLS로 암호화되고 HTTP 프로토콜로 실려 나간다. 커넥션이 왜 느린지, 왜 첫 요청만 유독 느린지, 왜 커넥션 풀 설정을 잘못하면 장애가 나는지를 이해하려면 이 계층을 알아야 한다. Docker/CI-CD 글에서 다룬 배포 파이프라인도, 캐시 스탬피드 글에서 다룬 재시도 폭주 문제도 결국 네트워크 계층의 동작을 모르면 절반만 이해한 것이다. 그래서 다음 학습 주제로 **TCP 3-way handshake, TLS 핸드셰이크, HTTP/2·HTTP/3, 커넥션 풀링** 같은 네트워크 심화 지식을 추천한다.

이 주제는 단순히 "네트워크 이론"이 아니라, 지금까지 만들어온 앱과 API, 분산 시스템의 지연 시간과 장애를 실제로 디버깅할 수 있는 도구를 준다는 점에서 실용적이다.

## 학습 로드맵

| 단계 | 주제 | 왜 필요한가 |
|---|---|---|
| 1 | TCP 3-way handshake와 슬로우 스타트 | 연결 수립 지연과 처리량 증가 곡선의 근본 원리 이해 |
| 2 | TLS 핸드셰이크(TLS 1.2 vs 1.3) | HTTPS 첫 요청이 느린 이유와 암호화 비용 파악 |
| 3 | HTTP/1.1 vs HTTP/2 vs HTTP/3 | 멀티플렉싱, 헤더 압축, QUIC이 지연을 줄이는 원리 |
| 4 | 커넥션 풀링과 Keep-Alive | 매 요청마다 핸드셰이크를 반복하지 않는 재사용 전략 |
| 5 | DNS 조회와 CDN·엣지 라우팅 | 요청이 실제로 어떤 경로로 서버에 도달하는지 파악 |

이 순서대로 학습하면 "요청 한 번"이 클라이언트를 떠나 서버 응답으로 돌아오기까지 거치는 모든 구간을 계층별로 설명할 수 있게 된다.

## 핵심 개념: TCP 3-way handshake와 TLS 핸드셰이크

**TCP 3-way handshake**는 클라이언트와 서버가 데이터를 주고받기 전에 `SYN → SYN-ACK → ACK` 세 번의 패킷 교환으로 연결을 수립하는 과정이다. 이 왕복만으로도 최소 1-RTT(Round Trip Time)가 소요되며, 지리적으로 먼 서버일수록 이 비용이 체감상 커진다. 네이버 클라우드 지도 API처럼 원격 API를 자주 호출하는 앱에서 응답이 늦게 느껴지는 원인 중 하나가 바로 이 연결 수립 비용이다.

HTTPS를 쓴다면 TCP 핸드셰이크 위에 **TLS 핸드셰이크**가 추가로 얹힌다. TLS 1.2는 인증서 교환과 키 협상에 추가로 1-2 RTT가 더 필요했지만, TLS 1.3은 핸드셰이크를 1-RTT로, 재접속 시에는 0-RTT까지 단축했다. 즉 같은 HTTPS 요청이라도 TLS 버전에 따라 첫 바이트를 받기까지 걸리는 시간이 크게 달라진다. 분산 SQL 노드 간 통신이나 MCP 에이전트 간 통신에서 mTLS(상호 인증)를 쓴다면 이 비용은 양방향으로 발생하므로 더욱 신경 써야 한다.

## 예제: TLS 핸드셰이크를 curl로 직접 관찰하기

아래처럼 `curl -v` 옵션으로 TCP 연결과 TLS 핸드셰이크가 실제로 어떤 순서로 일어나는지 확인할 수 있다.

```bash
$ curl -v --http2 https://example.com

*   Trying 93.184.216.34:443...
* Connected to example.com (93.184.216.34) port 443 (#0)   # TCP 3-way handshake 완료
* ALPN: offers h2,http/1.1
* TLSv1.3 (OUT), TLS handshake, Client hello (1):          # TLS 핸드셰이크 시작
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
* ALPN: server accepted h2                                  # HTTP/2 협상 성공
> GET / HTTP/2
> Host: example.com
>
< HTTP/2 200
```

`ALPN`(Application-Layer Protocol Negotiation)이 TLS 핸드셰이크 도중에 HTTP/2 사용 여부를 함께 협상한다는 점, 그리고 TCP 연결 수립과 TLS 협상이 별개의 단계로 순차 진행된다는 점을 로그에서 직접 확인할 수 있다.

## 실무 포인트

- **커넥션을 재사용한다**: HTTP Keep-Alive나 커넥션 풀을 쓰면 매 요청마다 TCP·TLS 핸드셰이크를 반복하지 않아도 되어, 특히 짧은 요청을 자주 보내는 서비스에서 지연이 크게 줄어든다.
- **TLS 세션 재개(Session Resumption)를 활용한다**: 세션 티켓이나 세션 ID를 이용하면 재접속 시 전체 핸드셰이크를 생략하고 훨씬 빠르게 연결을 복구할 수 있다.
- **HTTP/2·HTTP/3 지원 여부를 확인한다**: HTTP/2는 하나의 TCP 연결 위에서 여러 요청을 멀티플렉싱하고, HTTP/3(QUIC)은 TCP 자체를 UDP 기반으로 대체해 헤드 오브 라인 블로킹 문제를 줄인다.
- **커넥션 풀 크기 설정에 주의한다**: 풀이 너무 작으면 요청이 대기하고, 너무 크면 서버 쪽 리소스를 낭비하거나 캐시 스탬피드 글에서 다뤘던 것과 비슷한 방식으로 백엔드에 과부하를 줄 수 있다.

## 3줄 요약

- 지금까지 다룬 API 연동, 분산 시스템, AI 에이전트 통신은 모두 TCP·TLS 계층 위에서 동작하므로, 이 계층을 이해하면 지연·장애 디버깅 능력이 크게 는다.
- TCP 3-way handshake와 TLS 핸드셰이크가 각각 최소 1-RTT를 소비하며, TLS 1.3과 HTTP/2·HTTP/3은 이 비용을 줄이기 위한 발전이다.
- 커넥션 풀링과 Keep-Alive로 핸드셰이크 반복을 줄이는 것이 실무에서 가장 즉각적인 효과를 내는 최적화다.

## 참고 자료

- [MDN — An overview of HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview)
- [Cloudflare Learning Center — What happens in a TLS handshake?](https://www.cloudflare.com/learning/ssl/what-happens-in-a-tls-handshake/)
- [RFC 9000 — QUIC: A UDP-Based Multiplexed and Secure Transport](https://www.rfc-editor.org/rfc/rfc9000)
- [High Performance Browser Networking (Ilya Grigorik)](https://hpbn.co/)
