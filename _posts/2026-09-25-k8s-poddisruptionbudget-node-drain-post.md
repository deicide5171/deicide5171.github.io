---
layout: single
title: "PodDisruptionBudget과 노드 드레인 — 클러스터 유지보수 중에도 가용성 지키기"
date: 2026-09-25 12:40:00 +0530
categories: infra
tags: ["Kubernetes", "PodDisruptionBudget", "노드드레인", "무중단운영", "클러스터업그레이드"]
toc: true
toc_sticky: true
excerpt: "노드 업그레이드나 오토스케일러의 노드 축소 작업 중에 특정 서비스의 파드가 한꺼번에 종료되며 순간적으로 서비스가 끊기는 문제를, PodDisruptionBudget으로 동시 종료 가능한 파드 수를 제한해 막는 방법을 정리했다."
---

## 왜 지금 PodDisruptionBudget을 다시 봐야 하는가

쿠버네티스 클러스터를 운영하다 보면 노드 커널 패치, 컨트롤 플레인 업그레이드, 클러스터 오토스케일러의 노드 축소(scale-in)처럼 사람이나 시스템이 의도적으로 노드를 비우는 작업이 정기적으로 발생한다. 이런 작업은 `kubectl drain` 명령이나 클라우드의 관리형 업그레이드 절차를 통해 노드 위의 파드를 다른 노드로 옮기며 진행되는데, 문제는 replicas 3인 서비스의 파드 세 개가 우연히 같은 노드 두세 곳에 몰려 있다면 드레인 한 번으로 서비스 전체 인스턴스가 동시에 종료될 수 있다는 점이다. 이런 상황을 "자발적 중단(voluntary disruption)"이라 부르는데, 하드웨어 장애 같은 "비자발적 중단(involuntary disruption)"과 달리 클러스터가 미리 예측하고 통제할 수 있는 유형이다. PodDisruptionBudget(PDB)은 바로 이 자발적 중단 상황에서 "동시에 사용할 수 없는 상태가 되어도 되는 파드 수"의 상한선을 명시적으로 선언해, 드레인 절차 자체가 그 한도를 넘지 않도록 강제하는 리소스다.

## 핵심 개념 1 — minAvailable과 maxUnavailable의 차이

PDB는 두 가지 방식 중 하나로 예산을 정의한다. `minAvailable`은 "언제나 최소 이만큼은 살아있어야 한다"는 절대적/비율적 하한을, `maxUnavailable`은 "동시에 최대 이만큼까지만 죽어도 된다"는 상한을 지정한다. replicas가 고정된 Deployment라면 두 값은 사실상 서로 변환 가능하지만(예: replicas 10에 minAvailable 8 = maxUnavailable 2), HPA로 replicas가 계속 변하는 워크로드라면 `maxUnavailable`을 퍼센트(예: 25%)로 지정하는 편이 스케일 변화에 자동으로 대응해 더 안전하다. 중요한 것은 PDB 자체가 파드를 종료시키거나 재생성하지 않는다는 점이다. PDB는 오직 "누군가 자발적으로 파드를 지우려 할 때 이 예산을 넘기면 그 요청을 거부한다"는 수동적인 가드레일 역할만 한다.

## 핵심 개념 2 — Eviction API와 드레인 절차가 PDB를 만나는 지점

`kubectl drain`은 내부적으로 파드를 직접 삭제하지 않고 Eviction API를 통해 "이 파드를 축출해도 되는지" API 서버에 묻는다. API 서버는 이 요청을 받으면 해당 파드가 속한 워크로드에 걸린 PDB를 확인해, 축출을 허용했을 때 `disruptionsAllowed`(현재 예산 여유분)가 음수가 되지 않는 경우에만 축출을 승인한다. 예산이 이미 소진된 상태라면 API 서버는 오류를 반환하고, `kubectl drain`은 해당 파드를 잠시 건너뛰었다가 다른 파드가 새 노드에서 Ready 상태가 되어 예산이 회복될 때까지 재시도를 반복한다. 이 재시도 루프 덕분에 운영자는 별도 스크립트 없이도 "안전한 속도로만" 노드를 비우는 효과를 얻는다. 다만 이 메커니즘은 Eviction API를 거치는 자발적 중단에만 적용되므로, 노드가 갑자기 죽는 비자발적 중단에는 PDB가 아무런 영향을 주지 못한다는 한계를 분명히 알아야 한다.

| 항목 | minAvailable | maxUnavailable |
|---|---|---|
| 의미 | 항상 유지되어야 할 최소 가용 파드 수 | 동시에 허용되는 최대 중단 파드 수 |
| 고정 replicas | 직관적 계산 용이 | 직관적 계산 용이 |
| HPA와 함께 사용 | 절대값이면 스케일 축소 시 과도하게 제약적일 수 있음 | 퍼센트로 지정하면 스케일에 자동 비례 |
| 적용 범위 | Eviction API 경유 자발적 중단만 | Eviction API 경유 자발적 중단만 |

## 예제 — PDB 정의와 드레인 동작 확인

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-api-pdb
spec:
  maxUnavailable: 25%
  selector:
    matchLabels:
      app: payment-api
```

```bash
# 드레인 시도 — PDB 예산이 소진되면 일부 파드는 evict가 거부되고 재시도된다
kubectl drain node-3 --ignore-daemonsets --delete-emptydir-data

# 특정 워크로드의 현재 예산 여유분 확인
kubectl get pdb payment-api-pdb -o jsonpath='{.status.disruptionsAllowed}'
```

## 실무 포인트

- **replicas가 1이거나 2인 워크로드에 `maxUnavailable: 0`을 걸면 드레인 자체가 영원히 멈출 수 있다.** 예산을 0으로 두면 이론상 안전해 보이지만, 실제로는 노드 업그레이드가 그 파드 앞에서 무한정 대기하게 되므로 최소 replicas 수를 늘리거나 예산을 현실적인 값으로 조정해야 한다.
- **PDB만으로는 부족하다 — PodAntiAffinity나 Topology Spread Constraints와 함께 써야 실효성이 있다.** PDB는 "몇 개까지 죽어도 되는가"만 정하지 "애초에 같은 노드에 몰리지 않게" 막지는 못하므로, 분산 배치 정책과 조합해야 한다.
- **클라우드 관리형 노드 업그레이드(예: GKE Auto-Upgrade)도 내부적으로 Eviction API를 쓰므로 PDB의 보호를 그대로 받는다.** 관리형 서비스라고 PDB 설정을 소홀히 하면 자동 업그레이드 중 예기치 않은 서비스 중단을 겪을 수 있다.

## 마무리 요약

- PDB는 노드 드레인·클러스터 업그레이드처럼 사람이나 시스템이 의도하는 자발적 중단 상황에서, 동시에 사용 불가능해질 수 있는 파드 수의 상한을 강제하는 가드레일이다.
- Eviction API가 드레인 요청마다 PDB의 남은 예산을 확인해 승인 여부를 결정하며, 예산 소진 시 자동으로 재시도되므로 별도 스크립트 없이 안전한 속도의 드레인을 얻을 수 있다.
- PDB는 비자발적 중단(하드웨어 장애 등)에는 적용되지 않으며, Topology Spread Constraints 같은 분산 배치 정책과 함께 써야 실질적인 가용성 보호 효과를 낸다.

## 참고 자료

- [Kubernetes 공식 문서 - Disruptions](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [Kubernetes 공식 문서 - Specifying a Disruption Budget for your Application](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
