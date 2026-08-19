---
layout: single
title: "배포와 노출을 분리하라 — 프로그레시브 딜리버리와 피처 플래그 인프라 연계"
date: 2026-08-30 12:40:00 +0530
categories: infra
tags: ["infra", "progressive-delivery", "feature-flags", "canary", "kubernetes", "observability"]
toc: true
toc_sticky: true
excerpt: "카나리 배포·서비스 메시 트래픽 분할과 피처 플래그를 함께 묶어, 코드 배포와 기능 노출을 완전히 분리하는 프로그레시브 딜리버리 인프라 구성을 정리한다."
---

카나리 배포는 새 버전을 일부 트래픽에만 흘려보내 문제를 조기에 잡는다. 하지만 카나리로 잡을 수 있는 건 인프라·성능 회귀 정도다. "새 결제 UI가 특정 지역 사용자에게만 이상하게 보인다" 같은 비즈니스 로직 회귀는 카나리 트래픽 비율만으로는 세밀하게 제어하기 어렵다. 반대로 피처 플래그는 사용자 속성 기반으로 정교하게 노출을 제어하지만, 플래그 온오프 자체가 배포 파이프라인과 분리돼 있으면 "언제 이 플래그를 켰길래 장애가 났는가"를 배포 이력과 따로 추적해야 한다.

**프로그레시브 딜리버리(Progressive Delivery)**는 이 둘을 하나의 파이프라인으로 묶는다. 배포는 인프라 레벨(카나리, 블루-그린, 트래픽 분할)에서 점진적으로 진행하고, 그 위에서 기능 노출은 피처 플래그로 더 세밀하게 통제하며, 두 신호(배포 진행률 + 플래그 상태)를 관측 지표와 연동해 자동으로 롤백 판단까지 내리는 구조다. 이 글에서는 배포 인프라와 피처 플래그 시스템이 실제로 어떻게 연동되는지, 그리고 그 연동에서 흔히 놓치는 지점을 정리한다.

## 핵심 개념 1: 배포 축과 노출 축의 분리

프로그레시브 딜리버리를 이해하는 가장 쉬운 방법은 두 개의 독립된 축을 떠올리는 것이다. **배포 축**은 "새 코드가 얼마나 많은 인스턴스/파드에 떠 있는가"를 다루고, Argo Rollouts나 Flagger 같은 도구가 서비스 메시(Istio, Linkerd)나 인그레스 컨트롤러의 트래픽 분할 기능을 이용해 5% → 25% → 50% → 100% 식으로 새 버전 비중을 늘린다. **노출 축**은 "코드가 떠 있는 것과 무관하게, 어떤 사용자에게 어떤 기능이 보이는가"를 다루고, LaunchDarkly·Unleash·Flagsmith 같은 피처 플래그 시스템이 사용자 ID, 지역, 플랜 등급 같은 속성 기준으로 제어한다.

이 분리의 실무적 이점은 명확하다. 배포는 안전하게 100%까지 끝냈지만 기능 자체는 아직 아무에게도 안 보이게(다크 런치, dark launch) 유지할 수 있고, 반대로 배포가 진행 중인 상태에서도 이미 배포된 인스턴스의 새 기능만 내부 QA 계정에 먼저 노출하는 것도 가능하다. 배포와 릴리스가 같은 이벤트일 필요가 없어진다.

## 핵심 개념 2: 두 시스템을 연동할 때의 신호 구조

두 시스템을 각자 따로 운영하면 "카나리는 통과했는데 특정 플래그 조합에서만 에러율이 튀는" 상황을 진단하기 어렵다. 실전에서는 배포 도구의 카나리 분석 단계에 피처 플래그 상태를 관측 라벨로 심는다 — 메트릭에 `deployment_version`뿐 아니라 `flag_variant` 같은 차원을 함께 붙여, 카나리 자동 분석(Flagger의 metric provider, Argo Rollouts의 AnalysisTemplate)이 "새 버전 + 특정 플래그 조합"의 조합별 에러율까지 비교하게 만드는 식이다.

| 구분 | 배포 축(카나리/블루-그린) | 노출 축(피처 플래그) |
|---|---|---|
| 제어 단위 | 인스턴스/파드 비율 | 사용자·세그먼트 속성 |
| 롤백 방법 | 트래픽 가중치 되돌리기 | 플래그 즉시 off |
| 롤백 속도 | 수 분(재배포·트래픽 전환) | 즉시(설정 값만 변경) |
| 실패 원인 격리 | 버전 단위 | 기능 단위 |
| 적합한 시나리오 | 인프라·성능 회귀 | 비즈니스 로직·UX 회귀 |

