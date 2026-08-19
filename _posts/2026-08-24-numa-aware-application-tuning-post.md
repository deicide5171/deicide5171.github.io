---
layout: single
title: "메모리도 거리가 있다 — NUMA를 고려한 애플리케이션·DB 튜닝"
date: 2026-08-24 13:40:00 +0530
categories: infra
tags: ["numa", "linux", "performance-tuning", "postgresql", "jvm", "memory-locality"]
toc: true
toc_sticky: true
excerpt: "멀티소켓 서버에서 동일한 RAM 접근이라도 물리적 거리에 따라 지연 시간이 달라지는 NUMA 구조를 짚고, numactl과 애플리케이션·DB 설정으로 이를 고려하는 실무 튜닝법을 정리한다."
---

같은 서버, 같은 RAM 용량인데 벤치마크 점수가 재현되지 않는다면 NUMA(Non-Uniform Memory Access) 배치를 의심해볼 시점이다. 멀티소켓 서버에서는 각 CPU 소켓(NUMA 노드)이 자신에게 물리적으로 붙어 있는 로컬 메모리와, 다른 소켓에 붙은 원격 메모리를 모두 접근할 수 있지만, 두 접근의 지연 시간은 같지 않다. 커널 스케줄러나 메모리 할당자가 프로세스를 잘못된 노드에 배치하면, 논리적으로는 아무 문제가 없어 보이는 코드가 실제로는 매번 원격 메모리를 오가며 성능을 갉아먹는다.

이 글에서는 NUMA 아키텍처의 기본 개념, `numactl`로 확인·제어하는 법, 그리고 PostgreSQL과 JVM 같은 무거운 애플리케이션에서 NUMA를 고려해야 하는 지점을 정리한다.

## 핵심 개념 1: NUMA 노드와 로컬/원격 접근 지연

멀티소켓 서버는 각 CPU 소켓마다 자신의 메모리 컨트롤러에 직접 연결된 RAM 뱅크(로컬 메모리)를 갖고, 소켓 간은 QPI/UPI(Intel) 또는 Infinity Fabric(AMD) 같은 인터커넥트로 연결된다. 소켓 A의 코어가 소켓 B에 붙은 메모리에 접근하려면 이 인터커넥트를 거쳐야 하므로, 로컬 접근보다 지연 시간이 늘어나고(전형적으로 수십~100% 이상) 인터커넥트 대역폭도 공유해야 한다.

`numactl --hardware`로 노드 구성과 노드 간 거리(distance)를 확인할 수 있다. distance 값이 클수록 원격 접근 비용이 크다는 뜻이며, 이 값이 애플리케이션 배치 결정의 기초 데이터가 된다.

```bash
$ numactl --hardware
available: 2 nodes (0-1)
node 0 cpus: 0 1 2 3 4 5 6 7
node 0 size: 128932 MB
node 1 cpus: 8 9 10 11 12 13 14 15
node 1 size: 129012 MB
node distances:
node   0   1
  0:  10  21
  1:  21  10
```

## 핵심 개념 2: 메모리 정책 — bind, interleave, preferred

리눅스는 프로세스·스레드가 어느 노드의 메모리를 쓸지 정하는 정책을 제공한다.

| 정책 | 동작 | 적합한 상황 |
|---|---|---|
| `--cpunodebind` + `--membind` | 특정 노드의 CPU·메모리만 사용, 넘지 않음 | 노드 크기에 맞는 단일 인스턴스, 예측 가능한 지연이 중요할 때 |
| `--interleave` | 여러 노드에 라운드로빈으로 메모리 분산 | 노드 하나보다 큰 메모리를 쓰는 단일 프로세스(대형 캐시 등) |
| `--preferred` | 가능하면 지정 노드, 부족하면 다른 노드도 허용 | 유연성이 필요한 경우 |

