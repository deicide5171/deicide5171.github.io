---
layout: single
title: "한 DB에 모두 담을까, 테넌트마다 나눌까 — 멀티테넌시 Pool vs Silo 아키텍처"
date: 2026-08-17 13:45:00 +0530
categories: system-design
tags: ["multi-tenancy", "saas", "tenant-isolation", "row-level-security", "architecture"]
toc: true
toc_sticky: true
excerpt: "SaaS에서 여러 고객사(테넌트)의 데이터를 한 DB에 모아 둘지(Pool), 테넌트마다 완전히 분리할지(Silo) 결정하는 기준과 그 사이의 하이브리드 전략을 정리한다."
---

## 왜 지금 멀티테넌시 아키텍처인가

SaaS 제품 하나로 수십, 수백 개의 고객사(테넌트)를 동시에 서비스하는 구조는 이제 특이한 선택이 아니라 기본값에 가깝다. 문제는 "테넌트가 늘어날수록 인프라도 그만큼 늘려야 하는가"라는 질문이다. 테넌트마다 서버와 DB를 통째로 복제하면 운영 비용이 테넌트 수에 비례해 커지고, 반대로 모든 테넌트를 하나의 애플리케이션·DB에 몰아넣으면 한 테넌트의 장애나 트래픽 폭주가 다른 테넌트에게 그대로 전이되는 **노이즈 이웃(Noisy Neighbor)** 문제와, "내 데이터가 다른 회사 데이터와 물리적으로 같은 테이블에 있어도 되는가"라는 보안·규제 질문이 남는다.

이 딜레마를 정리하는 표준 어휘가 **Pool(공유) 모델**과 **Silo(격리) 모델**이다. 초기 스타트업은 대개 개발 속도와 비용 효율을 위해 Pool로 시작하지만, 금융·의료 고객사나 엔터프라이즈 계약이 들어오는 순간 데이터 상주(residency)·감사(audit) 요구 때문에 Silo 격리를 고려하게 된다. 이 글에서는 두 모델의 차이, 그 사이의 격리 스펙트럼, 그리고 실무에서 흔한 하이브리드 전략인 **테넌트 티어링(Tenant Tiering)**을 정리한다.

## 핵심 개념 1: Pool 모델 vs Silo 모델

Pool 모델은 모든 테넌트가 같은 애플리케이션 인스턴스와 같은 데이터베이스를 공유하고, 각 데이터 행에 `tenant_id` 같은 식별 컬럼을 두어 논리적으로만 구분한다. Silo 모델은 반대로 테넌트마다 별도의 DB(또는 애플리케이션 스택 전체)를 두어 물리적으로 격리한다.

| 항목 | Pool 모델 (공유) | Silo 모델 (격리) |
|---|---|---|
| 인프라 비용 | 낮음(자원을 여러 테넌트가 나눠 씀) | 높음(테넌트 수만큼 자원 복제) |
| 데이터 격리 강도 | 논리적 격리(쿼리 조건에 의존) | 물리적 격리(테넌트 간 접근 경로 자체가 분리) |
| 노이즈 이웃 위험 | 있음(한 테넌트의 폭주가 전체에 영향) | 없음(테넌트별 자원 한도가 독립적) |
| 운영 복잡도 | 낮음(배포·모니터링 대상이 하나) | 높음(테넌트 수만큼 배포·마이그레이션 반복) |
| 규제 대응(데이터 상주 등) | 어려움 | 쉬움(테넌트별로 리전·인프라 지정 가능) |
| 적합한 단계 | 초기, 다수의 중소형 테넌트 | 소수의 대형/규제 테넌트 |

## 핵심 개념 2: 격리 스펙트럼 — Row-Level부터 Silo까지

실제로는 "Pool 아니면 Silo"라는 이분법이 아니라, 그 사이에 여러 단계가 있다. DB를 얼마나 잘게 나누느냐에 따라 격리 강도와 운영 비용이 함께 올라간다.

| 단계 | 방식 | 격리 강도 | 대표 구현 |
|---|---|---|---|
| 1. Row-Level (완전 Pool) | 하나의 테이블, `tenant_id` 컬럼으로 구분 | 낮음 | PostgreSQL Row-Level Security(RLS), 애플리케이션 레벨 `WHERE tenant_id = ?` |
| 2. Schema-per-Tenant (Bridge) | 같은 DB 인스턴스, 테넌트마다 별도 스키마 | 중간 | PostgreSQL/Oracle 스키마 분리, Hibernate `MultiTenancyStrategy.SCHEMA` |
| 3. Database-per-Tenant | 같은 서버, 테넌트마다 별도 데이터베이스 | 중간~높음 | 테넌트별 커넥션 풀 라우팅 |
| 4. Silo(Infra-per-Tenant) | 테넌트마다 완전히 별도의 DB 서버·애플리케이션 스택 | 높음 | 테넌트별 독립 배포, 필요 시 리전까지 분리 |

아래는 이 스펙트럼을 도식화한 것이다. Pool은 하나의 테이블 안에서 `tenant_id`로 행을 구분하고, Bridge는 같은 DB 인스턴스 안에서 스키마로 나누며, Silo는 애플리케이션과 DB 스택 자체를 테넌트마다 분리한다.

<img src="/assets/images/posts/2026-08-17-multitenancy-pool-vs-silo-1.svg" alt="멀티테넌시 격리 스펙트럼 - Pool(공유 테이블), Bridge(스키마 분리), Silo(완전 격리 스택) 구조 비교도" style="width:100%;">

