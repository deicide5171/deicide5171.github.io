---
layout: single
title: "캐시는 채우기보다 지우기가 어렵다 — 쿼리 결과 캐싱과 무효화 전략"
date: 2026-08-30 12:35:00 +0530
categories: database
tags: ["database", "caching", "cache-invalidation", "redis", "query-optimization", "consistency"]
toc: true
toc_sticky: true
excerpt: "쿼리 결과를 캐싱할 때 실제로 어려운 부분은 저장이 아니라 언제 지우느냐다. 키 설계, TTL과 태그 기반 무효화, 그리고 부분 갱신 전략을 데이터베이스 관점에서 정리한다."
---

읽기 비중이 압도적으로 높은 서비스에서 쿼리 결과를 캐싱하는 건 당연한 선택이다. 문제는 캐싱 자체가 아니라 **원본 데이터가 바뀌었을 때 캐시를 어떻게 정확히, 늦지 않게 지우느냐**다. "캐시 무효화, 이름 짓기, 오프바이원 에러"가 컴퓨터 과학에서 가장 어려운 두 가지 문제 중 하나로 꼽히는 데는 이유가 있다 — 무효화 로직은 데이터 변경 경로마다 빠짐없이 걸려 있어야 하고, 하나라도 놓치면 사용자는 오래된 데이터를 계속 보게 되는데 이 버그는 재현하기도, 알아차리기도 어렵다.

이 글은 애플리케이션 코드 캐시가 아니라 **쿼리 결과 캐싱을 DB 접근 계층에서 어떻게 설계하는가**에 초점을 맞춘다. 키 설계, TTL만으로 버틸 수 있는 경우와 버틸 수 없는 경우, 그리고 태그 기반 무효화로 정확도를 올리는 방법을 정리한다.

## 핵심 개념 1: 캐시 키 설계 — 무엇이 결과를 결정하는가

쿼리 결과 캐시의 키는 그 쿼리 결과를 유일하게 결정하는 모든 입력을 반영해야 한다. 단순히 `user:123`처럼 엔티티 ID만 키로 쓰면, 같은 사용자 데이터를 서로 다른 필터·정렬·페이지네이션으로 조회하는 여러 쿼리가 전부 한 키에 뒤섞여 캐시가 무의미해지거나 잘못된 결과를 반환한다. 실무에서는 쿼리 파라미터 전체(필터 조건, 정렬 기준, 페이지 오프셋, 스키마 버전)를 정규화해 해시로 압축한 값을 키의 일부로 쓴다.

```
cache:orders:user_id=123:status=shipped:sort=created_desc:page=2:v=3
```

여기서 `v=3` 같은 스키마 버전 접미사는 응답 필드가 바뀌는 배포를 할 때 이전 캐시를 자동으로 무효화하는 값싼 방법이다. 캐시 키 형식 자체를 바꿀 때마다 버전을 올리면, 굳이 기존 키를 찾아 지우지 않아도 새 버전 키만 채워지기 시작하고 옛 키는 TTL에 따라 자연히 사라진다.

## 핵심 개념 2: TTL만으로 버틸 수 있는 경계

가장 단순한 무효화 전략은 TTL(Time To Live)뿐이다. 원본이 바뀌어도 캐시를 굳이 찾아 지우지 않고, 일정 시간 지나면 자연히 만료되게 둔다. 이 방식이 통하려면 "데이터가 바뀐 뒤 TTL이 끝날 때까지 오래된 값을 보여줘도 되는가"라는 질문에 답이 "그렇다"여야 한다. 상품 상세 설명, 리뷰 평점 평균처럼 초 단위 정확도가 중요하지 않은 데이터는 TTL만으로 충분하다.

반대로 재고 수량, 결제 상태, 권한 정보처럼 변경 직후 즉시 반영돼야 하는 데이터는 TTL만으로는 부족하고 **쓰기 시점에 능동적으로 무효화**해야 한다. 이때 흔히 저지르는 실수가 "쓰기 후 캐시부터 지우고 DB를 갱신"하는 순서다 — 그 사이 다른 요청이 옛 DB 값으로 캐시를 다시 채워버리는 경쟁 조건이 생긴다. 올바른 순서는 **DB를 먼저 갱신하고, 그 다음 캐시를 지우는 것**(cache-aside 패턴의 invalidate-after-write)이며, 그래도 남는 짧은 경쟁 조건 창은 짧은 TTL을 안전망으로 함께 둬서 완화한다.

| 전략 | 적합한 데이터 | 최신성 보장 | 구현 복잡도 |
|---|---|---|---|
| TTL만 | 상품 설명, 통계성 집계 | 최대 TTL만큼 지연 허용 | 낮음 |
| 쓰기 시 무효화 | 재고, 주문 상태 | 거의 즉시(경쟁 조건 창 존재) | 중간 |
| 쓰기 시 갱신(write-through) | 자주 읽고 정확도 중요 | 즉시 | 중간~높음 |
| 태그 기반 무효화 | 다대다 참조 관계 데이터 | 관련 키 전체 즉시 | 높음 |

