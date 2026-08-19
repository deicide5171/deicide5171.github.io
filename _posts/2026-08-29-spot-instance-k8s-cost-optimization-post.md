---
layout: single
title: "언제 뺏길지 모르는 서버로 클러스터 비용 줄이기 — 쿠버네티스 스팟 인스턴스 실전"
date: 2026-08-29 12:40:00 +0530
categories: infra
tags: ["kubernetes", "spot-instance", "cost-optimization", "karpenter", "autoscaling", "devops"]
toc: true
toc_sticky: true
excerpt: "온디맨드 대비 최대 90% 저렴하지만 언제든 회수될 수 있는 스팟 인스턴스를 쿠버네티스 워커 노드로 안전하게 쓰는 노드 그룹 분리, 회수 대응, 오토스케일러 전략을 정리한다."
---

클라우드 비용 청구서에서 컴퓨트가 차지하는 비중이 커지면 누구나 스팟 인스턴스(AWS Spot, GCP Preemptible/Spot VM, Azure Spot)를 검토한다. 온디맨드 대비 60~90% 저렴하다는 숫자는 매력적이지만, "클라우드 제공자가 그 용량이 필요해지면 몇 분의 경고만 주고 회수해간다"는 조건이 붙는다. 이 조건을 무시하고 스팟 인스턴스를 스테이트풀 워크로드나 회수 대응 없는 노드 그룹에 그대로 붙이면, 비용은 줄지만 장애 빈도가 늘어나는 결과로 이어지기 쉽다.

쿠버네티스는 이 문제에 비교적 잘 맞는 실행 환경이다. 파드가 재스케줄링 가능한 단위로 설계돼 있고, 오토스케일러가 노드 회수를 감지해 다른 노드로 파드를 옮길 수 있기 때문이다. 다만 "그냥 스팟으로 바꾸면 된다"가 아니라, 노드 그룹 분리·회수 신호 처리·워크로드 배치 정책을 함께 설계해야 실제로 비용과 안정성을 둘 다 잡을 수 있다.

## 핵심 개념 1: 스팟 회수는 예고 없는 장애가 아니라 예고 있는 이벤트다

스팟 인스턴스가 회수될 때 클라우드는 보통 2분(AWS) 안팎의 사전 종료 알림을 인스턴스 메타데이터로 제공한다. 이 신호를 감지해 파드를 정상 종료(graceful shutdown)하고 워크로드를 다른 노드로 옮길 시간을 버는 컴포넌트가 필요한데, 대표적으로 AWS Node Termination Handler나 Karpenter의 내장 인터럽션 처리가 이 역할을 한다. 이 컴포넌트는 종료 알림을 받으면 해당 노드에 `cordon`(신규 스케줄 차단)과 `drain`(기존 파드를 다른 노드로 축출)을 수행해, 애플리케이션이 SIGTERM을 받고 정상 종료할 시간을 확보한다.

여기서 핵심은 애플리케이션 자체가 SIGTERM을 받았을 때 진행 중인 요청을 마무리하고 종료하는 그레이스풀 셧다운 로직을 갖추고 있어야 한다는 것이다. `terminationGracePeriodSeconds`를 늘려놔도 애플리케이션이 SIGTERM을 무시하면 강제 종료(SIGKILL)까지 이어지는 시간만 낭비하는 셈이다.

## 핵심 개념 2: 노드 그룹 분리 — 스팟과 온디맨드를 함께 쓰는 법

실무에서는 클러스터 전체를 스팟으로 채우지 않는다. 대신 워크로드 성격에 따라 노드 그룹(노드 풀)을 분리한다.

- **온디맨드 전용 그룹**: 상태를 가진 워크로드(DB, 메시지 큐, 코어 컨트롤 플레인 애드온), 회수에 민감한 시스템 파드
- **스팟 전용 그룹**: 상태 없는(stateless) 워크로드, 배치 작업, 여러 레플리카로 중복 실행되는 API 서버
- **혼합 그룹(스팟 우선 + 온디맨드 폴백)**: 스팟 용량이 부족할 때 온디맨드로 자동 대체

쿠버네티스의 `nodeSelector`/`taint-toleration`과 토폴로지 분산 제약(topology spread constraints)을 조합해, 같은 디플로이먼트의 레플리카가 스팟 노드 하나에 몰리지 않도록 여러 노드·가용영역에 분산시키는 것이 중요하다. 스팟 노드 하나가 회수돼도 나머지 레플리카가 서비스를 유지할 수 있어야 진짜 무중단이 된다.

