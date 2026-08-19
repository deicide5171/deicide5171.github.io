---
layout: single
title: "재시도 버튼 두 번 누르면 결제도 두 번 — Spring에서 멱등성 키 실제 구현"
date: 2026-08-26 12:25:00 +0530
categories: backend
tags: ["backend", "spring", "idempotency", "redis", "api-design", "java"]
toc: true
toc_sticky: true
excerpt: "네트워크 타임아웃 후 클라이언트가 재시도하면 서버에는 이미 처리된 요청이 다시 도착한다. Spring에서 어노테이션 기반 인터셉터와 Redis로 멱등성 키를 실제로 구현하는 법을 정리한다."
---

클라이언트가 결제 요청을 보냈는데 응답이 타임아웃됐다고 하자. 실제로는 서버가 결제를 정상 처리했지만 응답 패킷이 유실됐을 뿐이라면, 클라이언트는 실패로 판단하고 같은 요청을 재시도한다. 이 재시도가 서버에 다시 도달하면 결제가 두 번 일어난다. 네트워크는 본질적으로 신뢰할 수 없고(at-least-once), 클라이언트의 재시도 로직은 이 사실을 전제로 짜여 있으므로, 중복 요청을 걸러내는 책임은 결국 서버 쪽 API가 져야 한다.

멱등성 키(Idempotency Key)는 이 문제를 클라이언트가 요청마다 고유한 키를 헤더에 실어 보내고, 서버는 같은 키로 온 요청을 두 번째부터는 처리하지 않고 첫 번째 결과를 그대로 돌려주는 방식으로 해결한다. 아이디어는 단순하지만 실제로 Spring 애플리케이션에 넣으려면 동시성(같은 키로 요청 두 개가 동시에 도착하는 경우), 만료 정책, 응답 캐싱 범위를 모두 정해야 한다. 이 글에서는 어노테이션 기반 인터셉터와 Redis를 이용한 실제 구현을 정리한다.

## 핵심 개념 1: 멱등성 키의 상태 전이

멱등성 키 하나는 "아직 처리된 적 없음 → 처리 중 → 완료(응답 저장됨)"라는 세 상태를 가진다. 이 상태 전이를 원자적으로 관리하지 못하면, 같은 키로 온 두 요청이 동시에 "처리된 적 없음"을 확인하고 둘 다 실제 로직을 실행해버리는 경쟁 조건이 생긴다. Redis의 `SETNX`(SET if Not eXists)가 이 원자적 상태 전이에 적합하다.

| 상태 | 의미 | 두 번째 요청의 동작 |
|---|---|---|
| 키 없음 | 처음 보는 요청 | 처리 시작, 키를 "처리 중"으로 선점 |
| 처리 중 | 같은 요청이 아직 처리되고 있음 | 409 Conflict 또는 짧게 대기 후 폴링 |
| 완료 | 이미 처리 끝났고 응답이 저장됨 | 저장된 응답을 그대로 반환(실제 로직 미실행) |

## 핵심 개념 2: 키의 스코프와 만료 정책

멱등성 키는 "무엇을 기준으로 같은 요청인가"를 정확히 정의해야 실효성이 있다. 클라이언트가 보낸 키 값만으로 판단하면, 다른 사용자가 우연히 같은 키를 보내는 경우까지 같은 요청으로 취급될 위험이 있다. 따라서 실무에서는 키를 `사용자ID + 엔드포인트 + 클라이언트 제공 키`의 조합으로 네임스페이스를 나눠 저장한다. 만료 시간도 중요한데, 결제처럼 재시도가 몇 분 내에 집중되는 도메인은 24시간 정도로 충분하지만, 무한정 보관하면 Redis 메모리가 계속 쌓인다.

## 예제: Spring AOP 인터셉터로 멱등성 처리

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface IdempotentRequest {
    long ttlSeconds() default 86400; // 기본 24시간
}

