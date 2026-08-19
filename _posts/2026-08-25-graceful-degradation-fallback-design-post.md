---
layout: single
title: "다 죽지 말고 조금만 아프자 — 점진적 성능 저하(Graceful Degradation)와 폴백 설계"
date: 2026-08-25 12:45:00 +0530
categories: system-design
tags: ["graceful-degradation", "fallback", "resilience", "load-shedding", "system-design"]
toc: true
toc_sticky: true
excerpt: "의존 서비스가 흔들릴 때 전체 응답을 실패시키는 대신 기능 등급을 낮춰 서비스를 이어가는 점진적 성능 저하 설계를, 서킷 브레이커와 구분되는 관점에서 정리한다."
---

추천 서비스가 죽었다고 상품 상세 페이지 전체가 502를 뱉는 게 맞을까? 개인화 배너 API가 타임아웃 났다고 장바구니 결제까지 막혀야 할까? 많은 장애 사후 분석에서 반복되는 패턴은, 시스템의 핵심 기능이 아니라 **부가 기능 하나가 흔들리면서 전체가 함께 무너졌다**는 것이다. 서킷 브레이커나 타임아웃 같은 개별 호출 단위의 방어 패턴은 이미 익숙하지만, "그 호출이 실패했을 때 사용자에게 무엇을 보여줄 것인가"라는 설계는 종종 코드 곳곳에 임기응변으로 흩어져 있다.

점진적 성능 저하(graceful degradation)는 이 질문에 정면으로 답하는 설계 원칙이다. 장애나 과부하 상황에서 시스템을 "전부 정상" 또는 "전부 실패"의 이분법이 아니라, 기능 등급을 여러 단으로 나눠 상황에 맞게 낮춰가며 서비스를 유지하는 접근이다. 이 글에서는 서킷 브레이커·재시도 같은 개별 호출 보호 패턴과 무엇이 다른지, 그리고 폴백 단계를 어떻게 설계하는지를 정리한다.

## 핵심 개념 1: 서킷 브레이커와 무엇이 다른가

서킷 브레이커, 타임아웃, 재시도는 모두 **하나의 원격 호출**이 실패했을 때 그 호출 자체를 어떻게 다룰지에 대한 패턴이다. 반면 graceful degradation은 그보다 한 단계 위, **사용자에게 보여줄 기능/응답 전체**를 어떻게 조립할지에 대한 설계다. 서킷 브레이커가 "이 호출을 계속 시도할지 말지"를 결정한다면, graceful degradation은 "그 호출이 끊겼을 때 화면에 무엇을 채울지"를 결정한다.

실무에서는 둘이 짝을 이룬다. 서킷 브레이커가 개인화 추천 API 호출을 차단하기로 결정하면, graceful degradation 로직이 그 자리를 인기 상품 목록이나 정적 배너로 채운다. 하나가 실패 감지 장치라면 다른 하나는 그 실패를 사용자 경험으로 흡수하는 장치인 셈이다.

## 핵심 개념 2: 기능 등급을 나누는 기준

효과적인 degradation 설계의 출발점은 기능을 우선순위로 등급화하는 것이다. 보통 세 갈래로 나눈다.

| 등급 | 정의 | 예시 |
|---|---|---|
| 필수(core) | 없으면 서비스 자체가 성립하지 않음 | 로그인, 결제, 재고 확인 |
| 향상(enhanced) | 있으면 좋지만 없어도 핵심 흐름은 유지 | 개인화 추천, 리뷰 요약 |
| 장식(cosmetic) | 완전히 빠져도 사용자 흐름에 영향 없음 | 실시간 방문자 수, 애니메이션 배너 |

장애 상황에서 시스템 자원(스레드, 커넥션, 외부 API 쿼터)이 제한적이라면, 이 등급에 따라 우선순위를 정해 필수 기능부터 자원을 배정하고 장식 기능은 가장 먼저 꺼야 한다. 이 판단을 장애가 터진 후 즉흥적으로 하면 늦는다 — 평상시에 기능 목록을 이 표로 미리 분류해 두는 것 자체가 설계 산출물이다.

