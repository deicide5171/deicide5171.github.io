---
layout: single
title: "cgroup v2 통합 계층 구조로 CPU·IO 리소스 실전 제어하기"
date: 2026-08-25 12:40:00 +0530
categories: infra
tags: ["cgroup-v2", "linux", "cpu-throttling", "io-control", "container", "resource-isolation"]
toc: true
toc_sticky: true
excerpt: "cgroup v1의 컨트롤러별 분리 계층 구조가 cgroup v2에서 단일 계층으로 통합되며 무엇이 달라졌는지, cpu.max와 io.max로 실제 리소스를 제어하는 방법을 정리한다."
---

같은 노드에 컨테이너를 여러 개 올려두면 언젠가 반드시 겪는 문제가 있다. 로그를 몰아서 쓰는 배치 작업 하나가 디스크 IO를 독점해서 옆 컨테이너의 DB 쿼리가 갑자기 느려지거나, CPU를 많이 쓰는 워커 하나가 같은 노드의 API 서버 레이턴시를 끌어올리는 경우다. `docker run --cpus`나 쿠버네티스의 `resources.limits`를 설정했다고 안심하기 쉽지만, 그 뒤에서 실제로 커널이 어떻게 자원을 나누는지는 cgroup(control group)이라는 리눅스 커널 기능이 담당한다.

최근 배포되는 리눅스 배포판 대부분은 이제 cgroup v1이 아니라 **cgroup v2**를 기본으로 쓴다. v2는 단순히 버전만 올라간 것이 아니라 계층 구조 자체가 근본적으로 바뀌었고, 이 차이를 모르면 리소스 제한 설정이 기대와 다르게 동작하는 이유를 진단하기 어렵다. 이 글에서는 cgroup v1과 v2의 구조적 차이, 그리고 CPU·IO 제어를 실전에서 어떻게 튜닝하는지를 정리한다.

## 핵심 개념 1: v1의 분리 계층 vs v2의 통합 계층

cgroup v1에서는 컨트롤러(cpu, memory, blkio, pids 등)마다 **독립된 계층 구조**를 가질 수 있었다. 즉 `/sys/fs/cgroup/cpu/`와 `/sys/fs/cgroup/memory/` 아래에 프로세스를 서로 다른 그룹 트리로 배치하는 것이 허용됐다. 유연해 보이지만 실제로는 "이 프로세스가 CPU 관점에서는 그룹 A에 속하는데 메모리 관점에서는 그룹 B에 속한다"는 앞뒤가 안 맞는 구성이 흔했고, 컨트롤러 간 상호작용(예: 메모리 회수와 IO 쓰로틀링의 연계)도 구현하기 어려웠다.

cgroup v2는 이를 **단일 통합 계층(unified hierarchy)** 하나로 합쳤다. 프로세스는 하나의 트리에서 정확히 하나의 cgroup에만 속하고, 그 cgroup에 여러 컨트롤러(cpu, memory, io, pids)를 동시에 붙여 함께 관리한다. 이 구조 덕분에 메모리 압박 상황에서 IO 쓰로틀링을 함께 고려하는 것 같은 컨트롤러 간 협조가 커널 차원에서 가능해졌고, 컨테이너 런타임(containerd, CRI-O)과 systemd도 v2를 기본 전제로 리소스 관리 로직을 단순화했다.

## 핵심 개념 2: v1과 v2 핵심 차이 비교

| 구분 | cgroup v1 | cgroup v2 |
|---|---|---|
| 계층 구조 | 컨트롤러별 독립 트리 | 단일 통합 트리 |
| CPU 제한 파일 | cpu.cfs_quota_us / cpu.cfs_period_us | cpu.max (`quota period` 한 줄) |
| IO 제한 파일 | blkio.throttle.* (디바이스별 분산) | io.max (디바이스별 단일 인터페이스) |
| 메모리 압박 알림 | 제한적 | PSI(Pressure Stall Information) 통합 |
| 하위 트리 위임 | 제한적 | delegation 모델로 컨테이너 내부에 안전하게 위임 |

특히 컨테이너 안에서 다시 컨테이너를 띄우는 rootless 환경이나, 컨테이너에 일부 cgroup 제어 권한을 위임하는 delegation 모델은 v2에서 훨씬 안전하고 표준화된 방식으로 지원된다. 쿠버네티스 1.25 이후 클러스터가 cgroup v2를 기본으로 요구하기 시작한 것도 이런 배경 때문이다.

## 핵심 개념 3: cpu.max와 io.max로 실제 제어하기