가장 흔한 실무 패턴은 "위험한 변경은 반드시 새 코드 배포(카나리로 인프라 안전 확인) + 신규 플래그 뒤에 숨김(기본 off) 조합으로 나간다"는 것이다. 배포가 100%까지 끝난 뒤에야 플래그를 단계적으로 올리기 시작하면, 배포로 인한 회귀와 기능으로 인한 회귀를 시간축에서 분리해 진단할 수 있다.

## 핵심 개념 3: 플래그가 늘어날수록 커지는 부채

피처 플래그 인프라의 함정은 기술이 아니라 운영이다. 플래그가 수백 개로 늘어나면 코드 안에 `if (flag.isEnabled(...))` 분기가 곳곳에 쌓이고, 이미 100% 롤아웃이 끝나 영구화된 플래그를 제거하지 않으면 코드 경로 조합이 기하급수적으로 늘어 테스트 커버리지가 뚫린다. 또한 서버사이드 평가(플래그 SDK가 서버에서 평가)와 클라이언트사이드 평가(브라우저에서 평가)를 혼용하면, 같은 사용자가 새로고침 시점에 따라 다른 변형을 보는 플리커링 문제도 생긴다.

## 예제: Argo Rollouts + 피처 플래그 라벨 연동

```yaml
# rollout.yaml — 카나리 분석에 flag_variant 차원을 포함
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: checkout-service
spec:
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: { duration: 5m }
        - analysis:
            templates:
              - templateName: error-rate-by-flag
        - setWeight: 50
        - pause: { duration: 10m }
        - setWeight: 100
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-rate-by-flag
spec:
  metrics:
    - name: error-rate-new-checkout-flag
      interval: 1m
      successCondition: result < 0.02
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(http_requests_total{
              version="canary", flag_variant="new-checkout-on", status="5xx"
            }[2m]))
            /
            sum(rate(http_requests_total{
              version="canary", flag_variant="new-checkout-on"
            }[2m]))
```

이 구성은 카나리 버전 중에서도 특정 플래그가 켜진 트래픽만 따로 떼어 에러율을 검사한다. 카나리 자체는 정상이어도 특정 플래그 조합에서만 실패율이 튀면 이 분석 단계에서 자동으로 롤아웃이 중단된다.

## 실무 포인트

- **플래그 수명주기를 배포 파이프라인의 일부로 관리해야 한다.** 롤아웃이 100%로 끝난 플래그는 일정 기간(예: 2주) 뒤 코드에서 물리적으로 제거하는 절차를 CI에 강제하지 않으면, "죽은 플래그"가 계속 쌓여 코드 복잡도와 테스트 조합 폭발을 만든다.
- **킬 스위치와 점진적 롤아웃 플래그는 분리해서 관리한다.** 장애 시 즉시 꺼야 하는 킬 스위치 플래그는 평가 지연이 없어야 하므로 캐시 무효화 전파 시간을 별도로 관리해야 하고, 점진적 롤아웃 플래그와 같은 인프라를 쓰더라도 알림·대응 절차는 다르게 설계해야 한다.
- **평가 위치(서버 vs 클라이언트) 혼용을 문서화하라.** SSR 페이지에서 서버가 평가한 플래그 값과 하이드레이션 후 클라이언트 SDK가 재평가한 값이 다르면 화면이 깜빡이거나 불일치가 생긴다. 초기 값은 서버에서 내려주고 클라이언트는 그 값을 그대로 이어받는 방식으로 통일하는 것이 안전하다.

## 3줄 요약

- 프로그레시브 딜리버리는 코드 배포(카나리·블루-그린)와 기능 노출(피처 플래그)을 서로 다른 축으로 분리해, 배포 안전성 검증과 비즈니스 로직 회귀 진단을 독립적으로 수행할 수 있게 한다.
- 카나리 분석 지표에 플래그 상태를 관측 차원으로 함께 심으면, 배포 자체는 정상인데 특정 플래그 조합에서만 실패율이 튀는 상황까지 자동으로 잡아낼 수 있다.
- 플래그가 늘어날수록 코드 복잡도와 테스트 조합이 기하급수적으로 늘어나므로, 롤아웃이 끝난 플래그를 제거하는 절차와 킬 스위치·점진적 롤아웃 플래그의 운영 방식 분리가 반드시 필요하다.

## 참고 자료

- [Argo Rollouts 공식 문서: Progressive Delivery](https://argo-rollouts.readthedocs.io/en/stable/)
- [Flagger 공식 문서: Progressive Delivery Operator](https://docs.flagger.app/)
- [LaunchDarkly 공식 문서: Feature Flag Best Practices](https://docs.launchdarkly.com/guides/best-practices)
- [CNCF 블로그: Progressive Delivery](https://www.cncf.io/blog/2020/07/07/progressive-delivery-what-you-need-to-know/)
