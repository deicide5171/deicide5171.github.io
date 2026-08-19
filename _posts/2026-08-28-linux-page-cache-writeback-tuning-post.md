---
layout: single
title: "쓰기 몰릴 때 서버가 멈추는 이유 — 리눅스 페이지 캐시와 writeback 튜닝"
date: 2026-08-28 12:40:00 +0530
categories: infra
tags: ["infra", "linux", "page-cache", "writeback", "dirty-ratio", "kernel"]
toc: true
toc_sticky: true
excerpt: "리눅스가 쓰기를 페이지 캐시에 모아뒀다 나중에 디스크로 흘려보내는 writeback 구조와, dirty_ratio 계열 파라미터를 잘못 두면 대량 쓰기 순간 서버가 멎어버리는 이유를 정리한다."
---

대량 파일 쓰기나 로그 몰림이 있을 때 갑자기 애플리케이션 전체가 몇 초에서 몇십 초씩 응답을 멈추는 현상을 겪어본 적이 있다면, 원인은 애플리케이션 코드가 아니라 리눅스 커널의 **페이지 캐시 writeback** 메커니즘일 가능성이 높다. `write()` 시스템 콜은 기본적으로 데이터를 디스크가 아니라 메모리(페이지 캐시)에만 쓰고 즉시 반환한다. 실제 디스크 반영은 커널이 백그라운드에서 나중에 처리하는데, 이 "나중에"를 제어하는 파라미터를 모르면 메모리가 가득 찬 순간 커널이 응답 없는 동기 쓰기 모드로 강제 전환되며 애플리케이션이 통째로 멈춘다.

이 동작은 디스크 성능을 숨기고 쓰기 처리량을 높이기 위한 의도된 설계지만, 기본값은 대부분 일반 데스크톱 워크로드를 기준으로 잡혀 있어 대용량 쓰기가 잦은 서버에는 그대로 맞지 않는 경우가 많다. 이 글에서는 페이지 캐시가 더티 페이지를 쌓아두는 구조와, `vm.dirty_*` 계열 파라미터가 그 상한을 어떻게 제어하는지 정리한다.

## 핵심 개념 1: write()는 디스크가 아니라 메모리에 쓴다

애플리케이션이 파일에 `write()`를 호출하면 커널은 해당 데이터를 페이지 캐시에 있는 메모리 페이지에 복사하고, 그 페이지를 "더티(dirty)"로 표시한 뒤 즉시 시스템 콜을 반환한다. 디스크에는 아직 아무것도 쓰이지 않았다. 이 방식 덕분에 쓰기 성능은 메모리 속도에 가깝게 나오고, 같은 파일을 짧은 시간에 여러 번 고칠 때도 디스크 I/O는 한 번만 발생한다(쓰기 병합).

더티 페이지는 커널의 `flusher` 스레드(`kworker` 계열)가 백그라운드에서 주기적으로 디스크에 내려보낸다. 이 시점을 언제로 잡을지가 튜닝의 핵심이다. 너무 빨리 내려보내면 캐시의 이점이 줄고, 너무 늦게 내려보내면 한 번에 내려보낼 더티 페이지가 쌓여 그 순간 디스크 I/O가 폭주한다.

## 핵심 개념 2: dirty_ratio와 dirty_background_ratio — 두 개의 임계값

리눅스는 더티 페이지 비율에 두 개의 임계값을 둔다.

| 파라미터 | 의미 | 초과 시 동작 |
|---|---|---|
| `vm.dirty_background_ratio` | 전체 메모리 대비 더티 페이지 비율(낮은 임계값) | flusher 스레드가 **백그라운드**에서 조용히 쓰기 시작 |
| `vm.dirty_ratio` | 전체 메모리 대비 더티 페이지 비율(높은 임계값) | 쓰기를 시도하는 **프로세스 자신이 동기적으로** 페이지를 flush할 때까지 블로킹 |

`dirty_background_ratio`(기본 10~20)를 넘으면 커널이 알아서 백그라운드로 디스크에 쓰기 시작하므로 애플리케이션은 눈치채지 못한다. 문제는 `dirty_ratio`(기본 20~40)까지 넘어설 때다. 이 시점부터는 `write()`를 호출하는 프로세스 자신이 강제로 멈춰서 더티 페이지가 임계값 아래로 내려갈 때까지 동기적으로 디스크에 쓰기를 떠맡는다. 메모리가 크고 디스크가 느릴수록, 이 임계값에 도달했을 때 한 번에 밀어내야 할 데이터 양이 커서 블로킹 시간도 길어진다.