## 핵심 개념 3: 테넌트 티어링 — 실무의 하이브리드 전략

전체 테넌트를 하나의 모델로 통일해야 할 이유는 없다. 실무에서는 **요금제 등급에 따라 격리 모델을 다르게 적용하는 티어링**이 흔하다. 무료·스타터 테넌트는 Pool로 저렴하게 수용하고, 엔터프라이즈나 규제 산업 고객사는 Database-per-Tenant 또는 완전 Silo로 격리해 SLA와 데이터 상주 요구를 만족시키는 식이다. 이때 애플리케이션 계층에는 "테넌트 ID → 실제 접속 정보"를 매핑하는 라우팅 레이어가 필요해지고, 이 레이어의 설계 복잡도가 티어링 전략의 실질적인 비용이 된다.

## 예제 1: PostgreSQL Row-Level Security로 Pool 모델 격리하기

```sql
-- tenant_id 컬럼을 가진 공유 테이블
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- 세션에 설정된 tenant_id와 일치하는 행만 보이도록 정책 생성
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- 애플리케이션은 요청마다 현재 테넌트를 세션 변수로 설정
SET app.current_tenant = '11111111-1111-1111-1111-111111111111';
SELECT * FROM orders; -- 위 tenant_id 를 가진 행만 반환됨
```

RLS를 쓰면 애플리케이션 코드가 `WHERE tenant_id = ?`를 빠뜨리는 실수를 하더라도 DB 엔진이 강제로 필터링해준다는 점이 핵심이다. 다만 세션 변수 설정을 커넥션 풀 반환 시점에 반드시 초기화해야, 커넥션이 재사용될 때 이전 테넌트 컨텍스트가 새 요청에 새어 들어가는 사고를 막을 수 있다.

## 예제 2: 테넌트별 DB 라우팅 (Spring `AbstractRoutingDataSource`)

```java
public class TenantRoutingDataSource extends AbstractRoutingDataSource {

    @Override
    protected Object determineCurrentLookupKey() {
        return TenantContext.getCurrentTenant(); // 요청 스레드에 저장된 테넌트 ID
    }
}

@Bean
public DataSource routingDataSource() {
    TenantRoutingDataSource routingDataSource = new TenantRoutingDataSource();
    Map<Object, Object> targetDataSources = new HashMap<>();
    targetDataSources.put("tenant_a", tenantADataSource());
    targetDataSources.put("tenant_b", tenantBDataSource());
    routingDataSource.setTargetDataSources(targetDataSources);
    routingDataSource.setDefaultTargetDataSource(poolDataSource()); // 신규/소형 테넌트는 공유 풀로 폴백
    return routingDataSource;
}
```

`determineCurrentLookupKey`가 반환하는 키에 따라 매 요청마다 실제 커넥션이 달라진다. 여기서 `setDefaultTargetDataSource`로 공유 Pool을 기본값으로 지정해 두면, 별도 DB가 배정되지 않은 신규 테넌트는 자동으로 Pool 모델로 수용되고 이후 필요할 때만 전용 DataSource를 등록하는 점진적 티어링이 가능해진다.

## 실무 포인트

- **테넌트 컨텍스트 누락은 곧 데이터 유출이다**: RLS든 애플리케이션 필터링이든, 테넌트 식별자를 빠뜨린 코드 경로가 하나라도 남아 있으면 다른 회사의 데이터가 노출될 수 있다. 통합 테스트에 "테넌트 A로 로그인해 테넌트 B의 리소스 ID를 직접 요청" 같은 교차 테넌트 접근 시나리오를 포함해야 한다.
- **마이그레이션 전략을 모델별로 따로 준비한다**: Pool은 스키마 변경이 한 번으로 끝나지만, Schema-per-Tenant나 Database-per-Tenant는 테넌트 수만큼 반복 적용해야 하므로 자동화(순차 실행, 실패 시 롤백·재시도)가 필수다.
- **격리 모델 전환은 무중단으로 설계한다**: 성장한 테넌트를 Pool에서 Silo로 옮길 때는 데이터 마이그레이션과 트래픽 전환 시점을 분리해, 전환 중 이중 쓰기나 읽기 불일치가 없도록 별도의 이관 절차를 마련해야 한다.

## 3줄 요약

- Pool 모델은 비용 효율적이지만 논리적 격리에 그치고, Silo 모델은 물리적으로 완전히 격리되지만 테넌트 수만큼 운영 비용이 커진다.
- 실제로는 Row-Level → Schema-per-Tenant → Database-per-Tenant → Silo로 이어지는 격리 스펙트럼이 존재하며, 요금제 등급별로 다른 모델을 적용하는 테넌트 티어링이 흔한 실무 전략이다.
- 어떤 모델을 쓰든 테넌트 컨텍스트 누락은 곧 데이터 유출로 이어지므로, 교차 테넌트 접근을 막는 테스트와 격리 전환 시 무중단 이관 절차를 반드시 함께 설계해야 한다.

## 참고 자료

- [AWS Well-Architected — SaaS Lens: Tenant Isolation](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/tenant-isolation.html)
- [PostgreSQL 공식 문서 — Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Microsoft Learn — Multi-tenant SaaS database tenancy patterns](https://learn.microsoft.com/en-us/azure/azure-sql/database/saas-tenancy-app-design-patterns)
