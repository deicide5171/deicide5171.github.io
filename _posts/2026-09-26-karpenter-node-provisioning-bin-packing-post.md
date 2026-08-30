---
layout: single
title: "Karpenter 노드 프로비저닝 내부 동작 — Cluster Autoscaler와 다른 즉시 빈패킹 방식"
date: 2026-09-26 13:40:00 +0530
categories: infra
tags: ["Karpenter", "쿠버네티스", "노드프로비저닝", "ClusterAutoscaler", "빈패킹"]
toc: true
toc_sticky: true
excerpt: "미리 정의한 노드 그룹 중에서만 골라 스케일링하는 Cluster Autoscaler가 파드 스케줄링 요구사항과 실제 노드 사양 사이에서 자원을 낭비하는 문제를, 파드가 필요로 하는 정확한 사양의 인스턴스를 그때그때 계산해 즉시 프로비저닝하는 Karpenter의 내부 동작으로 정리했다."
---

## 왜 지금 노드 오토스케일러를 다시 봐야 하는가

Cluster Autoscaler는 사전에 정의된 노드 그룹(Auto Scaling Group 등)의 최소·최대 대수 범위 안에서만 스케일을 조절한다. 문제는 파드가 실제로 필요로 하는 CPU·메모리 조합이 노드 그룹이 제공하는 고정된 인스턴스 타입과 정확히 맞아떨어지지 않을 때다. 예를 들어 c5.xlarge(4vCPU, 8GB) 노드 그룹만 있는데 메모리를 많이 쓰는 파드가 들어오면, 실제로는 r5.xlarge가 훨씬 효율적인데도 c5 노드를 계속 늘리며 CPU를 낭비한다. 여러 워크로드 패턴을 커버하려고 노드 그룹을 여러 개 만들면, 이번에는 각 그룹의 최소 대수만큼 유휴 자원이 상시로 떠 있게 된다. Karpenter는 이 문제를 "노드 그룹" 개념 자체를 없애고, 스케줄링 안 된 파드들의 실제 요구사항을 보고 그때그때 최적의 인스턴스 타입·수를 계산해 노드를 직접 만드는 방식으로 접근한다.

## 핵심 개념 1 — 노드 그룹 없이 스케줄링 요구사항에서 바로 프로비저닝

Karpenter는 클러스터를 계속 감시하다가 스케줄링되지 못한(Pending) 파드가 쌓이면, 그 파드들의 CPU·메모리 요청량, nodeSelector, 어피니티, 톨러레이션 조건을 종합해 "이 조건을 만족하는 가장 저렴하고 적합한 인스턴스 조합"을 클라우드 API에서 실시간으로 계산한다. 사전에 정의된 노드 그룹 목록을 순회하는 대신, `NodePool`(구 Provisioner)이라는 리소스에 "이 정도 조건이면 어떤 인스턴스 패밀리든 허용"이라는 넓은 제약만 선언해두면, Karpenter가 그 순간 스팟 가격과 가용 용량까지 고려해 최적의 구체적인 인스턴스 타입을 선택한다. 이는 노드 그룹 방식이 "미리 정해둔 메뉴 중에서 고르기"라면, Karpenter는 "필요한 사양을 그때그때 맞춤 주문"하는 것에 가깝다.

## 핵심 개념 2 — 빈패킹 최적화와 노드 통합(Consolidation)

Karpenter는 노드를 만들 때도 최적화하지만, 이미 떠 있는 노드들의 활용률이 떨어지면 재배치를 시도하는 Consolidation 기능도 핵심이다. 여러 노드에 파드가 듬성듬성 흩어져 있어 각 노드의 활용률이 낮다면, Karpenter는 그 파드들을 더 적은 수의 노드로 옮겨 담을 수 있는지 계산하고, 가능하다면 파드를 재스케줄링한 뒤 남는 노드를 종료한다. 이 과정은 빈패킹(bin packing) 문제를 지속적으로 재계산하는 것과 같으며, Cluster Autoscaler에도 비슷한 스케일다운 로직이 있지만 Karpenter는 노드 그룹 경계에 얽매이지 않고 클러스터 전체 노드를 대상으로 더 자유롭게 재배치를 고려할 수 있다는 차이가 있다.

| 항목 | Cluster Autoscaler | Karpenter |
|---|---|---|
| 노드 선택 단위 | 사전 정의된 노드 그룹(ASG) | 실시간 계산된 구체적 인스턴스 타입 |
| 확장 속도 | 노드 그룹 스케일링 API 대기 | 클라우드 API 직접 호출로 더 빠름 |
| 자원 최적화 범위 | 노드 그룹 경계 내 | 클러스터 전체 노드 대상 |
| 스팟 인스턴스 혼합 | 별도 노드 그룹 구성 필요 | NodePool 하나에서 정책적으로 혼합 |

## 코드 예제 — 스팟과 온디맨드를 혼합하는 NodePool 정의

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general-purpose
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
      nodeClassRef:
        name: default-ec2-class
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 30s
```

`capacity-type` 조건에 spot과 on-demand를 함께 허용해두면, Karpenter가 스팟 가용성과 파드의 톨러레이션 설정을 보고 그때그때 어느 쪽을 쓸지 판단한다. 인터럽트에 취약한 워크로드는 별도 NodePool에서 on-demand만 강제하면 된다.

## 실무 포인트

- **`consolidateAfter` 값이 너무 짧으면 잦은 파드 재배치로 불필요한 재시작이 늘어난다.** 워크로드의 시작 시간과 트래픽 패턴에 맞춰 여유를 두는 것이 안전하다.
- **PodDisruptionBudget을 반드시 함께 설정해야 한다.** Consolidation은 파드를 옮기기 위해 축출(evict)을 수행하므로, PDB 없이는 가용성이 중요한 서비스가 순간적으로 다운될 수 있다.
- **인스턴스 타입 제약을 지나치게 좁히면 Karpenter의 장점이 사라진다.** 특정 인스턴스 패밀리 하나로만 제한하면 사실상 노드 그룹 방식과 다를 바 없어지므로, 최소한의 제약(아키텍처, 세대 등)만 걸고 나머지는 Karpenter의 선택에 맡기는 것이 비용 효율적이다.

## 마무리 요약

- Karpenter는 사전 정의된 노드 그룹 대신, 스케줄링 안 된 파드의 실제 요구사항을 보고 그 순간 최적의 인스턴스 타입을 클라우드 API에서 실시간으로 계산해 프로비저닝한다.
- Consolidation 기능은 활용률이 낮은 노드들의 파드를 더 적은 노드로 재배치해 빈패킹 효율을 지속적으로 개선하며, 이는 노드 그룹 경계에 얽매이지 않는 클러스터 전역 최적화다.
- NodePool의 인스턴스 타입 제약은 최소한으로 열어둬야 Karpenter의 비용·효율 이점을 최대로 얻을 수 있으며, Consolidation 사용 시 PodDisruptionBudget 설정이 필수다.

## 참고 자료

- [Karpenter 공식 문서](https://karpenter.sh/docs/)
- [AWS 공식 블로그 — Karpenter 소개](https://aws.amazon.com/blogs/aws/introducing-karpenter-an-open-source-high-performance-kubernetes-cluster-autoscaler/)
