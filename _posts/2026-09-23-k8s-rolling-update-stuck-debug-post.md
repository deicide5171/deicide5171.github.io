---
layout: single
title: "쿠버네티스 롤링 업데이트가 멈출 때 — maxUnavailable/maxSurge와 헬스체크 디버깅"
date: 2026-09-23 13:40:00 +0530
categories: infra
tags: ["쿠버네티스", "롤링업데이트", "maxsurge", "readinessprobe", "배포"]
toc: true
toc_sticky: true
excerpt: "새 이미지를 배포했는데 새 Pod는 안 뜨고 기존 Pod도 안 지워지며 Deployment가 그대로 멈춰 있을 때, RollingUpdate 전략 파라미터와 Readiness Probe 설정을 함께 진단하는 방법을 정리했다."
---

## 왜 배포가 반쯤 진행되다 멈출까

`kubectl set image`나 CI 파이프라인으로 새 버전을 배포했는데, `kubectl get pods`를 확인해보면 새 버전 Pod 몇 개는 `Pending`이나 `0/1 Running`으로 걸려 있고, 예전 버전 Pod도 그대로 남아 있는 상태로 몇 분째 진행이 안 되는 경우가 있다. 사용자 입장에서는 절반은 새 코드, 절반은 옛 코드가 트래픽을 받는 애매한 상태가 계속되는 셈이라 위험하다.

이 현상의 원인은 대부분 두 곳 중 하나다. 첫째는 **RollingUpdate 전략의 수치 설정**(`maxUnavailable`, `maxSurge`)이 새 Pod를 띄우거나 옛 Pod를 지울 수 있는 여유를 만들어주지 못하는 경우이고, 둘째는 **새 Pod가 Readiness Probe를 통과하지 못해** 쿠버네티스가 "아직 준비 안 됐다"고 판단하고 다음 단계로 넘어가지 않는 경우다.

## 핵심 개념 1 — maxUnavailable과 maxSurge가 진행 속도를 결정한다

RollingUpdate 전략에는 이 두 값이 있고, 각각 다른 방향의 여유를 만든다.

| 파라미터 | 의미 | 기본값 |
|---|---|---|
| `maxUnavailable` | 업데이트 중 동시에 내려갈 수 있는(사용 불가능한) Pod의 최대 개수/비율 | 25% |
| `maxSurge` | 원하는 replica 수보다 초과해서 추가로 띄울 수 있는 Pod의 최대 개수/비율 | 25% |

두 값이 모두 0으로 설정돼 있거나, 클러스터 리소스가 부족해 `maxSurge`만큼의 추가 Pod조차 스케줄링될 자리가 없다면 롤링 업데이트는 새 Pod를 띄울 수도, 옛 Pod를 내릴 수도 없는 교착 상태에 빠진다. 특히 리소스 제약이 빡빡한 클러스터에서 `maxSurge: 0`으로 설정해두면, 새 Pod가 뜨려면 먼저 옛 Pod가 내려가야 하는데 옛 Pod는 `maxUnavailable` 제약 때문에 아직 내려갈 수 없는 순환 대기가 생길 수 있다.

<img src="/assets/images/posts/2026-09-23-k8s-rolling-update-stuck-debug-1.svg" alt="쿠버네티스 롤링 업데이트에서 maxSurge가 추가로 띄울 수 있는 Pod 수를, maxUnavailable이 동시에 내려갈 수 있는 Pod 수를 제한하며, Readiness Probe를 통과하지 못한 Pod는 Ready로 전환되지 않아 다음 단계 진행을 막는 과정을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — Ready 상태가 안 되면 업데이트는 절대 다음 단계로 못 간다

`maxUnavailable`, `maxSurge`가 여유를 만들어줘도, 새로 뜬 Pod가 **Readiness Probe를 계속 실패**하면 쿠버네티스는 그 Pod를 여전히 "준비 안 됨"으로 취급해 옛 Pod를 내리는 다음 단계로 넘어가지 않는다. 겉으로는 배포가 멈춘 것처럼 보이지만, 실제로는 쿠버네티스가 정직하게 "새 버전이 정상 응답하지 않으니 무작정 트래픽을 넘기지 않겠다"고 판단하고 있는 정상적인 안전 동작인 경우가 많다.

