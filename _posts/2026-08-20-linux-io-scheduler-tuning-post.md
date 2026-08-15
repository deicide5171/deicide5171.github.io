---
layout: single
title: "리눅스 I/O 스케줄러 튜닝 — NVMe 시대엔 mq-deadline 대신 none을 써야 할까"
date: 2026-08-20 13:40:00 +0530
categories: infra
tags: ["linux", "io-scheduler", "nvme", "block-layer", "performance-tuning"]
toc: true
toc_sticky: true
excerpt: "회전 디스크 시절에 만들어진 I/O 스케줄러 기본값을 NVMe SSD에 그대로 쓰면 오히려 손해일 수 있다. blk-mq 구조와 none·mq-deadline·bfq·kyber의 차이를 실무 관점에서 정리한다."
---

## 왜 지금 I/O 스케줄러인가

리눅스 I/O 스케줄러는 원래 회전 디스크(HDD)의 물리적 한계, 즉 헤드 이동(seek) 비용을 줄이기 위해 만들어졌다. 요청을 정렬하고 병합해서 헤드가 최대한 적게 움직이게 만드는 것이 CFQ나 deadline 같은 전통 스케줄러의 핵심 임무였다. 그런데 NVMe SSD에는 seek 비용이라는 개념 자체가 없다. 수만 개의 병렬 하드웨어 큐를 갖춘 장치에 "헤드 이동을 줄이기 위한" 정렬 로직을 그대로 적용하면, 병합·정렬에 들이는 CPU 비용이 순수한 오버헤드가 되는 경우가 생긴다.

리눅스 커널은 이미 오래전에 단일 큐 기반 블록 계층을 blk-mq(multi-queue block layer)로 전환했고, 최신 배포판에서는 legacy I/O 스케줄러(구식 CFQ 등)를 아예 제거하고 blk-mq 기반 스케줄러(mq-deadline, bfq, kyber, none)만 남겨두는 방향으로 정리되어 있다. 문제는 배포판 기본값이 모든 장치에 최적은 아니라는 점이다. NVMe 장치에 회전 디스크 시절 감각으로 스케줄러를 고르면 성능을 오히려 깎아먹을 수 있다.

## 핵심 개념 1: blk-mq와 큐 구조

전통적인 블록 계층은 커널 전체에서 하나의 요청 큐를 공유하고, 그 큐에 스핀락을 걸어가며 스케줄링했다. 코어 수가 늘어날수록 이 단일 큐 락 경합이 병목이 됐다. blk-mq는 이를 두 단계로 나눈다.

<img src="/assets/images/posts/2026-08-20-linux-io-scheduler-tuning-1.svg" alt="blk-mq 구조 - 애플리케이션 요청이 CPU별 소프트웨어 큐를 거쳐 I/O 스케줄러(none 또는 mq-deadline)를 지나 NVMe 하드웨어 디스패치 큐로 전달되는 흐름" style="width:100%;">

CPU 코어(또는 CPU 그룹)마다 별도의 **소프트웨어 큐(Software Staging Queue)** 를 두어 락 경합을 없애고, 그 뒤에 장치가 지원하는 **하드웨어 디스패치 큐(Hardware Dispatch Queue)** 로 매핑한다. NVMe는 하드웨어 큐 자체를 코어 수만큼 병렬로 여러 개 가질 수 있어서, 이 구조와 궁합이 좋다. I/O 스케줄러는 소프트웨어 큐와 하드웨어 큐 사이에서 요청을 병합·정렬·지연시킬지 결정하는 선택적 계층이며, `none`은 이 계층을 사실상 건너뛰고 큐에 들어온 순서 그대로 하드웨어에 전달한다.

## 핵심 개념 2: 스케줄러별 특성 비교

| 스케줄러 | 원래 설계 대상 | 동작 방식 | 적합한 상황 |
|---|---|---|---|
| `none` | 다중 큐 SSD/NVMe | 병합·정렬 없이 FIFO에 가깝게 전달 | 병렬 큐가 충분한 고속 NVMe, 지연시간 최소화가 목표일 때 |
| `mq-deadline` | 일반 SSD, 저가 스토리지 | 요청별 만료 시각(deadline)을 두어 기아(starvation) 방지, 읽기 우선 | 읽기·쓰기 지연시간 균형이 필요한 범용 서버 |
| `bfq` | 데스크톱, 공유 스토리지 | 프로세스별 대역폭을 공평하게 분배(CFQ의 후신) | 여러 프로세스가 동시에 디스크를 두고 경쟁하는 환경 |
| `kyber` | 고속 다중 큐 장치 | 읽기/쓰기 목표 지연시간을 정해두고 큐 깊이를 동적 조절 | 지연시간 SLA가 있는 NVMe, `none`보다는 약간의 공평성 필요 시 |

