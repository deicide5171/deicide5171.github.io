---
layout: single
title: "멀티테넌트 SaaS 아키텍처 — Pool vs Silo 모델과 Noisy Neighbor 격리 전략"
date: 2026-09-25 13:45:00 +0530
categories: system-design
tags: ["멀티테넌시", "SaaS아키텍처", "NoisyNeighbor", "테넌트격리", "확장성"]
toc: true
toc_sticky: true
excerpt: "고객사 한 곳이 대량 배치 작업을 돌리는 순간 같은 인프라를 쓰는 다른 고객사 전체가 느려지는 Noisy Neighbor 문제를, 테넌트를 어떻게 묶고 나눌지 결정하는 Pool·Silo·Bridge 모델의 트레이드오프로 정리했다."
---

## 왜 지금 멀티테넌시 아키텍처를 다시 봐야 하는가

SaaS 제품이 고객사(테넌트)를 하나둘 늘려가다 보면 반드시 마주치는 질문이 있다. 새 고객사가 들어올 때마다 완전히 별도의 인프라를 준다면 안전하지만 비용이 선형으로 늘어나고, 반대로 모든 고객사가 같은 애플리케이션·DB 인스턴스를 공유하면 비용은 아끼지만 한 고객사의 트래픽 폭주나 무거운 배치 작업이 다른 모든 고객사의 응답 속도를 함께 끌어내리는 "Noisy Neighbor" 문제가 생긴다. 초기에는 단순히 "공유냐 분리냐"의 이분법으로 접근하기 쉽지만, 실제로는 컴퓨트·데이터베이스·큐 등 리소스 종류별로 격리 수준을 다르게 가져가는 것이 정답에 가깝다. 고객사 수가 늘고 엔터프라이즈 계약이 데이터 격리를 계약 조건으로 요구하기 시작하면, 이 결정을 뒤늦게 바꾸는 비용은 처음부터 신중히 설계하는 비용보다 훨씬 크다.

## 핵심 개념 1 — Pool, Silo, Bridge 세 가지 배치 모델

Pool 모델은 모든 테넌트가 동일한 애플리케이션 인스턴스와 데이터 저장소를 공유하고, 테넌트 구분은 오직 데이터 행의 `tenant_id` 컬럼 같은 논리적 경계로만 이뤄진다. 인프라 비용이 가장 낮고 운영 부담(배포·모니터링 대상)이 적지만, 리소스 격리가 전혀 없어 Noisy Neighbor에 가장 취약하다. Silo 모델은 정반대로, 테넌트마다 별도의 애플리케이션 인스턴스와 DB를 완전히 분리해서 프로비저닝한다. 격리는 완벽하지만 테넌트 수만큼 인프라가 곱해지므로 비용과 운영 복잡도가 가장 크다. Bridge(하이브리드) 모델은 이 둘 사이에서, 예를 들어 컴퓨트는 공유하되 DB는 테넌트 등급(일반/엔터프라이즈)에 따라 공유 스키마와 전용 인스턴스로 나누는 식으로 리소스별로 다른 격리 수준을 적용한다. 실무에서는 처음엔 Pool로 시작해 특정 리소스만 선택적으로 Silo화하는 방향으로 진화하는 경우가 많다.

## 핵심 개념 2 — Noisy Neighbor를 막는 리소스별 격리 장치

Pool 모델의 비용 이점을 유지하면서 Noisy Neighbor를 완화하려면 리소스별로 별도의 안전장치가 필요하다. 컴퓨트 레벨에서는 테넌트별 요청에 Rate Limiting과 동시성 상한을 걸어 한 테넌트가 스레드 풀이나 커넥션 풀을 독점하지 못하게 막는다. 데이터베이스 레벨에서는 PostgreSQL의 리소스 그룹이나 커넥션 풀러(PgBouncer)의 테넌트별 풀 분리, 또는 무거운 쿼리를 실행하는 테넌트를 자동 탐지해 별도 읽기 복제본으로 라우팅하는 방식을 쓴다. 메시지 큐 레벨에서는 테넌트별로 별도 큐나 파티션을 두어, 한 테넌트의 메시지 폭주가 다른 테넌트의 처리 지연으로 이어지지 않게 한다. 이런 장치들의 공통 원칙은 "완전히 분리하지 않고도, 한 테넌트가 쓸 수 있는 자원의 상한을 명시적으로 그어둔다"는 것이다.

