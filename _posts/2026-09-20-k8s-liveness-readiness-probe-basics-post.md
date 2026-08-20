---
layout: single
title: "쿠버네티스 Liveness·Readiness 프로브가 뭔가요"
date: 2026-09-20 13:40:00 +0530
categories: infra
tags: ["kubernetes", "probe", "liveness", "readiness", "입문"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스가 컨테이너의 생존과 준비 상태를 확인하는 liveness·readiness 프로브의 차이와 설정 감각을 처음 배우는 사람 기준으로 정리했다."
---

## "파드는 Running인데 요청이 에러난다"

파드가 `Running`이어도 앱이 아직 초기화 중이거나 내부적으로 멈춰 있을 수 있다. 쿠버네티스는 이를 **프로브(probe)**로 점검한다. 대표적으로 **liveness**(살아 있나)와 **readiness**(요청 받을 준비됐나)가 있다.

## 두 프로브의 차이

| 프로브 | 질문 | 실패하면 |
|---|---|---|
| liveness | 앱이 살아 있나? | 컨테이너를 재시작 |
| readiness | 트래픽 받을 준비됐나? | 서비스에서 제외(트래픽 차단) |

liveness가 실패하면 "죽었다"고 보고 재시작하고, readiness가 실패하면 "아직 준비 안 됨"으로 보고 트래픽만 끊는다(재시작 X).

## 설정 예시

```yaml
livenessProbe:
  httpGet: { path: /healthz, port: 8080 }
  initialDelaySeconds: 10
  periodSeconds: 5
readinessProbe:
  httpGet: { path: /ready, port: 8080 }
  periodSeconds: 5
```

## 실무 포인트

- **readiness로 무중단 배포.** 새 파드가 준비될 때까지 트래픽을 안 보내므로, 초기화 중 요청이 에러나는 걸 막는다. 롤링 업데이트의 핵심이다.
- **liveness는 신중히.** 잘못 설정하면 멀쩡한 앱을 계속 재시작하는 루프에 빠진다. `initialDelaySeconds`로 초기화 시간을 충분히 준다.
- **엔드포인트를 분리.** 헬스체크는 DB 등 외부 의존성까지 확인할지 신중히 정한다. liveness에 외부 의존성을 넣으면 DB 장애가 앱 재시작으로 번질 수 있다.

## 마무리 요약

- liveness는 생존 확인(실패 시 재시작), readiness는 준비 확인(실패 시 트래픽 차단)이다.
- readiness는 무중단 배포의 핵심이며, liveness는 재시작 루프에 주의한다.
- 초기 지연·의존성 포함 여부를 신중히 설정한다.

## 참고 자료

- [Kubernetes 문서 - Liveness, Readiness Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
