---
layout: single
title: "Kubernetes Admission Webhook 내부 동작 — Mutating과 Validating으로 클러스터 정책 강제하기"
date: 2026-09-26 12:40:00 +0530
categories: infra
tags: ["쿠버네티스", "AdmissionWebhook", "정책강제", "K8sAPI서버", "클러스터보안"]
toc: true
toc_sticky: true
excerpt: "라벨 누락, 리소스 제한 미설정, 위험한 이미지 태그처럼 리뷰만으로는 막기 어려운 매니페스트 실수를, API 서버가 오브젝트를 저장하기 직전에 가로채 검사·수정하는 Admission Webhook의 요청 처리 파이프라인과 실패 모드를 정리했다."
---

## 왜 지금 승인 단계를 다시 봐야 하는가

RBAC은 "누가 어떤 리소스에 어떤 동작을 할 수 있는가"를 결정하지만, "그 요청의 내용이 우리 조직의 규칙에 맞는가"는 전혀 검사하지 않는다. 개발자에게 파드 생성 권한이 있어도, latest 태그 이미지를 쓰거나 리소스 requests/limits를 아예 설정하지 않은 매니페스트를 막을 방법이 RBAC에는 없다. 코드 리뷰나 CI 검사로 걸러내려 해도, kubectl apply를 CI 바깥에서 직접 실행하는 경로는 여전히 뚫려 있다. Kubernetes API 서버는 이 틈을 메우기 위해 요청이 etcd에 저장되기 직전 마지막 관문으로 Admission Webhook이라는 확장점을 제공한다.

## 핵심 개념 1 — 요청이 etcd에 도달하기까지의 파이프라인

kubectl apply로 보낸 요청은 API 서버 내부에서 인증(Authentication) → 인가(Authorization, RBAC) → 어드미션 컨트롤(Admission Control) 순으로 통과해야 한다. 어드미션 단계는 다시 두 하위 단계로 나뉜다. 먼저 Mutating Admission Webhook들이 순서대로 실행되며 오브젝트를 수정할 수 있다(예: 사이드카 컨테이너 자동 주입, 누락된 라벨 채우기). 이어서 스키마 검증을 거친 뒤, Validating Admission Webhook들이 병렬로 실행되며 오브젝트를 검사만 하고 거부하거나 통과시킨다. 이 순서가 중요한 이유는, Mutating 단계에서 수정된 최종 형태를 기준으로 Validating 단계가 검사를 수행하기 때문이다 — 검증 로직이 원본이 아니라 수정 후 오브젝트를 봐야 한다는 뜻이다.

## 핵심 개념 2 — 웹훅은 결국 외부 HTTP 서버다

Admission Webhook의 실체는 API 서버가 특정 리소스·동작(CREATE, UPDATE, DELETE)에 대해 HTTPS로 호출하는 외부 서버다. API 서버는 `AdmissionReview` 오브젝트를 요청 본문으로 보내고, 웹훅 서버는 허용 여부와 (Mutating이라면) JSON Patch를 담아 응답한다. 이 구조 때문에 웹훅 서버 자체의 가용성이 곧 클러스터의 파드 생성 가용성과 직결된다. `failurePolicy`를 `Fail`로 두면 웹훅 서버가 응답하지 않을 때 해당 리소스 생성 자체가 전부 막히고, `Ignore`로 두면 웹훅이 죽어도 검증 없이 통과시킨다. 보안이 중요한 웹훅(예: 이미지 서명 검증)은 `Fail`을, 부가 기능 웹훅은 `Ignore`를 택하는 것이 일반적이지만, `Fail` 설정에서 웹훅 배포 자체가 클러스터 부트스트랩을 막는 순환 의존성 문제가 실무에서 자주 발생한다.

| 설정 | 웹훅 서버 다운 시 동작 | 적합한 용도 |
|---|---|---|
| failurePolicy: Fail | 해당 요청 전체 거부 | 보안 정책, 컴플라이언스 강제 |
| failurePolicy: Ignore | 검증 생략하고 통과 | 부가 기능, 자동 라벨링 |
| namespaceSelector로 kube-system 제외 | - | 순환 의존성·클러스터 부트스트랩 보호 |

## 코드 예제 — 리소스 제한 미설정을 막는 ValidatingWebhookConfiguration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: require-resource-limits
webhooks:
  - name: resource-limits.example.com
    clientConfig:
      service:
        name: policy-webhook-svc
        namespace: policy-system
        path: "/validate-pods"
      caBundle: <base64-encoded-ca-cert>
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE"]
        resources: ["pods"]
    failurePolicy: Fail
    namespaceSelector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values: ["kube-system"]
    sideEffects: None
    admissionReviewVersions: ["v1"]
```

`namespaceSelector`로 시스템 네임스페이스를 제외하지 않으면, 웹훅 배포 자체가 새 파드 생성을 필요로 할 때 자기 자신 때문에 막히는 교착 상태에 빠질 수 있다.

## 실무 포인트

- **웹훅 서버는 반드시 고가용성으로 배포해야 한다.** `failurePolicy: Fail`을 쓴다면 웹훅 서버 레플리카가 한 대뿐일 때 그 파드가 재시작되는 짧은 순간 클러스터 전체의 파드 생성이 멈출 수 있다.
- **타임아웃을 짧게 설정해야 한다.** 기본 10초 타임아웃 동안 웹훅이 응답하지 않으면 요청 전체가 지연되므로, 실제로는 1~2초 이내에 응답하도록 웹훅 로직을 가볍게 유지해야 한다.
- **OPA Gatekeeper·Kyverno 같은 정책 엔진을 직접 웹훅을 작성하는 대신 고려하라.** 대부분의 정책 강제 요구사항은 이미 성숙한 정책 엔진으로 선언적으로 표현 가능하며, 커스텀 웹훅 서버 운영 부담을 줄여준다.

## 마무리 요약

- Admission Webhook은 인증·인가를 통과한 요청이 etcd에 저장되기 직전, Mutating(수정)과 Validating(검증) 두 단계로 나뉘어 실행되는 API 서버의 확장점이다.
- 웹훅은 API 서버가 호출하는 외부 HTTPS 서버이므로, failurePolicy 설정에 따라 웹훅 서버의 가용성이 곧 클러스터 리소스 생성 가용성이 된다.
- 순환 의존성을 피하려면 시스템 네임스페이스 제외, 짧은 타임아웃, 고가용성 배포가 필수이며, 커스텀 구현 전에 OPA Gatekeeper·Kyverno 같은 기존 정책 엔진을 검토하는 편이 안전하다.

## 참고 자료

- [Kubernetes 공식 문서 — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [Kyverno 공식 문서](https://kyverno.io/docs/)
