---
layout: single
title: "분산 DB는 '지금'을 어떻게 아는가 — HLC와 TrueTime으로 보는 시간 동기화"
date: 2026-08-29 12:35:00 +0530
categories: database
tags: ["distributed-database", "hlc", "truetime", "clock-synchronization", "spanner", "distributed-systems"]
toc: true
toc_sticky: true
excerpt: "물리 시계만으로는 분산 트랜잭션의 순서를 보장할 수 없는 이유와, HLC(Hybrid Logical Clock)와 구글 TrueTime이 이 문제를 각각 다르게 해결하는 방식을 비교한다."
---

단일 서버 DB에서는 "이 트랜잭션이 저 트랜잭션보다 먼저 커밋됐다"는 순서를 시스템 시계 하나로 자연스럽게 판정할 수 있다. 하지만 여러 대륙에 흩어진 노드가 각자 커밋을 수행하는 분산 DB에서는 이 질문이 생각보다 어렵다. 각 서버의 물리 시계(NTP로 동기화된 시계)는 수 밀리초에서 수십 밀리초까지 어긋날 수 있고, 이 오차가 트랜잭션 순서 판정에 그대로 섞여 들어가면 "미래에 커밋된 트랜잭션이 과거 트랜잭션보다 먼저 보이는" 인과관계 위반이 생길 수 있다.

이 문제를 푸는 접근은 크게 두 갈래로 갈렸다. 하나는 논리적 순서 정보를 물리 시각에 얹어 인과관계를 보정하는 **HLC(Hybrid Logical Clock)**이고, 다른 하나는 아예 물리 시계의 불확실성 자체를 하드웨어로 줄이고 그 불확실성 구간을 명시적으로 다루는 구글의 **TrueTime**이다. CockroachDB와 MongoDB, YugabyteDB 등 많은 분산 DB가 HLC를 채택했고, 구글 Spanner는 TrueTime 위에서 외부 일관성을 구현한다. 이 글에서는 두 접근의 원리와 차이를 정리한다.

## 핵심 개념 1: 왜 물리 시계만으로는 부족한가

분산 시스템에서 "인과관계(causality)"란 A가 B의 원인이 되는 이벤트라면(예: A 커밋 결과를 읽고 B가 시작), B의 타임스탬프는 반드시 A보다 커야 한다는 요구다. 각 노드가 자신의 로컬 시계만 찍어서 타임스탬프를 매기면, 노드 간 시계 오차 때문에 실제로는 A 다음에 일어난 B가 더 이른 타임스탬프를 받는 상황이 생길 수 있다. NTP로 동기화해도 오차를 완전히 0으로 만들 수는 없고, 오차 범위(clock skew)는 네트워크 상황에 따라 변한다.

램포트(Lamport)의 논리 시계는 이 문제를 물리 시각을 아예 버리고 "이벤트 발생 순서를 세는 카운터"로 해결했지만, 그 값 자체는 사람이 읽는 실제 시각과 무관해 운영·디버깅 시 활용도가 떨어진다는 단점이 있었다.

## 핵심 개념 2: HLC — 물리 시각에 논리 카운터를 얹는다

HLC는 램포트 논리 시계의 인과관계 보장과 물리 시각의 가독성을 동시에 취하는 절충안이다. HLC 타임스탬프는 `(물리 시각, 논리 카운터)` 쌍으로 구성되며, 다음 규칙으로 갱신된다.

1. 로컬에서 이벤트가 발생하면, HLC의 물리 시각 부분을 로컬 시계값과 이전 HLC 값 중 큰 쪽으로 갱신한다.
2. 다른 노드로부터 메시지(타임스탬프 포함)를 받으면, 자신의 HLC를 "로컬 시계, 자신의 이전 HLC, 수신한 메시지의 HLC" 세 값 중 가장 큰 물리 시각으로 맞추고, 물리 시각이 같다면 논리 카운터를 1 증가시킨다.

이 규칙 덕분에 HLC는 인과관계가 있는 두 이벤트 사이에는 항상 순서가 보장되면서도, 물리 시각과 거의 같은 값을 유지해 사람이 봐도 대략 "언제 일어난 일인지" 알 수 있다. CockroachDB는 HLC를 트랜잭션 타임스탬프로 사용해 MVCC 버전 관리와 분산 트랜잭션의 순서를 결정하는 데 활용한다.

<img src="/assets/images/posts/2026-08-29-distributed-clock-sync-hlc-1.svg" alt="HLC는 물리 시각과 논리 카운터 쌍으로 인과관계를 보정하고, TrueTime은 불확실성 구간을 두고 커밋 대기로 순서를 보장하는 구조 비교" style="width:100%;">

## 핵심 개념 3: TrueTime — 불확실성 자체를 API로 노출한다

구글 Spanner의 TrueTime은 다른 방향에서 접근한다. GPS 수신기와 원자시계를 각 데이터센터에 배치해 물리 시계의 오차를 극히 작게(수 밀리초 이하) 줄이고, 이 잔여 불확실성을 숨기지 않고 `TT.now()` API로 `[earliest, latest]` 구간을 그대로 노출한다. 즉 "지금 시각은 정확히 몇 시다"라고 답하는 대신 "지금은 이 구간 사이의 어느 시점이다"라고 정직하게 답하는 것이다.