cgroup v2에서 CPU 제한은 `cpu.max` 파일 하나로 표현한다. 형식은 `$MAX $PERIOD`이며, 지정한 기간(period, 마이크로초) 동안 이 그룹이 쓸 수 있는 CPU 시간의 상한(quota)을 의미한다. 예를 들어 `200000 100000`은 100ms 주기마다 최대 200ms(=2코어 분량)까지 쓸 수 있다는 뜻이고, 이 값을 넘기면 커널이 그 그룹의 프로세스들을 **쓰로틀링(실행 지연)**한다.

IO 제한은 `io.max`로 디바이스별 상한을 건다. `rbps`(읽기 바이트/초), `wbps`(쓰기 바이트/초), `riops`, `wiops`를 디바이스 메이저:마이너 번호와 함께 지정한다. blkio 시절 분산돼 있던 인터페이스가 io 컨트롤러 하나로 정리되면서, 특정 디바이스에 대해 "이 그룹은 초당 50MB까지만 쓴다"는 제약을 한 줄로 걸 수 있게 됐다.

## 예제: cgroup v2로 CPU·IO 제한 걸기

```bash
# cgroup v2가 마운트돼 있는지, 통합 계층인지 확인
mount | grep cgroup2
cat /sys/fs/cgroup/cgroup.controllers   # 사용 가능한 컨트롤러 목록 확인

# 배치 작업용 cgroup 생성
mkdir /sys/fs/cgroup/batch-job
echo "+cpu +io" > /sys/fs/cgroup/cgroup.subtree_control

# CPU: 100ms 주기 중 최대 50ms(0.5코어)만 허용
echo "50000 100000" > /sys/fs/cgroup/batch-job/cpu.max

# IO: 특정 디스크(8:0)에 대해 쓰기 대역폭 50MB/s로 제한
echo "8:0 wbps=52428800" > /sys/fs/cgroup/batch-job/io.max

# 이 cgroup에 프로세스 소속시키기
echo $BATCH_PID > /sys/fs/cgroup/batch-job/cgroup.procs

# 현재 CPU 쓰로틀링 발생 여부 확인
cat /sys/fs/cgroup/batch-job/cpu.stat
# nr_periods, nr_throttled, throttled_usec 값으로 얼마나 자주/오래 눌렸는지 확인 가능
```

쿠버네티스 환경에서는 이 파일을 직접 만지는 대신 파드의 `resources.limits.cpu`와 `resources.limits.memory`를 설정하면 kubelet과 컨테이너 런타임이 위 cgroup 파일을 대신 써준다. 다만 IO 제한은 표준 리소스 필드로 직접 표현되지 않아, 필요하다면 별도의 어드미션 웹훅이나 노드 레벨 설정이 필요하다.

## 실무 포인트

- **`cpu.stat`의 `nr_throttled`를 반드시 모니터링한다**: CPU 사용률(usage)만 보면 쓰로틀링이 잦은데도 평균 사용률은 낮게 나오는 착시가 생긴다. quota 대비 실제 요구량이 몰리는 버스트 워크로드는 사용률이 아니라 쓰로틀링 발생 빈도로 판단해야 한다.
- **quota와 period 비율이 코어 수와 안 맞으면 멀티스레드 앱이 손해를 본다**: 예를 들어 4코어짜리 앱에 `cpu.max`를 `50000 100000`(0.5코어)으로 걸면, 짧은 period 안에 스레드들이 몰려 요청해 조기에 quota를 소진하고 나머지 period 동안 계속 쉬는 지터가 생길 수 있다. period를 늘려 완충 여유를 주는 것이 도움이 되는 경우가 많다.
- **memory.high와 io.max를 함께 본다**: 메모리 압박이 심해지면 커널이 페이지 캐시를 회수하며 IO가 급증하는 경우가 있다. cgroup v2의 PSI(`cpu.pressure`, `io.pressure`, `memory.pressure`)를 함께 관찰하면 어느 자원이 실제 병목인지 훨씬 명확히 드러난다.

## 3줄 요약

- cgroup v2는 컨트롤러별로 흩어져 있던 v1의 계층 구조를 단일 통합 트리로 합쳐, 컨트롤러 간 협조와 안전한 위임을 가능하게 했다.
- CPU는 `cpu.max`(quota/period), IO는 `io.max`(디바이스별 rbps/wbps/riops/wiops)로 각각 상한을 걸며, 쿠버네티스에서는 리소스 필드를 통해 간접적으로 이 파일들이 설정된다.
- 쓰로틀링 여부는 평균 사용률이 아니라 `cpu.stat`의 `nr_throttled`와 PSI 지표로 판단해야 실제 자원 경합을 놓치지 않는다.

## 참고 자료

- [커널 공식 문서: Control Group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Kubernetes 공식 문서: About cgroup v2](https://kubernetes.io/docs/concepts/architecture/cgroups/)
- [Facebook Engineering: Pressure Stall Information (PSI)](https://www.kernel.org/doc/html/latest/accounting/psi.html)
