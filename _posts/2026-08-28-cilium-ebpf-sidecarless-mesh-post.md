---
layout: single
title: "사이드카 없이 서비스 메시를 — Cilium eBPF 기반 사이드카리스 메시 실무"
date: 2026-08-28 13:40:00 +0530
categories: infra
tags: ["infra", "cilium", "ebpf", "service-mesh", "kubernetes"]
toc: true
toc_sticky: true
excerpt: "파드마다 붙는 Envoy 사이드카 없이 커널의 eBPF로 트래픽을 직접 가로채 처리하는 Cilium의 사이드카리스 서비스 메시 구조와, 기존 사이드카 모델 대비 얻는 것과 잃는 것을 정리한다."
---

Istio나 Linkerd 같은 전통적인 서비스 메시는 각 파드에 Envoy 사이드카 컨테이너를 함께 띄워, 그 파드로 들고 나는 모든 트래픽을 iptables 규칙으로 사이드카를 거치도록 강제한다. mTLS, 재시도, 회로 차단 같은 메시 기능은 모두 이 사이드카 안에서 처리된다. 문제는 파드 수가 늘어날수록 사이드카 개수도 똑같이 늘어난다는 점이다. 사이드카 하나가 쓰는 CPU·메모리는 크지 않아도, 수천 개 파드를 운영하는 클러스터에서는 이 오버헤드가 누적되어 상당한 인프라 비용과 지연으로 돌아온다.

**사이드카리스(sidecarless) 서비스 메시**는 파드마다 프록시를 띄우는 대신, 각 노드에 하나씩 있는 커널의 **eBPF(extended Berkeley Packet Filter)** 프로그램이 해당 노드의 모든 트래픽을 커널 레벨에서 직접 처리하도록 구조를 바꾼다. Cilium이 이 접근을 대표하는 구현체로, 최근 Istio도 Ambient Mesh라는 이름으로 유사한 방향을 취하고 있다. 이 글에서는 Cilium의 eBPF 기반 메시가 어떻게 사이드카를 없앴는지, 그리고 그 대가로 무엇을 다시 챙겨야 하는지 정리한다.

## 핵심 개념 1: 사이드카 모델과 eBPF 모델의 트래픽 경로 차이

사이드카 모델에서 트래픽은 애플리케이션 컨테이너 → iptables 리다이렉션 → 같은 파드의 Envoy 사이드카 → 다시 iptables → 실제 목적지로 흐른다. 매 홉마다 컨테이너 네트워크 네임스페이스 경계를 넘고 사용자 공간(userspace) 프록시를 거치므로 지연이 누적된다.

eBPF 모델에서는 커널 안에 로드된 eBPF 프로그램이 소켓 레벨 또는 TC(traffic control) 레벨에서 패킷을 가로채 mTLS, 로드밸런싱, 정책 적용을 **커널 공간(kernel space)에서** 직접 처리한다. 사용자 공간 프록시를 거치는 홉 자체가 없어지므로, 패킷이 네트워크 네임스페이스를 오가며 컨텍스트 스위칭하는 비용이 크게 줄어든다.

<img src="/assets/images/posts/2026-08-28-cilium-ebpf-sidecarless-mesh-1.svg" alt="사이드카 모델은 애플리케이션과 목적지 사이에 파드별 Envoy 프록시를 거치지만, eBPF 모델은 노드당 하나의 커널 프로그램이 직접 트래픽을 처리하는 구조 비교" style="width:100%;">

## 핵심 개념 2: 노드 단위 자원 vs 파드 단위 자원

가장 직접적인 이점은 리소스 사용 방식의 변화다. 사이드카 모델은 파드 수에 비례해 프록시 개수가 늘어나(N개 파드 = N개 사이드카), 각 사이드카가 CPU·메모리를 점유한다. eBPF 모델은 정책 적용과 트래픽 처리를 노드 단위로 수행하므로, 한 노드에 파드가 몇 개든 오버헤드가 상대적으로 일정하게 유지된다. 파드 밀도가 높은 클러스터일수록 이 차이가 크게 벌어진다.

| 기준 | 사이드카 모델(Istio 사이드카, Linkerd) | eBPF 사이드카리스(Cilium) |
|---|---|---|
| 프록시 배치 단위 | 파드마다 1개 | 노드마다 1개(일부는 노드 단위 프록시도 병행) |
| 트래픽 경로 | userspace 프록시 경유 | 커널 내 eBPF에서 직접 처리 |
| 파드 증가 시 오버헤드 | 파드 수에 비례해 선형 증가 | 노드 수 기준으로 상대적으로 완만 |
| L7 기능(HTTP 라우팅 등) | 사이드카가 전담 | 일부는 노드 단위 프록시로 보완 필요 |
| 관측 성숙도 | Envoy 생태계로 성숙 | 비교적 최근, 빠르게 발전 중 |

