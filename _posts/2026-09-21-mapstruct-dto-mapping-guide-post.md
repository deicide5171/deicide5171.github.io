---
layout: single
title: "MapStruct로 DTO 변환 자동화하기 — 수동 매핑과 비교"
date: 2026-09-21 13:25:00 +0530
categories: backend
tags: ["mapstruct", "dto변환", "spring", "자바", "코드생성"]
toc: true
toc_sticky: true
excerpt: "엔티티와 DTO를 오가는 반복적인 필드 복사 코드를 MapStruct로 컴파일 타임에 자동 생성하는 방법과, 수동 매핑·리플렉션 기반 매핑과의 차이를 정리했다."
---

## 왜 지금 이 문제를 다뤄야 하나

Spring 기반 백엔드에서 엔티티를 그대로 API 응답으로 내보내지 않고 DTO로 변환하는 것은 이제 거의 상식이 됐다. 순환 참조, 지연 로딩(LAZY) 예외, 불필요한 내부 필드 노출을 막기 위해서다. 문제는 프로젝트가 커질수록 엔티티-DTO 변환 코드가 기하급수적으로 늘어난다는 점이다.

```java
public OrderDto toDto(Order order) {
    OrderDto dto = new OrderDto();
    dto.setId(order.getId());
    dto.setCustomerName(order.getCustomer().getName());
    dto.setAmount(order.getAmount());
    dto.setStatus(order.getStatus().name());
    // 필드가 늘어날 때마다 여기도 계속 늘어난다
    return dto;
}
```

필드 하나가 추가될 때마다 이 변환 메서드를 빠뜨리지 않고 고쳐야 하고, 엔티티가 수십 개면 이런 변환 클래스도 수십 개가 된다. 코드 리뷰에서도 "필드 하나 빠뜨렸다"는 지적이 반복해서 나온다.

## 잘못된 대안: 리플렉션 기반 매핑 라이브러리

이 문제를 해결하려고 ModelMapper 같은 **런타임 리플렉션 기반** 매핑 라이브러리를 쓰는 경우가 많다. 필드 이름이 같으면 자동으로 값을 복사해주니 확실히 코드량은 준다. 하지만 대가가 있다.

- **런타임에야 매핑 오류를 발견한다.** 필드명 오타나 타입 불일치가 있어도 컴파일은 통과하고, 실제로 그 매핑이 실행되는 순간에야(혹은 결과 값이 null로 나오는 걸 뒤늦게 발견하고서야) 문제를 알게 된다.
- **리플렉션 오버헤드가 있다.** 매핑할 때마다 리플렉션으로 필드에 접근하므로, 대량 데이터를 변환하는 배치 작업에서는 성능 차이가 체감된다.
- **디버깅이 어렵다.** 매핑 로직이 라이브러리 내부의 리플렉션 코드 안에 숨어 있어, "왜 이 필드가 null로 나오지?"를 스택 트레이스로 추적하기 힘들다.

## 올바른 접근: MapStruct의 컴파일 타임 코드 생성

MapStruct는 애노테이션 프로세서로 동작해, **컴파일 시점에 실제 매핑 코드를 생성**한다.

```java
@Mapper(componentModel = "spring")
public interface OrderMapper {
    @Mapping(source = "customer.name", target = "customerName")
    @Mapping(source = "status", target = "status", qualifiedByName = "statusToString")
    OrderDto toDto(Order order);

    @Named("statusToString")
    default String statusToString(OrderStatus status) {
        return status.name();
    }
}
```

이 인터페이스만 작성하면, 빌드 시점에 MapStruct가 실제 필드 대입 코드가 담긴 구현체 클래스를 자동으로 만들어준다. 생성된 코드를 열어보면 앞서 손으로 짰던 것과 거의 똑같은 순수 자바 코드다.

```java
// 생성되는 코드 (개념적 예시)
public class OrderMapperImpl implements OrderMapper {
    public OrderDto toDto(Order order) {
        if (order == null) return null;
        OrderDto dto = new OrderDto();
        dto.setId(order.getId());
        dto.setCustomerName(order.getCustomer().getName());
        dto.setStatus(statusToString(order.getStatus()));
        return dto;
    }
}
```

리플렉션이 아니라 일반 getter/setter 호출로 컴파일되므로 런타임 성능이 수동 매핑과 동일하고, 필드명이 틀리거나 타입이 맞지 않으면 **컴파일 시점에 에러**로 바로 드러난다.

## 비교 정리

| 방식 | 오류 발견 시점 | 런타임 성능 | 초기 작성 부담 |
|---|---|---|---|
| 수동 매핑 | 컴파일 타임 | 좋음 | 반복 코드 많음 |
| 리플렉션 기반(ModelMapper) | 런타임 | 상대적으로 느림 | 매핑 규칙 설정 필요 |
| MapStruct | 컴파일 타임 | 좋음(수동과 동일) | 인터페이스 선언만 |

## 실무 포인트

- **필드명이 다를 때는 반드시 `@Mapping`으로 명시하라.** MapStruct는 이름이 같은 필드는 자동 매핑하지만, 이름이 다르면 매핑하지 않고 조용히 넘어갈 수 있어(경고는 뜬다) 빌드 설정에서 `unmappedTargetPolicy = ReportingPolicy.ERROR`로 엄격하게 잡아두는 것이 안전하다.
- **양방향 매핑(Entity→DTO, DTO→Entity)이 필요하면 각각 메서드를 선언하라.** 자동으로 역방향을 추론해주지 않으므로, 필요한 방향의 메서드를 명시적으로 작성한다.
- **중첩 객체 매핑도 다른 `@Mapper`를 참조하게 구성할 수 있다.** `uses = {CustomerMapper.class}`처럼 지정하면 복잡한 객체 그래프도 각 매퍼가 분담해서 처리한다.
- **테스트를 생략하지 마라.** 코드 생성이라 안전해 보이지만, `@Mapping` 설정 자체가 잘못되면 여전히 논리적 버그가 날 수 있다. 매퍼도 단위 테스트 대상으로 다룬다.

## 마무리 요약

- 엔티티-DTO 변환을 손으로 짜면 필드 추가마다 실수하기 쉽고, 리플렉션 기반 라이브러리는 런타임에야 오류가 드러난다.
- MapStruct는 컴파일 시점에 실제 매핑 코드를 생성해, 수동 매핑과 동일한 성능을 유지하면서 필드 누락·타입 불일치를 빌드 단계에서 잡아준다.
- `unmappedTargetPolicy` 엄격 설정과 매퍼 단위 테스트를 함께 갖추면 안정적으로 운영할 수 있다.

## 참고 자료

- [MapStruct 공식 문서](https://mapstruct.org/documentation/stable/reference/html/)
- [Baeldung - Mapping with MapStruct](https://www.baeldung.com/mapstruct)
