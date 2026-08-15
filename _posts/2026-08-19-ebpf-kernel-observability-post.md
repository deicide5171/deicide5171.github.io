---
layout: single
title: "eBPF로 커널 레벨 관측성 확보하기 — 애플리케이션 코드 한 줄 안 건드리고 시스템 내부 들여다보기"
date: 2026-08-19 12:40:00 +0530
categories: infra
tags: ["ebpf", "linux", "observability", "bpftrace", "kernel", "devops"]
toc: true
toc_sticky: true
excerpt: "APM 에이전트나 로그 삽입 없이도 커널 훅에 프로그램을 붙여 시스템 호출·네트워크·지연을 실시간으로 들여다볼 수 있는 eBPF의 구조와 bpftrace 실전 예제를 정리한다."
---

## 왜 지금 eBPF인가

서비스 장애의 원인을 추적하다 보면 애플리케이션 로그만으로는 답이 나오지 않는 순간이 있다. "느린 건 애플리케이션 코드인가, TCP 재전송인가, 디스크 I/O 대기인가, 아니면 커널 스케줄러의 컨텍스트 스위치인가"라는 질문에 답하려면 커널 내부를 들여다봐야 하는데, 전통적으로는 커널 모듈을 직접 작성하거나(위험하고 크래시 가능성이 있음) `strace`처럼 무겁고 대상 프로세스를 느리게 만드는 도구에 의존해야 했다.

**eBPF(extended Berkeley Packet Filter)**는 이 문제를 근본적으로 다르게 접근한다. 커널을 재컴파일하거나 모듈을 올리지 않고도, 사용자가 작성한 소규모 프로그램을 커널 내부의 지정된 지점(훅)에 안전하게 적재해 실행시킨다. 애플리케이션 쪽 코드는 한 줄도 건드리지 않는다는 점이 핵심이다. Cilium, Falco, Pixie 같은 관측성·보안 도구들이 이미 eBPF를 기반으로 동작하고 있고, 커널 자체에 내장된 기능이라 별도 에이전트 설치 없이도 상당 부분을 다룰 수 있다는 점에서 인프라 엔지니어가 알아둘 가치가 크다.

## 핵심 개념 1: eBPF는 어떻게 안전한가

커널 모듈은 커널과 동일한 권한으로 동작하기 때문에 버그 하나가 시스템 전체를 크래시시킬 수 있다. eBPF 프로그램은 이 위험을 **검증기(Verifier)** 로 통제한다. 프로그램을 커널에 적재하기 전, 검증기가 바이트코드를 정적으로 분석해 무한 루프가 없는지, 허용되지 않은 메모리 영역에 접근하지 않는지, 스택 크기가 제한을 넘지 않는지를 확인한다. 이 검증을 통과하지 못하면 애초에 적재 자체가 거부된다.

<img src="/assets/images/posts/2026-08-19-ebpf-kernel-observability-1.svg" alt="eBPF 프로그램이 kprobe, tracepoint, syscall, XDP 등 커널 훅에 붙어 맵과 링버퍼를 통해 사용자 공간 도구로 데이터를 전달하는 구조도" style="width:100%;">

## 핵심 개념 2: 훅(Hook) 포인트의 종류

eBPF 프로그램은 아무 데나 붙는 것이 아니라, 커널이 미리 정의해둔 지점에만 부착(attach)된다. 어떤 훅을 쓰느냐에 따라 관측할 수 있는 내용이 달라진다.

| 훅 종류 | 부착 지점 | 대표 활용 |
|---|---|---|
| kprobe / kretprobe | 커널 함수의 진입·반환 시점 | 특정 커널 함수 호출 빈도·소요 시간 측정 |
| tracepoint | 커널이 안정적으로 유지하는 정적 이벤트 | 스케줄러 전환, 시스템 콜 진입/종료 |
| USDT / uprobe | 사용자 공간 프로세스의 함수 | 애플리케이션 재컴파일 없이 특정 함수 계측 |
| XDP / tc | 네트워크 드라이버·패킷 경로 | 초고속 패킷 필터링·로드밸런싱 |

tracepoint는 커널 버전이 바뀌어도 인터페이스가 잘 유지되는 편이라 안정적인 반면, kprobe는 커널 내부 함수 이름에 의존하므로 커널 버전이 바뀌면 깨질 수 있다는 차이를 알아두는 것이 좋다.

