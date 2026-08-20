---
layout: single
title: "Helm이 뭔가요 — 쿠버네티스의 패키지 매니저"
date: 2026-09-13 13:40:00 +0530
categories: infra
tags: ["helm", "쿠버네티스", "kubernetes", "패키지", "입문"]
toc: true
toc_sticky: true
excerpt: "여러 쿠버네티스 리소스를 하나의 패키지로 묶어 설치·관리하는 Helm의 개념과 차트를 처음 배우는 사람 기준으로 정리했다."
---

## YAML이 수십 개가 되면 관리가 안 된다

쿠버네티스에 앱 하나를 배포하려면 Deployment·Service·ConfigMap·Ingress 등 YAML 파일이 여러 개 필요하다. 환경마다 값도 조금씩 다르다. **Helm**은 **이 여러 리소스를 하나의 패키지(차트)로 묶어 설치·업그레이드·삭제를 명령 한 줄로** 하게 해주는 쿠버네티스의 패키지 매니저다. `apt`나 `npm` 같은 역할이다.

## 핵심 개념

| 용어 | 설명 |
|---|---|
| Chart(차트) | 쿠버네티스 리소스 묶음 패키지 |
| Values | 차트에 넣는 설정값(환경별로 다르게) |
| Release | 차트를 클러스터에 설치한 인스턴스 |

## 사용 흐름

```text
helm install myapp ./mychart        # 설치
helm upgrade myapp ./mychart        # 업그레이드
helm rollback myapp 1               # 이전 버전으로 롤백
helm uninstall myapp                # 삭제

values.yaml로 replicas, image 등을 환경마다 다르게 주입
```

## 실무 포인트

- **공개 차트로 빠르게 설치.** PostgreSQL, Redis, nginx 등은 이미 잘 만들어진 공개 Helm 차트가 있다. 직접 YAML을 쓰지 않고 `helm install`로 검증된 구성을 바로 설치할 수 있다.
- **values로 환경을 분리.** 같은 차트에 `values-dev.yaml`, `values-prod.yaml`을 달리 주면 개발/운영 환경을 하나의 차트로 관리한다. 중복 YAML을 줄이는 핵심 이점이다.
- **버전 관리와 롤백.** Helm은 릴리스 이력을 관리해, 업그레이드가 잘못되면 `helm rollback`으로 이전 상태로 되돌릴 수 있다. 배포 안정성에 도움이 된다.

## 마무리 요약

- Helm은 여러 쿠버네티스 리소스를 차트로 묶어 설치·업그레이드·롤백을 한 줄로 하는 패키지 매니저다.
- Chart(패키지)·Values(설정값)·Release(설치본) 개념으로 동작한다.
- 공개 차트로 빠르게 설치하고, values로 환경을 분리하며, 롤백으로 안정성을 높인다.

## 참고 자료

- [Helm 공식 문서](https://helm.sh/docs/)
