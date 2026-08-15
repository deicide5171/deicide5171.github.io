---
layout: single
title: "리눅스 방화벽 밑바닥 들여다보기 — conntrack 연결 추적과 nftables 규칙 설계"
date: 2026-08-17 12:40:00 +0530
categories: infra
tags: ["linux", "conntrack", "nftables", "netfilter", "firewall"]
toc: true
toc_sticky: true
excerpt: "iptables 문법으로 방화벽 규칙을 외우기 전에, 커널이 연결을 어떻게 기억하고 nftables가 그 정보를 어떻게 규칙에 활용하는지부터 정리한다."
---

## 왜 지금 conntrack과 nftables인가

많은 개발자·운영자에게 리눅스 방화벽은 "규칙을 외워서 붙여넣는" 대상이다. 포트를 열고 막는 규칙은 검색해서 복사하면 되지만, 정작 "이 규칙이 왜 되돌아오는 응답 패킷은 자동으로 허용하는지", "NAT을 거친 패킷이 어떻게 원래 목적지로 돌아가는지"는 설명하지 못하는 경우가 많다. 그 답은 규칙 자체가 아니라 커널이 별도로 유지하는 **연결 추적 테이블(conntrack)** 에 있다.

최근 여러 배포판이 기존 iptables 대신 **nftables**를 기본 방화벽 프레임워크로 채택하는 추세이고, 컨테이너·Kubernetes 환경의 네트워크 구성 요소들도 nftables 기반 규칙을 점점 더 많이 활용한다. 문법은 바뀌었지만 conntrack이 연결 상태를 기억하고 방화벽 규칙이 그 상태를 참조하는 근본 구조는 그대로다. 이 글에서는 conntrack이 무엇을 기억하는지, nftables가 iptables와 무엇이 다른지, 두 시스템이 실제로 어떻게 맞물려 동작하는지를 정리한다.

## 핵심 개념 1: conntrack — 커널의 연결 상태 테이블

conntrack은 리눅스 커널의 netfilter 서브시스템이 관리하는 메모리 내 테이블로, 커널을 통과하는 패킷을 **5-tuple**(프로토콜, 출발지 IP·포트, 목적지 IP·포트) 기준으로 식별해 하나의 "연결"로 묶어 기억한다. 방화벽이 패킷마다 독립적으로 판단하는 대신 "이 패킷이 이미 진행 중인 연결의 일부인지"를 먼저 물어볼 수 있는 것은 이 테이블 덕분이다.

conntrack이 각 연결에 부여하는 상태는 다음 네 가지가 핵심이다.

| 상태 | 의미 |
|---|---|
| `NEW` | 테이블에 없던 5-tuple의 첫 패킷 — 새 연결 시도 |
| `ESTABLISHED` | 양방향으로 패킷이 오간 것이 확인된 연결 |
| `RELATED` | 기존 연결과 연관되어 파생된 새 연결(예: FTP 데이터 채널) |
| `INVALID` | 어떤 추적 중인 연결과도 맞지 않는, 상태 판별이 불가능한 패킷 |

이 상태 정보 덕분에 방화벽 규칙은 "새 연결만 검사하고, 이미 허가한 연결의 응답 패킷은 규칙을 다시 타지 않고 곧바로 통과시킨다"는 식으로 설계할 수 있다. NAT(SNAT/DNAT) 역시 conntrack이 원본 5-tuple과 변환된 5-tuple을 함께 기억하기 때문에, 응답 패킷이 들어왔을 때 역방향 변환을 정확히 적용할 수 있는 것이다.

## 핵심 개념 2: iptables에서 nftables로 — 무엇이 달라졌는가

nftables는 iptables/ip6tables/arptables/ebtables로 나뉘어 있던 도구들을 하나의 프레임워크로 통합한 후속 프레임워크다. 규칙을 다루는 방식 자체가 다르다.

| 구분 | iptables | nftables |
|---|---|---|
| 규칙 문법 | 명령줄 옵션 나열 방식 | 선언적 규칙 언어(`nft` 문법) |
| 테이블/체인 | 프로토콜별 고정 테이블(filter, nat 등) | `table` 안에 chain을 자유롭게 정의 |
| 프로토콜 통합 | IPv4/IPv6를 별도 도구로 관리 | `inet` family로 통합 관리 가능 |
| 도구 | `iptables`, `ip6tables` 등 별도 실행 파일 | `nft` 단일 실행 파일 |

가장 체감되는 차이는 **하나의 `table inet` 안에서 IPv4·IPv6 규칙을 함께 관리할 수 있다는 점**이다. 다만 conntrack이라는 하부 개념 자체는 iptables 시절과 동일하게 유지된다 — 바뀐 것은 정보를 참조하는 문법이지, 정보를 기억하는 메커니즘이 아니다.

## 핵심 개념 3: conntrack과 nftables가 만나는 지점

nftables 규칙에서 conntrack 정보를 읽는 문법이 바로 `ct` 표현식이다. `ct state established,related accept`처럼 쓰면, 커널이 conntrack 테이블에서 해당 패킷의 상태를 조회한 뒤 그 결과에 따라 규칙을 적용한다. 이 한 줄이 사실상 "상태 기반(stateful) 방화벽"의 핵심이며, 전체 흐름은 아래와 같다.

