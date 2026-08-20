---
layout: single
title: "kubectl 기본 명령이 뭔가요 — 쿠버네티스를 다루는 첫걸음"
date: 2026-09-14 13:40:00 +0530
categories: infra
tags: ["kubectl", "쿠버네티스", "kubernetes", "cli", "입문"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스 클러스터를 명령줄에서 조작하는 kubectl의 자주 쓰는 기본 명령을 처음 배우는 사람 기준으로 정리했다."
---

## 쿠버네티스에 명령을 어떻게 내리나

쿠버네티스 클러스터를 다루는 표준 명령줄 도구가 **kubectl**이다. 파드 조회, 배포, 로그 확인 등 대부분의 작업을 kubectl로 한다. 몇 가지 기본 명령만 익히면 클러스터 상태를 보고 문제를 진단할 수 있다.

## 자주 쓰는 명령

| 명령 | 하는 일 |
|---|---|
| `kubectl get pods` | 파드 목록 조회 |
| `kubectl describe pod <이름>` | 파드 상세·이벤트 |
| `kubectl logs <이름>` | 파드 로그 보기 |
| `kubectl apply -f <파일>` | YAML로 리소스 적용 |
| `kubectl exec -it <이름> -- bash` | 파드 안에 접속 |

## 문제 진단 흐름

```text
1. kubectl get pods         # 상태 확인 (Running? CrashLoop?)
2. kubectl describe pod X   # 왜 안 뜨나(이벤트 메시지)
3. kubectl logs X           # 앱이 뭐라 하나(에러 로그)
-> 대부분의 문제는 이 3단계로 원인이 보인다
```

## 실무 포인트

- **`-n 네임스페이스`를 잊지 마라.** 기본은 `default` 네임스페이스만 본다. 다른 네임스페이스의 리소스는 `-n dev`처럼 지정해야 보인다. 안 보이면 네임스페이스부터 확인한다.
- **`describe`와 `logs`를 구분.** `describe`는 쿠버네티스 관점의 이벤트(스케줄 실패, 이미지 못 받음 등), `logs`는 앱 자체의 출력이다. 파드가 아예 안 뜨면 `describe`, 떴는데 오작동이면 `logs`를 본다.
- **`apply`는 선언적, `delete`는 신중히.** `apply`는 YAML의 원하는 상태로 맞춘다. `delete`는 리소스를 지우니 대상(특히 네임스페이스·PVC)을 꼭 확인하고 실행한다.

## 마무리 요약

- kubectl은 쿠버네티스 클러스터를 명령줄에서 다루는 표준 도구다.
- `get`(조회)·`describe`(상세)·`logs`(로그)·`apply`(적용)·`exec`(접속)가 기본이다.
- 문제 진단은 get→describe→logs 순서가 정석이며, 네임스페이스 지정을 잊지 않는다.

## 참고 자료

- [Kubernetes 공식 문서 - kubectl](https://kubernetes.io/docs/reference/kubectl/)
