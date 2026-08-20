---
layout: single
title: "@Value와 @ConfigurationProperties — 스프링에서 설정값 읽기"
date: 2026-09-10 13:25:00 +0530
categories: backend
tags: ["value", "configurationproperties", "spring", "설정", "입문"]
toc: true
toc_sticky: true
excerpt: "application.yml의 설정값을 코드로 읽어오는 @Value와 @ConfigurationProperties의 차이와 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 설정값을 코드에 박아 넣지 마라

API 키, 서버 주소, 페이지 크기 같은 값을 코드에 직접 써넣으면, 바꿀 때마다 코드를 고치고 다시 빌드해야 한다. 스프링에서는 이런 값을 **`application.yml`(또는 `.properties`)에 두고 코드로 읽어온다.** 읽는 방법이 **`@Value`**와 **`@ConfigurationProperties`** 두 가지다.

## @Value vs @ConfigurationProperties

| 구분 | @Value | @ConfigurationProperties |
|---|---|---|
| 방식 | 값 하나씩 주입 | 관련 값들을 객체로 묶음 |
| 적합 | 단순 값 몇 개 | 그룹화된 여러 설정 |
| 타입 안전 | 약함 | 강함(검증 가능) |

## 예시

```yaml
# application.yml
app:
  name: myservice
  page-size: 20
```

```java
// 1) @Value: 값 하나씩
@Value("${app.page-size}")
private int pageSize;

// 2) @ConfigurationProperties: 묶어서
@ConfigurationProperties(prefix = "app")
public class AppProps {
    private String name;
    private int pageSize;
    // getter/setter
}
```

설정이 몇 개뿐이면 `@Value`, `app.*`처럼 관련 설정이 많으면 `@ConfigurationProperties`로 묶는 것이 깔끔하다.

## 실무 포인트

- **비밀값은 yml에 그대로 두지 마라.** API 키·비밀번호를 `application.yml`에 평문으로 넣고 깃에 올리면 유출된다. 환경 변수나 시크릿 매니저로 주입하고, 설정 파일엔 참조만 둔다.
- **기본값을 지정할 수 있다.** `@Value("${app.timeout:5000}")`처럼 콜론 뒤에 기본값을 주면, 설정이 없어도 5000을 쓴다. 필수 설정 누락으로 앱이 안 뜨는 상황을 줄일 수 있다.
- **환경별로 파일을 분리하라.** `application-dev.yml`, `application-prod.yml`로 나누고 프로파일로 전환하면, 개발/운영 설정을 안전하게 관리할 수 있다.

## 마무리 요약

- 설정값은 코드에 박지 말고 `application.yml`에 두고 읽어온다.
- 단순 값은 `@Value`, 관련 설정 묶음은 `@ConfigurationProperties`로 객체에 매핑한다.
- 비밀값은 환경 변수/시크릿으로 주입하고, 기본값 지정과 환경별 파일 분리를 활용한다.

## 참고 자료

- [Spring 공식 문서 - Externalized Configuration](https://docs.spring.io/spring-boot/reference/features/external-config.html)
