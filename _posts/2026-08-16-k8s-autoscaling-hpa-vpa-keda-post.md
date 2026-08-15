---
layout: single
title: "쿠버네티스 오토스케일링 완전정복 — HPA·VPA·KEDA, 언제 무엇을 조합할까"
date: 2026-08-16 12:40:00 +0530
categories: infra
tags: ["kubernetes", "hpa", "vpa", "keda", "autoscaling", "devops"]
toc: true
toc_sticky: true
excerpt: "CPU 기준 HPA 하나만 붙여놓고 오토스케일링을 끝냈다고 착각하기 쉽지만, 실제로는 HPA·VPA·KEDA가 서로 다른 축을 담당한다. 세 도구의 동작 원리 차이와 실전 조합 전략을 정리한다."
---

## 왜 지금 오토스케일링을 다시 봐야 하는가

많은 팀이 `kubectl autoscale`로 HPA 하나만 걸어두고 "오토스케일링은 끝났다"고 생각한다. 하지만 트래픽이 몰릴 때 Pod 개수는 늘어나는데 개별 Pod의 자원 배분(requests/limits)은 그대로라 여전히 스로틀링이 걸리거나, 반대로 메시지 큐에 작업이 쌓여도 CPU 사용률이 낮아 HPA가 전혀 반응하지 않는 경우를 겪어본 적이 있을 것이다. 이는 오토스케일링이 사실 서로 다른 축의 문제라는 것을 보여준다.

- **얼마나 많은 Pod를 띄울 것인가** → HPA(Horizontal Pod Autoscaler)
- **Pod 하나가 얼마만큼의 자원을 쓸 것인가** → VPA(Vertical Pod Autoscaler)
- **CPU·메모리가 아닌 다른 신호(큐 길이, 이벤트)로 스케일할 것인가** → KEDA(Kubernetes Event-Driven Autoscaling)

세 도구는 경쟁 관계가 아니라 서로 다른 문제를 푸는 보완 관계에 가깝다. 이 차이를 모르면 "오토스케일링을 붙였는데 왜 장애가 그대로냐"는 질문에 답하기 어렵다.

## 핵심 개념 1: HPA — 수평 확장의 기본기

HPA는 지정한 메트릭(기본은 CPU 사용률)이 목표치를 넘으면 Deployment의 replica 수를 늘리고, 낮아지면 줄인다. Kubernetes 표준 컨트롤러로 metrics-server만 있으면 바로 쓸 수 있고, Custom Metrics API를 붙이면 요청 수·큐 대기시간 같은 지표로도 확장할 수 있다.

핵심 제약은 **상태를 갖지 않는(stateless) 워크로드**에 적합하다는 점이다. Pod를 여러 개로 늘려도 각 Pod가 독립적으로 요청을 처리할 수 있어야 의미가 있다.

## 핵심 개념 2: VPA — 수직 확장과 자원 추천

VPA는 Pod의 실제 CPU·메모리 사용 이력을 관찰해 requests/limits 값을 자동으로 조정(또는 추천)한다. "이 Pod는 250m로 설정했지만 실제로는 늘 480m 근처를 쓴다"는 식의 과소/과대 할당 문제를 줄여준다.

다만 VPA가 값을 바꾸려면 대부분 **Pod 재시작**이 필요하다(In-place resize 기능은 Kubernetes 버전에 따라 지원 범위가 다르므로 클러스터 버전을 반드시 확인해야 한다). 그래서 트래픽이 몰리는 순간에 실시간으로 반응하는 용도보다는, 배치 잡이나 리소스 사이징을 정기적으로 최적화하는 용도에 더 잘 맞는다. HPA와 VPA를 **같은 메트릭(CPU) 기준으로 동시에** 적용하면 서로 충돌할 수 있어 공식 문서도 주의를 권고한다.

## 핵심 개념 3: KEDA — 이벤트 기반 확장과 Scale-to-Zero

KEDA는 CPU·메모리가 아닌 **외부 이벤트 소스**(메시지 큐 길이, Kafka consumer lag, 예약 큐 대기 작업 수 등)를 기준으로 스케일링을 트리거한다. 내부적으로는 HPA를 생성해 위임하는 구조이며, 다양한 시스템을 위한 Scaler를 제공한다. 가장 큰 차별점은 **Scale-to-Zero** — 유휴 상태일 때 Pod를 0개까지 줄였다가 이벤트가 들어오면 다시 띄우는 것으로, CPU 기반 HPA는 할 수 없는 동작이다.