주의할 점은 이 표가 "정답"이 아니라 "출발점"이라는 것이다. 동일한 NVMe 장치라도 워크로드가 순차 대용량 쓰기 위주인지, 소규모 랜덤 읽기가 섞인 DB 워크로드인지에 따라 최적 스케줄러가 달라질 수 있으므로, 실제 적용 전 벤치마크로 확인하는 과정이 필요하다.

## 예제: 현재 스케줄러 확인과 변경

```bash
# 장치별 사용 가능/현재 스케줄러 확인 (대괄호가 현재 값)
cat /sys/block/nvme0n1/queue/scheduler
# [none] mq-deadline kyber bfq

# 즉시 변경 (재부팅 시 초기화됨, 테스트용)
echo mq-deadline > /sys/block/nvme0n1/queue/scheduler

# 회전 여부·요청 큐 깊이 등 관련 파라미터도 함께 확인
cat /sys/block/nvme0n1/queue/rotational   # NVMe는 보통 0
cat /sys/block/nvme0n1/queue/nr_requests
```

영구 적용은 재부팅에도 유지되도록 udev 규칙으로 관리하는 것이 일반적이다.

```text
# /etc/udev/rules.d/60-io-scheduler.rules
# NVMe 장치에는 none, 회전 디스크에는 mq-deadline을 강제
ACTION=="add|change", KERNEL=="nvme*", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="none"
ACTION=="add|change", KERNEL=="sd*", ATTR{queue/rotational}=="1", ATTR{queue/scheduler}="mq-deadline"
```

## 실무 포인트

- **바꾸기 전에 반드시 벤치마크한다**: `fio`로 스케줄러별 IOPS·지연시간(p99 포함)을 실제 워크로드 패턴(랜덤/순차, 읽기/쓰기 비율)에 맞춰 비교하지 않고 "NVMe면 무조건 none"이라고 단정하면 특정 워크로드에서는 오히려 손해를 볼 수 있다.
- **가상화·클라우드 환경은 계층이 다르다**: 클라우드 인스턴스의 블록 스토리지는 하이퍼바이저·네트워크 스토리지 계층을 거치므로, 게스트 OS의 스케줄러 설정 효과가 베어메탈만큼 크지 않을 수 있다. 벤더가 권장하는 설정을 우선 확인한다.
- **`iostat -x`의 `avgqu-sz`, `%util`, `await`를 함께 본다**: 스케줄러를 바꾼 뒤 IOPS만 좋아졌는지, 지연시간 분포(특히 tail latency)까지 개선됐는지 같이 확인해야 한다.
- **컨테이너·다중 프로세스 경쟁 환경에서는 `bfq`도 후보에 넣는다**: 처리량만 보면 `none`이 앞서 보여도, 여러 프로세스가 디스크 I/O를 공평하게 나눠 써야 하는 상황이라면 공평성 있는 스케줄러가 전체 서비스 품질에는 더 나을 수 있다.

## 3줄 요약

- blk-mq는 CPU별 소프트웨어 큐와 장치의 하드웨어 디스패치 큐를 분리해 락 경합을 없앴고, I/O 스케줄러는 그 사이에서 병합·정렬 여부를 결정하는 선택적 계층이다.
- `none`은 병렬 큐가 풍부한 NVMe에서 오버헤드를 줄이는 선택지이고, `mq-deadline`·`bfq`·`kyber`는 각각 기아 방지·공평성·지연시간 SLA라는 다른 목표를 위한 것이라 장치·워크로드에 맞게 골라야 한다.
- 스케줄러 변경은 `/sys/block/<dev>/queue/scheduler`로 즉시 테스트하고, 영구 적용은 udev 규칙으로 관리하되, 반드시 실제 워크로드 기준 벤치마크로 검증한 뒤 적용한다.

## 참고 자료

- [Linux kernel documentation — Block layer (blk-mq multi-queue)](https://docs.kernel.org/block/index.html)
- [Linux kernel documentation — I/O schedulers](https://docs.kernel.org/block/switching-sched.html)
- [Red Hat Documentation — Setting the disk scheduler](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/setting-the-disk-scheduler_optimizing-the-system-for-throughput)
