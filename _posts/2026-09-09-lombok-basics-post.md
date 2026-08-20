---
layout: single
title: "Lombok이 뭔가요 — 게터·세터 반복을 없애주는 라이브러리"
date: 2026-09-09 13:25:00 +0530
categories: backend
tags: ["lombok", "롬복", "java", "spring", "입문"]
toc: true
toc_sticky: true
excerpt: "자바에서 게터·세터·생성자 같은 반복 코드를 애너테이션으로 자동 생성해주는 Lombok의 사용법과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## 게터·세터를 매번 손으로 써야 하나

자바 클래스에 필드가 10개면 게터·세터가 20개, 여기에 생성자·`toString`·`equals`까지 더하면 코드가 수십 줄로 늘어난다. 정작 중요한 로직은 그 사이에 파묻힌다. **Lombok(롬복)**은 이런 **반복 코드를 애너테이션 하나로 자동 생성**해주는 자바 라이브러리다.

## 자주 쓰는 애너테이션

| 애너테이션 | 자동 생성하는 것 |
|---|---|
| `@Getter` / `@Setter` | 게터 / 세터 |
| `@ToString` | `toString()` |
| `@NoArgsConstructor` | 기본 생성자 |
| `@AllArgsConstructor` | 모든 필드 생성자 |
| `@Data` | 위의 여러 개를 한 번에 |

## 사용 예시

```java
import lombok.Getter;
import lombok.Setter;

@Getter @Setter
public class User {
    private Long id;
    private String name;
    private String email;
}
// getId(), setName() 등이 자동으로 생긴다 (컴파일 시)
```

애너테이션만 붙였는데 게터·세터가 만들어진다. 실제 코드는 컴파일 시점에 자동으로 삽입된다.

## 실무 포인트

- **`@Data`는 신중히 써라.** `@Data`는 세터까지 다 만들어 객체를 아무 데서나 바꿀 수 있게 한다. 불변으로 두고 싶은 엔티티엔 `@Getter`만 쓰거나 필요한 것만 골라 쓰는 것이 안전하다.
- **엔티티에 `@ToString` 전체는 위험하다.** JPA 엔티티에서 연관 관계 필드까지 `toString`에 넣으면, 로그를 찍는 순간 연관 엔티티를 줄줄이 조회하거나 무한 순환에 빠질 수 있다. 연관 필드는 제외한다.
- **IDE 플러그인이 필요하다.** Lombok이 만드는 코드는 컴파일 시 생기므로, IDE가 이를 인식하려면 Lombok 플러그인을 설치해야 한다. 안 그러면 "메서드 없음" 오류처럼 보인다.

## 마무리 요약

- Lombok은 게터·세터·생성자·`toString` 등 반복 코드를 애너테이션으로 자동 생성한다.
- `@Getter`, `@Setter`, `@Data` 등을 붙이면 컴파일 시점에 해당 코드가 삽입된다.
- `@Data`·전체 `@ToString`은 부작용이 있으니 신중히 쓰고, IDE 플러그인 설치가 필요하다.

## 참고 자료

- [Project Lombok 공식 사이트](https://projectlombok.org/)
