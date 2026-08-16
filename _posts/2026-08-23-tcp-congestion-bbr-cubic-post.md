---
layout: single
title: "TCP 혼잡 제어의 두 철학 — 손실을 기다리는 CUBIC, 대역폭을 재는 BBR"
date: 2026-08-23 12:40:00 +0530
categories: infra
tags: ["tcp", "bbr", "cubic", "혼잡제어", "네트워크", "리눅스"]
toc: true
toc_sticky: true
excerpt: "리눅스 기본값 CUBIC과 구글이 만든 BBR는 '네트워크가 혼잡하다'는 신호를 완전히 다르게 읽는다. 두 알고리즘의 대역폭 추정 방식 차이와 서버에 BBR를 켜야 할 때·켜지 말아야 할 때의 판단 기준을 정리한다."
---

서버 대역폭은 계속 늘었는데, 해외 사용자 다운로드 속도는 왜 그만큼 안 나올까. 원인이 애플리케이션이 아니라 커널의 TCP 혼잡 제어 알고리즘인 경우가 의외로 많다. 리눅스는 오랫동안 **CUBIC**을 기본값으로 써왔고, 대부분의 서버는 이 사실조차 의식하지 않은 채 운영된다. 그런데 구글이 자사 서비스와 유튜브에 적용해 성과를 공개한 **BBR**가 등장한 이후, "우리 서버도 BBR로 바꿔야 하나"는 질문이 인프라 튜닝의 단골 주제가 됐다.

문제는 이 질문에 "무조건 바꿔라"로 답할 수 없다는 점이다. 두 알고리즘은 단순히 성능 수치가 다른 게 아니라, **네트워크가 혼잡하다는 사실을 감지하는 방법 자체가 다르다.** 이 차이를 이해해야 어떤 환경에서 BBR가 이득이고 어떤 환경에서는 오히려 해가 되는지 판단할 수 있다.

## CUBIC: 패킷 손실이 곧 혼잡 신호다

CUBIC은 전통적인 **손실 기반(loss-based)** 계열이다. 혼잡 윈도우(cwnd)를 계속 키우다가 패킷 손실이 감지되면 "경로 어딘가의 버퍼가 넘쳤다"고 해석하고 윈도우를 줄인 뒤, 직전 최대치(W_max)를 향해 3차 함수(cubic function) 곡선으로 다시 키운다. W_max 근처에서는 완만하게 접근해 안정성을 확보하고, 그 지점을 넘어서면 다시 공격적으로 탐색하는 구조다. RTT가 커도 윈도우 성장 속도가 RTT에 덜 묶이도록 설계되어, 이전 세대인 Reno보다 대역폭이 크고 지연이 긴 경로(long fat network)에서 유리하다.

핵심은 CUBIC이 대역폭을 **직접 추정하지 않는다**는 것이다. "손실이 날 때까지 밀어붙인다"가 탐색 방법의 전부이므로, 경로 위의 버퍼가 가득 찰 때까지 데이터를 채운다. 라우터 버퍼가 과도하게 큰 요즘 환경에서는 이 동작이 **버퍼블로트(bufferbloat)** — 처리량은 안 늘면서 대기 큐 때문에 RTT만 치솟는 현상 — 를 유발한다. 또 무선망처럼 혼잡과 무관한 랜덤 손실이 있는 경로에서는, 손실을 혼잡으로 오판해 불필요하게 속도를 줄인다.

## BBR: 병목 대역폭과 최소 RTT를 직접 측정한다

BBR(Bottleneck Bandwidth and Round-trip propagation time)는 이름 그대로 **모델 기반(model-based)** 접근이다. 손실을 기다리는 대신, ACK가 돌아오는 속도로 **병목 구간의 실제 전달률(BtlBw)**을, 큐가 비어 있을 때의 왕복 시간으로 **경로의 최소 RTT(RTprop)**를 지속적으로 추정한다. 이 둘을 곱한 값이 **BDP(대역폭-지연 곱)**, 즉 큐를 쌓지 않고 경로에 실을 수 있는 최적 데이터양이다. BBR는 inflight 데이터를 BDP 근처로 유지하고, 페이싱(pacing)으로 패킷을 추정 대역폭에 맞춰 고르게 흘려보낸다. 주기적으로 전송률을 살짝 올렸다 내리며(ProbeBW) 대역폭 변화를 재탐색하고, RTprop 갱신을 위해 가끔 inflight를 확 줄이는(ProbeRTT) 구간도 갖는다.

<img src="/assets/images/posts/2026-08-23-tcp-congestion-bbr-cubic-1.svg" alt="inflight 데이터양에 따른 전송 속도·RTT 그래프와 BBR·CUBIC의 동작 지점 비교" style="width:100%;">

위 그림처럼 CUBIC은 버퍼가 가득 차 손실이 나는 오른쪽 끝에서 동작하고, BBR는 속도는 최대이면서 지연은 최소인 BDP 지점을 노린다.