<img src="/assets/images/posts/2026-08-17-linux-conntrack-nftables-1.svg" alt="패킷이 conntrack 조회를 거쳐 nftables chain에서 평가되고 conntrack 테이블이 갱신되는 흐름도" style="width:100%;">

패킷이 인터페이스로 들어오면 먼저 conntrack이 5-tuple로 테이블을 조회해 상태를 분류하고, 이 결과를 nftables의 `input`·`forward` 같은 chain이 `ct state` 매치로 참조해 최종 판정을 내린다. 판정 이후에는 결과가 다시 conntrack 테이블에 반영되어 다음 패킷 처리 시 곧바로 참조된다. NAT 규칙(`snat`/`dnat`) 역시 이 테이블을 거쳐야만 역방향 변환이 가능하므로, conntrack 없이는 nftables의 NAT 기능 자체가 성립하지 않는다.

## 예제 1: 상태 기반 nftables 룰셋

```nft
#!/usr/sbin/nft -f

flush ruleset

table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        ct state established,related accept   # 기존 연결의 응답/연관 패킷은 재검사 없이 허용
        ct state invalid drop                  # 어떤 연결과도 안 맞는 비정상 패킷 차단
        iif lo accept                          # 루프백은 항상 허용

        tcp dport 22 ct state new accept       # 새 SSH 연결만 허용
        tcp dport 443 ct state new accept      # 새 HTTPS 연결만 허용
    }

    chain forward {
        type filter hook forward priority 0; policy drop;
        ct state established,related accept
        ct state invalid drop
    }
}
```

규칙 순서가 성능과 직결된다. `ct state established,related accept`를 최상단에 두면 이미 허가된 연결의 트래픽 대부분이 이 한 줄에서 걸러지고, 나머지 규칙은 새 연결(`NEW`)에 대해서만 평가된다.

## 예제 2: conntrack 상태 확인과 튜닝

```bash
# 현재 추적 중인 연결 수 확인
$ cat /proc/sys/net/netfilter/nf_conntrack_count
48213

# 테이블 최대 크기 확인 (기본값은 배포판·메모리 용량에 따라 다르므로 반드시 현재 값을 직접 확인해야 한다)
$ cat /proc/sys/net/netfilter/nf_conntrack_max
65536

# conntrack-tools 패키지로 실시간 연결 목록 조회
$ conntrack -L | head -3
tcp      6 431999 ESTABLISHED src=10.0.0.5 dst=10.0.0.20 sport=51000 dport=443 \
    src=10.0.0.20 dst=10.0.0.5 sport=443 dport=51000 [ASSURED] mark=0 use=1

# 테이블이 가득 차기 전에 여유를 두고 임계값 조정 (환경에 맞게 검증 후 적용)
$ sysctl -w net.netfilter.nf_conntrack_max=131072
```

## 실무 포인트

- **conntrack 테이블 고갈은 곧바로 신규 연결 거부로 이어진다.** 특히 NAT 게이트웨이나 아웃바운드 연결이 많은 서버에서는 `nf_conntrack_count`가 `nf_conntrack_max`에 근접하는지를 모니터링 지표로 추적해야 한다.
- **타임아웃 설정을 이해하고 조정한다.** `established` 상태의 기본 타임아웃은 길게 잡혀 있어, 유휴 연결이 테이블 슬롯을 오래 점유할 수 있다. 짧은 커넥션이 많은 서비스라면 타임아웃 값을 검토한다.
- **`notrack`은 신중하게 사용한다.** 특정 트래픽을 추적 대상에서 제외하면 `ct state` 기반 규칙이 더 이상 그 트래픽에 적용되지 않아, 의도치 않게 정책을 우회시킬 수 있다.
- **컨테이너·Kubernetes 환경에서는 규칙 수와 conntrack 부하를 함께 살핀다.** 서비스·파드가 늘어날수록 생성되는 규칙과 추적 연결 수도 함께 늘어나므로, 노드 단위 conntrack 지표를 관제에 포함하는 것이 안전하다.
- **자주 매치되는 조건을 규칙 앞쪽에 배치한다.** `ct state established,related accept`를 먼저 두면 체인 평가 비용을 줄일 수 있다.

## 3줄 요약

- conntrack은 커널이 5-tuple 기준으로 연결 상태(NEW/ESTABLISHED/RELATED/INVALID)를 기억하는 테이블이며, 이 상태 정보가 상태 기반 방화벽과 NAT의 기반이 된다.
- nftables는 iptables의 문법과 도구를 통합·정리한 후속 프레임워크로, `ct state` 표현식을 통해 conntrack 테이블을 직접 참조해 규칙을 적용한다.
- 실무에서는 conntrack 테이블 고갈·타임아웃·`notrack` 오용을 주의하고, 자주 매치되는 규칙을 앞쪽에 배치해야 안전하고 효율적인 방화벽을 유지할 수 있다.

## 참고 자료

- [nftables Wiki — 공식 문서](https://wiki.nftables.org/wiki-nftables/index.php/Main_Page)
- [conntrack-tools 프로젝트 공식 사이트](https://conntrack-tools.netfilter.org/)
- [nft(8) man page](https://man7.org/linux/man-pages/man8/nft.8.html)
- [Linux Kernel Documentation — nf_conntrack sysctl](https://docs.kernel.org/networking/nf_conntrack-sysctl.html)
