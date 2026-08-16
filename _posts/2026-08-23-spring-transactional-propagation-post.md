---
layout: single
title: "@Transactional은 왜 조용히 배신하는가 — 전파, self-invocation, rollbackFor 실전 정리"
date: 2026-08-23 12:25:00 +0530
categories: backend
tags: ["spring", "transactional", "propagation", "jpa", "backend"]
toc: true
toc_sticky: true
excerpt: "@Transactional이 적용되지 않거나 의도와 다르게 롤백되는 3대 함정 — self-invocation, 체크 예외와 rollbackFor, readOnly의 실체 — 를 프록시 동작 원리부터 실전 대안까지 정리한다."
---

`@Transactional`은 스프링에서 가장 많이 쓰이는 어노테이션 중 하나지만, 동시에 "붙였는데 동작하지 않는" 사고가 가장 자주 나는 어노테이션이기도 하다. 문제는 이 어노테이션이 실패할 때 컴파일 에러도, 경고 로그도 없이 **조용히** 실패한다는 점이다. 트랜잭션이 걸린 줄 알았던 메서드가 사실은 트랜잭션 없이 돌고 있었고, 그 사실을 데이터 정합성이 깨진 뒤에야 알게 되는 식이다.

이런 사고의 뿌리는 대부분 하나로 수렴한다. `@Transactional`은 마법이 아니라 **프록시 기반 AOP**라는 것. 스프링은 대상 빈을 프록시 객체로 감싸고, 외부에서 들어오는 호출을 프록시가 가로채 트랜잭션을 시작·커밋·롤백한다. 이 구조를 이해하면 self-invocation이 왜 안 되는지, 전파(propagation) 옵션이 왜 필요한지, `rollbackFor`를 언제 써야 하는지가 한 줄로 꿰어진다. 이 글에서는 실무에서 가장 자주 밟는 함정 세 가지를 원인부터 대안까지 정리한다.

## 전파(Propagation) 옵션, 언제 무엇을 써야 하나

트랜잭션 전파는 "이미 트랜잭션이 진행 중인 상태에서 또 다른 트랜잭션 메서드가 호출되면 어떻게 할 것인가"에 대한 정책이다. 기본값인 `REQUIRED`는 기존 트랜잭션이 있으면 합류하고, 없으면 새로 만든다. 대부분의 경우 이 기본값이 정답이지만, 나머지 옵션이 필요한 순간이 분명히 있다.

| 전파 옵션 | 기존 트랜잭션 있을 때 | 없을 때 | 대표 사용처 |
|---|---|---|---|
| `REQUIRED` (기본) | 합류 | 새로 생성 | 일반적인 서비스 로직 |
| `REQUIRES_NEW` | 기존 것 **일시 중단** 후 새 트랜잭션 | 새로 생성 | 감사 로그, 이력 저장 (본 작업이 롤백돼도 남겨야 할 때) |
| `NESTED` | 세이브포인트 생성 (부분 롤백 가능) | 새로 생성 | JDBC 세이브포인트 지원 환경의 부분 실패 허용 |
| `MANDATORY` | 합류 | **예외 발생** | "반드시 트랜잭션 안에서만 호출돼야 한다"는 계약 강제 |
| `NOT_SUPPORTED` | 일시 중단 후 트랜잭션 없이 실행 | 그대로 실행 | 트랜잭션이 오히려 해가 되는 장시간 조회 |
| `NEVER` | **예외 발생** | 그대로 실행 | 트랜잭션 밖 실행을 강제 |

여기서 가장 오해가 많은 것이 `REQUIRES_NEW`다. "독립 트랜잭션"이라는 말 때문에 병렬 실행처럼 생각하기 쉽지만, 실제로는 **바깥 트랜잭션의 커넥션을 잡아둔 채로 새 커넥션을 하나 더 가져온다**. 커넥션 풀이 작은 환경에서 `REQUIRES_NEW`가 중첩되면 커넥션 고갈로 전체 서비스가 멈출 수 있다. "롤백돼도 남아야 하는 기록"이라는 명확한 요구가 있을 때만 쓰고, 그 외에는 기본값을 유지하는 것이 안전하다.

