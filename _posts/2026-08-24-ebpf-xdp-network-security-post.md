---
layout: single
title: "커널 스택 진입 전에 막는다 — eBPF/XDP로 하는 네트워크 보안·DDoS 완화"
date: 2026-08-24 12:40:00 +0530
categories: infra
tags: ["ebpf", "xdp", "ddos", "network-security", "linux-kernel", "cilium"]
toc: true
toc_sticky: true
excerpt: "eBPF와 XDP가 iptables/netfilter보다 훨씬 이른 시점에서 패킷을 처리해 커널 레벨 DDoS 완화와 네트워크 보안을 구현하는 원리와 실무 적용법을 정리한다."
---

초당 수백만 패킷 규모의 SYN 플러드나 볼류메트릭 DDoS 앞에서 iptables는 근본적인 한계를 드러낸다. netfilter 체인은 패킷마다 커널 소켓 버퍼(sk_buff)를 할당하고 여러 훅을 거쳐 규칙을 순회하는데, 이 과정 자체가 이미 상당한 CPU 사이클을 소모한다. 악성 트래픽인지 판정하기도 전에 자원을 다 써버리는 셈이다.

eBPF와 XDP(eXpress Data Path)는 이 문제를 아예 다른 지점에서 접근한다. 패킷이 커널 네트워크 스택에 들어가기도 전, NIC 드라이버 수준에서 프로그램을 실행해 판정을 끝낸다. Cloudflare가 자사 DDoS 완화 파이프라인에, Meta가 Katran L4 로드밸런서에, Cilium이 쿠버네티스 네트워킹 데이터 플레인에 이 기술을 쓰는 이유다.

이 글에서는 XDP가 왜 빠른지, 어떤 방식으로 룰을 적용하는지, 그리고 도입 시 마주치는 제약을 정리한다.

## 핵심 개념 1: XDP 훅의 위치가 성능의 전부다

XDP 프로그램은 NIC 드라이버가 패킷을 받은 직후, `sk_buff` 구조체를 할당하기 전에 실행된다. 이 지점에서 내릴 수 있는 판정은 제한적이지만 그만큼 빠르다.

- **XDP_DROP**: 패킷을 즉시 폐기. 소켓 버퍼 할당·스택 진입 자체가 일어나지 않아 CPU 비용이 최소
- **XDP_PASS**: 일반 커널 네트워크 스택(netfilter 포함)으로 정상 전달
- **XDP_TX**: 패킷을 수정해 같은 NIC로 즉시 반사 (로드밸런서, 응답 캐싱에 활용)
- **XDP_REDIRECT**: 다른 인터페이스나 CPU로 전달 (AF_XDP 소켓과 결합해 유저 공간 고성능 패킷 처리에 사용)

동작 모드도 세 가지로 나뉜다. **네이티브(native)** 모드는 NIC 드라이버가 XDP를 직접 지원해 가장 빠르고, **오프로드(offloaded)** 모드는 NIC 하드웨어(스마트NIC) 자체에서 실행돼 CPU를 아예 쓰지 않으며, **제네릭(generic/SKB)** 모드는 드라이버 지원이 없을 때 커널이 소프트웨어로 에뮬레이션하지만 이미 sk_buff가 할당된 뒤라 성능 이점이 줄어든다.

## 핵심 개념 2: iptables/netfilter vs XDP vs DPDK

| 구분 | iptables/netfilter | XDP/eBPF | DPDK |
|---|---|---|---|
| 처리 위치 | 커널 스택 내부(여러 훅) | 드라이버 직후, 스택 진입 전 | 커널 우회, 유저 공간 폴링 |
| 커널 호환성 | 표준 커널 기능 | 커널 내 실행, 검증기 통과 필요 | 커널 네트워킹 완전 우회 |
| 동적 갱신 | 규칙 재적재 필요 | 맵(map)으로 무중단 갱신 | 자체 관리 필요 |
| 대표 활용 | 범용 방화벽 | DDoS 완화, L4 LB, 관측성 | 초고속 패킷 처리(NFV) |
| 러닝커브 | 낮음 | 중간(검증기 제약 이해 필요) | 높음 |

