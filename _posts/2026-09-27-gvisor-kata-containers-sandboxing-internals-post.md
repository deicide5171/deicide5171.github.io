---
layout: single
title: "gVisor vs Kata Containers — 컨테이너를 '진짜로' 격리하는 두 가지 접근"
date: 2026-09-27 12:40:00 +0530
categories: infra
tags: ["gVisor", "KataContainers", "컨테이너보안", "샌드박싱", "리눅스커널"]
toc: true
toc_sticky: true
excerpt: "일반 컨테이너는 커널을 호스트와 공유하기 때문에 근본적인 격리 한계가 있다. 이를 해결하는 두 가지 다른 접근인 gVisor(유저스페이스 커널 에뮬레이션)와 Kata Containers(경량 VM)의 내부 동작 원리와 트레이드오프를 정리했다."
---

## 왜 컨테이너 격리가 다시 논의되는가

멀티테넌트 환경에서 신뢰할 수 없는 코드를 실행해야 하는 경우가 늘고 있다. AI 에이전트가 생성한 코드를 즉석에서 실행하는 서비스, 서드파티 플러그인을 격리 실행해야 하는 SaaS, 여러 고객의 워크로드를 하나의 노드에 올리는 서버리스 플랫폼이 대표적이다. 문제는 일반적인 Docker/containerd 컨테이너가 격리의 상당 부분을 리눅스 커널의 네임스페이스와 cgroup에 의존한다는 점이다. 컨테이너와 호스트는 **같은 커널**을 공유하므로, 컨테이너 안에서 커널의 취약점을 트리거하는 syscall을 호출하면 이론적으로 호스트를 탈출할 수 있다. gVisor와 Kata Containers는 이 근본적인 한계를 서로 다른 방식으로 해결한다.

## 핵심 개념 1 — gVisor: 유저스페이스에 커널을 하나 더 두기

gVisor는 `runsc`라는 OCI 호환 런타임으로 동작하며, 핵심 아이디어는 애플리케이션과 호스트 커널 사이에 **Sentry**라는 유저스페이스 프로세스를 끼워 넣는 것이다. 컨테이너 안의 프로세스가 syscall을 호출하면, 실제 호스트 커널로 바로 전달되는 대신 ptrace나 KVM 기반 인터셉트로 Sentry가 가로챈다. Sentry는 자체적으로 구현한 리눅스 syscall 서브셋을 처리하고, 정말로 필요한 경우에만 훨씬 좁은 syscall 집합으로 호스트 커널과 통신한다. 즉 호스트 커널이 직접 노출하는 공격 표면을 수백 개의 syscall에서 십여 개로 줄이는 것이다. 대신 Sentry가 리눅스 syscall을 흉내 내는 과정에서 오버헤드가 생기고, 일부 고급 syscall(특정 ioctl, io_uring 등)은 아예 지원하지 않아 호환성 문제가 생길 수 있다.

## 핵심 개념 2 — Kata Containers: 컨테이너처럼 보이는 경량 VM

Kata Containers는 다른 길을 택한다. 컨테이너마다 실제로 **경량 하이퍼바이저(QEMU, Cloud Hypervisor, Firecracker 등)** 위에서 별도의 게스트 커널을 구동하는 마이크로 VM을 띄운다. 즉 격리 경계가 유저스페이스 에뮬레이션이 아니라 하드웨어 가상화(VT-x/AMD-V)로 강제된다. 커널 자체가 완전히 분리되어 있으므로 syscall 호환성 문제가 거의 없고, 호스트 커널의 취약점이 게스트에 직접 영향을 주지 않는다. 대신 VM을 부팅하는 비용이 있어 컨테이너 시작 시간이 gVisor보다 느리고, 게스트마다 커널 메모리 오버헤드가 추가된다. Kubernetes에서는 `kata-runtime`을 containerd/CRI-O의 런타임 클래스로 등록해, 특정 파드만 선택적으로 Kata 샌드박스에서 실행할 수 있다.

| 항목 | gVisor | Kata Containers |
|---|---|---|
| 격리 메커니즘 | 유저스페이스 syscall 에뮬레이션 | 하드웨어 가상화(경량 VM) |
| 커널 공유 여부 | 호스트 커널 syscall 표면 축소 | 게스트 커널 완전 분리 |
| 시작 속도 | 빠름(수십 ms) | 상대적으로 느림(VM 부팅 필요) |
| syscall 호환성 | 일부 미지원(에뮬레이션 한계) | 높음(실제 커널 실행) |
| 대표 사용처 | Google Cloud Run, gVisor 자체 서비스 | Kubernetes RuntimeClass, 금융/공공 멀티테넌시 |

## 코드 예제 — Kubernetes에서 RuntimeClass로 샌드박스 지정

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata-qemu
handler: kata-qemu
---
apiVersion: v1
kind: Pod
metadata:
  name: untrusted-workload
spec:
  runtimeClassName: kata-qemu   # 이 파드만 Kata 샌드박스에서 실행
  containers:
  - name: app
    image: untrusted-image:latest
```

`runtimeClassName`을 지정하지 않은 파드는 기본 runc(일반 컨테이너)로, 지정한 파드만 선택적으로 격리 강도를 높여 실행할 수 있다. gVisor도 동일하게 `runtimeClassName: gvisor`로 등록해 혼용 가능하다.

## 실무 포인트

- **성능이 중요한 워크로드는 신중히 검토하라.** gVisor는 파일 I/O나 네트워크 syscall이 잦은 워크로드에서 syscall 에뮬레이션 오버헤드가 누적되어 네이티브 대비 체감 성능 저하가 발생할 수 있다. 벤치마크 없이 전면 적용하지 말 것.
- **필요한 워크로드에만 선택적으로 적용하라.** 모든 파드를 샌드박스로 돌리면 노드당 밀도와 시작 지연이 나빠진다. 신뢰할 수 없는 코드 실행, 멀티테넌트 경계처럼 격리가 실제로 중요한 워크로드에만 RuntimeClass를 지정하는 것이 현실적이다.
- **Firecracker 기반 Kata는 서버리스에 특화됐다.** AWS Lambda의 격리 기술로 유명한 Firecracker는 Kata의 VMM 백엔드로도 쓸 수 있으며, 매우 빠른 부팅(수십 ms)과 최소한의 메모리 오버헤드를 목표로 설계됐다.

## 마무리 요약

- 일반 컨테이너는 호스트와 커널을 공유하기 때문에 신뢰할 수 없는 코드 실행에는 근본적인 격리 한계가 있다.
- gVisor는 유저스페이스 Sentry로 syscall을 가로채 호스트 공격 표면을 줄이고, Kata Containers는 경량 VM으로 커널 자체를 분리해 하드웨어 수준 격리를 제공한다.
- Kubernetes RuntimeClass로 필요한 워크로드에만 선택적으로 샌드박스를 적용하는 것이 성능과 보안의 균형점이다.

## 참고 자료

- [gVisor 공식 문서 — Architecture Guide](https://gvisor.dev/docs/architecture_guide/)
- [Kata Containers 공식 문서](https://katacontainers.io/docs/)
- [Kubernetes RuntimeClass 공식 문서](https://kubernetes.io/docs/concepts/containers/runtime-class/)