| 모델 | 격리 수준 | 인프라 비용 | 온보딩 속도 | 적합한 대상 |
|---|---|---|---|---|
| Pool | 낮음(논리적 경계만) | 최소 | 빠름 | 초기 스타트업, 소규모 고객 다수 |
| Silo | 완전 | 테넌트 수에 비례 증가 | 느림 | 규제 산업, 데이터 격리 계약 요구 |
| Bridge(하이브리드) | 리소스별 상이 | 중간 | 중간 | 성장 단계, 등급별 요금제 SaaS |

## 예제 — 테넌트별 커넥션 풀 분리와 요청 상한

```yaml
# PgBouncer 설정 예 — 엔터프라이즈 테넌트만 전용 풀 배정
[databases]
tenant_pool_shared = host=shared-db.internal port=5432 dbname=app pool_size=50
tenant_acme_dedicated = host=acme-dedicated-db.internal port=5432 dbname=app pool_size=20
```

```java
// 테넌트별 요청 상한 필터(Spring 의사코드)
@Component
public class TenantRateLimitFilter extends OncePerRequestFilter {
    private final Map<String, RateLimiter> limiters; // 테넌트 등급별로 다른 한도

    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                     FilterChain chain) throws IOException, ServletException {
        String tenantId = resolveTenant(req);
        if (!limiters.get(tenantId).tryAcquire()) {
            res.setStatus(429); // 이 테넌트의 상한 초과 — 다른 테넌트에는 영향 없음
            return;
        }
        chain.doFilter(req, res);
    }
}
```

## 실무 포인트

- **격리 수준을 나중에 올리는 것보다 처음부터 리소스별로 경계를 명확히 그어두는 것이 훨씬 싸다.** Pool 모델의 스키마에 `tenant_id`를 처음부터 모든 테이블에 일관되게 포함시키고, 애플리케이션 레이어에서 그 값을 빠뜨리는 쿼리가 없는지 검증하는 자동화(예: JPA 인터셉터, RLS)를 초기에 갖춰두면 이후 특정 테넌트만 Silo로 분리하는 마이그레이션이 훨씬 수월해진다.
- **PostgreSQL의 Row Level Security(RLS)를 Pool 모델의 안전망으로 적극 활용하라.** 애플리케이션 코드의 `WHERE tenant_id = ?` 누락이라는 사람의 실수를 DB 레벨에서 한 번 더 막아주므로, 논리적 격리의 신뢰도를 크게 높인다.
- **엔터프라이즈 계약에서 요구하는 "물리적 데이터 분리"는 계약서 문구를 정확히 확인해야 한다.** 단순히 암호화 키를 분리하는 것으로 충분한지, 정말 별도 DB 인스턴스가 필요한지에 따라 필요한 아키텍처 변경 범위가 완전히 달라진다.

## 마무리 요약

- Pool은 비용이 가장 낮지만 격리가 없고, Silo는 완전히 격리되지만 비용이 테넌트 수에 비례해 커지며, 대부분의 성장하는 SaaS는 리소스별로 격리 수준을 달리하는 Bridge 모델로 수렴한다.
- Noisy Neighbor는 컴퓨트·DB·큐 각 레이어에 테넌트별 상한과 라우팅 장치를 둠으로써, 완전 분리 없이도 상당 부분 완화할 수 있다.
- 테넌트 격리 전략은 초기 스키마 설계와 자동 검증 체계에 크게 좌우되므로, 온보딩 속도만 보고 설계를 미루면 나중에 훨씬 비싼 마이그레이션을 치르게 된다.

## 참고 자료

- [AWS SaaS Lens - Tenant Isolation](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/tenant-isolation.html)
- [PostgreSQL 공식 문서 - Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
