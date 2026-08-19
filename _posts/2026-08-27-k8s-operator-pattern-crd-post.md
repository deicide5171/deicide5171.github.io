---
layout: single
title: "쿠버네티스에게 우리 운영 지식을 가르치다 — 오퍼레이터 패턴과 CRD 설계"
date: 2026-08-27 13:40:00 +0530
categories: infra
tags: ["kubernetes", "operator", "crd", "reconcile", "controller"]
toc: true
toc_sticky: true
excerpt: "Deployment와 Service만으로는 표현 못 하는 운영 지식(백업 스케줄, 페일오버 절차)을 쿠버네티스 API 자체로 확장하는 오퍼레이터 패턴과 CRD 설계를 정리한다."
---

Postgres 클러스터를 쿠버네티스에 운영한다고 하자. Deployment, StatefulSet, Service, ConfigMap을 조합하면 배포는 되지만, "프라이머리가 죽으면 레플리카 중 하나를 승격시키고, 승격 후 나머지를 새 프라이머리에 재연결한다"는 절차는 이 기본 리소스들만으로는 표현할 수 없다. 이런 절차는 결국 사람이 수동으로 하거나 별도 스크립트로 처리하게 된다.

오퍼레이터 패턴은 이 운영 지식 자체를 쿠버네티스 API의 일부로 만든다. CRD(Custom Resource Definition)로 `PostgresCluster`라는 새로운 리소스 종류를 정의하고, 컨트롤러가 그 리소스의 "원하는 상태"와 "실제 상태"를 끊임없이 비교해 차이를 좁히는 조정(reconcile) 루프를 돌린다. 사람이 `kubectl apply -f postgres-cluster.yaml`을 실행하면, 그 뒤로는 오퍼레이터가 사람이 하던 운영 판단을 대신 수행한다.

## 핵심 개념 1: CRD + 컨트롤러 = 오퍼레이터

CRD는 쿠버네티스 API 서버에 새로운 리소스 타입을 등록하는 스키마다. 등록되고 나면 `PostgresCluster`도 `Pod`, `Deployment`처럼 `kubectl get`, `kubectl apply`로 다룰 수 있는 1급 시민이 된다. 하지만 CRD 자체는 그냥 데이터 구조일 뿐, 아무 동작도 하지 않는다. 실제 동작은 컨트롤러가 담당한다.

컨트롤러는 API 서버를 감시(watch)하다가 해당 CRD 리소스가 생성·수정·삭제될 때마다 조정 함수(reconcile function)를 실행한다. 이 함수의 역할은 단순하다. "지금 선언된 스펙(원하는 상태)"과 "클러스터의 실제 상태"를 비교해서, 차이가 있으면 그 차이를 줄이는 액션(Pod 생성, 설정 갱신, 페일오버 트리거)을 수행하는 것. 이 루프는 이벤트가 없어도 주기적으로 재실행되어(레벨 트리거 방식) 일시적 오류로 놓친 조정도 결국 수렴한다.

## 핵심 개념 2: 조정 루프 설계 원칙

| 원칙 | 이유 |
|---|---|
| 멱등성(idempotent) | 같은 조정을 여러 번 실행해도 결과가 같아야 재시도·중복 이벤트에 안전 |
| 레벨 기반, 엣지 기반 아님 | "무엇이 바뀌었는지"가 아니라 "지금 상태가 무엇인지"만 보고 판단 |
| Status 서브리소스 갱신 | 컨트롤러가 관측한 실제 상태를 `status` 필드에 기록해 사용자가 확인 가능하게 |
| Finalizer로 삭제 훅 처리 | 리소스 삭제 시 외부 자원(볼륨, DNS 레코드) 정리를 보장 |

레벨 기반 설계가 특히 중요하다. "Pod가 죽었다"는 이벤트를 놓쳐도, 다음 조정 주기에 "원하는 레플리카 수 vs 실제 레플리카 수"를 다시 비교하면 결국 올바른 상태로 수렴한다. 이벤트를 하나하나 따라가는 엣지 기반 설계는 이벤트 유실에 취약하다.

