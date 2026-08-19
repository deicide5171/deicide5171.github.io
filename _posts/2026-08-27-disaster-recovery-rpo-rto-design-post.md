---
layout: single
title: "몇 분을 잃어도 되는가, 몇 분 안에 복구해야 하는가 — RPO/RTO 기반 재해복구 설계"
date: 2026-08-27 13:45:00 +0530
categories: system-design
tags: ["disaster-recovery", "rpo", "rto", "architecture", "resilience", "backup"]
toc: true
toc_sticky: true
excerpt: "재해복구 설계는 기술팀이 임의로 정하는 게 아니라 비즈니스가 감내할 수 있는 데이터 손실과 다운타임을 먼저 숫자로 정하는 데서 시작한다. RPO/RTO 기준 DR 전략을 정리한다."
---

"재해복구 계획이 있나요?"라는 질문에 "백업은 매일 하고 있습니다"로 답하는 팀을 종종 본다. 그런데 이건 재해복구 계획이 아니라 백업 정책일 뿐이다. 진짜 재해복구(DR) 설계는 두 개의 숫자에서 시작한다. RPO(Recovery Point Objective, 목표 복구 시점)는 "장애 시 얼마만큼의 데이터 손실까지 감내할 수 있는가"이고, RTO(Recovery Time Objective, 목표 복구 시간)는 "장애 후 서비스가 다시 정상화되기까지 얼마나 걸려도 되는가"다.

이 두 숫자는 기술팀이 임의로 정하는 것이 아니라 비즈니스 영향 분석(Business Impact Analysis)을 거쳐 사업 부서와 함께 정해야 한다. 결제 시스템의 RPO가 5분이라면 "장애 시 최근 5분간의 결제 데이터를 잃어도 감내 가능하다"는 뜻이 아니라, 그 이상 잃으면 사업적으로 용납 불가하다는 뜻이다. 이 글에서는 RPO/RTO를 기준으로 어떤 DR 전략을 선택할지 정리한다.

## 핵심 개념 1: RPO/RTO에 따른 DR 전략 스펙트럼

DR 전략은 RPO/RTO 목표가 빡빡해질수록 복잡도와 비용이 기하급수적으로 늘어나는 스펙트럼을 이룬다.

| 전략 | RPO | RTO | 비용 | 설명 |
|---|---|---|---|---|
| 백업-복원(Backup & Restore) | 시간~하루 단위 | 시간~일 단위 | 낮음 | 정기 백업만 원격지에 보관, 장애 시 새 인프라에 복원 |
| 파일럿 라이트(Pilot Light) | 분~시간 단위 | 시간 단위 | 중간 | 핵심 DB만 상시 복제, 나머지 인프라는 장애 시 기동 |
| 웜 스탠바이(Warm Standby) | 초~분 단위 | 분 단위 | 높음 | 축소된 규모로 상시 가동, 장애 시 스케일업 |
| 액티브-액티브(Active-Active) | 0에 근접 | 초 단위(사실상 무중단) | 매우 높음 | 여러 리전이 동시에 실제 트래픽 처리 |

RPO를 줄이려면 복제 빈도를 높여야 하고, RTO를 줄이려면 대체 인프라가 이미 가동 중이어야 한다. 두 목표 모두 극한으로 밀어붙이면 액티브-액티브에 도달하지만, 이는 데이터 정합성 관리(멀티 리전 쓰기 충돌)와 인프라 이중 운영 비용을 동반한다.

## 핵심 개념 2: 숨어있는 RPO 킬러 — 복제 지연

RPO를 설계상 "5분"으로 잡아도 실제로는 그보다 나쁠 수 있다. 비동기 복제를 쓰는 대부분의 DR 구성에서, 복제 지연(replication lag)이 커지면 실제 RPO는 설계값이 아니라 그 순간의 지연시간이 된다. 예를 들어 평소엔 복제 지연이 1초 미만이어도, 대량 배치 작업이나 네트워크 혼잡 시 지연이 몇 분으로 튀면 그 순간 장애가 나면 실제 데이터 손실은 설계했던 RPO보다 훨씬 커진다.

