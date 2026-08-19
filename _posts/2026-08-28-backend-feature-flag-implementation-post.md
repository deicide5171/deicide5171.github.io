---
layout: single
title: "피처 플래그, 직접 만들 것인가 LaunchDarkly를 쓸 것인가 — 백엔드 구현 실전"
date: 2026-08-28 12:25:00 +0530
categories: backend
tags: ["backend", "feature-flag", "launchdarkly", "spring-boot", "deployment"]
toc: true
toc_sticky: true
excerpt: "배포와 기능 노출을 분리하는 피처 플래그를 자체 구현할 때 필요한 최소 구조와, LaunchDarkly·Unleash 같은 전용 도구가 그 위에 추가로 해결해주는 문제를 비교해 언제 무엇을 선택할지 정리한다."
---

배포(deploy)와 릴리스(release)를 분리하는 것이 피처 플래그의 핵심 가치다. 코드는 프로덕션에 배포됐지만 기능은 아직 사용자에게 보이지 않는 상태를 만들 수 있으면, 배포 자체의 위험도가 크게 줄어든다. 문제가 생기면 재배포 없이 플래그만 끄면 되고, 특정 사용자군에게만 먼저 노출하는 카나리 릴리스도 코드 배포와 무관하게 진행할 수 있다.

그런데 피처 플래그를 "얼마나 진지하게" 구현할지는 팀마다 크게 갈린다. `if (config.getBoolean("new-feature"))` 한 줄로 시작한 플래그가 몇 년 뒤 수백 개로 불어나 아무도 지우지 못하는 코드 잔해가 되는 경우도 흔하고, 반대로 처음부터 LaunchDarkly 같은 전용 SaaS를 도입했다가 실제로 쓰는 기능은 온오프 스위치 몇 개뿐이라 비용 대비 효용이 안 맞는 경우도 있다. 이 글에서는 피처 플래그를 자체 구현할 때 반드시 있어야 하는 최소 구조와, 전용 도구가 그 위에 추가로 풀어주는 문제를 비교한다.

## 핵심 개념 1: 피처 플래그의 네 가지 유형

모든 피처 플래그가 같은 목적을 갖는 것은 아니다. Martin Fowler의 분류를 실무에 맞게 정리하면 다음과 같다.

| 유형 | 목적 | 수명 |
|---|---|---|
| 릴리스 플래그(release toggle) | 미완성 기능을 배포하되 숨김 | 짧음(기능 완성 후 제거) |
| 실험 플래그(experiment toggle) | A/B 테스트, 특정 그룹에만 노출 | 실험 기간 동안만 |
| 운영 플래그(ops toggle) | 장애 시 특정 기능을 긴급 차단(킬 스위치) | 김(상시 유지) |
| 권한 플래그(permission toggle) | 요금제·권한에 따라 기능 노출 차등 | 매우 김(비즈니스 로직에 가까움) |

이 분류가 중요한 이유는, 유형마다 "언제 지워도 되는가"의 기준이 다르기 때문이다. 릴리스 플래그는 기능이 안정화되면 반드시 제거해야 하는 임시 코드지만, 권한 플래그는 사실상 영구적인 비즈니스 로직이라 같은 방식으로 관리하면 안 된다. 이 구분 없이 모든 플래그를 한 시스템에 뭉뚱그리면 "언제 지워야 할지 아무도 모르는" 플래그가 계속 쌓인다.

## 핵심 개념 2: 자체 구현의 최소 구조

가장 단순한 형태는 설정 파일이나 DB 테이블에 `flag_key`, `enabled` 컬럼만 두고 조회하는 것이지만, 이것만으로는 카나리 릴리스나 사용자별 타겟팅을 할 수 없다. 실무에서 최소한으로 필요한 구조는 다음 세 가지다.

1. **평가 컨텍스트(evaluation context)**: 어떤 사용자, 어떤 환경(dev/staging/prod)에서 평가하는지를 담는 객체. 사용자 ID, 소속 그룹, 요금제 등이 여기 들어간다.
2. **규칙 기반 평가**: 단순 on/off가 아니라 "요금제가 enterprise인 사용자 중 10%"처럼 조건과 퍼센티지 롤아웃을 함께 평가하는 로직.
3. **캐시된 로컬 평가**: 매 요청마다 원격 설정 서버를 호출하면 지연이 누적되므로, 플래그 설정을 로컬에 주기적으로 동기화해두고 평가 자체는 로컬 메모리에서 수행한다.

## 핵심 개념 3: 전용 도구(LaunchDarkly, Unleash)가 추가로 푸는 문제

