---
layout: single
title: "컨테이너는 어떻게 자기만의 네트워크를 갖는가 — 리눅스 네트워크 네임스페이스 내부구조"
date: 2026-08-26 12:40:00 +0530
categories: infra
tags: ["infra", "linux", "network-namespace", "container", "docker", "networking"]
toc: true
toc_sticky: true
excerpt: "docker0 브리지 하나에 컨테이너 수백 개가 붙어도 서로의 네트워크를 침범하지 않는 이유를, 리눅스 네트워크 네임스페이스와 veth 페어, iptables NAT 흐름으로 뜯어본다."
---

같은 호스트에서 컨테이너 A와 컨테이너 B를 띄우면 둘 다 `eth0`이라는 이름의 인터페이스를 갖고, 둘 다 `172.17.0.x` 대역의 IP를 받는다. 호스트 입장에서 물리 네트워크 인터페이스는 하나뿐인데, 어떻게 같은 이름·같은 대역의 인터페이스가 컨테이너마다 독립적으로 존재할 수 있을까. 답은 Docker나 Kubernetes가 특별한 마법을 부리는 게 아니라, 리눅스 커널이 제공하는 **네트워크 네임스페이스(network namespace, netns)**라는 격리 기능을 그대로 활용한다는 데 있다.

네임스페이스는 프로세스가 보는 커널 리소스의 뷰를 격리하는 리눅스 커널 기능이다. PID 네임스페이스가 프로세스 ID 공간을 격리하듯, 네트워크 네임스페이스는 라우팅 테이블, 인터페이스 목록, 방화벽 규칙, 포트 공간을 통째로 격리한다. 컨테이너 런타임의 "네트워크 격리"라는 기능은 사실 이 커널 기능을 얇게 감싼 것에 불과하다. 이 글에서는 `ip netns` 명령으로 네트워크 네임스페이스를 직접 만들어보며, 컨테이너 네트워킹의 내부 동작을 처음부터 재구성한다.

## 핵심 개념 1: 네임스페이스 격리와 veth 페어로 연결하기

새 네트워크 네임스페이스를 만들면 그 안에는 루프백(`lo`)만 존재하는 완전히 빈 네트워크 스택이 생긴다. 외부와 연결하려면 **veth(virtual ethernet) 페어**를 쓴다. veth는 항상 쌍으로 생성되는 가상 인터페이스로, 한쪽에 들어간 패킷이 다른 쪽으로 그대로 나오는 파이프처럼 동작한다. 한쪽 끝을 컨테이너의 네임스페이스에 넣고 다른 쪽 끝을 호스트의 브리지에 연결하면, 격리된 네임스페이스와 호스트 네트워크가 이어진다.

Docker가 컨테이너를 띄울 때 하는 일이 정확히 이것이다. 새 netns를 만들고, veth 페어를 생성해 한쪽을 컨테이너 netns의 `eth0`으로 이름을 바꿔 넣고, 다른 쪽을 호스트의 `docker0` 브리지에 연결한다. 컨테이너가 수백 개라도 각자 다른 netns에 있으므로 모두 `eth0`이라는 이름을 써도 충돌하지 않고, `docker0` 브리지가 이 모든 veth를 마치 스위치처럼 묶어 같은 L2 대역으로 만든다.

## 핵심 개념 2: 외부 통신은 결국 NAT를 거친다

컨테이너의 IP(`172.17.0.x`)는 호스트 밖에서는 라우팅되지 않는 사설 대역이다. 컨테이너가 외부 인터넷과 통신하려면 호스트가 출발지 주소를 자신의 것으로 바꿔주는 **SNAT(Source NAT, 마스커레이딩)**이 필요하고, 외부에서 컨테이너로 들어오는 포트 포워딩은 **DNAT**로 이뤄진다. 이 규칙은 Docker가 `iptables`(또는 `nftables`) 규칙으로 자동 생성한다.

| 방향 | 처리 | 실행 위치 |
|---|---|---|
| 컨테이너 → 외부 | 출발지 IP를 호스트 IP로 SNAT | `iptables -t nat POSTROUTING` |
| 외부 → 컨테이너(포트 매핑) | 목적지를 컨테이너 IP:포트로 DNAT | `iptables -t nat PREROUTING/DOCKER` |
| 같은 브리지 내 컨테이너 간 | netns만 거쳐 L2 통신, NAT 없음 | `docker0` 브리지 |

