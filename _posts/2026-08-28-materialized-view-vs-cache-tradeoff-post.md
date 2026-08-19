---
layout: single
title: "실시간 집계를 어디서 미리 계산할 것인가 — 구체화 뷰 vs 캐시 설계 트레이드오프"
date: 2026-08-28 12:45:00 +0530
categories: system-design
tags: ["system-design", "materialized-view", "cache", "aggregation", "data-freshness"]
toc: true
toc_sticky: true
excerpt: "대시보드나 랭킹처럼 매번 무거운 집계 쿼리가 필요한 화면을, DB의 구체화 뷰(materialized view)로 미리 계산할지 애플리케이션 캐시로 결과를 저장할지를 신선도·일관성·인프라 복잡도 기준으로 비교한다."
---

주문 건수, 매출 합계, 인기 상품 랭킹처럼 여러 행을 집계해야 나오는 값은 원본 테이블이 커질수록 매 요청마다 다시 계산하기 부담스러워진다. 이 문제를 푸는 방법은 크게 두 갈래로 갈린다. 하나는 DB 안에서 미리 계산해두는 **구체화 뷰(materialized view)**이고, 다른 하나는 계산 결과를 애플리케이션 레이어의 **캐시(Redis 등)**에 저장하는 방식이다. 둘 다 "미리 계산해서 저장해둔다"는 발상은 같지만, 신선도를 관리하는 위치와 일관성 보장 수준이 근본적으로 다르다.

이 선택을 잘못하면 두 가지 실패 양상 중 하나로 빠진다. 캐시 무효화 로직이 원본 데이터의 모든 변경 경로를 놓치지 않고 따라가야 하는 부담을 애플리케이션이 떠안거나, 반대로 구체화 뷰의 갱신 주기가 요구되는 신선도보다 느려서 사용자가 오래된 숫자를 보게 되는 것이다. 이 글에서는 두 접근의 구조적 차이와, 실무에서 어떤 기준으로 선택하는지를 정리한다.

## 핵심 개념 1: 구체화 뷰 — DB가 신선도를 책임진다

구체화 뷰는 쿼리 결과를 실제 디스크 테이블처럼 저장해두는 DB 객체다. PostgreSQL의 `CREATE MATERIALIZED VIEW`, 혹은 스트리밍 방식으로 원본 변경을 실시간 반영하는 `pg_ivm` 확장이나 ClickHouse의 Materialized View가 대표적이다. 핵심은 **신선도 관리 책임이 DB 안에 있다**는 것이다. 애플리케이션은 그냥 뷰를 조회할 뿐이고, 언제 갱신할지는 `REFRESH MATERIALIZED VIEW`를 스케줄러로 주기 실행하거나(배치형), 원본 테이블 변경 시 자동으로 증분 반영하는 트리거/스트리밍 방식(증분형) 중 하나로 DB 쪽에서 처리한다.

이 방식의 장점은 애플리케이션 코드가 캐시 무효화라는 어려운 문제에서 완전히 자유로워진다는 것이다. 단점은 배치형의 경우 갱신 주기(예: 5분마다 REFRESH) 동안은 필연적으로 오래된 데이터를 보여준다는 것이고, 증분형은 구현 및 운영 복잡도가 상당히 올라간다는 것이다.

## 핵심 개념 2: 애플리케이션 캐시 — 유연하지만 무효화가 어렵다

캐시 방식은 집계 쿼리 결과를 Redis 같은 별도 저장소에 TTL과 함께 저장한다. 원본 데이터가 바뀌면 관련 캐시 키를 지우거나(무효화), 새 값으로 다시 채운다(write-through). 장점은 원본 DB와 물리적으로 분리돼 있어 DB 부하와 무관하게 초저지연 조회가 가능하고, 여러 다른 형태의 집계를 자유롭게 캐싱할 수 있다는 유연성이다.

문제는 **무효화 책임이 애플리케이션 코드로 넘어온다**는 것이다. 집계에 영향을 주는 원본 데이터 변경 경로가 늘어날수록(주문 생성, 주문 취소, 환불, 관리자 수동 조정 등) 그 모든 경로에서 캐시 무효화를 빠뜨리지 않아야 한다. 하나라도 놓치면 캐시가 영원히 오래된 값을 보여주는 버그가 생긴다.

| 기준 | 구체화 뷰 | 애플리케이션 캐시 |
|---|---|---|
| 신선도 관리 주체 | DB | 애플리케이션 코드 |
| 갱신 방식 | 배치 REFRESH 또는 증분 스트리밍 | TTL 만료 또는 수동 무효화 |
| 일관성 실패 시 증상 | 정직하게 "오래된 스냅샷"임이 명확 | 무효화 누락 시 조용히 틀린 값 반환 |
| 조회 지연 | DB 인프라에 종속 | Redis 등 별도 인프라로 매우 빠름 |
| 신선도 커스터마이징 | 뷰 단위로 일괄 (초 단위 세밀 제어 어려움) | 쿼리·키별로 TTL 세밀 조정 가능 |
| 인프라 추가 | 불필요(같은 DB) | Redis 등 별도 스토리지 필요 |