자체 구현으로 위 세 가지를 갖추고 나면 "이 정도면 충분하지 않나"라는 생각이 들 수 있지만, 전용 도구는 그 위에 조직 운영 관점의 문제를 추가로 해결한다. **감사 추적**(누가 언제 어떤 플래그를 바꿨는지), **점진적 롤아웃 자동화**(1% → 5% → 25%처럼 시간에 따라 자동 확대), **다중 환경 동기화**(같은 플래그 정의를 dev/staging/prod에 안전하게 전파), **비개발자용 관리 UI**(PM이 코드 배포 없이 플래그를 직접 조작)가 대표적이다.

| 기준 | 자체 구현 | LaunchDarkly / Unleash |
|---|---|---|
| 초기 구축 비용 | 낮음(수 일) | 낮음(SaaS 가입, Unleash는 자체 호스팅도 가능) |
| 운영 비용 | 팀이 직접 유지보수 | 사용자/MAU 기반 과금(LD), 무료 오픈소스(Unleash 자체호스팅) |
| 감사·거버넌스 | 직접 구현 필요 | 기본 제공 |
| 비개발자 접근성 | 낮음(관리 UI 직접 구축 필요) | 높음(전용 대시보드) |
| 벤더 종속 | 없음 | 있음(SaaS) 또는 낮음(Unleash OSS) |

## 예제: Spring Boot에서 자체 구현 최소 버전

```java
public record EvaluationContext(String userId, String plan, String environment) {}

@Component
public class FeatureFlagEvaluator {

    private final Map<String, FlagRule> localCache; // 원격 설정 서버에서 주기 동기화됨

    public boolean isEnabled(String flagKey, EvaluationContext ctx) {
        FlagRule rule = localCache.get(flagKey);
        if (rule == null || !rule.enabled()) {
            return false; // 정의 안 된 플래그는 안전하게 off
        }
        if (rule.targetPlans() != null && !rule.targetPlans().contains(ctx.plan())) {
            return false;
        }
        // 사용자 ID 해시 기반 퍼센티지 롤아웃 - 같은 사용자는 항상 같은 결과
        int bucket = Math.abs(ctx.userId().hashCode()) % 100;
        return bucket < rule.rolloutPercentage();
    }
}
```

```java
@GetMapping("/checkout")
public ResponseEntity<?> checkout(@AuthenticationPrincipal User user) {
    var ctx = new EvaluationContext(user.getId(), user.getPlan(), activeProfile);
    if (featureFlagEvaluator.isEnabled("new-checkout-flow", ctx)) {
        return newCheckoutService.process(user);
    }
    return legacyCheckoutService.process(user);
}
```

퍼센티지 롤아웃에서 사용자 ID를 해시해 버킷을 결정하는 방식은 **같은 사용자가 새로고침할 때마다 다른 결과를 보지 않도록** 일관성을 보장하는 핵심 장치다. 매번 난수를 새로 뽑으면 사용자가 배정된 그룹을 왔다 갔다 하게 되어 실험 결과와 사용자 경험 모두 망가진다.

## 실무 포인트

- **릴리스 플래그는 제거 기한을 티켓으로 걸어둘 것**: 기능이 안정화된 뒤에도 남아있는 릴리스 플래그는 코드 복잡도만 높인다. 플래그 생성 시점에 제거 기한 티켓을 함께 만드는 습관이 누적을 막는다.
- **로컬 캐시의 폴백 값을 반드시 정할 것**: 설정 서버 장애나 네트워크 단절 시 로컬 캐시가 비어 있으면 어떤 값을 반환할지(안전하게 off인지, 마지막으로 알려진 값인지)를 명시적으로 결정해둬야 장애가 연쇄되지 않는다.
- **팀 규모와 플래그 개수로 도구를 결정할 것**: 킬 스위치 몇 개, 팀 규모가 작다면 자체 구현으로 충분하다. 여러 팀이 수십~수백 개 플래그를 운영하고 비개발자의 참여가 필요하다면 감사·거버넌스가 갖춰진 전용 도구의 비용이 자체 구축·유지보수 비용보다 합리적일 때가 많다.

## 3줄 요약

- 피처 플래그는 배포와 릴리스를 분리하는 도구지만, 릴리스/실험/운영/권한 네 가지 유형은 수명과 관리 방식이 다르므로 구분해서 다뤄야 한다.
- 자체 구현의 최소 구조는 평가 컨텍스트, 규칙 기반 평가, 로컬 캐시 동기화 세 가지이며 사용자 해시 기반 버킷팅으로 롤아웃 일관성을 보장해야 한다.
- 전용 도구는 감사 추적·점진적 롤아웃 자동화·비개발자 접근성을 추가로 제공하므로, 플래그 규모와 조직 구조에 따라 자체 구현과 전용 도구 중 비용 대비 효용을 따져 선택해야 한다.

## 참고 자료

- [Martin Fowler: Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)
- [LaunchDarkly 공식 문서: Feature Flag Best Practices](https://docs.launchdarkly.com/guides/flags/flag-best-practices)
- [Unleash 공식 문서: Feature Flag Types](https://docs.getunleash.io/reference/feature-toggle-types)
