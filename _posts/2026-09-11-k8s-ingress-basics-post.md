---
layout: single
title: "쿠버네티스 인그레스가 뭔가요 — 하나의 입구로 여러 서비스 노출"
date: 2026-09-11 13:40:00 +0530
categories: infra
tags: ["쿠버네티스", "kubernetes", "ingress", "라우팅", "입문"]
toc: true
toc_sticky: true
excerpt: "여러 서비스를 도메인·경로에 따라 하나의 진입점으로 노출하는 쿠버네티스 인그레스(Ingress)의 개념을 처음 배우는 사람 기준으로 정리했다."
---

## 서비스마다 로드밸런서를 만들면 낭비다

쿠버네티스에서 외부 노출은 서비스의 LoadBalancer 타입으로 할 수 있다. 하지만 서비스가 10개면 로드밸런서(그리고 공인 IP)가 10개 필요해 비용이 크고 관리가 번거롭다. **인그레스(Ingress)**는 **하나의 진입점에서 도메인·URL 경로를 보고 알맞은 서비스로 라우팅**해준다.

## 무엇으로 나누나

| 기준 | 예 |
|---|---|
| 호스트(도메인) | `api.example.com` → api 서비스 |
| 경로(path) | `/shop` → shop, `/blog` → blog |

## 라우팅 예시

```text
                 ┌─> /api  -> api-service
example.com ──── ├─> /shop -> shop-service
 (Ingress)       └─> /blog -> blog-service

하나의 도메인/IP로 들어와 경로에 따라 분배된다.
```

## 실무 포인트

- **Ingress 컨트롤러가 있어야 동작한다.** Ingress 규칙(YAML)만 만든다고 되는 게 아니라, 실제로 트래픽을 처리하는 **Ingress 컨트롤러**(nginx-ingress 등)를 클러스터에 설치해야 규칙이 적용된다.
- **TLS(HTTPS)를 여기서 처리한다.** 인그레스에서 인증서를 설정하면 HTTPS 종료(TLS termination)를 한곳에서 처리할 수 있다. cert-manager로 인증서 자동 발급·갱신을 붙이는 경우가 많다.
- **서비스와 역할이 다르다.** 서비스는 클러스터 안에서 파드로 트래픽을 분배하고, 인그레스는 클러스터 밖에서 들어오는 HTTP(S)를 서비스로 라우팅한다. 보통 인그레스 → 서비스 → 파드 순으로 흐른다.

## 마무리 요약

- 인그레스는 하나의 진입점에서 도메인·경로에 따라 여러 서비스로 트래픽을 라우팅한다.
- 서비스마다 로드밸런서를 만드는 낭비를 줄이고, TLS(HTTPS)도 한곳에서 처리한다.
- Ingress 컨트롤러 설치가 필요하며, 흐름은 인그레스 → 서비스 → 파드다.

## 참고 자료

- [Kubernetes 공식 문서 - Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