## 핵심 개념 3: 폴백의 층위 — 무엇으로 대체할 것인가

같은 기능이라도 폴백 방식은 여러 층위로 설계할 수 있고, 상황에 따라 순서대로 시도한다.

1. **캐시된 이전 응답**: 최신은 아니지만 최근에 성공했던 응답을 그대로 재사용.
2. **정적/기본값 응답**: 개인화 추천 대신 전체 인기 상품 같은 일반화된 기본값.
3. **기능 자체를 숨김**: UI에서 해당 섹션을 아예 렌더링하지 않음.
4. **동기 처리 → 비동기 처리 전환**: 응답 시점에 강제로 채우는 대신 나중에 채워지는 자리로 표시(스켈레톤 UI + 지연 로딩).

어떤 층위를 쓸지는 데이터 신선도 요구 수준과 사용자 경험 영향도로 결정한다. 재고 수량처럼 신선도가 중요한 데이터는 캐시 폴백이 위험할 수 있어 차라리 숨기는 편이 낫고, 배너처럼 신선도가 중요하지 않은 데이터는 캐시 폴백이 최선이다.

## 예제: 등급별 타임아웃과 폴백을 적용한 애그리게이션 (Java, 의사코드)

```java
ProductPageResponse buildPage(String productId) {
    // 필수: 실패 시 전체 요청 실패
    ProductCore core = coreService.get(productId);

    // 향상: 짧은 타임아웃 + 실패 시 폴백, 페이지 자체는 살린다
    List<Recommendation> recs;
    try {
        recs = recommendationClient.withTimeout(150, TimeUnit.MILLISECONDS)
                                    .get(productId);
    } catch (TimeoutException | CircuitOpenException e) {
        recs = fallbackCache.getPopularItems(core.getCategory()); // 캐시 폴백
        metrics.increment("recs.degraded");
    }

    // 장식: 실패하면 그냥 빈 값, 로그도 남기지 않을 정도로 가볍게
    String liveViewerBadge = safeGetOrEmpty(() -> viewerCountClient.get(productId));

    return new ProductPageResponse(core, recs, liveViewerBadge);
}
```

## 실무 포인트

- **degradation은 관측 가능해야 한다**: 폴백이 조용히 발동하면 장애가 언제부터 시작됐는지 아무도 모른다. 폴백 경로를 탈 때마다 메트릭을 남기고, 특정 등급의 degradation이 일정 비율을 넘으면 알림을 울려야 한다.
- **폴백 자체가 또 다른 장애 지점이 되지 않게 한다**: 캐시 폴백을 위한 캐시 저장소가 죽으면 폴백도 실패한다. 폴백 경로는 원본 경로와 다른 인프라, 가능하면 더 단순한 구조를 쓴다.
- **degradation 모드를 정기적으로 훈련한다**: 카오스 엔지니어링 실험으로 의존 서비스를 의도적으로 끊어보고, 실제로 등급이 낮아지며 핵심 기능이 살아남는지 주기적으로 검증하지 않으면 폴백 코드는 아무도 모르는 새 죽어 있는 경우가 많다.

## 3줄 요약

- Graceful degradation은 개별 호출을 보호하는 서킷 브레이커와 달리, 실패한 자리에 무엇을 채울지를 결정하는 사용자 경험 설계다.
- 기능을 필수·향상·장식 등급으로 미리 분류해 두면 장애 상황에서 어떤 기능부터 낮출지를 즉흥적으로 판단하지 않아도 된다.
- 폴백은 캐시 재사용부터 완전 숨김까지 여러 층위로 설계하고, 폴백 발동 자체를 관측 가능하게 만들어야 조용한 성능 저하를 놓치지 않는다.

## 참고 자료

- [Google SRE Book: Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
- [AWS Well-Architected Framework: Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [Netflix Tech Blog: Fault Tolerance in a High Volume, Distributed System](https://netflixtechblog.com/)