| 도구 | 확장 축 | 트리거 | Scale-to-Zero | 대표 적합 대상 |
|---|---|---|---|---|
| HPA | 수평(Pod 개수) | CPU/메모리, 커스텀 메트릭 | 불가 | 상태 없는 웹/API 서버 |
| VPA | 수직(자원 요청량) | 사용량 이력 분석 | 해당 없음 | 배치, 단일 인스턴스 워크로드 |
| KEDA | 수평(Pod 개수) | 외부 이벤트(큐, 메시지 lag 등) | 가능 | 비동기 워커, 큐 컨슈머 |

<img src="/assets/images/posts/2026-08-16-k8s-autoscaling-hpa-vpa-keda-1.svg" alt="HPA·VPA·KEDA 동작 비교 개념도 - 수평 확장, 수직 확장, 이벤트 기반 확장의 차이" style="width:100%;">

## 예제 1: HPA 기본 설정 (YAML)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # 트래픽 급감 시 급격한 축소 방지
```

`behavior.scaleDown.stabilizationWindowSeconds`는 트래픽이 일시적으로 빠졌다가 다시 늘어나는 패턴에서 Pod를 줄였다 늘렸다 반복하는 플래핑(flapping)을 막는 데 유용하다.

## 예제 2: KEDA ScaledObject — 큐 길이 기반 확장 (YAML)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-worker-scaler
spec:
  scaleTargetRef:
    name: order-worker
  minReplicaCount: 0
  maxReplicaCount: 20
  cooldownPeriod: 60
  triggers:
    - type: rabbitmq
      metadata:
        queueName: order-queue
        mode: QueueLength
        value: "5"          # 메시지 5개당 Pod 1개 목표
```

`minReplicaCount: 0`이 KEDA의 핵심 기능이다. 큐가 비어 있으면 워커 Pod를 0개까지 줄여 유휴 비용을 없애고, 메시지가 쌓이기 시작하면 다시 Pod를 띄운다.

## 실무 포인트

- **HPA와 VPA를 같은 메트릭으로 동시에 걸지 않는다.** CPU 기준 HPA + CPU 기준 VPA를 함께 쓰면 서로의 판단이 충돌할 수 있다. VPA는 메모리처럼 HPA가 다루지 않는 자원 위주로, 또는 "추천 모드"로만 운용하는 방식이 안전하다.
- **KEDA는 결국 HPA 위에서 동작한다.** ScaledObject를 만들면 KEDA가 내부적으로 HPA 리소스를 생성하므로, 기존 HPA 운영 노하우(stabilization window, minReplicas 등)를 그대로 적용할 수 있다.
- **Scale-to-Zero는 콜드 스타트 비용과 함께 검토한다.** Pod가 0개에서 다시 뜨는 데 걸리는 시간(이미지 pull, 초기화)이 서비스 지연 요구사항과 맞는지 확인해야 한다.
- **버전별 기능 차이를 반드시 클러스터에서 재확인한다.** VPA의 In-place resize, HPA의 세부 옵션 등은 Kubernetes 배포판·버전에 따라 지원 범위가 다르므로 공식 문서와 실제 클러스터 버전을 함께 확인하는 것이 안전하다.

## 3줄 요약

- HPA는 Pod 개수(수평), VPA는 Pod당 자원량(수직), KEDA는 외부 이벤트 기반 확장(+ Scale-to-Zero)을 담당하는 서로 다른 도구다.
- KEDA는 내부적으로 HPA를 생성해 위임하는 구조이므로 기존 HPA 지식을 그대로 활용할 수 있다.
- HPA와 VPA를 같은 메트릭으로 동시에 적용하지 말고, 워크로드 특성(상태 없음/배치/이벤트 기반)에 맞게 조합하는 것이 핵심이다.

## 참고 자료

- [Kubernetes 공식 문서 — Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Kubernetes Autoscaler 프로젝트 — Vertical Pod Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [KEDA 공식 문서 — Concepts](https://keda.sh/docs/latest/concepts/)
