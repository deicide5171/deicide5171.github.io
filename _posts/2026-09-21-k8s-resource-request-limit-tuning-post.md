---
layout: single
title: "쿠버네티스 Pod가 자꾸 재시작될 때 — Request/Limit과 OOMKilled 진단하기"
date: 2026-09-21 12:40:00 +0530
categories: infra
tags: ["kubernetes", "oomkilled", "리소스설정", "cgroup", "쿠버네티스트러블슈팅"]
toc: true
toc_sticky: true
excerpt: "Pod가 이유 없이 재시작되고 kubectl describe에 OOMKilled가 찍힐 때, requests/limits 설정이 어떻게 문제를 일으키는지 원인별로 정리했다."
---

## 왜 지금 이 문제를 다뤄야 하나

운영 중인 서비스에서 어느 날 갑자기 특정 Pod만 계속 재시작을 반복한다. `kubectl get pods`에 `RESTARTS` 숫자가 계속 올라가고, `kubectl describe pod`로 들여다보면 `Last State: Terminated, Reason: OOMKilled`가 찍혀 있다. 애플리케이션 로그에는 특별한 에러가 없는데도 프로세스가 죽는다. 이건 애플리케이션 버그가 아니라 대부분 쿠버네티스의 `resources.requests`/`resources.limits` 설정과 리눅스 cgroup 메모리 제한이 부딪히는 문제다.

문제는 이 설정이 "숫자만 크게 넣으면 안전하다"는 식으로 다뤄지기 쉽다는 점이다. requests와 limits는 각각 다른 시점에, 다른 방식으로 스케줄러와 커널에 작동하기 때문에 개념을 정확히 모르면 값을 아무리 조정해도 같은 문제가 반복된다.

## requests와 limits는 서로 다른 일을 한다

| 항목 | 언제 작동하나 | 무슨 일을 하나 |
|---|---|---|
| requests | Pod 스케줄링 시점 | 노드에 이 정도 자원은 확보되어 있어야 배치 가능 |
| limits (CPU) | 실행 중 상시 | 이 값을 넘는 CPU 사용은 스로틀링(느려짐)만 발생 |
| limits (메모리) | 실행 중 상시 | 이 값을 넘는 메모리 사용은 즉시 프로세스 강제 종료(OOMKilled) |

여기서 가장 자주 오해하는 지점이 CPU와 메모리 limit의 성격 차이다. **CPU limit을 초과하면 그냥 느려질 뿐 죽지 않는다.** 반면 **메모리 limit을 초과하면 커널 OOM killer가 즉시 프로세스를 죽인다.** 이 차이를 모르고 메모리 limit도 CPU처럼 "여유 있게 크게" 잡거나, 반대로 "빡빡하게" 잡으면 트러블슈팅 방향이 완전히 엇나간다.

## 잘못된 접근과 그 결과

가장 흔한 실수는 limits를 아예 설정하지 않거나, requests와 limits를 똑같은 값으로 맞추는 것이다. limits를 설정하지 않으면 한 Pod가 메모리를 무한정 늘려 노드 전체의 다른 Pod까지 함께 OOMKilled 시키는 "이웃 사고(noisy neighbor)"가 발생한다.

반대로 QoS를 `Guaranteed`로 만들겠다고 requests와 limits를 완전히 동일하게 맞추는 경우도 있는데, JVM처럼 시작 시점과 GC 시점에 메모리 사용량이 크게 출렁이는 애플리케이션에서는 평상시 사용량 기준으로 값을 잡으면 GC 직전 순간의 스파이크에서 바로 OOMKilled가 난다. 힙 크기(`-Xmx`)를 컨테이너 메모리 limit보다 여유 있게 낮춰 잡지 않으면, JVM 자체는 살아있다고 착각해도 컨테이너 레벨에서 먼저 죽는다.

## 올바른 접근

```yaml
resources:
  requests:
    cpu: "250m"
    memory: "512Mi"
  limits:
    cpu: "1000m"
    memory: "768Mi"
```

이렇게 requests보다 limits를 여유 있게(보통 1.5~2배) 잡아 버스트를 흡수하면서도, 무한정 늘어나지 않게 상한을 둔다. 자바 애플리케이션이라면 `-XX:MaxRAMPercentage=70.0` 같은 옵션으로 힙을 컨테이너 limit의 일정 비율로 자동 계산하게 하면, limit 값을 바꿔도 힙 크기가 같이 조정돼 유지보수가 쉬워진다.

실제 사용량을 모른 채 값을 추측하지 말고, `kubectl top pod`나 Prometheus의 `container_memory_working_set_bytes` 지표로 최소 1~2주간의 실제 사용 패턴(특히 피크 시점)을 관찰한 뒤 값을 정하는 것이 정석이다.

## 실무 포인트

- **OOMKilled와 CrashLoopBackOff를 구분하라.** OOMKilled는 메모리 초과가 원인, CrashLoopBackOff는 그 결과로 반복 재시작하는 상태 표시일 뿐이다. `describe pod`의 `Last State` 항목에서 정확한 원인을 먼저 확인한다.
- **VPA(Vertical Pod Autoscaler)의 추천값을 참고만 하고 그대로 적용하지 마라.** 트래픽 패턴이 주기적으로 변하는 서비스는 특정 시점 스냅샷 기반 추천이 피크 상황을 놓칠 수 있다.
- **네임스페이스 LimitRange와 함께 검토하라.** 개별 Pod의 requests/limits가 정상이어도 네임스페이스 전체의 ResourceQuota를 넘기면 스케줄링 자체가 거부된다.
- **사이드카 컨테이너의 메모리도 잊지 마라.** 로그 수집기, 서비스 메시 프록시 같은 사이드카가 메인 컨테이너와 별도로 자체 limit을 갖는다는 점을 놓치면 전체 Pod 메모리 예산 계산이 틀어진다.

## 마무리 요약

- CPU limit 초과는 스로틀링, 메모리 limit 초과는 즉시 강제 종료(OOMKilled)로 성격이 완전히 다르다.
- requests와 limits를 같게 맞추면 안전할 것 같지만, GC나 시작 시점 스파이크가 있는 애플리케이션에서는 오히려 위험하다.
- 추측이 아니라 실제 모니터링 지표를 근거로 requests/limits 값을 정하고, 사이드카·네임스페이스 쿼터까지 함께 고려해야 한다.

## 참고 자료

- [Kubernetes 공식 문서 - Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes 공식 문서 - Assign Memory Resources to Containers and Pods](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/)