| 구분 | CUBIC | BBR |
|---|---|---|
| 혼잡 신호 | 패킷 손실 | 전달률·RTT 측정 모델 |
| 대역폭 추정 | 없음(손실까지 탐색) | BtlBw를 직접 측정 |
| 버퍼 사용 | 가득 채움(버퍼블로트 유발) | BDP 수준 유지(지연 낮음) |
| 랜덤 손실 내성 | 약함 | 강함 |
| 리눅스 지원 | 기본값 | 커널 4.9+ 내장(tcp_bbr) |

## 서버에 BBR 적용하기

리눅스에서 BBR 적용은 sysctl 두 줄이면 된다. BBR는 페이싱이 전제이므로 qdisc를 `fq`로 함께 설정한다. 비교적 최근 커널은 TCP 내부 페이싱을 지원해 `fq`가 필수는 아니지만, 공식 문서가 여전히 `fq`를 권장한다.

```bash
# 사용 가능한 알고리즘과 현재 값 확인
sysctl net.ipv4.tcp_available_congestion_control
sysctl net.ipv4.tcp_congestion_control

# /etc/sysctl.d/90-bbr.conf 로 영구 적용
cat <<'EOF' | sudo tee /etc/sysctl.d/90-bbr.conf
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
sudo sysctl --system

# 실제 커넥션이 bbr를 쓰는지 확인 (기존 커넥션은 영향 없음, 신규부터 적용)
ss -ti state established | grep -o 'bbr[^ ]*' | head
```

적용 후에는 처리량만 보지 말고 `ss -ti`의 pacing_rate, 재전송률, 그리고 클라이언트 체감 지연(p95 응답 시간)을 함께 비교해야 효과를 제대로 판단할 수 있다.

## 언제 쓰고, 언제 쓰지 말아야 하나

**BBR가 유리한 경우**는 뚜렷하다. 해외 사용자 대상 다운로드·스트리밍처럼 RTT가 길고 경로에 랜덤 손실이 섞이는 인터넷 구간, 모바일망 대상 API 서버, 버퍼블로트가 심한 경로다. 이런 환경에서는 손실 몇 번에 주저앉는 CUBIC 대비 처리량과 지연 모두 개선되는 사례가 많다.

**신중해야 하는 경우**도 분명하다. 첫째, 같은 데이터센터 내부 통신처럼 RTT가 수백 마이크로초 수준이고 손실이 거의 없는 구간에서는 CUBIC도 이미 최적에 가깝게 동작하므로 바꿀 이유가 약하다. 둘째, **공정성 문제**다. 초기 버전 BBR(v1)는 손실 기반 흐름과 한 병목을 공유할 때 대역폭을 과점하는 경향이 보고됐다. 내 서버는 빨라져도 같은 회선의 다른 트래픽을 밀어낼 수 있다는 뜻이다. 구글은 이를 개선한 후속 버전(v2, v3)을 공개해왔지만, 현 시점 기준 배포판 커널에 기본 포함된 것은 초기 계열이므로 공유 인프라에서는 계측 후 도입해야 한다.

흔한 함정 하나를 짚자면, **로드밸런서나 프록시 뒤의 백엔드 서버에만 BBR를 켜고 효과가 없다고 결론 내리는 것**이다. TCP 커넥션은 홉 단위로 종료된다. 사용자와 긴 RTT 구간을 맺는 쪽은 LB/프록시(또는 CDN 엣지)이므로, 혼잡 제어를 바꿔야 할 지점도 그곳이다. 백엔드-LB 구간은 대개 저지연 내부망이라 BBR의 이득이 거의 없다. 반대로 정답은 사용자와 직접 TCP를 맺는 종단에 적용하고, 내부 구간은 CUBIC을 유지하는 것이다.

## 마무리 요약

- CUBIC은 손실이 날 때까지 버퍼를 채우는 손실 기반, BBR는 병목 대역폭(BtlBw)과 최소 RTT(RTprop)를 직접 측정해 BDP 지점에서 동작하는 모델 기반이다.
- 긴 RTT·랜덤 손실·버퍼블로트가 있는 인터넷 구간(해외 사용자, 모바일망)에서는 BBR가 유리하고, 저지연 내부망에서는 굳이 바꿀 이유가 약하다.
- 적용 지점은 사용자와 직접 TCP를 맺는 종단(LB·프록시·엣지)이어야 하며, 도입 전후로 처리량·재전송률·p95 지연을 함께 계측해 판단한다.

## 참고 자료

- [BBR: Congestion-Based Congestion Control (ACM Queue)](https://queue.acm.org/detail.cfm?id=3022184)
- [RFC 9438 — CUBIC for Fast and Long-Distance Networks](https://datatracker.ietf.org/doc/html/rfc9438)
- [google/bbr — BBR 개발 저장소](https://github.com/google/bbr)
- [Linux ip-sysctl 문서 (tcp_congestion_control)](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt)