## 핵심 개념 3: 데이터는 어떻게 사용자 공간으로 나오는가

커널 안에서 수집한 값을 사용자 공간 도구가 읽으려면 중간 저장소가 필요하다. 이 역할을 **eBPF Maps**(키-값 저장소, 프로그램 간 및 커널-유저 공간 공유)와 **Ring Buffer/Perf Buffer**(이벤트를 순서대로 스트리밍)가 담당한다. `bpftrace`나 `bcc` 같은 도구는 이 메커니즘을 추상화해, 사용자는 고수준 스크립트만 작성하면 된다.

## 예제: bpftrace로 시스템 콜 지연 관측하기

아래는 `openat` 시스템 콜의 호출 횟수를 프로세스별로 집계하는 간단한 bpftrace 스크립트다.

```bash
# openat 시스템 콜을 호출한 프로세스별 횟수를 실시간 집계
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_openat
{
    @calls[comm] = count();
}

interval:s:5
{
    print(@calls);
    clear(@calls);
}
'
```

`tracepoint:syscalls:sys_enter_openat`가 훅 포인트, `@calls[comm]`이 eBPF Map(프로세스 이름별 카운터)에 해당한다. 5초마다 누적치를 출력하고 초기화해 어떤 프로세스가 파일을 자주 여는지 실시간으로 확인할 수 있다. 조금 더 나아가면 함수 진입·반환 시각 차이를 히스토그램으로 뽑아 지연 분포를 보는 것도 몇 줄이면 충분하다.

```bash
# read 시스템 콜의 지연 시간을 히스토그램으로 집계
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_read { @start[tid] = nsecs; }
tracepoint:syscalls:sys_exit_read /@start[tid]/ {
    @latency_ns = hist(nsecs - @start[tid]);
    delete(@start[tid]);
}
'
```

## 실무 포인트

- **운영 환경 적용 전 오버헤드를 반드시 실측한다.** eBPF는 전통적인 프로파일링 도구보다 가볍지만 공짜는 아니다. 훅 개수와 맵 접근 빈도가 늘어날수록 CPU 비용이 커지므로, 프로덕션에 걸기 전 스테이징에서 부하 테스트로 영향도를 확인해야 한다.
- **커널 버전 호환성을 확인한다.** kprobe 기반 스크립트는 커널 내부 함수명에 의존하므로, 커널 마이너 버전이 바뀌면 동작하지 않을 수 있다. 가능하면 tracepoint나 CO-RE(Compile Once – Run Everywhere)를 지원하는 도구 체인을 우선 고려한다.
- **읽기 전용 관측용과 트래픽에 개입하는 용도를 구분한다.** XDP처럼 패킷 경로에 직접 개입하는 프로그램은 잘못 작성하면 네트워크 장애로 직결되므로, 순수 관측(tracing) 목적과는 검증·롤백 절차를 다르게 가져가야 한다.
- **컨테이너 환경에서는 커널 기능 노출 여부를 먼저 점검한다.** 일부 관리형 쿠버네티스 환경은 보안 정책상 eBPF 프로그램 적재에 필요한 권한(CAP_BPF 등)을 기본 제한하므로, 클러스터 정책을 먼저 확인해야 한다.

## 3줄 요약

- eBPF는 커널 모듈 없이도 검증기를 통과한 소규모 프로그램을 커널 훅(kprobe, tracepoint, XDP 등)에 안전하게 적재해 애플리케이션 코드 수정 없이 시스템을 관측한다.
- 수집한 데이터는 eBPF Maps와 Ring/Perf Buffer를 거쳐 사용자 공간 도구로 전달되며, bpftrace 같은 도구는 이 과정을 몇 줄의 스크립트로 추상화해준다.
- 실무 적용 시에는 오버헤드 실측, 커널 버전 호환성, 관측용과 개입용 프로그램의 구분, 클러스터 권한 정책 확인이 함께 필요하다.

## 참고 자료

- [eBPF 공식 문서 — ebpf.io](https://ebpf.io/)
- [bpftrace 공식 리포지토리 및 레퍼런스 가이드](https://github.com/bpftrace/bpftrace)
- [Linux Kernel 문서 — BPF Design Q&A](https://www.kernel.org/doc/html/latest/bpf/bpf_design_QA.html)