XDP는 커널과 공존하면서도 netfilter보다 훨씬 이른 시점에서 개입할 수 있다는 점에서, "커널 우회"인 DPDK와 "커널 내부"인 iptables 사이의 실용적인 중간 지점을 차지한다.

<img src="/assets/images/posts/2026-08-24-ebpf-xdp-network-security-1.svg" alt="XDP 훅이 sk_buff 할당 전에 위치해 DROP/PASS/TX를 판정하고, 맵을 통해 차단 IP와 레이트 카운터를 커널-유저 공간이 공유하는 구조도" style="width:100%;">

## 예제: per-IP 레이트 리미팅 XDP 프로그램 (C, libbpf)

```c
// xdp_ratelimit.c — 초당 요청 수 기준으로 소스 IP를 드롭하는 최소 예제
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 1 << 20);
    __type(key, __u32);   // 소스 IP
    __type(value, __u64); // 마지막 윈도우 시작 시각 + 카운트(패킹)
} rate_map SEC(".maps");

SEC("xdp")
int xdp_ratelimit(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;

    __u32 src_ip = ip->saddr;
    __u64 *count = bpf_map_lookup_elem(&rate_map, &src_ip);
    __u64 now = bpf_ktime_get_ns();

    if (count && now - *count < 1000000000ULL /* 1초 윈도 초과 판정은 생략된 단순화 */) {
        return XDP_DROP; // 임계치 초과 시 즉시 폐기
    }

    bpf_map_update_elem(&rate_map, &src_ip, &now, BPF_ANY);
    return XDP_PASS;
}
```

실전에서는 슬라이딩 윈도 카운터, CIDR 단위 차단을 위한 `BPF_MAP_TYPE_LPM_TRIE`, 화이트리스트 우선 처리 등을 추가로 조합한다. Cilium의 `cilium monitor`나 `bpftool map dump`로 맵 상태를 실시간 점검할 수 있다.

## 실무 포인트

- **검증기(verifier) 제약을 설계 초기에 고려한다**: eBPF 프로그램은 무한 루프 금지, 스택 크기 제한(512바이트), 명령어 수 상한 같은 정적 검증을 통과해야 로드된다. 복잡한 로직은 여러 프로그램(tail call)으로 쪼개거나 맵에 상태를 위임해야 한다.
- **네이티브 모드 지원 여부를 먼저 확인한다**: 모든 NIC 드라이버가 XDP 네이티브 모드를 지원하지 않는다. 제네릭 모드로 떨어지면 sk_buff 할당 이후 실행돼 기대한 성능 이득이 줄어드므로, 배포 전 `ip link show` 등으로 드라이버 지원 여부를 확인해야 한다.
- **관측성 없는 XDP는 블랙박스가 된다**: 프로그램이 패킷을 드롭하기 시작하면 일반적인 tcpdump로는 원인을 보기 어렵다. eBPF 프로그램 자체에 카운터 맵을 두고 Prometheus exporter로 노출하거나, `bpftrace`로 훅 지점의 통계를 별도로 수집하는 체계를 함께 구축해야 한다.

## 3줄 요약

- XDP는 sk_buff 할당 이전, NIC 드라이버 직후 시점에서 패킷을 판정해 iptables/netfilter보다 훨씬 적은 CPU 비용으로 DDoS 트래픽을 걸러낸다.
- 맵(map)을 통해 커널 프로그램과 유저 공간이 차단 목록·카운터를 공유하며, 재적재 없이 실시간으로 정책을 갱신할 수 있다.
- 검증기 제약(스택 크기, 루프 금지)과 드라이버별 네이티브/제네릭 모드 차이를 사전에 파악하지 않으면 기대한 성능이 나오지 않는다.

## 참고 자료

- [Linux 커널 공식 문서: XDP (eXpress Data Path)](https://www.kernel.org/doc/html/latest/networking/af_xdp.html)
- [Cilium 공식 문서: eBPF and XDP Reference Guide](https://docs.cilium.io/en/stable/reference-guides/bpf/)
- [eBPF 공식 사이트: What is eBPF?](https://ebpf.io/what-is-ebpf/)
- [Cloudflare 블로그: XDP in practice](https://blog.cloudflare.com/tag/xdp/)
