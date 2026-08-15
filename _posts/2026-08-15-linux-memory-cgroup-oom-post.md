---
layout: single
title: "리눅스 메모리 관리 실전 — cgroup v2와 OOM Killer, memory.pressure로 미리 감지하기"
date: 2026-08-15 11:40:00 +0530
categories: infra
tags: ["linux", "cgroup", "oom-killer", "kubernetes", "memory"]
toc: true
toc_sticky: true
excerpt: "컨테이너가 갑자기 죽거나 서버가 먹통이 되는 원인의 상당수는 리눅스 메모리 관리에 있다. cgroup v2의 memory.max·memory.pressure와 OOM Killer 동작 원리를 실무 관점에서 정리한다."
---

## 왜 지금 리눅스 메모리 관리인가

"컨테이너가 이유 없이 재시작됐다", "서버가 응답 없이 멈췄는데 로그엔 별다른 에러가 없다" — 이런 장애의 상당수는 애플리케이션 코드가 아니라 리눅스 커널의 메모리 관리 계층에서 벌어진다. Kubernetes가 v1.25부터 cgroup v2를 기본값으로 쓰고 v1.31에서 v1 지원을 완전히 걷어내면서, 이제 "컨테이너 메모리 제한이 어떻게 걸리는지"를 정확히 모르면 장애 원인을 추적하기 어려워졌다.

문제는 OOM Killer가 프로세스를 죽이는 시점이 이미 "손 쓸 수 없는 상황"이라는 점이다. 커널이 메모리를 회수(reclaim)하려고 애쓰다가 실패한 다음에야 프로세스를 강제 종료하기 때문에, 그 전 단계에서 미리 압박 신호를 감지하는 것이 실무에서 훨씬 중요하다.

## 핵심 개념: cgroup v2 메모리 제어 구조

cgroup v1은 memory, cpu, io 같은 컨트롤러를 각각 따로 마운트했지만, v2는 `/sys/fs/cgroup/` 아래 단일 계층 구조로 통합했다. 메모리 관련 핵심 파일은 다음과 같다.

| 파일 | 의미 |
|---|---|
| `memory.max` | 하드 리밋. 초과 시 회수 시도 후 실패하면 cgroup 범위 OOM 발생 |
| `memory.high` | 소프트 리밋. 초과 시 즉시 죽이지 않고 강하게 스로틀링·회수 유도 |
| `memory.low` | 이 값 아래로는 메모리 압박 시에도 최대한 보호 |
| `memory.pressure` | PSI(Pressure Stall Information) 기반, 메모리 부족으로 대기한 시간 비율 |
| `memory.oom.group` | 1이면 OOM 발생 시 프로세스 하나가 아니라 그룹 전체를 종료 |

`memory.max`가 하드 리밋이라면 `memory.high`는 그 앞단의 안전장치다. 사용량이 `memory.high`를 넘으면 커널은 해당 cgroup의 프로세스를 강하게 스로틀링하면서 메모리 회수를 유도하고, 그래도 안 되면 결국 `memory.max`에서 OOM이 발생한다. 즉 튜닝의 핵심은 `memory.max`를 여유 있게 잡고 `memory.high`로 먼저 경고성 압박을 주는 것이다.

## OOM Killer 동작 흐름

시스템 전체 OOM과 cgroup 범위 OOM은 트리거 조건이 다르다.

1. 특정 cgroup이 `memory.max`에 도달하고 회수로도 해소되지 않으면, 커널은 **그 cgroup 내부**에서 희생 프로세스를 골라 종료한다(cgroup-aware OOM).
2. `memory.oom.group=1`이 설정된 경우 프로세스 하나만 죽이지 않고 그룹 전체를 종료해, "메모리 누수 하나 때문에 나머지 프로세스만 이상하게 살아남는" 상황을 막는다.
3. 시스템 전체 메모리가 고갈되면 전역 OOM Killer가 `oom_score`가 가장 높은 프로세스를 선택해 종료한다. `oom_score_adj`로 특정 프로세스의 우선순위를 조정할 수 있다.

여기서 실무적으로 중요한 점은, OOM Killer가 개입하는 시점에는 이미 애플리케이션이 심각하게 느려진 뒤라는 것이다. `memory.high` 스로틀링 구간에서 지연시간이 치솟는 것이 먼저고, OOM은 그 다음이다.

## 예제: memory.pressure로 사전 감지하기

PSI 기반 `memory.pressure`는 "메모리가 없어서 얼마나 대기했는지"를 백분율로 알려준다. OOM이 터지기 전에 조기 경보로 쓸 수 있다.

```bash
# 특정 cgroup의 메모리 압박 지표 확인
cat /sys/fs/cgroup/myapp.slice/memory.pressure
# some avg10=2.15 avg60=1.30 avg300=0.42 total=184320
# full avg10=0.51 avg60=0.20 avg300=0.05 total=32104

# avg10(최근 10초 평균)이 지속적으로 몇 % 이상이면 알림을 울리는 방식으로 활용
```

```yaml
# Kubernetes Pod에서 memory.high에 해당하는 소프트 리밋 개념 적용 예시
resources:
  requests:
    memory: "512Mi"
  limits:
    memory: "1Gi"   # memory.max에 매핑, 초과 시 컨테이너 OOMKilled
```

Kubernetes는 `resources.limits.memory`를 cgroup의 `memory.max`에 직접 매핑한다. `memory.high` 같은 소프트 스로틀링을 세밀하게 제어하고 싶다면 커널 파라미터를 직접 다루거나, 이를 지원하는 컨테이너 런타임 설정을 확인해야 한다.

## 실무 포인트

- **`memory.max` 하나만 보지 말 것**: `memory.high`로 여유 구간을 두면 OOM 전에 스로틀링으로 완충할 수 있다. 하드 리밋만 걸어두면 "잘 돌다가 갑자기 죽는" 패턴이 반복된다.
- **`memory.pressure`를 모니터링 지표로 편입한다**: OOM 발생 횟수는 이미 늦은 지표다. PSI 기반 압박 수치를 Prometheus 등으로 수집해 임계치 알림을 걸어두면 장애를 미리 잡을 수 있다.
- **`oom.group` 설정을 점검한다**: 멀티 프로세스 컨테이너(사이드카 포함)에서 하나만 죽고 나머지가 좀비처럼 남는 상황을 막으려면 그룹 단위 종료 설정이 필요한지 검토한다.
- **swap 정책도 함께 확인한다**: swap이 있으면 OOM 발생이 늦춰지는 대신 지연시간이 급격히 나빠질 수 있다. 레이턴시가 중요한 서비스는 swap을 끄고 메모리 리밋을 명확히 설계하는 편이 예측 가능하다.

## 3줄 요약

- cgroup v2는 `memory.max`(하드 리밋)와 `memory.high`(소프트 스로틀링)를 분리해 OOM 이전에 완충 구간을 둘 수 있다.
- OOM Killer는 cgroup 범위와 시스템 전체 범위로 나뉘어 동작하며, `memory.oom.group`으로 그룹 단위 종료 여부를 정할 수 있다.
- `memory.pressure`(PSI) 지표를 모니터링에 편입하면 OOM이 터지기 전에 메모리 압박을 조기에 감지할 수 있다.

## 참고 자료

- [cgroup v2 — Linux kernel documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [PSI (Pressure Stall Information) — Linux kernel documentation](https://docs.kernel.org/accounting/psi.html)
- [Kubernetes: Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
