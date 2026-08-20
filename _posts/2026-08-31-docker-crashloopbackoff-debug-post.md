---
layout: single
title: "Docker 컨테이너가 계속 재시작될 때 — CrashLoopBackOff 원인 찾는 법"
date: 2026-08-31 12:40:00 +0530
categories: infra
tags: ["docker", "kubernetes", "트러블슈팅", "crashloopbackoff", "디버깅"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스나 Docker Compose에서 컨테이너가 계속 재시작될 때, 원인을 단계별로 좁혀가는 실전 디버깅 순서."
---

## 왜 이 에러가 골치 아픈가

`CrashLoopBackOff`는 쿠버네티스가 "이 컨테이너를 계속 재시작했지만 계속 죽는다"고 알려주는 상태일 뿐, 정작 왜 죽었는지는 말해주지 않는다. Docker Compose에서도 `Restarting (1) ...`이 반복되는 동일한 증상이 나타난다. 처음 마주치면 로그부터 봐야 할지, 리소스 문제인지, 설정 문제인지 감을 잡기 어렵다. 이 글은 원인을 좁혀가는 순서를 정리했다.

## 원인 카테고리 4가지

| 카테고리 | 대표 증상 | 확인 명령 |
|---|---|---|
| 애플리케이션 크래시 | 시작 직후 에러 로그 후 종료 | `kubectl logs --previous` |
| 리소스 부족(OOM) | Exit Code 137 | `kubectl describe pod` 의 `Last State` |
| 헬스체크 실패 | Ready는 됐다가 Liveness 실패로 재시작 | `kubectl describe pod` 의 Events |
| 설정·의존성 오류 | 환경변수 누락, DB 연결 실패로 즉시 종료 | 로그의 스택트레이스 첫 줄 |

## 진단 순서

```bash
# 1. 현재 상태와 재시작 횟수, 마지막 종료 사유 확인
kubectl describe pod <pod-name>

# 2. 방금 죽은 컨테이너의 로그 확인 (현재 로그가 아니라 --previous가 핵심)
kubectl logs <pod-name> --previous

# 3. Exit Code 확인 — 숫자로 원인 범위를 좁힌다
#    0   : 정상 종료 (재시작 정책 때문에 반복될 수도 있음)
#    1   : 애플리케이션 자체 에러
#    137 : OOM Killer에 의해 강제 종료 (128 + SIGKILL(9))
#    139 : 세그멘테이션 폴트
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
```

Docker Compose 환경이라면 `docker logs <container> --tail 100`과 `docker inspect <container>`의 `State.ExitCode`로 같은 정보를 얻을 수 있다.

## 실무 포인트

- **Exit Code 137이 보이면 로그를 아무리 봐도 답이 없다.** 메모리 제한(`resources.limits.memory`)을 올리거나, 애플리케이션의 힙/메모리 사용량 자체를 줄여야 한다.
- **Liveness Probe 설정이 너무 빡빡하면 정상 앱도 재시작 루프에 빠진다.** `initialDelaySeconds`를 애플리케이션 부팅 시간보다 넉넉하게 주는 것이 첫 번째 점검 포인트다.
- **로컬에서는 멀쩡한데 클러스터에서만 죽는다면** 환경변수·시크릿 마운트 차이, 또는 네트워크 정책으로 인한 DB 연결 실패를 의심한다. `kubectl exec`로 컨테이너에 직접 들어가 연결을 테스트해보면 빠르게 확인된다.

## 마무리 요약

- `kubectl logs --previous`로 죽기 직전 로그를 봐야 진짜 원인이 보인다.
- Exit Code 137은 로그가 아니라 메모리 제한을 먼저 의심해야 한다.
- Liveness Probe의 initialDelaySeconds 설정 미스도 흔한 원인 중 하나다.

## 참고 자료

- [Kubernetes 공식 문서 - Debug Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [Docker 공식 문서 - docker logs](https://docs.docker.com/engine/reference/commandline/logs/)