<img src="/assets/images/posts/2026-08-28-linux-page-cache-writeback-tuning-1.svg" alt="더티 페이지 비율이 dirty_background_ratio를 넘으면 백그라운드 flush, dirty_ratio를 넘으면 쓰기 프로세스가 동기 블로킹되는 구조" style="width:100%;">

## 핵심 개념 3: 메모리가 클수록 비율 기반 설정이 위험해지는 이유

`dirty_ratio`는 절대량이 아니라 **전체 메모리 대비 비율**이다. 메모리가 16GB인 서버에서 `dirty_ratio=20`이면 최대 3.2GB의 더티 페이지가 쌓일 수 있다는 뜻이고, 메모리가 256GB인 서버라면 같은 20%가 51.2GB에 달한다. 디스크 쓰기 대역폭은 메모리 용량과 함께 늘지 않으므로, 메모리가 큰 서버일수록 비율 기반 기본값을 그대로 쓰면 한 번에 밀어내야 할 데이터 양이 디스크가 감당하기 어려운 수준까지 쌓인 뒤에야 flush가 강제된다. 이런 서버에서는 `dirty_ratio` 대신 절대 바이트 단위인 `dirty_bytes`/`dirty_background_bytes`로 상한을 직접 지정하는 것이 더 예측 가능하다.

## 예제: sysctl로 writeback 파라미터 조정

```bash
# 현재 값 확인
sysctl vm.dirty_ratio vm.dirty_background_ratio vm.dirty_expire_centisecs

# 메모리가 큰 서버는 비율 대신 절대 바이트로 상한 고정 (예: 백그라운드 flush 200MB, 강제 블로킹 1GB)
sudo sysctl -w vm.dirty_background_bytes=209715200
sudo sysctl -w vm.dirty_ratio=0        # bytes 설정을 쓰려면 ratio는 0으로
sudo sysctl -w vm.dirty_bytes=1073741824

# 더티 페이지가 이 시간(centisecs, 1/100초)보다 오래되면 만료로 간주해 강제 flush 대상에 포함
sudo sysctl -w vm.dirty_expire_centisecs=3000   # 30초

# 영구 반영은 /etc/sysctl.d/99-writeback.conf 에 위 값들을 기록
```

값을 바꾼 뒤에는 `iostat -x 1`로 `%util`과 `await`가 대량 쓰기 구간에서 어떻게 변하는지, 그리고 애플리케이션의 p99 지연이 flush 타이밍과 겹치는지 함께 관찰해야 튜닝 효과를 확인할 수 있다.

## 실무 포인트

- **`dirty_ratio`를 낮추는 게 항상 답은 아니다**: 값을 너무 낮추면 flush가 너무 자주 일어나 평상시 쓰기 처리량 자체가 떨어진다. 목표는 "동기 블로킹에 걸리는 상황을 없애는 것"이지 flush를 없애는 것이 아니다.
- **로그 몰림·배치 작업 전후로 별도 관찰이 필요하다**: 로그 로테이션, 대량 백업, 배치 익스포트처럼 짧은 시간에 쓰기가 몰리는 작업은 평상시 트래픽과 별개로 더티 페이지 급증을 유발한다. 해당 작업 시간대에 `dirty_ratio` 블로킹이 발생하는지 별도로 확인한다.
- **컨테이너 환경에서는 cgroup 단위 writeback도 함께 고려한다**: cgroup v2는 컨테이너별로 writeback 압력을 분리할 수 있어, 한 컨테이너의 대량 쓰기가 다른 컨테이너의 쓰기 지연에 전이되는 것을 줄일 수 있다.

## 3줄 요약

- `write()`는 즉시 디스크가 아니라 페이지 캐시에만 쓰고, 실제 디스크 반영(writeback)은 커널이 백그라운드에서 나중에 처리한다.
- `dirty_background_ratio`를 넘으면 조용히 백그라운드 flush가 시작되지만, `dirty_ratio`를 넘으면 쓰기 프로세스 자신이 동기적으로 블로킹되며 응답이 멎는다.
- 메모리가 큰 서버일수록 비율 기반 기본값은 위험하므로, `dirty_bytes`/`dirty_background_bytes`로 절대 상한을 직접 지정하고 대량 쓰기 작업 전후로 지연을 관찰해야 한다.

## 참고 자료

- [Linux 커널 문서: sysctl vm.txt](https://www.kernel.org/doc/Documentation/sysctl/vm.txt)
- [Red Hat: Understanding Virtual Memory Writeback](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/)
- [LWN: Page cache writeback](https://lwn.net/Kernel/Index/#Page_cache-Writeback)
