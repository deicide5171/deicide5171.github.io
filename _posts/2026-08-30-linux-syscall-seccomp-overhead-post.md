---
layout: single
title: "보안 필터 하나가 컨테이너를 느리게 만든다 — 시스템콜 오버헤드와 seccomp 프로파일"
date: 2026-08-30 13:40:00 +0530
categories: infra
tags: ["infra", "linux", "seccomp", "syscall", "container-security", "performance"]
toc: true
toc_sticky: true
excerpt: "seccomp은 컨테이너가 호출할 수 있는 시스템콜을 화이트리스트로 제한해 공격 표면을 줄이지만, 필터 규칙 수와 BPF 평가 비용에 따라 syscall-heavy 워크로드에서 눈에 띄는 지연을 만들 수 있다. 동작 원리와 실측 접근을 정리한다."
---

컨테이너 하나가 뚫리면 그 프로세스가 호출 가능한 시스템콜 전체가 공격 표면이 된다. `ptrace`, `mount`, 커널 모듈 로딩 관련 시스템콜처럼 컨테이너 워크로드가 평소 쓸 일이 없는 위험한 시스템콜까지 열려 있으면, 커널 취약점과 결합해 컨테이너 탈출로 이어질 수 있다. **seccomp(secure computing mode)**은 프로세스가 호출할 수 있는 시스템콜을 화이트리스트로 제한해 이 공격 표면을 줄이는 커널 기능이고, Docker와 Kubernetes 모두 기본 seccomp 프로파일을 적용한다.

문제는 이 보안 장치가 공짜가 아니라는 점이다. 시스템콜이 잦은 워크로드(파일 I/O가 많거나 네트워크 처리량이 높은 서비스)에서는 seccomp 필터 평가 자체가 눈에 띄는 오버헤드로 나타날 수 있다. 이 글은 seccomp이 어떻게 시스템콜을 가로채 필터링하는지, 그 비용이 어디서 오는지, 그리고 실무에서 오버헤드를 실측하고 최소화하는 방법을 정리한다.

## 핵심 개념 1: seccomp의 필터링 메커니즘 — BPF로 시스템콜을 검사한다

seccomp-bpf 모드에서는 프로세스가 시스템콜을 호출할 때마다, 커널이 등록된 **BPF(Berkeley Packet Filter) 프로그램**을 실행해 그 호출을 허용할지 차단할지 결정한다. 필터 프로그램은 시스템콜 번호와 인자를 검사해서 `ALLOW`, `KILL`, `ERRNO`(에러 반환), `TRACE`(ptrace로 위임) 같은 액션을 반환하고, 커널은 이 판정에 따라 실제 시스템콜 실행 여부를 결정한다.

이 과정이 오버헤드를 만드는 지점은 두 곳이다. 첫째, **모든** 시스템콜 호출마다 이 필터가 실행된다는 것 — 필터를 아무리 가볍게 짜도 시스템콜 하나하나에 검사 단계가 추가된다. 둘째, 필터 규칙의 개수와 구조다. BPF 필터는 규칙을 순차 또는 이진 탐색 형태로 평가하는데, 화이트리스트에 등록된 시스템콜 수가 많고 규칙이 단순 선형 비교로 구성돼 있으면, 허용 목록 뒤쪽에 있는 시스템콜일수록 더 많은 비교를 거쳐야 판정이 난다.

## 핵심 개념 2: syscall 빈도가 오버헤드를 증폭시킨다

seccomp 오버헤드는 절대적인 값보다 **시스템콜 호출 빈도**와 곱해져 체감된다. 시스템콜 하나당 오버헤드가 마이크로초 단위로 작더라도, 초당 수십만 번 시스템콜을 호출하는 워크로드(고빈도 네트워크 I/O, 파일 시스템 폴링, 락 경합이 잦은 멀티스레드 애플리케이션)에서는 그 작은 오버헤드가 누적돼 유의미한 처리량 저하로 나타난다. 반대로 시스템콜을 드물게 호출하는 CPU-바운드 워크로드에서는 seccomp을 켜도 체감 차이가 거의 없다.

| 워크로드 유형 | 시스템콜 호출 빈도 | seccomp 오버헤드 체감도 |
|---|---|---|
| CPU 집약 연산(암호화, 이미지 처리) | 낮음 | 거의 없음 |
| 일반 웹 API 서버 | 중간 | 미미~약간 |
| 고빈도 네트워크 프록시·로드밸런서 | 높음 | 측정 가능한 수준 |
| 파일 시스템 집약 배치 작업 | 매우 높음 | 뚜렷하게 나타날 수 있음 |

## 핵심 개념 3: 프로파일 설계 — 넓은 화이트리스트의 함정