<img src="/assets/images/posts/2026-08-27-k8s-operator-pattern-crd-1.svg" alt="사용자가 CRD 스펙을 apply하면 컨트롤러가 API 서버를 감시하다 원하는 상태와 실제 상태를 비교하는 조정 루프를 돌며 차이를 줄여나가는 구조도" style="width:100%;">

## 예제: 간단한 CRD 정의와 조정 로직 스케치

```yaml
# postgrescluster-crd.yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: postgresclusters.db.example.com
spec:
  group: db.example.com
  names:
    kind: PostgresCluster
    plural: postgresclusters
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                replicas: { type: integer }
                version: { type: string }
            status:
              type: object
              properties:
                readyReplicas: { type: integer }
                primaryPod: { type: string }
      subresources:
        status: {}
```

```go
// controller.go — 조정 함수 스케치 (kubebuilder 스타일)
func (r *PostgresClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var cluster dbv1.PostgresCluster
    if err := r.Get(ctx, req.NamespacedName, &cluster); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    actualReplicas := r.countReadyPods(ctx, cluster)
    if actualReplicas < cluster.Spec.Replicas {
        r.scaleUp(ctx, cluster, cluster.Spec.Replicas-actualReplicas)
    }

    if r.primaryIsDown(ctx, cluster) {
        r.promoteReplica(ctx, cluster) // 프라이머리 페일오버 — 운영 지식이 코드로
    }

    cluster.Status.ReadyReplicas = actualReplicas
    r.Status().Update(ctx, &cluster) // 관측 상태 기록
    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil // 레벨 기반 재확인
}
```

## 실무 포인트

- **모든 애플리케이션에 오퍼레이터가 필요한 건 아니다**: 상태를 갖지 않거나 표준 Deployment/HPA로 충분한 애플리케이션까지 오퍼레이터를 만드는 것은 과잉 엔지니어링이다. 오퍼레이터는 "우리만의 운영 절차"가 명확히 있고 그걸 자동화할 가치가 클 때(스테이트풀 클러스터, 백업/복구 절차 등)에 투자할 만하다.
- **Kubebuilder/Operator SDK 같은 프레임워크로 시작한다**: CRD 스키마 생성, 클라이언트 코드 생성, RBAC 매니페스트 생성 같은 보일러플레이트를 직접 짜지 말고 표준 프레임워크에 맡긴다. 처음부터 직접 작성하면 API 서버와의 상호작용에서 미묘한 버그를 만들기 쉽다.
- **조정 함수는 반드시 타임아웃과 백오프를 갖춘다**: 외부 API 호출이나 페일오버처럼 시간이 걸리는 작업을 조정 함수 안에서 동기로 기다리게 하면 컨트롤러 전체가 멈출 수 있다. 장시간 작업은 상태 필드에 진행 단계를 기록하고 다음 조정 주기에 이어서 확인하는 식으로 비동기화해야 한다.

## 3줄 요약

- 오퍼레이터는 CRD로 도메인 특화 리소스를 정의하고, 컨트롤러가 원하는 상태와 실제 상태를 비교하는 조정 루프로 운영 지식을 자동화하는 패턴이다.
- 조정 루프는 이벤트가 아니라 현재 상태만 보고 판단하는 레벨 기반 설계여야 이벤트 유실에도 결국 올바른 상태로 수렴한다.
- 오퍼레이터는 반복되는 운영 절차가 명확할 때 투자할 가치가 있으며, 단순한 애플리케이션까지 만드는 것은 과잉 엔지니어링이다.

## 참고 자료

- [쿠버네티스 공식 문서: Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [쿠버네티스 공식 문서: Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [Kubebuilder 공식 문서](https://book.kubebuilder.io/)
