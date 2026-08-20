---
layout: single
title: "ConfigMap과 Secret이 뭔가요 — 설정을 코드 밖으로 빼기"
date: 2026-09-12 13:40:00 +0530
categories: infra
tags: ["쿠버네티스", "kubernetes", "configmap", "secret", "입문"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스에서 설정값과 비밀값을 컨테이너 이미지에서 분리해 관리하는 ConfigMap과 Secret의 차이를 처음 배우는 사람 기준으로 정리했다."
---

## 설정을 이미지에 박으면 유연성이 없다

DB 주소, 기능 플래그, API 키 같은 값을 컨테이너 이미지 안에 넣으면, 값 하나 바꾸려고 이미지를 다시 빌드해야 한다. 개발/운영 환경별로 값이 다르면 더 곤란하다. **ConfigMap**과 **Secret**은 이런 **설정값을 이미지 밖으로 빼서** 파드에 주입하는 쿠버네티스 리소스다.

## ConfigMap vs Secret

| 구분 | ConfigMap | Secret |
|---|---|---|
| 용도 | 일반 설정값 | 비밀값(키·비밀번호) |
| 저장 | 평문 | base64 인코딩 |
| 예 | DB 주소, 로그 레벨 | API 키, DB 비밀번호 |

## 어떻게 주입하나

```text
ConfigMap/Secret에 값을 정의해두고, 파드에서 두 방식으로 사용:
1. 환경 변수로 주입: DB_URL, API_KEY 등
2. 파일로 마운트: /etc/config/... 경로에 파일로

앱은 이미지 변경 없이, 주입된 값을 읽어 동작한다.
```

## 실무 포인트

- **Secret은 기본적으로 암호화가 아니다.** Secret의 base64는 "인코딩"일 뿐 암호화가 아니다. 진짜 보호하려면 클러스터의 저장 암호화(encryption at rest)를 켜거나 외부 시크릿 매니저(Vault 등)를 연동한다.
- **환경별로 분리하라.** 같은 이미지를 개발/스테이징/운영에서 쓰되, ConfigMap/Secret만 환경마다 다르게 두면 이미지 재빌드 없이 환경을 전환할 수 있다.
- **Secret을 깃에 올리지 마라.** Secret YAML을 그대로 깃에 커밋하면 base64는 쉽게 풀려 유출된다. 시크릿은 별도 관리(외부 시크릿, sealed-secrets 등)하고 저장소에 원문을 두지 않는다.

## 마무리 요약

- ConfigMap은 일반 설정값, Secret은 비밀값을 이미지 밖으로 빼 파드에 주입하는 리소스다.
- 환경 변수나 파일 마운트로 주입하며, 이미지 재빌드 없이 값을 바꿀 수 있다.
- Secret의 base64는 암호화가 아니므로 저장 암호화·외부 시크릿을 쓰고, 깃에 원문을 올리지 않는다.

## 참고 자료

- [Kubernetes 공식 문서 - ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