또 하나의 고전적인 함정은 `REQUIRED`끼리의 합류에서 나온다. 내부 메서드에서 예외가 발생해 트랜잭션이 rollback-only로 마킹됐는데, 바깥 메서드가 그 예외를 `catch`로 삼켜버리면 바깥은 정상 커밋을 시도하다가 `UnexpectedRollbackException`을 만난다. "예외를 잡았는데 왜 롤백되지?"라는 질문의 답은, 두 메서드가 **물리적으로 같은 트랜잭션 하나**를 공유하고 있기 때문이다.

## self-invocation — @Transactional이 무시되는 대표 사례

가장 흔한 함정부터 보자. 같은 클래스 안에서 `this`로 자기 자신의 `@Transactional` 메서드를 부르면, 프록시를 거치지 않기 때문에 트랜잭션이 적용되지 않는다.

```java
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderService {

    public void processOrders(List<Long> ids) {
        for (Long id : ids) {
            // this.saveOrder(...) — 프록시를 우회하는 내부 호출!
            // @Transactional이 완전히 무시된다
            saveOrder(id);
        }
    }

    @Transactional
    public void saveOrder(Long id) {
        // 트랜잭션이 걸려 있을 것이라 믿지만, 위 경로로 오면 없다
    }
}
```

외부에서 `orderService.saveOrder()`를 직접 부르면 프록시가 가로채 트랜잭션을 열지만, `processOrders()` 내부에서의 호출은 프록시가 아닌 원본 객체의 메서드를 직접 부르는 것이라 어노테이션이 개입할 틈이 없다. `private` 메서드에 붙인 `@Transactional`이 무시되는 것도 같은 원리다(프록시가 오버라이드할 수 없으므로).

올바른 대안은 두 가지다. 첫째, 트랜잭션 경계가 필요한 로직을 **별도 빈으로 분리**해 프록시를 거치는 외부 호출로 만드는 것. 둘째, 선언적 방식 대신 `TransactionTemplate`으로 경계를 코드로 명시하는 것이다.

```java
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class OrderService {

    private final TransactionTemplate txTemplate;
    private final OrderRepository orderRepository;

    public OrderService(TransactionTemplate txTemplate,
                        OrderRepository orderRepository) {
        this.txTemplate = txTemplate;
        this.orderRepository = orderRepository;
    }

    public void processOrders(List<Long> ids) {
        for (Long id : ids) {
            // 건별로 트랜잭션 경계를 명시적으로 연다 — 내부 호출 문제 없음
            txTemplate.executeWithoutResult(status ->
                orderRepository.save(new Order(id)));
        }
    }
}
```

`AopContext.currentProxy()`로 자기 프록시를 꺼내 호출하는 우회법도 있지만, 설정(`exposeProxy = true`)이 필요하고 코드가 AOP 구현에 결합되므로 구조 개선이 가능한 상황에서는 권하지 않는다.

<img src="/assets/images/posts/2026-08-23-spring-transactional-propagation-1.svg" alt="프록시 경유 호출과 self-invocation의 차이" style="width:100%;">

## rollbackFor — 체크 예외는 기본적으로 롤백되지 않는다

두 번째 함정은 롤백 규칙이다. 스프링의 기본 정책은 **언체크 예외(`RuntimeException`, `Error`)만 롤백**하고, 체크 예외(`Exception`을 상속한 나머지)는 커밋한다. EJB 시절의 관례를 이어받은 것인데, "체크 예외 = 호출자가 복구할 수 있는 비즈니스 상황"이라는 가정이 깔려 있다. 문제는 실무 코드가 이 가정대로 작성되지 않는다는 것이다.

```java
@Transactional  // IOException이 던져져도 여기까지의 DB 변경은 커밋된다!
public void importAndSave(MultipartFile file) throws IOException {
    memberRepository.save(parseHeader(file));
    parseBody(file);  // IOException 발생 가능 — 그래도 위 save는 커밋
}
```