이 때문에 RPO는 "설계값"과 "실측값"을 구분해서 모니터링해야 한다. 복제 지연을 지속적으로 계측하고, 지연이 RPO 목표를 초과하는 시간의 비율(SLO 형태로)을 별도로 추적하는 것이 실무에서 흔히 빠지는 부분이다.

<img src="/assets/images/posts/2026-08-27-disaster-recovery-rpo-rto-design-1.svg" alt="장애 발생 시점을 기준으로 RPO는 그 이전 마지막 복제 시점까지의 데이터 손실 구간을, RTO는 장애 발생부터 서비스 정상화까지의 시간을 나타내는 타임라인" style="width:100%;">

## 예제: DR 티어별 RPO/RTO 목표를 코드/설정으로 명시하기

```yaml
# dr-policy.yaml — 서비스 티어별 RPO/RTO 목표와 검증 방식
tiers:
  tier-1-payment:
    rpo_target: "60s"
    rto_target: "5m"
    strategy: "active-active"
    replication: "synchronous-multi-region"
    dr_test_frequency: "monthly"

  tier-2-order:
    rpo_target: "5m"
    rto_target: "30m"
    strategy: "warm-standby"
    replication: "async-cross-region"
    dr_test_frequency: "quarterly"

  tier-3-analytics:
    rpo_target: "24h"
    rto_target: "8h"
    strategy: "backup-restore"
    replication: "daily-snapshot"
    dr_test_frequency: "yearly"
```

이렇게 서비스 티어별로 목표를 명문화해 두면, "이 시스템은 왜 이렇게 복잡한 복제 구조를 쓰는가"에 대한 근거가 문서로 남고, 신규 서비스를 추가할 때도 같은 기준으로 티어를 분류할 수 있다.

## 실무 포인트

- **DR 테스트(게임 데이)를 실제로 실행한다**: RPO/RTO 목표는 문서로만 존재하면 의미가 없다. 정기적으로 실제 페일오버를 실행해 보고(운영 트래픽을 실제로 전환하거나, 최소한 복원 절차를 처음부터 끝까지 실행해) 목표 시간 안에 실제로 복구되는지 검증해야 한다. 검증 안 된 DR 계획은 계획이 아니라 희망사항이다.
- **RTO는 사람의 개입 시간도 포함해야 한다**: 자동 페일오버가 아니라 사람이 판단하고 스위치를 눌러야 하는 구조라면, 알림이 오고 담당자가 깨어나 확인하는 시간까지 RTO에 포함해야 한다. 새벽 3시 장애라면 이 시간이 수십 분을 쉽게 넘길 수 있다.
- **티어를 나누고 전부 액티브-액티브로 만들려 하지 않는다**: 모든 서비스를 최고 등급 DR로 설계하면 비용이 감당 불가능해진다. 비즈니스 영향 분석으로 서비스를 몇 개 티어로 나누고, 핵심 결제·인증 시스템에만 강한 DR을 적용하는 것이 현실적이다.

## 3줄 요약

- RPO는 감내 가능한 데이터 손실을, RTO는 감내 가능한 다운타임을 뜻하며 둘 다 비즈니스 영향 분석에서 나와야 한다.
- 백업-복원부터 액티브-액티브까지 DR 전략은 RPO/RTO 목표가 빡빡해질수록 비용이 기하급수적으로 커지는 스펙트럼이다.
- 복제 지연은 설계된 RPO를 실측 RPO로 갉아먹는 숨은 요인이므로 지속적으로 계측해야 하고, DR 계획은 실제 페일오버 테스트로 검증해야 신뢰할 수 있다.

## 참고 자료

- [AWS Well-Architected: Disaster Recovery of Workloads on AWS](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html)
- [Google Cloud: Disaster recovery planning guide](https://cloud.google.com/architecture/dr-scenarios-planning-guide)
- [Microsoft Azure: Well-Architected Reliability](https://learn.microsoft.com/en-us/azure/well-architected/reliability/)