<img src="/assets/images/posts/2026-08-26-linux-netns-container-networking-1.svg" alt="컨테이너 네트워크 네임스페이스, veth 페어, docker0 브리지, NAT를 통한 외부 통신 흐름을 보여주는 구조도" style="width:100%;">

## 예제: `ip netns`로 컨테이너 네트워킹을 손으로 재현하기

```bash
# 1. 새 네트워크 네임스페이스 생성 (컨테이너 하나에 해당)
sudo ip netns add ns1

# 2. veth 페어 생성 — veth-host는 호스트에, veth-ns1는 ns1 안으로 옮길 예정
sudo ip link add veth-host type veth peer name veth-ns1

# 3. veth-ns1을 ns1 네임스페이스로 이동
sudo ip link set veth-ns1 netns ns1

# 4. ns1 안에서 인터페이스에 IP 부여 및 활성화
sudo ip netns exec ns1 ip addr add 172.18.0.2/24 dev veth-ns1
sudo ip netns exec ns1 ip link set veth-ns1 up
sudo ip netns exec ns1 ip link set lo up

# 5. 호스트 쪽 브리지에 veth-host 연결 (docker0과 동일한 역할)
sudo ip link add br-demo type bridge
sudo ip addr add 172.18.0.1/24 dev br-demo
sudo ip link set br-demo up
sudo ip link set veth-host master br-demo
sudo ip link set veth-host up

# 6. ns1에서 외부로 나가는 SNAT 규칙 (마스커레이딩)
sudo iptables -t nat -A POSTROUTING -s 172.18.0.0/24 ! -o br-demo -j MASQUERADE

# 검증: ns1 안에서 외부로 ping
sudo ip netns exec ns1 ping -c 3 8.8.8.8
```

이 여섯 단계가 곧 컨테이너 런타임이 매번 자동으로 수행하는 작업이다. Docker, containerd, CRI-O 모두 결국 이 커널 프리미티브(netns, veth, bridge, iptables) 위에 구현돼 있고, CNI(Container Network Interface) 플러그인들의 차이도 결국 이 조합을 어떻게 자동화하고 어떤 오버레이(VXLAN 등)를 얹느냐의 차이다.

## 실무 포인트

- **`docker0`은 단일 호스트 안에서만 유효하다**: 여러 노드에 걸친 컨테이너 통신(Kubernetes Pod 간 통신 등)은 `docker0` 브리지만으로는 안 되고, VXLAN 오버레이나 BGP 라우팅으로 노드 간 네트워크를 이어야 한다. Flannel, Calico 같은 CNI 플러그인이 이 부분을 담당한다.
- **네트워크 트러블슈팅은 `ip netns exec`로 컨테이너 관점에서 확인한다**: 컨테이너 안에서 `curl`이 안 되는데 원인을 못 찾겠다면, `nsenter --net=/proc/<pid>/ns/net` 또는 `ip netns exec`로 그 네임스페이스에 직접 들어가 라우팅 테이블과 iptables 카운터를 확인하는 것이 가장 빠르다.
- **성능이 중요한 워크로드는 `hostNetwork`를 고려한다**: veth+bridge+NAT 경로는 편의성 대비 약간의 오버헤드가 있다. 극한의 네트워크 성능이 필요한 경우(고빈도 트레이딩, 패킷 캡처 등) 컨테이너가 호스트 네트워크 네임스페이스를 그대로 쓰게 하는 옵션이 있지만, 격리를 포기하는 트레이드오프이므로 신중히 적용해야 한다.

## 3줄 요약

- 컨테이너의 네트워크 격리는 리눅스 커널의 네트워크 네임스페이스 기능을 그대로 활용한 것이며, 마법이 아니라 `ip netns`로 직접 재현 가능한 표준 기능이다.
- veth 페어가 격리된 네임스페이스와 호스트를 연결하고, 브리지가 여러 veth를 하나의 L2 대역으로 묶으며, iptables NAT이 외부 통신을 중계한다.
- 노드 간 컨테이너 통신은 단일 호스트 브리지로 해결되지 않으며 CNI 플러그인의 오버레이 네트워크가 필요하다.

## 참고 자료

- [man7.org: network_namespaces(7)](https://man7.org/linux/man-pages/man7/network_namespaces.7.html)
- [Docker 공식 문서: Networking overview](https://docs.docker.com/engine/network/)
- [Kubernetes 공식 문서: Cluster Networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