@Aspect
@Component
@RequiredArgsConstructor
public class IdempotencyAspect {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    @Around("@annotation(idempotentRequest)")
    public Object handle(ProceedingJoinPoint joinPoint, IdempotentRequest idempotentRequest) throws Throwable {
        String idempotencyKey = extractHeaderKey(); // "Idempotency-Key" 헤더 읽기
        Long userId = SecurityContextHolder.getContext()
                .getAuthentication().getPrincipal() instanceof UserPrincipal p ? p.getId() : null;

        if (idempotencyKey == null || userId == null) {
            throw new IllegalArgumentException("Idempotency-Key 헤더가 필요합니다");
        }

        String redisKey = "idem:%d:%s:%s".formatted(userId, joinPoint.getSignature().getName(), idempotencyKey);

        // 원자적 선점: 이미 있으면 false 반환 (SETNX)
        Boolean acquired = redisTemplate.opsForValue()
                .setIfAbsent(redisKey + ":lock", "1", Duration.ofSeconds(idempotentRequest.ttlSeconds()));

        if (Boolean.FALSE.equals(acquired)) {
            // 이미 처리됐거나 처리 중 — 저장된 응답이 있으면 그대로 반환
            String cached = redisTemplate.opsForValue().get(redisKey + ":result");
            if (cached != null) {
                return objectMapper.readValue(cached, joinPoint.getSignature().getName().equals("pay")
                        ? PaymentResult.class : Object.class);
            }
            throw new ResponseStatusException(HttpStatus.CONFLICT, "요청이 이미 처리 중입니다");
        }

        try {
            Object result = joinPoint.proceed();
            redisTemplate.opsForValue().set(
                    redisKey + ":result",
                    objectMapper.writeValueAsString(result),
                    Duration.ofSeconds(idempotentRequest.ttlSeconds())
            );
            return result;
        } catch (Exception e) {
            // 실제 처리 실패 시 락을 즉시 해제해 재시도를 허용
            redisTemplate.delete(redisKey + ":lock");
            throw e;
        }
    }
}
```

컨트롤러 메서드에는 `@IdempotentRequest`만 붙이면 된다. 처리 실패 시 락을 명시적으로 해제하는 부분이 중요한데, 이걸 빼먹으면 일시적 오류(DB 커넥션 순간 부족 등)로 실패한 요청도 TTL이 끝날 때까지 재시도가 막혀버린다.

## 실무 포인트

- **멱등성 키는 POST/PATCH 같은 비멱등 메서드에만 적용한다**: GET·PUT·DELETE는 프로토콜상 이미 멱등해야 하므로, 실제로 멱등성 키가 필요한 대상은 결제·주문 생성처럼 매번 새 리소스를 만들거나 상태를 전이시키는 POST 요청이다.
- **응답 캐싱은 성공 케이스만이 아니라 명시적 실패도 포함할지 정한다**: 검증 오류(400)처럼 재시도해도 항상 같은 결과가 나오는 실패는 캐싱해도 되지만, 일시적 인프라 오류(503)까지 캐싱하면 진짜 재시도가 필요한 상황에서 오래된 실패 응답만 계속 돌려주게 된다.
- **클라이언트에 멱등성 키 생성 책임을 명확히 안내한다**: 클라이언트가 매 요청마다 새 UUID를 생성해 버리면 재시도 시에도 다른 키가 붙어 멱등성이 무의미해진다. "같은 논리적 요청(사용자가 버튼을 한 번 누른 액션)에는 같은 키를 재사용하고, 재시도 시에도 그 키를 그대로 보낸다"는 규칙을 API 문서에 명시해야 한다.

## 3줄 요약

- 네트워크는 신뢰할 수 없고 클라이언트 재시도는 필연적이므로, 중복 요청을 걸러내는 책임은 서버 API가 져야 한다.
- Redis `SETNX`로 "처리 중" 상태를 원자적으로 선점하고, 실패 시 락을 명시적으로 해제해야 정상적인 재시도까지 막지 않는다.
- 멱등성 키는 사용자ID+엔드포인트+클라이언트 키로 스코프를 나누고, TTL과 실패 응답 캐싱 여부를 도메인 특성에 맞게 정해야 한다.

## 참고 자료

- [Stripe API 문서: Idempotent Requests](https://docs.stripe.com/api/idempotent_requests)
- [Spring 공식 문서: Aspect Oriented Programming with Spring](https://docs.spring.io/spring-framework/reference/core/aop.html)
- [Redis 공식 문서: SET command (NX option)](https://redis.io/docs/latest/commands/set/)
