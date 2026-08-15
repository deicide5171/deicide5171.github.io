---
layout: single
title: "서비스 메시, 어디부터 붙여야 할까 — Istio vs Linkerd 도입 실전 가이드"
date: 2026-08-18 13:40:00 +0530
categories: infra
tags: ["istio", "linkerd", "servicemesh", "sidecar", "mtls", "쿠버네티스"]
toc: true
toc_sticky: true
excerpt: "Istio와 Linkerd 중 무엇을 고를지보다 먼저, 사이드카를 몇 개 네임스페이스에 어떤 순서로 붙일지가 서비스 메시 도입의 성패를 가른다는 점을 실전 절차 중심으로 정리한다."
---

## 왜 지금 서비스 메시 도입을 실전으로 고민해야 하는가

서비스 메시를 "쓸 것인가 말 것인가"는 이미 많이 다뤄진 질문이다. 지금 실무에서 부딪히는 진짜 질문은 다르다. 도입하기로 정한 뒤 **어느 도구를 고를지, 그리고 그 도구를 어떤 순서로 클러스터에 붙여나갈지**다. Istio를 통째로 설치하고 나서 사이드카 리소스 사용량에 놀라거나, Linkerd로 가볍게 시작했다가 나중에 세밀한 트래픽 제어가 필요해져 다시 검토하는 사례가 반복되는 이유도 여기에 있다.

이 글은 API Gateway와 Service Mesh의 책임 범위를 나누는 개념 비교가 아니라, 이미 Service Mesh를 쓰기로 한 팀이 실제로 Istio와 Linkerd 중 무엇을 고르고 어떤 절차로 붙여나가는지에 초점을 맞춘다. 아키텍처 차이가 실제 운영 부담으로 어떻게 이어지는지, 그리고 전체 클러스터에 한 번에 켜지 않고 단계적으로 도입하는 방법을 정리한다.

## 핵심 개념 1: Istio와 Linkerd, 아키텍처가 다른 이유

두 프로젝트 모두 사이드카 프록시를 통해 mTLS·재시도·관측성을 제공한다는 목표는 같지만, 그 목표에 도달하는 방식과 그로 인한 운영 부담은 다르다.

| 구분 | Istio | Linkerd |
|---|---|---|
| 데이터 플레인 프록시 | Envoy (범용, 기능 풍부) | linkerd2-proxy (Rust, 경량 전용 구현) |
| 컨트롤 플레인 | Istiod (단일 바이너리로 통합) | linkerd-controller (컴포넌트 분리) |
| 사이드카 없는 모드 | Ambient 모드 제공(성숙도는 도입 시점에 직접 확인 필요) | 사이드카 모델이 기본 |
| 트래픽 제어 세밀도 | 매우 높음(EnvoyFilter, WASM 확장) | 상대적으로 단순(핵심 기능에 집중) |
| 기본 진입 장벽 | 설정 항목이 많아 학습 곡선이 가파름 | CLI·기본값이 단순해 초기 도입이 빠른 편 |

이 차이는 "어떤 기능을 지원하는가"보다 "장애가 났을 때 무엇을 디버깅해야 하는가"에서 더 크게 체감된다. Istio는 세밀한 제어가 가능한 만큼 설정 리소스(VirtualService, DestinationRule, EnvoyFilter 등)가 서로 얽힐 여지가 많고, Linkerd는 기능을 의도적으로 좁게 유지해 설정 표면이 작다. 팀의 운영 인력 규모와 트래픽 제어 요구 수준을 먼저 냉정하게 가늠하는 것이 도구 선택보다 우선이다.

## 핵심 개념 2: 한 번에 다 켜지 않는다 — 단계적 도입 전략

서비스 메시 장애 사례 대부분은 "기능이 부족해서"가 아니라 "한 번에 너무 많은 네임스페이스에 동시 적용해서" 생긴다. 아래와 같은 단계적 롤아웃이 안전하다.

| 단계 | 범위 | 목표 |
|---|---|---|
| 1 | 컨트롤 플레인만 설치 | 사이드카 주입 없이 컨트롤 플레인 안정성부터 확인 |
| 2 | 테스트 네임스페이스 1개 | 사이드카 주입·리소스 오버헤드 실측 |
| 3 | mTLS PERMISSIVE 모드 | 평문·mTLS 트래픽을 동시 허용하며 점진 전환 |
| 4 | 핵심 서비스 일부 확대 | 회로 차단·재시도 정책을 실제 트래픽에 검증 |
| 5 | mTLS STRICT 전환 + 전체 확대 | 검증된 네임스페이스부터 순차적으로 강제 적용 |

특히 3단계의 PERMISSIVE 모드를 건너뛰고 곧바로 STRICT를 적용하면, 아직 사이드카가 붙지 않은 서비스와의 통신이 갑자기 끊기는 사고로 이어지기 쉽다. 전환 일정은 팀 내부 사정에 따라 다르므로 특정 기간을 못박기보다, 각 단계에서 오류율·지연시간 지표가 안정된 뒤 다음 단계로 넘어가는 기준을 팀 내에서 합의해두는 편이 안전하다.