## 핵심 개념 3: 잃는 것 — L7 기능과 장애 격리 단위

eBPF는 L3/L4(IP, 포트, TCP/UDP) 레벨 처리에는 강력하지만, HTTP 헤더 기반 라우팅이나 재시도 정책처럼 L7(애플리케이션 레이어) 지식이 필요한 기능은 커널 안에서 직접 처리하기 어렵다. 그래서 Cilium을 포함한 사이드카리스 메시들은 L7 기능이 필요할 때 노드당 하나의 공유 프록시(Envoy 기반)를 별도로 두고, eBPF가 그 앞단 필터링과 L3/L4 처리를 맡는 하이브리드 구조를 취하는 경우가 많다. 즉 "완전히 프록시가 없다"기보다는 "프록시가 파드마다가 아니라 노드마다 하나로 공유된다"에 가깝다.

이 공유 구조는 장애 격리 단위도 바꾼다. 사이드카 모델에서는 한 파드의 사이드카 문제가 그 파드에만 영향을 주지만, 노드 단위 공유 프록시가 문제를 일으키면 그 노드의 모든 파드가 영향을 받을 수 있다. 격리 단위가 파드에서 노드로 넓어지는 셈이므로, 노드 단위 컴포넌트의 안정성과 리소스 격리(cgroup 등)에 더 신경 써야 한다.

## 예제: Cilium 설치와 사이드카리스 모드 확인

```bash
# Cilium CLI로 kube-proxy 대체 + eBPF 기반 데이터 플레인 설치
cilium install --set kubeProxyReplacement=true

# 사이드카 없이도 mTLS와 네트워크 정책이 노드 단위로 적용되는지 확인
cilium status --wait
cilium connectivity test   # 클러스터 내 연결성·정책 적용 검증

# L7 정책(HTTP 경로 기반)이 필요하면 CiliumNetworkPolicy에서 명시
```

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-get-only
spec:
  endpointSelector:
    matchLabels:
      app: backend
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: frontend
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
          rules:
            http:
              - method: "GET"
                path: "/api/.*"
```

L7 규칙(`rules.http`)이 포함된 정책은 내부적으로 노드 단위 Envoy로 트래픽을 위임해 처리되고, L3/L4만으로 충분한 규칙은 eBPF가 직접 처리해 프록시를 거치지 않는다. 이 구분을 이해하고 있어야 어떤 정책이 실제로 얼마나 빠른지 예측할 수 있다.

## 실무 포인트

- **기존 사이드카 메시에서 마이그레이션할 때는 L7 정책 목록부터 감사할 것**: HTTP 경로 기반 라우팅, 헤더 기반 트래픽 분할처럼 L7에 의존하는 정책이 많다면 마이그레이션 후에도 여전히 프록시 경유가 필요한 부분이 많다는 뜻이므로 기대 효과를 과대평가하지 말아야 한다.
- **커널 버전 요구사항을 미리 확인할 것**: Cilium의 고급 기능은 최신 커널 기능에 의존하는 경우가 많아, 오래된 커널을 쓰는 노드 풀이 섞여 있으면 일부 기능이 제한되거나 폴백 경로로 처리될 수 있다.
- **관측성 도구를 별도로 준비할 것**: Envoy 사이드카는 성숙한 메트릭·트레이싱 생태계를 갖고 있지만, eBPF 기반 처리는 커널 내부에서 일어나므로 Hubble 같은 Cilium 전용 관측 도구를 별도로 익혀야 한다.

## 3줄 요약

- 사이드카리스 메시는 파드마다 붙는 Envoy 사이드카 대신 노드당 하나의 eBPF 프로그램이 커널 레벨에서 트래픽을 직접 처리해 파드 수에 비례하던 오버헤드를 줄인다.
- L7 기능은 여전히 노드 단위 공유 프록시가 필요한 경우가 많아 "프록시가 완전히 없다"기보다는 "파드마다가 아니라 노드마다 하나로 공유된다"에 가깝다.
- 장애 격리 단위가 파드에서 노드로 넓어지므로, 마이그레이션 전 L7 정책 의존도와 커널 버전 요구사항을 함께 점검해야 한다.

## 참고 자료

- [Cilium 공식 문서: Introduction to Cilium](https://docs.cilium.io/en/stable/overview/intro/)
- [Cilium 공식 문서: Service Mesh & Networking](https://docs.cilium.io/en/stable/network/servicemesh/)
- [Isovalent(Cilium 개발사): eBPF vs Sidecars for Service Mesh](https://isovalent.com/blog/post/cilium-service-mesh/)
