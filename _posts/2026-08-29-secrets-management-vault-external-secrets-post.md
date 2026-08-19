---
layout: single
title: "쿠버네티스 Secret에 그대로 넣지 마라 — Vault와 External Secrets Operator로 보는 시크릿 관리"
date: 2026-08-29 13:40:00 +0530
categories: infra
tags: ["vault", "external-secrets-operator", "kubernetes", "secrets-management", "devops", "security"]
toc: true
toc_sticky: true
excerpt: "쿠버네티스 기본 Secret이 base64 인코딩에 불과한 이유와, HashiCorp Vault·External Secrets Operator로 시크릿을 중앙에서 관리하고 자동 회전시키는 아키텍처를 정리한다."
---

쿠버네티스 `Secret` 오브젝트는 이름부터 안전할 것 같은 인상을 주지만, 실제로는 값을 base64로 인코딩해 etcd에 저장할 뿐이다. base64는 암호화가 아니라 인코딩이므로, etcd에 접근 권한이 있거나 `kubectl get secret -o yaml`을 실행할 권한이 있는 사람은 누구나 원문 값을 즉시 복원할 수 있다. 여기에 더해 매니페스트에 시크릿 값을 그대로 커밋하는 실수, 여러 클러스터·환경에 흩어진 시크릿을 수작업으로 동기화하는 관행까지 겹치면, 시크릿 관리는 조직이 커질수록 리스크가 누적되는 영역이 된다.

이 문제를 푸는 실무 표준은 크게 두 축으로 정리된다. 시크릿을 실제로 저장·암호화·회전(rotation)시키는 중앙 저장소로서의 **HashiCorp Vault**, 그리고 그 중앙 저장소의 값을 쿠버네티스 네이티브 `Secret`으로 동기화해주는 **External Secrets Operator(ESO)**다. 이 글에서는 두 컴포넌트가 각각 어떤 역할을 하고 함께 어떻게 동작하는지를 정리한다.

## 핵심 개념 1: Vault — 시크릿의 단일 진실 공급원

Vault는 시크릿을 암호화된 상태로 저장하고, 접근할 때마다 정책 기반으로 권한을 검증하는 중앙 시크릿 저장소다. 정적 시크릿(DB 비밀번호, API 키)을 그냥 저장하는 것 외에도, **동적 시크릿(dynamic secrets)**이라는 개념이 Vault의 핵심 차별점이다. 예를 들어 DB 자격 증명을 요청하면 Vault가 그 순간 실제 DB에 접속해 짧은 TTL(예: 1시간)을 가진 임시 사용자 계정을 즉시 생성해 발급한다. TTL이 지나면 그 계정은 자동으로 폐기되므로, 자격 증명이 유출되더라도 피해 창구가 짧게 제한된다.

Vault는 또한 시크릿 접근 요청마다 감사 로그를 남기고, AppRole·Kubernetes 인증 등 다양한 인증 방식으로 "누가 어떤 시크릿에 접근할 자격이 있는지"를 정책(policy)으로 세밀하게 제어한다. 이는 시크릿이 여러 애플리케이션·팀에 흩어져 있을 때 "이 시크릿을 누가 봤는지"를 추적할 수 있게 해준다는 점에서, 단순 저장소를 넘어선 거버넌스 계층 역할을 한다.

## 핵심 개념 2: External Secrets Operator — Vault와 쿠버네티스 Secret 사이의 다리

Vault에 시크릿이 있어도, 애플리케이션 파드가 그 값을 쓰려면 결국 어떤 형태로든 파드에 전달돼야 한다. External Secrets Operator는 이 전달 과정을 쿠버네티스 네이티브 리소스로 선언적으로 처리한다. `SecretStore`(또는 `ClusterSecretStore`)로 Vault 같은 외부 저장소의 연결 정보를 정의하고, `ExternalSecret` 리소스로 "이 경로의 시크릿을 가져와서 이런 이름의 쿠버네티스 Secret으로 만들어라"라고 선언하면, ESO의 컨트롤러가 주기적으로 Vault를 폴링해 그 값을 쿠버네티스 `Secret`으로 동기화한다.

핵심은 애플리케이션 코드나 배포 매니페스트가 여전히 표준 쿠버네티스 `Secret`(볼륨 마운트나 환경 변수)을 참조한다는 점이다. 즉 애플리케이션 입장에서는 시크릿이 Vault에서 왔는지 몰라도 되고, 인프라 팀은 실제 시크릿 원본을 Vault 한 곳에서 관리하며 여러 클러스터에 자동으로 동기화할 수 있다. Vault의 시크릿이 회전(rotation)되면 ESO가 다음 폴링 주기에 이를 감지해 쿠버네티스 Secret도 함께 갱신한다.