## 핵심 개념 3: 태그 기반 무효화 — 관계형 캐시 무효화의 실전 해법

쿼리 결과가 여러 테이블을 조인한 결과라면 "이 캐시 키가 어떤 원본 로우들에 의존하는지"를 추적해야 정확한 무효화가 가능하다. 개별 키를 일일이 지우는 대신, 캐시 값을 저장할 때 그 값이 의존하는 엔티티들의 **태그**를 함께 등록하고(예: `order:456`, `product:789`), 해당 엔티티가 변경되면 그 태그에 연결된 모든 캐시 키를 한 번에 무효화하는 방식이다.

Redis에서는 이를 흔히 Set 자료구조로 구현한다 — `tag:order:456` 이라는 Set에 그 주문이 관여된 모든 캐시 키를 담아두고, 주문이 갱신되면 그 Set을 순회하며 각 키를 지운 뒤 Set 자체도 지운다. 이 패턴은 정확도가 높은 대신 쓰기마다 태그 인덱스 갱신 비용이 추가되므로, 조인이 복잡하고 변경 빈도가 낮은 쿼리에 적용하는 것이 비용 대비 효과가 좋다.

## 예제: cache-aside + 태그 무효화 (Node.js/Redis)

```javascript
// cache-aside 패턴 + 태그 기반 무효화
async function getOrderWithItems(orderId) {
  const key = `cache:order:${orderId}:v=2`;
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);

  const order = await db.query(
    `SELECT o.*, oi.* FROM orders o
     JOIN order_items oi ON oi.order_id = o.id
     WHERE o.id = $1`, [orderId]
  );

  await redis.set(key, JSON.stringify(order), 'EX', 300); // TTL 5분 안전망
  // 이 캐시가 의존하는 엔티티들을 태그 Set에 등록
  await redis.sadd(`tag:order:${orderId}`, key);
  for (const item of order.items) {
    await redis.sadd(`tag:product:${item.productId}`, key);
  }
  return order;
}

async function invalidateByTag(tagKey) {
  const keys = await redis.smembers(tagKey);
  if (keys.length > 0) {
    await redis.del(...keys);       // 관련 캐시 전부 무효화
  }
  await redis.del(tagKey);          // 태그 Set 자체도 정리
}

// 상품 가격이 바뀌면 그 상품이 들어간 모든 주문 캐시를 함께 무효화
async function updateProductPrice(productId, newPrice) {
  await db.query('UPDATE products SET price = $1 WHERE id = $2', [newPrice, productId]);
  await invalidateByTag(`tag:product:${productId}`);
}
```

## 실무 포인트

- **음성 캐싱(negative caching)을 잊지 말 것.** 존재하지 않는 리소스 조회가 반복되면 매번 DB까지 내려가 부하를 만든다("존재하지 않음"이라는 결과도 짧은 TTL로 캐싱해야 한다). 다만 리소스가 나중에 생성되는 케이스(예: 방금 가입한 사용자 조회)에서는 이 캐시가 오히려 최근 생성된 데이터를 숨기는 함정이 될 수 있으므로 TTL을 짧게 유지해야 한다.
- **캐시 스탬피드는 무효화 전략과 별개 문제로 다뤄야 한다.** 인기 키가 만료되는 순간 동시에 수백 요청이 DB로 몰리는 현상은 TTL을 아무리 잘 설계해도 발생한다. 락(단일 요청만 갱신)이나 확률적 조기 만료(probabilistic early expiration) 같은 별도 장치가 필요하다.
- **캐시 무효화 실패를 관측 가능하게 만들어라.** 무효화 호출 자체가 실패(네트워크 오류 등)해도 애플리케이션은 조용히 넘어가는 경우가 많다. 무효화 실패율을 메트릭으로 노출하고, 실패 시 해당 키를 짧은 TTL로 강제 만료시키는 폴백 경로를 반드시 둬야 "영원히 오래된 캐시"가 남는 사고를 막을 수 있다.

## 3줄 요약

- 쿼리 결과 캐싱의 핵심 난제는 저장이 아니라 무효화이며, 캐시 키는 결과를 결정하는 모든 입력(필터·정렬·페이지·스키마 버전)을 반영해야 한다.
- TTL만으로 버틸 수 있는 데이터와, 쓰기 시점에 능동적으로 무효화해야 하는 데이터를 구분하고, 후자는 반드시 "DB 갱신 후 캐시 삭제" 순서를 지켜야 경쟁 조건을 줄일 수 있다.
- 여러 테이블을 조인한 결과처럼 의존 관계가 복잡한 캐시는 태그 기반 무효화로 정확도를 높이고, 캐시 스탬피드와 무효화 실패는 각각 별도의 방어 장치와 관측 지표로 다뤄야 한다.

## 참고 자료

- [Redis 공식 문서: Client Side Caching](https://redis.io/docs/latest/develop/reference/client-side-caching/)
- [AWS 아키텍처 블로그: Caching Strategies](https://aws.amazon.com/caching/best-practices/)
- [Martin Fowler: Cache Invalidation 관련 논의](https://martinfowler.com/bliki/TwoHardThings.html)