DB나 JVM처럼 하나의 프로세스가 서버 메모리 대부분을 차지하는 경우, 무정책 상태로 두면 커널의 기본 할당 정책(보통 first-touch, 처음 접근한 CPU의 로컬 노드에 할당)에 의존하게 되는데, 스레드가 노드 간을 오가며 실행되면 처음 할당된 노드와 실제 접근하는 코어가 어긋나 원격 접근이 누적된다.

## 예제: numactl로 PostgreSQL 프로세스 바인딩

```bash
# 노드 0의 CPU와 메모리만 사용하도록 PostgreSQL 시작
numactl --cpunodebind=0 --membind=0 \
  pg_ctl -D /var/lib/postgresql/16/main start

# 이미 실행 중인 프로세스의 NUMA 정책을 확인
numastat -p $(pgrep -f postgres | head -1)

# shared_buffers처럼 큰 메모리 영역은 여러 노드에 걸쳐 분산해 병목을 완화하고 싶다면
numactl --interleave=all \
  pg_ctl -D /var/lib/postgresql/16/main start
```

PostgreSQL 커뮤니티에서는 `shared_buffers`가 단일 노드 크기를 넘는 대형 인스턴스에서 `--interleave=all`로 시작하는 것이 한 노드에 몰리는 것보다 안정적인 경우가 많다고 보고돼 왔다. 반대로 인스턴스를 노드 크기에 맞춰 여러 개로 쪼갤 수 있다면(샤딩), 각 인스턴스를 `--cpunodebind`/`--membind`로 노드에 고정하는 편이 더 예측 가능한 지연을 준다.

## 실무 포인트

- **JVM은 `-XX:+UseNUMA` 옵션을 확인한다**: G1GC 등 일부 GC는 NUMA 인식 할당을 지원해, 각 GC 스레드가 실행 중인 노드의 로컬 메모리를 우선 할당하도록 시도한다. 다만 애플리케이션 스레드가 GC와 무관하게 노드를 오가며 스케줄링되면 이 이점이 상쇄되므로, CPU 어피니티(taskset)와 함께 고려해야 한다.
- **Transparent Huge Page(THP)와 NUMA는 상호작용을 주의한다**: THP는 메모리 단편화를 줄이지만, 압축(compaction) 작업이 NUMA 노드 경계를 넘나들며 페이지를 재배치하는 과정에서 예기치 않은 지연 스파이크를 유발할 수 있다. DB 워크로드에서는 THP를 `madvise`로 제한하거나 끄고 애플리케이션이 직접 huge page를 관리하는 경우가 많다.
- **측정 없이 바인딩부터 하지 않는다**: `numastat -m`, `perf stat -e node-load-misses`로 실제 원격 접근 비율을 먼저 측정해야 한다. 워크로드가 애초에 메모리 지연에 민감하지 않다면(예: I/O 바운드), NUMA 튜닝에 들이는 노력 대비 이득이 없을 수 있다.

## 3줄 요약

- 멀티소켓 서버에서는 로컬/원격 메모리 접근의 지연 시간이 다르며, `numactl --hardware`의 노드 거리(distance)로 그 정도를 확인할 수 있다.
- 워크로드가 노드 하나에 들어가면 `cpunodebind`/`membind`로 고정하고, 노드보다 크면 `interleave`로 분산하는 것이 기본 전략이다.
- JVM의 NUMA 인식 GC 옵션, THP와의 상호작용, 그리고 바인딩 전 `numastat`/`perf`를 통한 실측이 실무 튜닝의 핵심이다.

## 참고 자료

- [Linux 커널 공식 문서: NUMA Memory Policy](https://www.kernel.org/doc/html/latest/admin-guide/mm/numa_memory_policy.html)
- [numactl(8) man page](https://man7.org/linux/man-pages/man8/numactl.8.html)
- [PostgreSQL Wiki: Linux NUMA and PostgreSQL](https://wiki.postgresql.org/wiki/Linux_Memory_Management)
- [OpenJDK: JEP과 NUMA 관련 GC 옵션 문서 (G1 -XX:+UseNUMA)](https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html)
