---
layout: single
title: "네임스페이스만으로는 부족하다 — 쿠버네티스 멀티테넌시 격리 실전"
date: 2026-08-25 13:40:00 +0530
categories: infra
tags: ["kubernetes", "multi-tenancy", "namespace", "network-policy", "resource-quota", "isolation"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스 네임스페이스를 나눈다고 팀 간 격리가 저절로 되는 것은 아니다. NetworkPolicy, ResourceQuota, RBAC를 함께 설계해야 완성되는 소프트 멀티테넌시의 구조를 정리한다."
---

여러 팀이 하나의 쿠버네티스 클러스터를 공유할 때 가장 먼저 하는 일은 팀별로 네임스페이스를 나누는 것이다. 그런데 네임스페이스는 기본적으로 **이름 충돌을 막는 논리적 구분**일 뿐, 그 자체로 네트워크 트래픽을 막거나 자원 사용을 제한하지 않는다. 네임스페이스 A의 파드가 네임스페이스 B의 서비스에 기본적으로 접근할 수 있고, 한 팀의 배치 작업이 노드의 CPU를 독점해 다른 팀의 서비스가 리소스 부족으로 죽는 일도 네임스페이스만으로는 막히지 않는다.

쿠버네티스가 제공하는 멀티테넌시는 흔히 "소프트 멀티테넌시(soft multi-tenancy)"라 불린다. 커널 수준 격리를 제공하는 가상머신 기반 멀티테넌시(하드 멀티테넌시)와 달리, 네임스페이스·RBAC·NetworkPolicy·ResourceQuota 같은 여러 리소스를 조합해서 논리적 격리를 만들어야 한다. 이 글에서는 네임스페이스 분리 이후 실제로 필요한 격리 계층들을 정리한다.

## 핵심 개념 1: 네임스페이스가 격리하는 것과 하지 않는 것

| 항목 | 네임스페이스만으로 격리됨 | 별도 설정 필요 |
|---|---|---|
| 리소스 이름 충돌 방지 | O | - |
| RBAC 권한 범위 | O(Role/RoleBinding 기준) | - |
| 네트워크 트래픽 격리 | X | NetworkPolicy |
| CPU/메모리 사용량 제한 | X | ResourceQuota, LimitRange |
| 파드 보안 설정 제약 | X | Pod Security Admission |
| 노드 레벨 격리 | X | 노드 어피니티/테인트, 별도 노드 풀 |

네임스페이스는 "누가 무엇을 볼 수 있는가"의 API 서버 관점 경계는 제공하지만, "실제 트래픽이 어디로 흐를 수 있는가"나 "얼마나 많은 자원을 쓸 수 있는가"는 전혀 다른 리소스가 담당한다. 이 차이를 모르고 네임스페이스만 나눈 채로 "격리했다"고 여기는 것이 실무에서 가장 흔한 오해다.

## 핵심 개념 2: NetworkPolicy — 기본은 전부 허용

쿠버네티스의 기본 네트워크 모델은 클러스터 내 모든 파드가 서로 통신 가능한 **flat network**다. NetworkPolicy 리소스를 하나도 만들지 않으면 네임스페이스를 아무리 나눠도 모든 파드가 서로에게 자유롭게 접근할 수 있다. NetworkPolicy는 CNI 플러그인(Calico, Cilium 등)이 실제로 이를 강제해야 동작하며, CNI가 NetworkPolicy를 지원하지 않으면 정책을 만들어도 아무 효과가 없다는 점을 먼저 확인해야 한다.

실무에서 권장되는 패턴은 **기본 거부(default-deny)**를 먼저 깔고, 필요한 통신만 명시적으로 허용하는 것이다. 네임스페이스마다 "이 네임스페이스로 들어오는 모든 트래픽을 기본 차단"하는 정책을 먼저 적용한 뒤, 실제로 필요한 서비스 간 통신만 selector로 열어주는 화이트리스트 방식이 안전하다.

## 핵심 개념 3: ResourceQuota와 LimitRange로 자원 경합 방지

네트워크가 격리돼도 한 네임스페이스의 워크로드가 노드의 CPU·메모리를 과도하게 점유하면 같은 노드에 스케줄된 다른 팀의 파드가 자원 부족을 겪는다(이른바 "noisy neighbor" 문제). `ResourceQuota`는 네임스페이스 단위로 전체 CPU/메모리/파드 개수의 상한을 걸고, `LimitRange`는 그 네임스페이스 안에서 개별 컨테이너가 요청/제한값을 반드시 명시하도록 강제하거나 기본값을 지정한다.

이 둘을 함께 쓰지 않으면 허점이 생긴다. ResourceQuota만 걸면 팀이 개별 파드에 과도하게 큰 리소스를 요청해 몇 개 파드만으로 quota를 소진할 수 있고, LimitRange만 걸면 파드 개수 자체가 무한정 늘어나는 것을 막지 못한다.

## 예제: 네임스페이스 단위 기본 거부 NetworkPolicy와 쿼터

```yaml
# 1) 네임스페이스로 들어오는 모든 트래픽 기본 차단
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: team-a
spec:
  podSelector: {}
  policyTypes:
    - Ingress

---
# 2) 같은 네임스페이스 안의 파드 간 통신만 명시적으로 허용
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-intra-namespace
  namespace: team-a
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}

---
# 3) 네임스페이스 단위 리소스 상한
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "100"

---
# 4) 개별 컨테이너의 요청/제한값 기본값과 상한
apiVersion: v1
kind: LimitRange
metadata:
  name: team-a-limits
  namespace: team-a
spec:
  limits:
    - type: Container
      default:
        cpu: "500m"
        memory: 512Mi
      defaultRequest:
        cpu: "250m"
        memory: 256Mi
      max:
        cpu: "4"
        memory: 8Gi
```

## 실무 포인트

- **CNI가 NetworkPolicy를 실제로 지원하는지 먼저 확인한다**: 일부 관리형 쿠버네티스 서비스는 기본 CNI가 NetworkPolicy를 강제하지 않는 경우가 있다. 정책을 배포했는데 아무 효과가 없다면 CNI 설정부터 점검해야 한다.
- **노이즈 네이버 문제는 네임스페이스만으로 완전히 막을 수 없다**: 팀 간 자원 격리를 더 엄격히 하려면 노드 풀 자체를 팀별로 분리하거나(taint/toleration), 별도 클러스터로 나누는 하드 멀티테넌시를 고려해야 한다. ResourceQuota는 스케줄링 결과까지 통제하지는 못한다.
- **Pod Security Admission으로 컨테이너 권한도 함께 통제한다**: 네트워크와 자원을 격리해도 특정 네임스페이스의 파드가 privileged 모드나 호스트 네트워크 접근 권한을 갖도록 허용돼 있으면 격리가 우회될 수 있다. 네임스페이스 라벨로 `enforce=restricted` 수준의 Pod Security Standard를 적용하는 것이 기본이어야 한다.

## 3줄 요약

- 쿠버네티스 네임스페이스는 이름과 API 권한 범위를 나눌 뿐, 네트워크 트래픽과 자원 사용량은 저절로 격리하지 않는다.
- NetworkPolicy는 CNI가 지원해야 동작하며, 기본 거부 후 화이트리스트로 여는 패턴이 안전하고, ResourceQuota와 LimitRange는 함께 써야 자원 경합의 허점이 사라진다.
- 더 엄격한 팀 간 격리가 필요하다면 노드 풀 분리나 별도 클러스터 같은 하드 멀티테넌시로 넘어가는 것을 고려해야 한다.

## 참고 자료

- [Kubernetes 공식 문서: Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes 공식 문서: Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes 공식 문서: Multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/)
