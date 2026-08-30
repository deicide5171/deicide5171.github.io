---
layout: single
title: "Zero Trust 네트워크 아키텍처 심화 — mTLS와 SPIFFE/SPIRE로 서비스 신원 증명하기"
date: 2026-09-24 13:40:00 +0530
categories: infra
tags: ["ZeroTrust", "mTLS", "SPIFFE", "SPIRE", "서비스보안"]
toc: true
toc_sticky: true
excerpt: "네트워크 위치만으로 신뢰를 부여하던 방식이 클라우드 네이티브 환경에서 왜 더 이상 통하지 않는지 짚고, SPIFFE 표준과 SPIRE로 서비스마다 검증 가능한 신원을 발급해 mTLS를 자동화하는 구조를 정리했다."
---

## 왜 지금 Zero Trust를 다시 봐야 하는가

전통적인 네트워크 보안 모델은 "사내망 안에 있으면 신뢰할 수 있다"는 경계 기반(perimeter-based) 사고에 기대어 왔다. 방화벽으로 외부와 내부를 나누고, 내부 트래픽은 상대적으로 느슨하게 다뤘다. 문제는 마이크로서비스와 컨테이너 환경에서는 이 경계 자체가 사실상 무의미해진다는 점이다. 파드는 수시로 뜨고 사라지며 IP는 재사용되고, 하나의 워크로드가 침해당하면 같은 네트워크 안의 다른 서비스로 옆으로 이동(lateral movement)하기가 너무 쉬워진다. Zero Trust는 "네트워크 위치가 아니라 신원(identity)을 기준으로 매 요청마다 검증한다"는 원칙으로 이 문제에 접근하며, 이를 실제로 구현하는 핵심 메커니즘이 서비스 간 mTLS(상호 TLS)와 그 신원을 관리하는 SPIFFE/SPIRE다.

## 핵심 개념 1 — SPIFFE: 워크로드에게 검증 가능한 신원을 부여하는 표준

SPIFFE(Secure Production Identity Framework For Everyone)는 워크로드마다 SPIFFE ID라는 고유한 URI 형식 신원(예: `spiffe://example.org/ns/payments/sa/order-service`)을 부여하는 표준을 정의한다. 이 신원은 IP나 호스트명처럼 배포 환경에 따라 바뀌는 값이 아니라, 워크로드의 논리적 정체성 자체를 나타낸다. 이 신원은 X.509 인증서(SVID, SPIFFE Verifiable Identity Document) 형태로 발급되며, 서비스는 이 인증서를 이용해 상대방에게 "나는 정말 order-service다"라는 것을 암호학적으로 증명할 수 있다.

## 핵심 개념 2 — SPIRE가 인증서 발급·회전을 자동화하는 방식

SPIRE는 SPIFFE 표준의 실제 구현체로, SPIRE Server와 각 노드에 배치되는 SPIRE Agent로 구성된다. 워크로드가 인증서를 요청하면, SPIRE Agent는 커널 정보(프로세스 UID, 컨테이너 cgroup, 쿠버네티스 서비스 어카운트 등)를 기반으로 그 워크로드가 실제로 주장하는 신원과 일치하는지 증명(attestation)한다. 이 증명이 통과하면 SPIRE Server가 짧은 수명(보통 수 시간 이내)의 SVID를 발급하고, 만료 전에 자동으로 갱신한다. 사람이 인증서를 발급하고 배포하고 만료 전에 갱신하는 수동 과정을 워크로드 신원 증명 기반으로 완전히 자동화한다는 것이 핵심 가치다.

| 항목 | 전통적 인증서 관리 | SPIFFE/SPIRE |
|---|---|---|
| 신원 발급 기준 | 사람이 수동 신청·승인 | 커널 증거 기반 자동 증명(attestation) |
| 인증서 수명 | 수개월~1년 | 수 시간~수 일 (짧고 자동 회전) |
| 회전 실패 위험 | 담당자가 놓치면 서비스 장애 | 에이전트가 만료 전 자동 갱신 |
| 신원 형식 | 조직·도메인 기반 CN | 워크로드 단위 SPIFFE ID(URI) |

## 예제 — Envoy sidecar에서 SPIFFE mTLS 검증 설정 스케치

```yaml
transport_socket:
  name: envoy.transport_sockets.tls
  typed_config:
    "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
    common_tls_context:
      tls_certificate_sds_secret_configs:
        - name: spiffe://example.org/ns/payments/sa/order-service
      validation_context:
        custom_validator_config:
          name: envoy.tls.cert_validator.spiffe
          typed_config:
            "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.SPIFFECertValidatorConfig
            trust_domains:
              - name: example.org
                trust_bundle: { filename: "/run/spire/bundle/bundle.pem" }
```

Envoy는 SVID를 클라이언트/서버 인증서로 사용하고, 상대방의 SVID가 신뢰 도메인(trust domain)의 번들로 검증 가능한지 확인해 mTLS 핸드셰이크를 완료한다.

## 실무 포인트

- **처음부터 모든 서비스에 강제 적용하지 말고 단계적으로 도입하라.** 신뢰 도메인 설계, attestation 정책, 인증서 회전 주기를 먼저 소수의 서비스로 검증한 뒤 확대하는 것이 실무에서 안전하다.
- **서비스 메시(Istio, Linkerd)가 이미 SPIFFE 기반 mTLS를 내장 지원하는 경우가 많다는 점을 활용하라.** SPIRE를 직접 통합하기 전에, 사용 중인 메시가 이미 이 기능을 제공하는지 먼저 확인하는 것이 구현 비용을 크게 줄인다.
- **레거시 워크로드(VM, 베어메탈)를 포함해야 한다면 attestation 방식을 별도로 설계하라.** 쿠버네티스 서비스 어카운트 기반 증명은 파드에는 잘 맞지만, VM에서는 다른 attestation 플러그인(예: AWS IID)이 필요하다.

## 마무리 요약

- Zero Trust는 네트워크 위치가 아니라 검증 가능한 워크로드 신원을 기준으로 매 요청을 검증하는 원칙이며, 컨테이너 환경에서 경계 기반 보안의 한계를 보완한다.
- SPIFFE는 워크로드마다 고유한 신원 표준(SPIFFE ID, SVID)을 정의하고, SPIRE는 커널 증거 기반 attestation으로 이 신원의 발급·회전을 자동화한다.
- 짧은 수명의 인증서를 자동으로 회전시키는 구조는 사람이 수동으로 인증서를 관리할 때 생기는 만료·유출 위험을 근본적으로 줄인다.

## 참고 자료

- [SPIFFE - Introduction](https://spiffe.io/docs/latest/spiffe-about/overview/)
- [SPIRE - Concepts](https://spiffe.io/docs/latest/spire-about/spire-concepts/)