## 핵심 개념 3: 선택 기준 — 신선도 요구와 변경 경로의 개수

실무에서는 이 둘을 이분법으로 고르기보다, **집계에 영향을 주는 원본 데이터의 변경 경로가 몇 개인지**를 먼저 센다. 변경 경로가 한두 개로 명확하고 예측 가능하면(예: 주문 생성 API 하나에서만 매출 합계가 바뀜) 캐시 무효화가 쉬우므로 애플리케이션 캐시가 유리하다. 변경 경로가 많고 앞으로도 계속 늘어날 것 같으면(배치 작업, 관리자 콘솔, 여러 마이크로서비스가 각자 원본 테이블을 건드림) 무효화 누락 위험이 커지므로 구체화 뷰가 안전하다.

두 번째 기준은 신선도 요구 수준이다. "몇 분 지연은 괜찮다"는 대시보드류는 배치형 구체화 뷰로 충분하고, "결제 직후 바로 반영돼야 한다"는 화면은 증분형 구체화 뷰나 캐시의 write-through 갱신이 필요하다. 두 방식을 함께 쓰는 것도 흔한 패턴이다 — 무거운 히스토리 집계는 야간 배치 구체화 뷰로, 최근 N분 실시간 카운터는 Redis로 따로 유지하고 조회 시 합산하는 식이다.

## 예제: PostgreSQL 증분 구체화 뷰 vs Redis write-through 캐시

```sql
-- 배치형: 야간 스케줄러가 주기적으로 REFRESH
CREATE MATERIALIZED VIEW daily_sales_summary AS
SELECT
  date_trunc('day', ordered_at) AS sale_date,
  product_id,
  count(*) AS order_count,
  sum(amount) AS total_amount
FROM orders
WHERE status = 'completed'
GROUP BY 1, 2;

CREATE UNIQUE INDEX ON daily_sales_summary (sale_date, product_id);

-- 갱신 시 락 없이 CONCURRENTLY로 (UNIQUE INDEX 필요)
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_sales_summary;
```

```python
# 애플리케이션 캐시: write-through로 즉시 최신화
def create_order(order):
    db.insert_order(order)
    key = f"sales_summary:{order.product_id}:{order.date}"
    cache.hincrby(key, "order_count", 1)
    cache.hincrbyfloat(key, "total_amount", order.amount)
    cache.expire(key, ttl=3600)  # 안전망: 무효화 누락돼도 1시간 후 자연 소멸
```

캐시 방식에서는 무효화 누락에 대비한 **안전망으로 TTL을 반드시 둔다**. TTL이 없는 캐시는 "영원히 틀릴 수 있는 값"이 되지만, TTL이 있으면 최악의 경우에도 만료 후 자연 복구된다.

## 실무 포인트

- **구체화 뷰의 REFRESH는 반드시 CONCURRENTLY 옵션을 검토할 것**: 기본 REFRESH는 뷰 전체에 락을 걸어 갱신 중 조회가 막힌다. `CONCURRENTLY`는 락 없이 갱신하지만 뷰에 UNIQUE 인덱스가 있어야 하고 갱신 시간도 더 오래 걸린다는 트레이드오프가 있다.
- **캐시 무효화는 "지우기"보다 "다시 채우기"가 안전한 경우가 많다**: 단순 삭제(invalidate)는 다음 조회가 몰릴 때 캐시 스탬피드를 유발할 수 있으므로, 변경 시점에 새 값을 바로 채워 넣는 write-through가 대량 트래픽 환경에서는 더 안정적이다.
- **신선도 SLA를 문서화해둘 것**: "이 대시보드는 최대 5분 지연될 수 있다"는 명시가 없으면, 나중에 누군가 실시간이 아니라는 이유로 버그 리포트를 올린다. 두 방식 모두 신선도 지연이 존재하므로 기대치를 명확히 알려야 한다.

## 3줄 요약

- 구체화 뷰는 신선도 관리 책임을 DB가 지고, 애플리케이션 캐시는 그 책임이 애플리케이션 코드로 넘어온다.
- 집계에 영향을 주는 원본 데이터 변경 경로가 많고 계속 늘어난다면 무효화 누락 위험이 큰 캐시보다 구체화 뷰가 안전하고, 경로가 단순하고 세밀한 TTL 제어가 필요하면 캐시가 유리하다.
- 두 방식은 배타적이지 않으며, 히스토리 집계는 구체화 뷰로, 최근 실시간 카운터는 캐시로 병행하는 하이브리드가 흔한 실무 패턴이다.

## 참고 자료

- [PostgreSQL 공식 문서: Materialized Views](https://www.postgresql.org/docs/current/rules-materializedviews.html)
- [PostgreSQL 공식 문서: REFRESH MATERIALIZED VIEW](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html)
- [Redis 공식 문서: Caching Patterns](https://redis.io/docs/latest/develop/use/patterns/)
