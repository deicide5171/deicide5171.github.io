---
layout: single
title: "쿠버네티스 오퍼레이터 패턴 — CRD와 컨트롤러로 운영 지식을 코드화하기"
date: 2026-09-24 12:40:00 +0530
categories: infra
tags: ["쿠버네티스", "오퍼레이터", "CRD", "컨트롤러", "K8s"]
toc: true
toc_sticky: true
excerpt: "단순 리소스 배포를 넘어 백업, 페일오버, 버전 업그레이드처럼 사람이 반복 수행하던 운영 작업을 쿠버네티스 오퍼레이터 패턴이 어떻게 코드로 자동화하는지 CRD와 컨트롤러 루프 구조부터 정리했다."
---

## 왜 지금 오퍼레이터 패턴을 다시 봐야 하는가

Deployment나 StatefulSet만으로 애플리케이션을 배포하는 단계를 지나면, 대부분의 팀은 곧 "이 상태를 유지하려면 사람이 계속 개입해야 한다"는 벽에 부딪힌다. 예를 들어 운영 중인 데이터베이스 클러스터가 리더 노드를 잃었을 때 자동으로 새 리더를 선출하고, 백업 스케줄을 관리하고, 버전 업그레이드 시 롤링 방식으로 안전하게 순서를 지켜야 하는 작업은 쿠버네티스의 기본 컨트롤러가 알지 못하는 애플리케이션 고유의 운영 지식이다.

오퍼레이터 패턴은 바로 이 지점을 메운다. 사람이 반복적으로 수행하던 운영 절차(runbook)를 쿠버네티스 API의 확장인 CRD(Custom Resource Definition)와, 그 상태를 지속적으로 감시하고 원하는 상태로 수렴시키는 컨트롤러로 코드화하는 것이다. Kubernetes 자체가 Deployment나 Service 같은 내장 리소스를 이 방식으로 관리하고 있으므로, 오퍼레이터는 이 원리를 애플리케이션 고유 도메인으로 확장한 것에 불과하다.

## 핵심 개념 1 — CRD로 도메인 개념을 API 객체로 만들기

CRD는 쿠버네티스 API 서버에 새로운 리소스 종류를 등록하는 메커니즘이다. 예를 들어 `PostgresCluster`라는 CRD를 정의하면, 사용자는 `kubectl apply -f postgres-cluster.yaml`처럼 익숙한 방식으로 데이터베이스 클러스터를 선언적으로 요청할 수 있다. CRD 자체는 스키마와 필드 정의만 담고 있을 뿐 실제 동작은 하지 않으며, 그 스펙을 실제로 실현하는 것은 별도로 배포되는 컨트롤러(오퍼레이터)의 역할이다.

## 핵심 개념 2 — 컨트롤 루프(Reconcile Loop)의 동작 원리

오퍼레이터의 핵심은 Reconcile 루프다. 컨트롤러는 감시 대상 CRD의 상태 변화를 API 서버로부터 이벤트로 전달받으면, "현재 실제 상태"와 "스펙에 선언된 원하는 상태"를 비교해 그 차이를 줄이는 작업을 수행한다. 이 루프는 한 번 실행하고 끝나는 것이 아니라 지속적으로 반복되며, 외부 요인(노드 장애, 수동 변경 등)으로 실제 상태가 어긋나더라도 스스로 다시 원하는 상태로 되돌린다는 점이 핵심이다.

| 구성 요소 | 역할 |
|---|---|
| CRD | 새로운 리소스 타입의 스키마 정의 (선언적 인터페이스) |
| Custom Resource(CR) | CRD 스키마를 따르는 실제 인스턴스 (사용자가 생성) |
| Controller | CR의 상태를 감시하고 Reconcile 루프를 실행 |
| Informer/Watch | API 서버 이벤트를 효율적으로 구독하는 캐시 계층 |

## 예제 — 최소한의 Reconcile 함수 (Go, controller-runtime 스타일)

```go
func (r *PostgresClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var cluster examplev1.PostgresCluster
    if err := r.Get(ctx, req.NamespacedName, &cluster); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 원하는 replica 수와 실제 StatefulSet의 replica 수를 비교
    var sts appsv1.StatefulSet
    err := r.Get(ctx, req.NamespacedName, &sts)
    if apierrors.IsNotFound(err) {
        return ctrl.Result{}, r.createStatefulSet(ctx, &cluster)
    }
    if *sts.Spec.Replicas != cluster.Spec.Replicas {
        sts.Spec.Replicas = &cluster.Spec.Replicas
        return ctrl.Result{}, r.Update(ctx, &sts)
    }
    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}
```

이 루프는 CR 자체가 변경될 때뿐 아니라 일정 주기(`RequeueAfter`)로도 재실행되어, 사람이 실수로 StatefulSet을 직접 수정하더라도 다시 스펙 상태로 되돌린다.

## 실무 포인트

- **직접 만들기 전에 Operator Hub나 공식 커뮤니티 오퍼레이터를 먼저 찾아라.** PostgreSQL, Kafka, Elasticsearch 같은 주요 스테이트풀 워크로드는 이미 검증된 오퍼레이터가 존재하는 경우가 많다.
- **Reconcile 함수는 반드시 멱등(idempotent)하게 작성하라.** 같은 입력으로 여러 번 실행돼도 동일한 결과를 내야 하며, 그렇지 않으면 재시도나 중복 이벤트에서 예상치 못한 부작용이 생긴다.
- **CRD 스키마 버전 관리를 처음부터 염두에 두라.** `v1alpha1`에서 `v1`으로 넘어갈 때 기존 CR을 변환하는 conversion webhook 설계를 미루면 나중에 마이그레이션 비용이 커진다.

## 마무리 요약

- 오퍼레이터 패턴은 사람이 반복 수행하던 애플리케이션 운영 지식을 CRD와 컨트롤러의 Reconcile 루프로 코드화하는 것이다.
- CRD는 선언적 API 스키마만 제공하며, 실제 상태 수렴은 컨트롤러가 지속적으로 반복하는 Reconcile 루프가 담당한다.
- 직접 오퍼레이터를 개발하기 전에 검증된 커뮤니티 오퍼레이터를 먼저 검토하고, Reconcile 함수의 멱등성과 CRD 버전 관리는 초기 설계 단계부터 고려해야 한다.

## 참고 자료

- [Kubernetes - Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Kubebuilder Book](https://book.kubebuilder.io/)