Spanner는 트랜잭션 커밋 시 이 불확실성 구간의 폭(ε)만큼 실제로 대기(commit wait)한 뒤 커밋을 확정한다. 이렇게 하면 커밋 타임스탬프가 실제 물리적으로 지나간 시각이 되는 것이 보장되어, 이후 시작되는 트랜잭션이 이전 트랜잭션의 커밋을 놓치는 일이 없다. 이 방식은 HLC처럼 메시지를 주고받으며 논리 카운터를 갱신하는 대신, 애초에 하드웨어로 오차를 좁히고 그 오차만큼 기다리는 전략이다.

| 구분 | HLC | TrueTime |
|---|---|---|
| 핵심 아이디어 | 물리 시각 + 논리 카운터 보정 | 불확실성 구간을 하드웨어로 축소 + 노출 |
| 필요 인프라 | 일반 NTP 동기화로 충분 | GPS 수신기·원자시계 전용 배치 필요 |
| 순서 보장 방식 | 메시지 교환 시 타임스탬프 병합 | 커밋 대기(commit wait)로 물리적 순서 확정 |
| 대표 채택 사례 | CockroachDB, MongoDB, YugabyteDB | Google Spanner |
| 도입 난이도 | 소프트웨어만으로 구현 가능 | 전용 하드웨어·데이터센터 인프라 필요 |

## 예제: HLC 갱신 로직 (의사코드)

```python
class HybridLogicalClock:
    def __init__(self):
        self.physical = 0   # 마지막으로 반영된 물리 시각(ms)
        self.logical = 0    # 물리 시각이 같을 때 순서를 매기는 카운터

    def local_event(self):
        now = wall_clock_ms()
        if now > self.physical:
            self.physical, self.logical = now, 0
        else:
            self.logical += 1   # 물리 시계가 안 움직였으면 논리 카운터로 순서 확보
        return (self.physical, self.logical)

    def receive_event(self, remote_physical, remote_logical):
        now = wall_clock_ms()
        new_physical = max(now, self.physical, remote_physical)
        if new_physical == self.physical == remote_physical:
            new_logical = max(self.logical, remote_logical) + 1
        elif new_physical == self.physical:
            new_logical = self.logical + 1
        elif new_physical == remote_physical:
            new_logical = remote_logical + 1
        else:
            new_logical = 0
        self.physical, self.logical = new_physical, new_logical
        return (self.physical, self.logical)
```

원격 메시지를 받을 때마다 "가장 앞선 물리 시각"으로 자신을 맞추고, 물리 시각이 겹치는 경우에만 논리 카운터로 순서를 세분화하는 것이 핵심이다.

## 실무 포인트

- **NTP 오차 모니터링을 소홀히 하지 않는다**: HLC는 NTP 동기화가 크게 어긋나 있어도 인과관계 자체는 보장하지만, 물리 시각 성분의 오차가 커지면 HLC 값이 벽시계 시각과 크게 벌어져 운영 관측성(로그 상관관계 분석 등)에 혼란을 준다. `chronyd`/`ntpd`의 오프셋을 정기 점검한다.
- **TrueTime류 시스템 도입은 하드웨어 투자를 전제한다**: 자체 데이터센터에 GPS·원자시계를 두지 않는 이상 TrueTime과 동일한 보장은 매니지드 서비스(Spanner 계열)를 통해서만 얻을 수 있다. 온프레미스에서 유사 효과를 노린다면 HLC 기반 오픈소스 분산 DB가 현실적인 선택지다.
- **커밋 대기(commit wait) 비용을 이해한다**: TrueTime 방식은 불확실성 구간만큼 커밋을 지연시키므로, 그 구간이 커질수록(시계 동기화 품질이 나쁠수록) 트랜잭션 지연이 늘어난다. 이는 "빠른 하드웨어 시계 동기화"가 곧 처리량에 직결되는 구조라는 뜻이다.

## 3줄 요약

- 분산 DB에서 노드별 물리 시계 오차는 트랜잭션 순서 판정에 인과관계 위반을 일으킬 수 있어, 별도의 논리적 순서 보정이 필요하다.
- HLC는 물리 시각에 논리 카운터를 얹어 소프트웨어만으로 인과관계를 보정하며 CockroachDB 등 여러 분산 DB가 채택했고, TrueTime은 하드웨어로 시계 오차 자체를 줄이고 그 불확실성 구간만큼 커밋을 대기시켜 순서를 보장한다.
- 두 방식은 상호 배타적이지 않은 트레이드오프이며, 전용 하드웨어 없이도 인과관계를 지키고 싶다면 HLC 기반 접근이 실무에서 더 접근하기 쉬운 선택지다.

## 참고 자료

- [Google Research: Spanner — TrueTime and External Consistency](https://research.google/pubs/pub39966/)
- [CockroachDB 공식 블로그: Living Without Atomic Clocks](https://www.cockroachlabs.com/blog/living-without-atomic-clocks/)
- [Hybrid Logical Clocks 논문(Kulkarni et al.)](https://cse.buffalo.edu/tech-reports/2014-04.pdf)
