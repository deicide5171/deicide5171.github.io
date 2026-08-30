---
layout: single
title: "TCP 혼잡제어 심화 — BBR과 CUBIC은 무엇이 다른가"
date: 2026-09-24 13:40:00 +0530
categories: infra
tags: ["TCP", "혼잡제어", "BBR", "CUBIC", "네트워크성능"]
toc: true
toc_sticky: true
excerpt: "리눅스 기본 혼잡제어 알고리즘인 CUBIC이 손실 신호에 의존하는 구조적 한계와, 구글이 개발해 유튜브 등에서 쓰이는 BBR이 대역폭·RTT를 직접 모델링해 이 한계를 넘어서려는 방식을 비교했다."
---

## 왜 지금 혼잡제어 알고리즘을 다시 봐야 하는가

TCP 연결의 처리량은 애플리케이션 코드나 서버 스펙만으로 결정되지 않는다. 커널 안에서 동작하는 혼잡제어(congestion control) 알고리즘이 "지금 네트워크가 얼마나 혼잡한지"를 추정하고 전송 속도를 조절하는 방식에 따라 같은 네트워크 조건에서도 실제 처리량이 크게 달라진다. 리눅스는 오랫동안 CUBIC을 기본 알고리즘으로 써왔지만, 장거리·고대역폭 네트워크나 손실률이 낮지 않은 무선 환경에서 CUBIC의 한계가 드러나면서 구글이 개발한 BBR(Bottleneck Bandwidth and Round-trip propagation time)이 대안으로 자리 잡았다. 두 알고리즘의 근본적인 설계 철학 차이를 이해하면 어떤 워크로드에 어떤 알고리즘이 유리한지 판단하는 감각을 얻을 수 있다.

## 핵심 개념 1 — CUBIC은 손실을 신호로 쓴다

CUBIC은 손실 기반(loss-based) 혼잡제어다. 패킷 손실이 발생하지 않는 한 전송 윈도우 크기를 3차 함수 곡선을 따라 계속 늘리다가, 패킷 손실(타임아웃이나 중복 ACK)을 감지하면 그 순간을 "네트워크가 혼잡하다"는 신호로 해석해 윈도우를 급격히 줄인다. 이 방식은 구현이 단순하고 오랫동안 검증됐지만, 근본적인 문제는 "손실이 곧 혼잡"이라는 전제가 항상 성립하지는 않는다는 점이다. 무선 네트워크에서는 혼잡과 무관한 전파 손실만으로도 패킷이 유실될 수 있고, 이때 CUBIC은 실제로 여유가 있는 네트워크에서도 불필요하게 윈도우를 줄여 처리량을 낮춘다.

## 핵심 개념 2 — BBR은 대역폭과 RTT를 직접 추정한다

BBR은 손실을 기다리는 대신, 전송 중인 패킷의 ACK 도착 패턴을 관찰해 병목 지점의 실제 대역폭(BtlBw)과 왕복 지연시간의 최솟값(RTprop)을 직접 추정한다. 이 두 값을 곱한 것이 이론적으로 최적인 전송 윈도우(BDP, Bandwidth-Delay Product)이며, BBR은 전송 속도를 이 최적점 근처로 유지하려고 시도한다. 손실이 발생해도 그 자체를 혼잡 신호로 즉시 해석하지 않고, 실제 대역폭 추정치가 변했는지를 기준으로 판단하기 때문에 무선 구간처럼 혼잡과 무관한 손실이 잦은 환경에서 CUBIC보다 훨씬 안정적인 처리량을 낸다.

| 항목 | CUBIC | BBR |
|---|---|---|
| 혼잡 판단 기준 | 패킷 손실 | 대역폭·RTT 변화 추정 |
| 무손실 무선 환경 | 불필요하게 윈도우 축소 | 손실 무시하고 처리량 유지 |
| 버퍼블로트(bufferbloat) | 버퍼가 가득 찰 때까지 채움 | RTprop 기준으로 버퍼 점유 최소화 지향 |
| 공정성(fairness) | 동일 CUBIC 간 잘 검증됨 | CUBIC과 공존 시 자원 점유 이슈 논쟁 존재 |

## 예제 — 리눅스에서 혼잡제어 알고리즘 확인·변경

```bash
# 현재 사용 가능한 혼잡제어 알고리즘 목록
sysctl net.ipv4.tcp_available_congestion_control

# 현재 기본 알고리즘 확인
sysctl net.ipv4.tcp_congestion_control

# BBR 커널 모듈 로드 및 기본값 변경 (커널이 BBR을 지원해야 함)
modprobe tcp_bbr
sysctl -w net.ipv4.tcp_congestion_control=bbr

# 특정 소켓에만 적용하려면 애플리케이션에서 setsockopt(TCP_CONGESTION) 사용
```

## 실무 포인트

- **BBR 도입 전 커널 버전과 큐잉 규율(qdisc)을 함께 확인하라.** BBR은 초기 버전에서 `fq`(fair queueing) qdisc와 함께 쓰는 것을 권장했으며, 기본 `pfifo_fast`와 조합하면 페이싱(pacing)이 제대로 동작하지 않을 수 있다.
- **BBR과 CUBIC 흐름이 같은 병목 링크를 공유하는 상황을 사전에 테스트하라.** 특히 초기 BBR 버전은 공정성 논쟁이 있었으므로, 프로덕션 전환 전 실제 트래픽 패턴에서 두 알고리즘이 섞였을 때의 처리량 분배를 검증하는 것이 안전하다.
- **CDN이나 장거리 API 호출이 많은 서비스일수록 BBR의 이득이 크다.** RTT가 크고 손실이 간헐적으로 발생하는 장거리 구간에서 CUBIC 대비 처리량 개선폭이 가장 뚜렷하게 나타난다.

## 마무리 요약

- CUBIC은 패킷 손실을 혼잡의 신호로 해석하는 손실 기반 알고리즘이며, 손실과 혼잡이 무관한 환경(무선 등)에서 불필요하게 처리량을 낮추는 한계가 있다.
- BBR은 대역폭과 RTT를 직접 모델링해 손실 여부와 무관하게 최적 전송 윈도우를 유지하려 시도한다.
- 두 알고리즘의 선택은 네트워크 환경(RTT, 손실 원인)과 공존하는 다른 흐름의 특성을 함께 고려해 결정해야 하며, 전환 전 qdisc 설정과 공정성 검증이 필요하다.

## 참고 자료

- [Google - BBR Congestion Control (IETF draft)](https://datatracker.ietf.org/doc/html/draft-cardwell-iccrg-bbr-congestion-control)
- [Linux kernel - tcp_bbr documentation](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt)