<img src="/assets/images/posts/2026-08-29-spot-instance-k8s-cost-optimization-1.svg" alt="온디맨드 노드 그룹과 스팟 노드 그룹으로 분리하고, 스팟 회수 신호가 오면 cordon과 drain을 거쳐 파드가 다른 노드로 재스케줄링되는 흐름" style="width:100%;">

## 핵심 개념 3: 오토스케일러와 다중 인스턴스 타입 전략

스팟 용량은 인스턴스 타입·가용영역별로 회수 확률이 다르다. 특정 인스턴스 타입 하나에만 의존하면 그 타입의 용량이 줄어드는 순간 클러스터 전체가 흔들릴 수 있으므로, 유사한 스펙(vCPU·메모리)의 인스턴스 타입을 여러 개 후보로 묶어 오토스케일러가 그때그때 여유 있는 타입을 선택하게 하는 것이 표준 패턴이다. Karpenter는 이런 다중 인스턴스 타입 provisioning을 선언적으로 지원하며, 클러스터 오토스케일러(CA)의 Auto Scaling Group 기반 방식보다 스팟 다양화·빠른 스케일업에 유리하다고 평가받는다.

| 구분 | 온디맨드 | 스팟 |
|---|---|---|
| 가격 | 기준가 | 최대 60~90% 할인 |
| 회수 가능성 | 없음(정책적 종료 제외) | 용량 부족 시 언제든 회수 |
| 사전 알림 | 해당 없음 | 통상 2분 안팎 |
| 적합 워크로드 | 상태 저장, 지연 민감 | 상태 없음, 배치, 다중 레플리카 |
| 필수 구성 | - | 회수 핸들러 + 노드 그룹 분리 + 다중 인스턴스 타입 |

## 예제: Karpenter NodePool로 스팟 우선 + 온디맨드 폴백 구성

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: spot-preferred
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]   # 스팟 우선, 부족하면 온디맨드로 폴백
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["m6i.large", "m6a.large", "m5.large", "m6i.xlarge"]  # 유사 스펙 다중 후보
      taints:
        - key: spot-workload
          effect: NoSchedule
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    expireAfter: 720h

---
# 스팟에 배치 가능한 워크로드만 이 taint를 toleration으로 허용
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stateless-api
spec:
  template:
    spec:
      tolerations:
        - key: spot-workload
          operator: Exists
          effect: NoSchedule
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels: { app: stateless-api }
      terminationGracePeriodSeconds: 30
```

## 실무 포인트

- **PodDisruptionBudget을 반드시 설정한다**: 스팟 회수로 인한 drain과 배포로 인한 롤링 업데이트가 겹치면 순간적으로 가용 레플리카가 급감할 수 있다. `minAvailable`을 지정해 동시 축출 가능한 파드 수를 제한해야 한다.
- **회수율은 인스턴스 타입·리전마다 다르다**: 특정 세대나 특이 스펙(대용량 메모리, GPU)의 인스턴스는 회수율이 높은 경향이 있다. 클라우드 제공자가 공개하는 스팟 배치 점수·회수 이력 데이터를 참고해 인스턴스 후보군을 정기적으로 재검토한다.
- **비용 절감 폭과 SLA를 함께 추적한다**: 스팟 도입 후 실제 비용 절감률과 함께 회수로 인한 재스케줄링 빈도, p99 지연 변화도 대시보드로 같이 봐야 한다. 비용만 보고 판단하면 안정성 저하를 늦게 발견한다.

## 3줄 요약

- 스팟 인스턴스는 온디맨드 대비 대폭 저렴하지만 예고 있는(통상 2분) 회수가 언제든 발생할 수 있어, 회수 핸들러로 cordon·drain을 자동화하는 것이 전제 조건이다.
- 상태 없는 워크로드는 스팟 노드 그룹으로, 상태 저장·회수 민감 워크로드는 온디맨드 노드 그룹으로 분리하고 토폴로지 분산으로 레플리카를 여러 노드에 흩어야 한다.
- Karpenter 같은 오토스케일러로 유사 스펙의 다중 인스턴스 타입을 후보군으로 묶어 특정 타입의 용량 부족에 대한 의존도를 낮추는 것이 실무 표준 패턴이다.

## 참고 자료

- [AWS 공식 문서: EC2 Spot 인스턴스 인터럽션](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [Karpenter 공식 문서: NodePool 및 Disruption](https://karpenter.sh/docs/concepts/disruption/)
- [쿠버네티스 공식 문서: Pod Disruption Budget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- [쿠버네티스 공식 문서: Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
