---
layout: single
title: "Kubernetes Topology Spread Constraints로 가용영역 안전하게 분산 배치하기"
date: 2026-09-24 12:40:00 +0530
categories: infra
tags: ["Kubernetes", "TopologySpread", "가용영역", "파드스케줄링", "고가용성"]
toc: true
toc_sticky: true
excerpt: "replicas 3으로 배포했는데 스케줄러가 우연히 파드 세 개를 모두 같은 가용영역에 몰아넣어 그 존 하나가 죽자 서비스 전체가 내려간 사고를, Topology Spread Constraints로 분산 배치를 강제하는 방법으로 정리했다."
---

## 왜 지금 Topology Spread Constraints를 다시 봐야 하는가

쿠버네티스 클러스터를 여러 가용영역(Availability Zone)에 걸쳐 구성했다고 해서, 파드가 자동으로 그 영역들에 고르게 흩어지는 것은 아니다. 기본 스케줄러는 리소스 여유가 있는 노드를 우선적으로 고르기 때문에, 특정 시점에 한 영역의 노드들이 상대적으로 여유가 많으면 같은 서비스의 레플리카 여러 개가 그 영역에 몰릴 수 있다. 이 상태에서 그 가용영역 하나에 장애가 나면, 이론적으로는 다중 영역 구성으로 장애를 견뎌야 할 서비스가 실제로는 레플리카 전체를 잃는 사고로 이어진다. `PodAntiAffinity`로 이 문제를 완화하려는 시도도 있지만, 이는 "완전히 같은 노드/영역은 피한다"는 이진 조건만 표현할 수 있어 세 개 영역에 파드를 정확히 몇 개씩 분산시킬지 같은 세밀한 제어는 어렵다. Topology Spread Constraints는 이 분산 배치 요구사항을 훨씬 정밀하게 표현할 수 있도록 설계된 스케줄링 API다.

## 핵심 개념 1 — maxSkew: 분산의 "허용 오차"를 숫자로 정의한다

Topology Spread Constraints의 핵심 파라미터는 `maxSkew`다. 이는 "토폴로지 도메인(예: 가용영역) 간 파드 개수 차이가 최대 얼마까지 허용되는가"를 나타낸다. 예를 들어 `maxSkew: 1`이고 영역이 3개라면, 한 영역에 파드가 2개 있을 때 다른 영역에는 최소 1개 이상 있어야 한다(차이가 1 이하). 스케줄러는 새 파드를 배치할 때마다 이 조건을 만족하는 영역만 후보로 고려하므로, 배포가 끝난 시점에는 각 영역의 파드 개수가 최대한 균등하게 유지된다. `topologyKey`로 어떤 단위(영역, 노드, 랙 등)를 기준으로 분산시킬지 지정하고, `labelSelector`로 어떤 파드들끼리 묶어서 분산 대상으로 셀지 정의한다.

## 핵심 개념 2 — whenUnsatisfiable: 조건을 못 지킬 때 스케줄링을 막을 것인가

분산 조건을 만족하는 노드가 하나도 없는 상황(예: 특정 영역의 모든 노드가 리소스 부족)이 생길 수 있다. 이때 `whenUnsatisfiable`을 `DoNotSchedule`로 설정하면 조건을 만족하는 노드가 나타날 때까지 파드는 Pending 상태로 남는다. 가용성이 최우선인 서비스에서는 이 설정으로 "차라리 배포를 지연시키더라도 분산 원칙을 절대 어기지 않는다"는 정책을 강제할 수 있다. 반대로 `ScheduleAnyway`로 설정하면 조건을 최대한 만족하는 노드를 우선하되, 안 되면 조건을 어기더라도 어떻게든 스케줄링을 진행한다 — 가용성보다 배포 성공 자체가 더 중요한 워크로드에 적합하다.

| 파라미터 | 역할 |
|---|---|
| `maxSkew` | 토폴로지 도메인 간 허용되는 최대 파드 개수 차이 |
| `topologyKey` | 분산 기준 단위(가용영역, 노드, 커스텀 라벨 등) |
| `whenUnsatisfiable` | 조건 불충족 시 `DoNotSchedule`(대기) 또는 `ScheduleAnyway`(강행) |
| `labelSelector` | 분산 대상으로 함께 셀 파드 그룹 지정 |

## 예제 — 가용영역 간 균등 분산을 강제하는 설정

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  replicas: 6
  template:
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: payment-service
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: payment-service
      containers:
        - name: payment-service
          image: payment-service:1.4.0
```

가용영역 기준은 `DoNotSchedule`로 엄격하게 강제하고, 같은 영역 안에서의 노드 분산은 `ScheduleAnyway`로 완화해두는 조합이 실무에서 자주 쓰인다 — 영역 분산은 절대 타협하지 않되, 개별 노드 분산은 리소스 상황에 따라 유연하게 대응하도록 만드는 것이다.

## 실무 포인트

- **`DoNotSchedule`을 남용하면 배포가 무한정 Pending 상태에 머무를 수 있다.** 특히 노드 오토스케일러가 새 노드를 충분히 빠르게 추가하지 못하는 환경에서는, 엄격한 제약이 오히려 배포 지연이나 롤아웃 실패로 이어질 수 있으므로 클러스터 오토스케일링 속도와 함께 검토해야 한다.
- **기존 `PodAntiAffinity`와 병행 사용 시 상호작용을 테스트하라.** 두 메커니즘이 동시에 걸려 있으면 스케줄링 조건이 과도하게 엄격해져 어떤 노드도 조건을 만족하지 못하는 상황이 생길 수 있다.
- **클러스터의 실제 가용영역 노드 수 불균형을 함께 고려하라.** 특정 영역의 노드 수 자체가 적다면, `maxSkew`를 아무리 엄격하게 걸어도 그 영역에 물리적으로 충분한 파드를 배치할 수 없다.

## 마무리 요약

- Topology Spread Constraints는 `maxSkew`로 가용영역 등 토폴로지 도메인 간 파드 분산의 허용 오차를 숫자로 정밀하게 제어할 수 있게 해준다.
- `whenUnsatisfiable`을 `DoNotSchedule`로 두면 분산 원칙을 절대 어기지 않도록 강제할 수 있고, `ScheduleAnyway`는 배포 성공을 우선하는 유연한 정책이다.
- 영역 단위는 엄격하게, 노드 단위는 유연하게 조합하는 설정이 실무에서 가용성과 배포 안정성의 균형을 맞추는 데 자주 쓰인다.

## 참고 자료

- [Kubernetes - Pod Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
- [Kubernetes - Assigning Pods to Nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
