---
layout: single
title: "쿠버네티스 Pod가 Pending에서 안 넘어갈 때 체크리스트"
date: 2026-08-31 13:40:00 +0530
categories: infra
tags: ["kubernetes", "pod pending", "트러블슈팅", "스케줄링", "디버깅"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스 Pod가 Pending 상태에서 멈춰 있을 때, 스케줄러 관점에서 원인을 순서대로 좁혀가는 체크리스트."
---

## 왜 Pending은 원인이 안 보이는가

`Running`이나 `CrashLoopBackOff`는 최소한 컨테이너가 뜨긴 떴다는 신호지만, `Pending`은 아예 노드에 배치조차 안 됐다는 뜻이라 로그를 볼 컨테이너 자체가 없다. 결국 스케줄러가 왜 이 Pod를 어떤 노드에도 못 올렸는지를 `describe`의 Events에서 찾아야 한다.

## Pending의 흔한 원인 4가지

| 원인 | Events에 뜨는 메시지 예시 | 해결 |
|---|---|---|
| 리소스 부족 | `Insufficient cpu` / `Insufficient memory` | 노드 추가(오토스케일러) 또는 요청량 축소 |
| PVC 바인딩 실패 | `pod has unbound immediate PersistentVolumeClaims` | StorageClass·PV 상태 확인 |
| 노드 셀렉터/어피니티 불일치 | `didn't match Pod's node affinity/selector` | 라벨·톨러레이션 확인 |
| 이미지 풀 실패로 착각 | (사실은 Pending이 아니라 ImagePullBackOff) | 별개 문제이므로 구분 필요 |

## 진단 순서

```bash
# 1. 이벤트 확인 — 여기에 사실상 답이 다 있다
kubectl describe pod <pod-name> | grep -A 20 Events

# 2. 클러스터 전체 리소스 여유 확인
kubectl top nodes
kubectl describe nodes | grep -A 5 "Allocated resources"

# 3. PVC 상태 확인 (스토리지 문제인 경우)
kubectl get pvc

# 4. 노드 셀렉터·어피니티·톨러레이션 확인
kubectl get pod <pod-name> -o yaml | grep -A 10 affinity
kubectl get nodes --show-labels
```

`Events` 섹션에 `0/5 nodes are available: 3 Insufficient cpu, 2 node(s) had taint...`처럼 노드별로 왜 후보에서 제외됐는지가 구체적으로 나온다. 이 메시지를 그대로 읽는 것이 가장 빠른 진단 방법이다.

## 실무 포인트

- **리소스 요청(`requests`)을 실제 사용량보다 과도하게 크게 잡으면, 클러스터 자원이 남아 있어도 스케줄링이 안 된다.** 실제 사용량 프로파일링 후 요청값을 현실적으로 조정해야 한다.
- **오토스케일러(Cluster Autoscaler)가 있어도 즉시 노드가 늘지 않는다.** 새 노드 프로비저닝에는 보통 1~3분이 걸리므로, 트래픽 급증 직후 잠깐의 Pending은 정상일 수 있다.
- **PVC가 특정 존(zone)의 PV에 묶여 있는데 Pod는 다른 존에 스케줄링하려 하면 영원히 Pending이다.** 스토리지와 컴퓨트의 존을 맞추는 것이 멀티 AZ 클러스터에서 자주 놓치는 부분이다.

## 마무리 요약

- Pending은 스케줄러가 Pod를 배치할 노드를 못 찾았다는 뜻이므로 `describe`의 Events부터 확인해야 한다.
- 리소스 부족, PVC 바인딩 실패, 노드 어피니티 불일치가 3대 원인이다.
- requests 값을 과도하게 크게 설정하는 것 자체가 스케줄링 실패의 흔한 원인이라는 점을 기억한다.

## 참고 자료

- [Kubernetes 공식 문서 - Pod 스케줄링](https://kubernetes.io/docs/concepts/scheduling-eviction/)
- [Kubernetes 공식 문서 - 리소스 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