<img src="/assets/images/posts/2026-08-29-secrets-management-vault-external-secrets-1.svg" alt="Vault가 시크릿을 중앙에서 암호화 저장하고 동적 시크릿을 발급하며, External Secrets Operator가 주기적으로 폴링해 쿠버네티스 Secret으로 동기화하고 애플리케이션 파드는 표준 Secret만 참조하는 구조" style="width:100%;">

## 핵심 개념 3: 회전과 폴링 주기의 트레이드오프

시크릿 회전이 자동화되면 좋은 점은 명확하지만, 회전 주기와 ESO의 폴링 주기 사이의 간극을 이해해야 실무에서 놀라지 않는다. ESO는 이벤트 기반으로 즉시 반응하는 것이 아니라 설정된 `refreshInterval`마다 Vault를 폴링하므로, Vault에서 시크릿이 갱신된 시점과 쿠버네티스 Secret에 실제로 반영되는 시점 사이에 최대 폴링 주기만큼의 지연이 생긴다. 게다가 쿠버네티스 `Secret`이 갱신돼도, 이미 실행 중인 파드가 이를 즉시 인지하는 것은 아니다. 환경 변수로 주입된 값은 파드가 재시작돼야 반영되고, 볼륨 마운트로 주입된 값은 kubelet의 동기화 주기에 따라 반영되지만 애플리케이션이 파일 변경을 감지해 재로드하는 로직이 없다면 여전히 이전 값을 메모리에 들고 있을 수 있다.

| 구분 | 쿠버네티스 기본 Secret | Vault + ESO |
|---|---|---|
| 저장 방식 | base64 인코딩(암호화 아님) | Vault가 암호화 저장 |
| 동적 시크릿 발급 | 미지원 | 지원(TTL 기반 임시 자격 증명) |
| 회전 자동화 | 수동 | Vault 회전 + ESO 폴링 동기화 |
| 접근 감사 로그 | 제한적(kube-apiserver 감사에 의존) | Vault 자체 상세 감사 로그 |
| 멀티 클러스터 동기화 | 수작업 | ClusterSecretStore로 중앙 관리 |

## 예제: ExternalSecret 리소스로 Vault 시크릿 동기화

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.internal:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "payments-service"   # Vault Kubernetes 인증 역할

---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: payments-db-credentials
  namespace: payments
spec:
  refreshInterval: 1h            # 폴링 주기 - 이 간격만큼 반영 지연 발생 가능
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: payments-db-secret       # 생성될 쿠버네티스 Secret 이름
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: database/creds/payments-role
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/payments-role
        property: password
```

## 실무 포인트

- **정적 시크릿부터 동적 시크릿으로 단계적으로 옮긴다**: 모든 시크릿을 한 번에 동적 발급으로 전환하기는 어렵다. DB 자격 증명처럼 회전 리스크가 큰 것부터 동적 시크릿으로 옮기고, 나머지는 정적 시크릿을 Vault에 저장하는 것만으로도 base64 노출 문제는 해결된다.
- **회전 후 애플리케이션 재로드 경로를 반드시 검증한다**: 시크릿이 갱신됐는데 애플리케이션이 이전 값을 계속 캐시하고 있다면 회전 자체가 무의미하다. 볼륨 마운트 변경 감지 후 재시작을 트리거하는 사이드카(예: Reloader류 컨트롤러)를 함께 쓰는 것이 일반적인 보완책이다.
- **폴링 주기를 시크릿 성격에 맞게 차등화한다**: 모든 `ExternalSecret`에 같은 `refreshInterval`을 쓰면, 자주 바뀌지 않는 시크릿까지 불필요하게 Vault를 폴링해 API 부하를 늘린다. 회전 빈도가 높은 시크릿은 짧게, 정적에 가까운 시크릿은 길게 설정한다.

## 3줄 요약

- 쿠버네티스 기본 `Secret`은 base64 인코딩일 뿐 암호화가 아니므로, etcd 접근 권한이 있으면 누구나 원문을 복원할 수 있다는 근본적 한계가 있다.
- Vault는 시크릿을 암호화 저장하고 TTL 기반 동적 시크릿을 발급하는 중앙 저장소이며, External Secrets Operator는 이 값을 쿠버네티스 네이티브 `Secret`으로 주기적으로 동기화하는 다리 역할을 한다.
- ESO의 폴링 주기와 파드의 재로드 방식 때문에 회전이 실제로 애플리케이션에 반영되기까지 지연이 생길 수 있어, 회전 자동화만큼이나 재로드 경로 검증이 중요하다.

## 참고 자료

- [HashiCorp Vault 공식 문서: Dynamic Secrets](https://developer.hashicorp.com/vault/docs/secrets)
- [External Secrets Operator 공식 문서](https://external-secrets.io/latest/)
- [Vault 공식 문서: Kubernetes Auth Method](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