파일 파싱이 중간에 실패했는데 앞서 저장한 데이터는 남는, 전형적인 부분 커밋 사고다. 해결은 `@Transactional(rollbackFor = Exception.class)`로 롤백 범위를 넓히거나, 애초에 도메인 예외를 `RuntimeException` 기반으로 설계하는 것이다. 최근의 스프링 코드베이스는 후자가 사실상 표준이라 체크 예외를 던지는 트랜잭션 메서드 자체가 드물지만, 외부 라이브러리의 체크 예외를 통과시키는 메서드라면 `rollbackFor`를 명시하는 습관이 안전하다.

## readOnly — 최적화 힌트이지 쓰기 방지 장치가 아니다

`@Transactional(readOnly = true)`는 이름 때문에 "쓰기를 막아주는 안전장치"로 오해받지만, 스펙상으로는 **최적화 힌트**다. 실제 효과는 세 갈래다. JPA(Hibernate)에서는 플러시 모드가 조정되고 스냅샷 기반 더티 체킹 비용이 줄어 조회 성능과 메모리에 이득이 있다. JDBC 드라이버 수준에서는 DB에 따라 read-only 커넥션 최적화가 적용될 수 있다. 그리고 리더-라이터 분리 환경에서는 라우팅 데이터소스가 이 플래그를 보고 **읽기 요청을 레플리카로 보내는 기준**으로 쓰인다.

뒤집어 말하면, `readOnly = true`를 붙였다고 해서 쓰기 SQL이 항상 예외로 차단된다는 보장은 없다(동작은 DB와 드라이버에 따라 다르다). 반대로 레플리카 라우팅을 쓰는 환경에서 습관적으로 `readOnly = true`를 빼먹으면 조회 트래픽이 전부 프라이머리로 몰리고, 잘못 붙이면 방금 쓴 데이터가 복제 지연 때문에 안 보이는 사고로 이어진다. 조회 전용 서비스 메서드에는 일관되게 붙이되, "쓰기 방지"가 목적이라면 DB 계정 권한 분리로 해결해야 한다.

## 실무 체크리스트

- **트랜잭션 경계는 진입점에서 한 번만**: 컨트롤러가 아닌 서비스 계층의 공개 메서드에 선언하고, 내부 헬퍼 메서드에는 붙이지 않는다. 붙여봐야 self-invocation으로 무시되거나 혼란만 준다.
- **트랜잭션이 실제로 걸렸는지 확인하는 습관**: 개발 중에는 `logging.level.org.springframework.transaction.interceptor=TRACE`로 트랜잭션 시작/커밋 로그를 확인하거나, `TransactionSynchronizationManager.isActualTransactionActive()`로 테스트에서 검증할 수 있다.
- **트랜잭션 안에서 외부 API 호출 금지**: HTTP 호출이나 메시지 발행이 트랜잭션 안에 들어오면 커넥션 점유 시간이 외부 지연에 묶인다. 커밋 후 처리가 필요하면 `@TransactionalEventListener(phase = AFTER_COMMIT)`를 쓴다.

## 마무리 요약

- `@Transactional`은 프록시 기반이므로 같은 빈 내부 호출(self-invocation)과 private 메서드에는 적용되지 않는다 — 빈 분리 또는 `TransactionTemplate`으로 해결한다.
- 체크 예외는 기본적으로 롤백되지 않으므로, 체크 예외가 흐르는 메서드에는 `rollbackFor`를 명시하고, `REQUIRES_NEW`는 커넥션을 추가 점유한다는 비용을 알고 써야 한다.
- `readOnly = true`는 쓰기 방지 장치가 아니라 플러시 생략·레플리카 라우팅을 위한 최적화 힌트다 — 조회 메서드에 일관되게 붙이되 안전장치로 믿지 않는다.

## 참고 자료

- [Spring Framework 공식 문서 — Declarative Transaction Management](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative.html)
- [Spring Framework 공식 문서 — Understanding the Spring Framework's Declarative Transaction Implementation](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-decl-explained.html)
- [Spring Framework 공식 문서 — Using @Transactional](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html)
- [Spring Framework 공식 문서 — Programmatic Transaction Management](https://docs.spring.io/spring-framework/reference/data-access/transaction/programmatic.html)