seccomp 오버헤드를 줄이는 가장 직접적인 방법은 필터 규칙 자체를 최소화하는 것이다. Docker의 기본 seccomp 프로파일은 대부분의 애플리케이션이 안전하게 쓸 수 있도록 상당히 넓은 화이트리스트를 제공하는데, 이는 호환성을 위한 절충이지 성능을 위한 최소 집합이 아니다. 실제 워크로드가 사용하는 시스템콜만 추려 좁힌 커스텀 프로파일을 적용하면, 필터 평가 자체의 부담은 크게 줄지 않더라도(여전히 모든 호출을 검사해야 하므로) 공격 표면 축소라는 본래 목적은 더 확실히 달성되고, 최신 커널의 BPF JIT 컴파일 최적화 덕분에 규칙 수 증가에 따른 성능 저하는 예전보다 완만해졌다.

<img src="/assets/images/posts/2026-08-30-linux-syscall-seccomp-overhead-1.svg" alt="애플리케이션 프로세스가 시스템콜을 호출할 때마다 커널이 seccomp BPF 필터를 평가해 허용·차단·에러 반환을 결정하는 흐름과, 시스템콜 빈도가 높을수록 필터 평가 비용이 누적되는 관계를 보여주는 다이어그램" style="width:100%;">

## 예제: strace로 시스템콜 빈도 측정, 커스텀 프로파일 적용

```bash
# 1) 컨테이너 안 프로세스의 시스템콜 호출 빈도와 소요 시간 집계
strace -f -c -p $(pgrep -f my-service) &
sleep 30
kill %1
# 출력 예: % time  seconds  usecs/call  calls  syscall
#           23.4%  0.0891   0.89       100234  epoll_wait
#           18.1%  0.0689   1.12        61523  read
#           ...
# → 호출 빈도 상위 시스템콜이 필터 규칙에서 앞쪽에 오도록 설계해야
#   조기 판정으로 평균 평가 비용을 낮출 수 있다
```

```json
// custom-seccomp-profile.json — 실제 사용 시스템콜만 화이트리스트
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": [
        "epoll_wait", "epoll_ctl", "read", "write", "accept4",
        "close", "futex", "mmap", "munmap", "rt_sigreturn",
        "recvfrom", "sendto", "getsockopt", "setsockopt"
      ],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

```bash
# Docker에서 커스텀 프로파일 적용
docker run --security-opt seccomp=custom-seccomp-profile.json my-service:latest

# Kubernetes에서는 SecurityContext에 localhostProfile로 지정
# securityContext:
#   seccompProfile:
#     type: Localhost
#     localhostProfile: profiles/custom-seccomp-profile.json
```

`strace -c`로 얻은 상위 호출 시스템콜 목록을 기반으로 프로파일을 구성하면, 실제 필요한 시스템콜만 허용하면서도 어떤 시스템콜이 성능에 민감한지 파악하는 데 도움이 된다.

## 실무 포인트

- **오버헤드를 추정하지 말고 A/B로 실측하라.** seccomp on/off 상태로 동일한 부하 테스트를 돌려 처리량과 p99 지연을 비교하는 것이 가장 확실하다. 문서나 벤치마크 자료의 수치는 커널 버전, 필터 규칙 수, 워크로드 특성에 따라 크게 달라지므로 참고치일 뿐 자신의 환경에 그대로 적용되지 않는다.
- **seccomp만으로 컨테이너 보안이 끝났다고 착각하지 말 것.** seccomp은 시스템콜 레벨 방어일 뿐이고, capabilities 제한, AppArmor/SELinux, 읽기 전용 루트 파일시스템 같은 다른 계층의 방어와 함께 적용해야 심층 방어(defense in depth)가 완성된다. 성능이 걱정된다고 seccomp만 끄고 다른 계층도 부실하면 전체 보안 태세가 약해진다.
- **커스텀 프로파일은 커널·런타임 버전 업그레이드마다 재검증해야 한다.** 애플리케이션이나 런타임(예: JVM, glibc)이 업그레이드되면 이전에 안 쓰던 시스템콜을 새로 호출하기 시작할 수 있고, 좁힌 화이트리스트에 없는 시스템콜을 만나면 프로세스가 예기치 않게 `EPERM`이나 `SIGSYS`로 죽는다. 프로파일 변경 시 스테이징 환경에서 전체 기능 테스트를 반드시 거쳐야 한다.

## 3줄 요약

- seccomp은 시스템콜마다 BPF 필터를 실행해 허용 여부를 판정하는 방식으로 공격 표면을 줄이며, 이 오버헤드는 절대값보다 시스템콜 호출 빈도와 곱해져 체감된다.
- CPU 집약 워크로드에서는 오버헤드가 거의 없지만, 고빈도 네트워크·파일 I/O 워크로드에서는 측정 가능한 수준의 지연으로 나타날 수 있어 실측이 필요하다.
- 실제 사용하는 시스템콜만 추린 커스텀 프로파일이 보안 측면에서 더 확실하며, seccomp 하나만으로 보안이 끝난 게 아니라 capabilities·AppArmor 등 다른 계층과 함께 심층 방어를 구성해야 한다.

## 참고 자료

- [Linux 커널 문서: seccomp BPF](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html)
- [Docker 공식 문서: Seccomp Security Profiles](https://docs.docker.com/engine/security/seccomp/)
- [Kubernetes 공식 문서: Restrict a Container's Syscalls with seccomp](https://kubernetes.io/docs/tutorials/security/seccomp/)
- [man7.org: seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html)