## 예제 1: Istio — 네임스페이스 단위 사이드카 주입과 mTLS 단계적 전환

```yaml
# 1) 특정 네임스페이스에만 사이드카 자동 주입 라벨 적용
apiVersion: v1
kind: Namespace
metadata:
  name: checkout
  labels:
    istio-injection: enabled
---
# 2) 해당 네임스페이스에 mTLS를 PERMISSIVE로 먼저 적용
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: checkout
spec:
  mtls:
    mode: PERMISSIVE   # 검증 끝난 뒤 STRICT로 전환
```

`istio-injection` 라벨을 네임스페이스 단위로 붙이면 클러스터 전체가 아니라 지정한 네임스페이스의 파드에만 사이드카가 주입된다. `PeerAuthentication`의 `mode`를 `PERMISSIVE`로 시작해 평문·mTLS 트래픽을 함께 받아들이며 지표를 관찰한 뒤, 문제가 없을 때 `STRICT`로 바꿔 mTLS를 강제하는 순서가 안전하다.

## 예제 2: Linkerd — 설치 검증과 서비스별 재시도 정책

```yaml
# linkerd CLI로 클러스터 사전 점검 (설치 전 필수)
# $ linkerd check --pre
# $ linkerd install | kubectl apply -f -
# $ linkerd check

# 서비스별 재시도 예산을 제한하는 ServiceProfile 예시
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: orders.checkout.svc.cluster.local
  namespace: checkout
spec:
  routes:
    - name: GET /orders
      condition:
        method: GET
        pathRegex: /orders
      isRetryable: true
  retryBudget:
    retryRatio: 0.2        # 원본 요청 대비 재시도 허용 비율
    minRetriesPerSecond: 10
    ttl: 10s
```

Linkerd는 설치 전 `linkerd check --pre`로 클러스터 사전 요건을 검증하는 단계를 CLI에 내장하고 있다. `ServiceProfile`의 `retryBudget`은 재시도를 무제한 허용하지 않고 원본 트래픽 대비 일정 비율로 제한해, 장애 시 재시도가 트래픽을 눈덩이처럼 불리는 상황(retry storm)을 막는다.

## 실무 포인트

- **사이드카 리소스 요청·제한을 반드시 명시한다**: 사이드카 프록시도 하나의 컨테이너이므로 CPU·메모리 request/limit을 지정하지 않으면 파드 전체 스케줄링과 QoS에 영향을 준다. 실측 없이 기본값만 믿지 말고 부하 테스트로 확인한다.
- **컨트롤 플레인 업그레이드 전략을 미리 정한다**: Istio는 revision 기반으로 신구 컨트롤 플레인을 함께 운영하며 네임스페이스를 순차 이전하는 방식을 지원한다. 업그레이드 중 사이드카 버전 불일치 구간이 생길 수 있다는 점을 감안한다.
- **관측성 도구를 처음부터 함께 붙인다**: Istio는 Kiali·Grafana, Linkerd는 자체 `linkerd viz` 확장으로 트래픽을 시각화한다. 메시를 붙이고 나서 관측 도구를 나중에 연동하면 초기 문제 진단이 훨씬 어려워진다.
- **모든 네임스페이스에 동시에 강제하지 않는다**: 팀 조직이 여러 개라면 네임스페이스별로 도입 속도가 다를 수밖에 없다. 전체 강제 적용 일정을 먼저 정하기보다, 네임스페이스별 롤아웃 완료 여부를 추적하는 체크리스트를 운영하는 편이 현실적이다.

## 3줄 요약

- Istio는 세밀한 트래픽 제어와 확장성을, Linkerd는 단순한 설정 표면과 가벼운 데이터 플레인을 우선한다는 아키텍처 차이가 실제 운영 부담을 가른다.
- 서비스 메시 장애는 대개 기능 부족이 아니라 한 번에 너무 넓은 범위에 적용해서 발생하므로, 네임스페이스 단위·PERMISSIVE→STRICT mTLS 전환 같은 단계적 롤아웃이 안전하다.
- 사이드카 리소스 실측, 컨트롤 플레인 업그레이드 전략, 관측성 도구 연동을 도입 초기부터 함께 설계해야 나중에 디버깅 비용을 줄일 수 있다.

## 참고 자료

- [Istio 공식 문서 — Installation Guides](https://istio.io/latest/docs/setup/install/)
- [Istio 공식 문서 — Mutual TLS Migration](https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/)
- [Linkerd 공식 문서 — Installing Linkerd](https://linkerd.io/2/tasks/install/)
- [Linkerd 공식 문서 — Retries and Timeouts](https://linkerd.io/2/features/retries-and-timeouts/)