## 예제 — 진단 명령과 원인 파악

```bash
# 1. Deployment의 현재 롤아웃 상태와 조건을 확인
kubectl rollout status deployment/my-app
kubectl describe deployment my-app

# 2. 새로 뜬 Pod가 왜 Ready가 안 되는지 이벤트 확인
kubectl get pods -l app=my-app
kubectl describe pod my-app-7d9f8c6b5-x2k9p

# 3. Readiness Probe 실패 로그는 describe의 Events 섹션에 찍힌다
# Warning  Unhealthy  Readiness probe failed: HTTP probe failed with statuscode: 503
```

`kubectl describe pod`의 `Events` 섹션에서 `Unhealthy` 경고가 반복해서 찍힌다면 Readiness Probe 설정 자체(경로, 포트, 초기 대기 시간)를 의심해야 한다. 애플리케이션이 실제로는 정상 기동됐지만 Probe의 `initialDelaySeconds`가 너무 짧아 아직 초기화 중인 애플리케이션에 헬스체크를 날리다 실패하는 경우가 흔하다.

```yaml
spec:
  strategy:
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    spec:
      containers:
        - name: my-app
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 20   # 애플리케이션 부팅 시간을 감안해 늘림
            periodSeconds: 5
            failureThreshold: 3
```

## 흔한 원인 체크리스트

| 원인 | 확인 방법 |
|---|---|
| 클러스터 리소스 부족으로 새 Pod 스케줄 불가 | `kubectl describe pod`에서 `Insufficient cpu/memory` 이벤트 확인 |
| Readiness Probe 경로가 애플리케이션 실제 헬스체크 경로와 다름 | 컨테이너 내부에서 curl로 직접 경로 테스트 |
| initialDelaySeconds가 애플리케이션 부팅 시간보다 짧음 | 애플리케이션 로그의 "Started ... in Ns" 시간과 비교 |
| 새 이미지 자체가 크래시 루프에 빠짐(CrashLoopBackOff) | `kubectl logs <pod> --previous`로 직전 종료 로그 확인 |
| ConfigMap/Secret 참조가 새 버전에서 깨짐 | Pod describe의 Events에서 마운트 실패 여부 확인 |

## 실무 포인트

- **Deployment 히스토리를 활용해 신속히 롤백할 준비를 항상 해둬라.** `kubectl rollout undo deployment/my-app`으로 즉시 이전 버전으로 되돌릴 수 있으므로, 원인 조사를 하는 동안 서비스 영향을 줄이기 위해 일단 롤백부터 하는 판단도 필요하다.
- **Liveness Probe와 Readiness Probe를 혼동하지 마라.** Liveness가 실패하면 컨테이너가 재시작되고, Readiness가 실패하면 트래픽만 안 가고 컨테이너는 그대로 유지된다. 롤링 업데이트가 멈춘 상황에서는 대개 Readiness가 원인이다.
- **progressDeadlineSeconds를 설정해두면 무한정 멈춰있지 않게 할 수 있다.** 이 시간 안에 롤아웃이 끝나지 않으면 Deployment 상태가 실패로 표시돼 알림 시스템과 연동해 조기에 알아챌 수 있다.

## 마무리 요약

- 롤링 업데이트가 멈추는 원인은 대부분 maxUnavailable/maxSurge가 만드는 여유 부족, 또는 새 Pod가 Readiness Probe를 통과하지 못하는 두 가지 중 하나다.
- Readiness Probe 실패는 배포 실패가 아니라 쿠버네티스가 준비 안 된 Pod에 트래픽을 넘기지 않는 정상적인 안전 동작인 경우가 많으므로 애플리케이션 부팅 시간과 Probe 설정을 먼저 비교해야 한다.
- progressDeadlineSeconds와 즉시 롤백 명령을 미리 익혀두면 원인 조사와 서비스 영향 최소화를 동시에 진행할 수 있다.

## 참고 자료

- [Kubernetes 공식 문서 - Deployment RollingUpdate](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)
- [Kubernetes 공식 문서 - Configure Liveness, Readiness Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
