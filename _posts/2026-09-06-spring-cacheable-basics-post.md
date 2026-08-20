---
layout: single
title: "Spring @Cacheable 처음 써보기 — 캐싱을 애노테이션 한 줄로"
date: 2026-09-06 13:25:00 +0530
categories: backend
tags: ["spring", "cacheable", "캐싱", "성능", "입문"]
toc: true
toc_sticky: true
excerpt: "Spring에서 메서드 결과를 캐싱해 반복 호출을 빠르게 만드는 @Cacheable의 기본 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 같은 조회를 반복하는 게 아깝다면

자주 조회되지만 잘 바뀌지 않는 데이터(예: 상품 카테고리 목록)를 매번 DB에서 가져오는 것은 낭비다. Spring의 **@Cacheable**은 메서드 위에 애노테이션 한 줄만 붙이면, 그 메서드의 결과를 캐시에 저장하고 다음 호출부터는 DB를 거치지 않고 캐시에서 바로 반환해준다.

## 기본 사용법

```java
@Service
public class ProductService {

    @Cacheable("products")  // 결과를 "products" 캐시에 저장
    public Product getProduct(Long id) {
        // 이 메서드는 캐시에 없을 때만 실행된다
        return productRepository.findById(id).orElseThrow();
    }
}
```

`getProduct(1)`을 처음 호출하면 메서드가 실행되어 DB를 조회하고 결과를 캐시에 저장한다. 다음에 `getProduct(1)`을 호출하면 메서드를 실행하지 않고 캐시된 결과를 즉시 반환한다. 인자(id)가 캐시의 키가 된다.

## 캐시를 비우는 애노테이션

| 애노테이션 | 역할 |
|---|---|
| @Cacheable | 결과를 캐시에 저장(있으면 캐시 반환) |
| @CachePut | 항상 메서드 실행 + 결과로 캐시 갱신 |
| @CacheEvict | 캐시 삭제(데이터 변경 시) |

```java
@CacheEvict(value = "products", key = "#product.id")
public void updateProduct(Product product) {
    productRepository.save(product);
    // 상품이 바뀌었으니 그 캐시를 지워 다음 조회 때 새로 가져오게 함
}
```

## 실무 포인트

- **캐시 무효화를 빠뜨리면 오래된 데이터가 계속 나온다.** 데이터를 수정·삭제하는 메서드에 `@CacheEvict`를 붙이지 않으면, 캐시에 옛 데이터가 남아 사용자가 바뀐 내용을 못 본다. "캐시는 채우기보다 지우기가 어렵다"는 말이 여기서 나온다.
- **기본 캐시는 애플리케이션 메모리라 서버가 여러 대면 공유가 안 된다.** 서버 A가 캐시한 것을 서버 B는 모르므로, 여러 서버 환경에서는 Redis 같은 공유 캐시 저장소를 캐시 매니저로 연결해야 한다.
- **`@Cacheable`도 self-invocation 함정이 있다.** 같은 클래스 안에서 캐시 메서드를 직접 호출하면 프록시를 거치지 않아 캐싱이 동작하지 않는다. `@Transactional`과 같은 이유의 함정이다.

## 마무리 요약

- `@Cacheable`은 메서드 결과를 캐시에 저장해 반복 호출을 DB 없이 빠르게 처리한다.
- 데이터 변경 시에는 `@CacheEvict`로 해당 캐시를 지워야 오래된 데이터가 나오지 않는다.
- 서버가 여러 대면 Redis 같은 공유 캐시를 써야 하고, self-invocation 함정에 주의해야 한다.

## 참고 자료

- [Spring 공식 문서 - 캐시 추상화](https://docs.spring.io/spring-framework/reference/integration/cache.html)
