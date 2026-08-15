---
layout: single
title: "CI가 배포까지 하지 않아야 하는 이유 — GitOps와 ArgoCD 실전 적용"
date: 2026-08-19 13:40:00 +0530
categories: infra
tags: ["argocd", "gitops", "kubernetes", "배포파이프라인", "선언형배포"]
toc: true
toc_sticky: true
excerpt: "CI 파이프라인이 클러스터 자격증명을 쥐고 직접 배포까지 밀어넣는 구조의 한계를 짚고, ArgoCD로 Git을 단일 진실 공급원 삼아 배포를 풀(pull) 기반으로 재설계하는 방법을 정리한다."
---

## 왜 지금 배포 파이프라인을 GitOps로 다시 그려야 하는가

많은 팀의 CI 파이프라인은 테스트 → 빌드 → `kubectl apply`(또는 `helm upgrade`)까지 한 번에 실행한다. 문제는 이 마지막 단계다. CI 러너가 운영 클러스터의 kubeconfig나 서비스 어카운트 토큰을 들고 있어야 하고, 배포가 실패하거나 중간에 끊기면 클러스터 상태와 Git의 매니페스트가 조용히 어긋난다(configuration drift). 누군가 급하게 `kubectl edit`으로 운영 환경을 고쳤다면, 그 변경은 어디에도 기록되지 않은 채 다음 배포 때 덮어써지거나 반대로 영원히 남아 혼란을 만든다.

**GitOps**는 이 구조를 뒤집는다. Git 리포지토리의 매니페스트를 "클러스터가 도달해야 할 목표 상태"로 선언하고, 클러스터 안(또는 클러스터에 가까운 위치)에서 동작하는 에이전트가 그 목표 상태와 실제 상태를 지속적으로 비교해 스스로 맞춰나간다. CI는 이미지를 빌드하고 매니페스트의 이미지 태그를 갱신해 Git에 커밋하는 데서 역할이 끝난다. 배포를 "실행"하는 주체가 CI에서 클러스터 내부 에이전트로 옮겨가는 것이 핵심이다.

**ArgoCD**는 이 역할을 맡는 대표적인 쿠버네티스 네이티브 도구다. 이 글은 ArgoCD가 무엇인지 개괄하기보다, `Application` 리소스를 어떻게 선언하고 여러 서비스를 어떤 구조로 묶어 관리하는지 실전 매니페스트 중심으로 정리한다.

## 핵심 개념 1: Push 기반 CI/CD와 Pull 기반 GitOps

두 방식 모두 "코드 변경을 클러스터에 반영한다"는 목표는 같지만, 배포를 누가 언제 실행하느냐가 근본적으로 다르다.

| 구분 | Push 기반 CI/CD | Pull 기반 GitOps(ArgoCD) |
|---|---|---|
| 배포 실행 주체 | CI 러너가 직접 `kubectl`/`helm` 실행 | 클러스터 내부 컨트롤러가 스스로 동기화 |
| 클러스터 자격증명 위치 | CI 시스템(외부)에 저장 | 클러스터 내부(외부 노출 최소화) |
| 실제 상태 확인 방법 | 배포 로그를 다시 뒤져야 함 | Git 커밋 = 배포 이력, 대시보드로 즉시 비교 |
| 수동 변경(drift) 감지 | 별도 도구 없이는 알기 어려움 | 컨트롤러가 목표 상태와 실시간 비교·감지 |
| 롤백 방법 | 이전 배포 스크립트 재실행 | Git revert 한 번으로 이전 목표 상태 복원 |

표에서 가장 중요한 줄은 자격증명 위치다. CI 시스템은 태생적으로 외부 서비스(플러그인, 서드파티 액션 등)와 많이 얽혀 있어 공격 표면이 넓다. 운영 클러스터 자격증명이 그 안에 있다는 것 자체가 리스크다. GitOps는 이 자격증명을 클러스터 내부로 거둬들이고, CI가 필요한 건 Git에 커밋할 권한뿐이라는 점에서 공격 표면을 구조적으로 줄인다.

## 핵심 개념 2: ArgoCD의 핵심 구성 요소

ArgoCD는 몇 개의 컴포넌트가 역할을 나눠 맡는다.

| 구성 요소 | 역할 |
|---|---|
| API Server | CLI·UI·CI가 호출하는 진입점, 인증·RBAC 처리 |
| Repo Server | Git 리포지토리를 캐싱하고 Helm/Kustomize를 렌더링해 최종 매니페스트 생성 |
| Application Controller | 렌더링된 매니페스트(목표 상태)와 클러스터 실제 상태를 비교(diff)하고 동기화 실행 |
| `Application` CRD | 어떤 Git 경로를, 어떤 클러스터의 어떤 네임스페이스에 동기화할지 선언하는 최상위 리소스 |
| App of Apps 패턴 | `Application`이 다른 `Application`들을 관리하는 상위 `Application`을 두어 여러 서비스를 한 번에 관장 |

