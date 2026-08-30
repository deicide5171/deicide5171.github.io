---
layout: single
title: "Kubernetes Operator 내부 동작 — Reconcile Loop는 왜 이벤트가 아니라 상태를 본다"
date: 2026-09-27 13:40:00 +0530
categories: infra
tags: ["KubernetesOperator", "CRD", "ReconcileLoop", "컨트롤러패턴", "controller-runtime"]
toc: true
toc_sticky: true
excerpt: "Operator가 클러스터 상태를 원하는 대로 유지하는 방식은 이벤트를 하나씩 처리하는 것이 아니라, 이벤트를 트리거로만 쓰고 매번 현재 상태 전체를 원하는 상태와 다시 비교하는 레벨 트리거링(level-triggered) 설계에 있다."
---

## 왜 Operator를 이벤트 핸들러로 오해하면 안 되는가

Kubernetes Operator를 처음 만들 때 흔히 하는 실수는 이를 "리소스 변경 이벤트를 받아서 처리하는 핸들러"로 설계하는 것이다. 예를 들어 "파드가 생성됨" 이벤트를 받으면 A 작업을, "파드가 삭제됨" 이벤트를 받으면 B 작업을 하는 식이다. 이 방식은 이벤트를 하나라도 놓치면(네트워크 단절, 컨트롤러 재시작, watch 스트림 끊김) 시스템 상태가 영원히 어긋난 채로 남는다는 근본적인 약점이 있다. Kubernetes의 모든 내장 컨트롤러(Deployment, ReplicaSet 등)와 잘 설계된 Operator는 이 문제를 다른 패러다임으로 피해간다. 바로 **엣지 트리거링이 아니라 레벨 트리거링**이다.

## 핵심 개념 1 — 레벨 트리거링: 이벤트는 신호일 뿐, 진실은 항상 다시 읽는다

레벨 트리거링에서 이벤트(리소스 생성·수정·삭제, 재동기화 타이머)는 "무언가 바뀌었을 수도 있으니 다시 확인하라"는 신호일 뿐이며, 실제 로직은 그 이벤트의 내용을 신뢰하지 않는다. Reconcile 함수가 호출되면 항상 **현재 클러스터의 실제 상태(observed state)를 API 서버에서 새로 조회**하고, 이를 CRD(Custom Resource Definition)에 선언된 **원하는 상태(desired state)**와 비교해서 그 차이를 줄이는 동작을 수행한다. 이벤트가 100번 연속으로 오든, 중간에 몇 개를 놓치든 상관없다. 다음 reconcile 호출에서 다시 현재 상태를 읽고 desired state와 비교하기 때문에, 결과적으로 항상 같은 최종 상태로 수렴한다. 이것이 멱등성(idempotency)이 Operator 설계의 제1원칙인 이유다.

## 핵심 개념 2 — Informer, Work Queue, Reconcile의 3단 구조

controller-runtime(Operator SDK, Kubebuilder의 기반) 아키텍처는 세 계층으로 나뉜다. **Informer**는 API 서버에 watch 커넥션을 열고 리소스 변경을 로컬 캐시에 반영하면서, 변경이 감지되면 해당 리소스의 키(namespace/name)를 **Work Queue**에 넣는다. Work Queue는 같은 키가 짧은 시간에 여러 번 들어와도 중복 제거(dedup)하고, 처리 중 실패하면 지수 백오프로 재큐잉한다. 마지막으로 워커가 큐에서 키를 꺼내 **Reconcile(ctx, key)** 함수를 호출하는데, 이 함수는 이벤트의 세부 내용이 아니라 키만 받는다. 그래서 Reconcile 함수 내부에서는 반드시 API 서버(또는 로컬 캐시)에서 해당 리소스를 다시 `Get`해야 하며, 이벤트 페이로드에 의존할 수 없는 구조로 강제된다.

| 구성 요소 | 역할 |
|---|---|
| Informer | API 서버 watch, 로컬 캐시 유지, 변경 감지 시 큐에 키 추가 |
| Work Queue | 중복 제거, 실패 시 지수 백오프 재시도, rate limiting |
| Reconciler | 키로 현재 상태를 다시 조회하고 desired state와 비교해 수렴 동작 실행 |
| Periodic Resync | 이벤트 누락에 대비해 일정 주기로 전체 재조정 강제 실행 |

## 코드 예제 — controller-runtime 기반 Reconcile 함수 골격

```go
func (r *AppReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var app appsv1.MyApp
    if err := r.Get(ctx, req.NamespacedName, &app); err != nil {
        // 리소스가 이미 삭제됐다면 별도 처리 없이 정상 종료
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 현재 상태 조회: 이 앱에 해당하는 Deployment가 실제로 존재하는가
    var deploy appsv1.Deployment
    err := r.Get(ctx, types.NamespacedName{Name: app.Name, Namespace: app.Namespace}, &deploy)
    if errors.IsNotFound(err) {
        // desired state(스펙에 정의된 replica 수 등)에 맞춰 새로 생성
        return ctrl.Result{}, r.Create(ctx, buildDeployment(&app))
    }

    // 이미 존재한다면 replica 수가 스펙과 다른지 비교 후 필요할 때만 업데이트
    if *deploy.Spec.Replicas != app.Spec.Replicas {
        deploy.Spec.Replicas = &app.Spec.Replicas
        return ctrl.Result{}, r.Update(ctx, &deploy)
    }

    // 30초 후 재확인을 요청해 이벤트 누락에 대비한 안전망을 둔다
    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}
```

## 실무 포인트

- **Reconcile은 여러 번 호출돼도 안전해야 한다.** 같은 입력으로 몇 번을 실행해도 같은 결과가 나오는 멱등성을 지키지 않으면, 재시도나 재동기화 시 리소스를 중복 생성하거나 상태를 어긋나게 만든다.
- **외부 API 호출은 반드시 타임아웃과 재시도 한계를 두라.** Reconcile 안에서 클라우드 API 같은 외부 시스템을 호출할 때 무한정 블로킹되면 Work Queue의 워커가 고갈되어 다른 리소스의 reconcile까지 지연된다.
- **`RequeueAfter`로 주기적 재확인을 명시적으로 설계하라.** watch 이벤트만 믿지 말고, 외부 상태(예: 클라우드 로드밸런서의 헬스체크 결과)처럼 Kubernetes API가 감지할 수 없는 변화는 주기적 재확인으로 보완해야 한다.

## 마무리 요약

- Operator는 이벤트를 처리 대상이 아니라 재조정 신호로만 쓰고, 매번 현재 상태를 다시 읽어 desired state와 비교하는 레벨 트리거링으로 이벤트 누락에도 강건하다.
- Informer-Work Queue-Reconciler의 3단 구조가 이 패턴을 표준화하며, Reconcile 함수는 키만 받고 항상 최신 상태를 재조회하도록 강제된다.
- 멱등성, 타임아웃 관리, 주기적 재확인(RequeueAfter)이 실무에서 안정적인 Operator를 만드는 핵심 원칙이다.

## 참고 자료

- [Kubernetes 공식 문서 — Operator 패턴](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Kubebuilder Book](https://book.kubebuilder.io/)
- [controller-runtime 공식 저장소](https://github.com/kubernetes-sigs/controller-runtime)