Application Controller가 계속 반복하는 이 비교·동기화 루프가 GitOps의 실체다. Git에 새 커밋이 들어오면(웹훅 또는 폴링으로 감지) Repo Server가 최신 매니페스트를 렌더링하고, Controller가 이를 실제 클러스터 상태와 비교해 차이가 있으면 적용한다. 누군가 클러스터를 직접 고쳐도 다음 동기화 주기에 Git의 상태로 되돌려진다(`selfHeal` 옵션을 켰을 때).

<img src="/assets/images/posts/2026-08-19-gitops-argocd-pipeline-1.svg" alt="GitOps 동기화 흐름 - Git 리포지토리, ArgoCD 컴포넌트, 쿠버네티스 클러스터 사이의 지속적 비교·동기화 루프" style="width:100%;">

## 예제 1: Application 리소스로 선언형 배포 정의하기

가장 기본적인 `Application` 매니페스트다. 어떤 Git 경로를 어떤 클러스터·네임스페이스에 동기화할지 선언한다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example-org/k8s-manifests.git
    targetRevision: main
    path: apps/order-service/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: order-service
  syncPolicy:
    automated:
      prune: true       # Git에서 삭제된 리소스는 클러스터에서도 제거
      selfHeal: true     # 수동 변경 감지 시 자동으로 Git 상태로 복원
    syncOptions:
      - CreateNamespace=true
```

`prune: true`는 Git에서 리소스를 삭제하면 클러스터에서도 함께 삭제한다는 뜻이고, `selfHeal: true`는 수동으로 변경된 리소스를 다음 동기화 때 Git 상태로 되돌린다는 뜻이다. 두 옵션 모두 강력하지만, 팀이 아직 GitOps 흐름에 익숙하지 않다면 처음에는 자동 동기화 없이 수동 승인(`Sync` 버튼 클릭)부터 시작해 신뢰를 쌓는 편이 안전하다.

## 예제 2: App of Apps 패턴으로 여러 서비스 한 번에 관리하기

서비스가 늘어나면 `Application`을 하나씩 만드는 대신, 여러 `Application`을 묶어 관리하는 상위 `Application`을 둔다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example-org/k8s-manifests.git
    targetRevision: main
    path: apps/root      # 이 경로 아래에 각 서비스별 Application yaml들이 있음
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

`apps/root` 디렉터리 안에 `order-service`, `payment-service` 같은 개별 `Application` 매니페스트를 두면, 새 서비스를 추가할 때 ArgoCD UI를 건드릴 필요 없이 이 디렉터리에 파일 하나를 커밋하는 것으로 끝난다. 클러스터나 팀 단위로 이 상위 `Application`을 여러 개 둬서 관리 경계를 나누는 것도 흔한 구성이다.

## 실무 포인트

- **Secret은 절대 평문으로 Git에 넣지 않는다**: GitOps는 "Git에 있는 것이 곧 배포된다"는 원칙이라, Secret도 예외가 아니다. Sealed Secrets나 External Secrets Operator처럼 암호화된 형태로 커밋하거나 외부 볼트를 참조하는 방식으로 우회해야 한다.
- **selfHeal은 팀의 GitOps 성숙도에 맞춰 켠다**: 이 옵션을 켜면 긴급 상황에서 누군가 `kubectl patch`로 급히 고친 값도 다음 주기에 되돌려진다. 알림 체계와 "긴급 시 Git을 먼저 고친다"는 팀 규칙이 갖춰지지 않은 상태에서 켜면 오히려 장애 대응을 방해할 수 있다.
- **Kustomize/Helm 오버레이로 환경별 차이를 관리한다**: 위 예제의 `overlays/production` 경로처럼, base 매니페스트에 환경별 패치를 얹는 구조를 쓰면 dev/staging/production 간 중복을 줄이면서도 차이를 명시적으로 드러낼 수 있다.
- **ArgoCD Project로 권한 경계를 나눈다**: 모든 `Application`을 `default` 프로젝트에 두면 팀 간 권한 분리가 어렵다. 팀·환경 단위로 Project를 나눠 접근 가능한 리포지토리·클러스터·네임스페이스를 제한하는 편이 운영 사고를 줄인다.

## 3줄 요약

- GitOps는 배포를 CI가 직접 실행하는 push 방식에서, 클러스터 내부 에이전트가 Git의 목표 상태에 스스로 맞춰가는 pull 방식으로 전환해 자격증명 노출과 drift 문제를 구조적으로 줄인다.
- ArgoCD는 `Application` CRD로 Git 경로와 배포 대상을 선언하고, Repo Server와 Application Controller가 목표 상태와 실제 상태를 지속적으로 비교·동기화한다.
- Secret 관리, selfHeal 활성화 시점, 환경별 오버레이 구조, Project 단위 권한 분리를 팀 상황에 맞춰 설계해야 GitOps 도입이 사고 없이 안착한다.

## 참고 자료

- [ArgoCD 공식 문서 — Core Concepts](https://argo-cd.readthedocs.io/en/stable/core_concepts/)
- [ArgoCD 공식 문서 — App of Apps Pattern](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)
- [OpenGitOps — GitOps Principles](https://opengitops.dev/)
