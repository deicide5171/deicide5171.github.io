---
layout: single
title: "Spring Security 6 인가 모델 깊이 이해하기 — 커스텀 AuthorizationManager"
date: 2026-08-22 13:25:00 +0530
categories: backend
tags: ["backend", "spring-security", "authorization", "spring-boot", "java"]
toc: true
toc_sticky: true
excerpt: "WebSecurityConfigurerAdapter가 사라진 이후 Spring Security 6이 인가 로직을 어떻게 재구성했는지, AuthorizationManager로 세밀한 커스텀 인가 규칙을 만드는 방법을 정리한다."
---

Spring Security 5.7 이전까지는 `WebSecurityConfigurerAdapter`를 상속해 `configure(HttpSecurity http)`를 오버라이드하는 방식이 사실상 표준이었다. 이 방식은 익숙했지만, 상속에 의존하다 보니 설정을 여러 조각으로 나누기 어렵고, 테스트를 위해 임의로 빈을 교체하기도 까다로웠다. 이후 버전들은 상속 대신 `SecurityFilterChain` 빈을 직접 등록하는 컴포넌트 기반 설정으로 전환됐고, Spring Security 6에서는 `WebSecurityConfigurerAdapter` 자체가 완전히 제거되면서 이 방식이 유일한 표준이 됐다.

설정 방식만 바뀐 것이 아니다. 인가(authorization) 로직을 판단하는 내부 구조도 함께 재편됐다. 과거에는 `AccessDecisionManager`와 여러 `AccessDecisionVoter`가 투표하듯 접근 허용 여부를 결정했다면, Spring Security 6은 이를 단일 책임을 지는 `AuthorizationManager` 인터페이스로 단순화했다. 이 변화는 단순히 내부 구현을 정리한 것을 넘어, `hasRole()`이나 `hasAuthority()`만으로는 표현하기 어려운 복잡한 인가 규칙 — 예를 들어 리소스 소유자 확인, 시간대별 접근 제한, 여러 조건의 조합 판단 — 을 개발자가 직접 끼워 넣을 수 있는 명확한 확장 지점을 제공한다.

이 글에서는 `SecurityFilterChain` 기반 설정이 인가 규칙을 어떻게 조립하는지, 그리고 그 안에서 `AuthorizationManager`를 커스텀 구현해 세밀한 규칙을 적용하는 방법을 정리한다.

## 핵심 개념 1: SecurityFilterChain 빈 기반 설정

Spring Security 6에서는 보안 설정을 `@Configuration` 클래스 안에서 `SecurityFilterChain` 타입의 빈을 반환하는 메서드로 작성한다. `HttpSecurity` 객체를 인자로 받아 `authorizeHttpRequests()`, `formLogin()`, `csrf()` 같은 람다 기반 DSL로 설정을 조립한 뒤 `build()`를 호출해 필터 체인을 완성하는 구조다. 상속이 사라진 대신 빈 하나하나가 독립적으로 정의되므로, 프로필이나 조건에 따라 서로 다른 `SecurityFilterChain` 빈을 등록해 요청 경로별로 다른 보안 정책을 적용하기도 쉬워졌다.

`authorizeHttpRequests()` 안에서는 `requestMatchers()`로 경로를 지정하고 그 뒤에 `permitAll()`, `hasRole()`, `authenticated()` 같은 판단 규칙을 이어 붙인다. 이 규칙들은 내부적으로 각각의 `AuthorizationManager` 구현체로 변환되어 필터 체인에 등록되며, 요청이 들어올 때마다 매칭되는 규칙의 `AuthorizationManager`가 순서대로 호출되어 접근 허용 여부를 판단한다.

## 핵심 개념 2: AuthorizationManager의 역할과 커스텀 구현 지점

`AuthorizationManager<T>`는 `authorize(Supplier<Authentication>, T object)` 형태의 메서드 하나로 정의되는 함수형 인터페이스에 가깝다. 여기서 `T`는 인가 판단의 대상 — HTTP 요청이라면 `RequestAuthorizationContext`, 메서드 호출이라면 `MethodInvocation` — 이 되며, 반환값인 `AuthorizationDecision`은 허용 여부(boolean)와 함께 판단 근거가 되는 부가 정보를 담을 수 있다.

`hasRole()`이나 `hasAuthority()` 같은 내장 규칙으로 표현할 수 없는 조건 — 리소스 소유자와 요청자가 같은지, 여러 권한의 조합을 판단해야 하는지, 외부 정책 서버의 응답이 필요한지 — 은 이 인터페이스를 직접 구현해 해결한다. `requestMatchers(...).access(customAuthorizationManager)` 형태로 필터 체인에 끼워 넣으면, 해당 경로에 대한 인가 판단을 완전히 위임할 수 있다. 여러 `AuthorizationManager`를 `AuthorityAuthorizationManager`나 `AuthorizationManagers.allOf()/anyOf()` 같은 조합 유틸리티로 엮어 복합 조건을 구성하는 것도 가능하다.

## 핵심 개념 3: 메서드 시큐리티(@PreAuthorize)와의 관계

`AuthorizationManager`는 URL 단위의 필터 체인뿐 아니라 메서드 시큐리티에도 동일하게 적용되는 공통 추상화다. `@PreAuthorize`, `@PostAuthorize`, `@Secured` 같은 어노테이션 기반 판단은 내부적으로 `PreAuthorizeAuthorizationManager`, `PostAuthorizeAuthorizationManager` 같은 구현체를 통해 이뤄지며, 이들도 결국 같은 `AuthorizationManager<MethodInvocation>` 계약을 따른다.

즉 HTTP 요청 단위에서 커스텀 `AuthorizationManager`를 만드는 것과, 메서드 단위에서 SpEL 표현식으로 커스텀 빈의 메서드를 호출하는 것(`@PreAuthorize("@myAuthorizer.check(#id)")`)은 같은 설계 철학의 두 표현이라 할 수 있다. 요청 경로에 걸기 애매한 세밀한 조건은 메서드 시큐리티로, 여러 엔드포인트에 공통으로 적용할 규칙은 필터 체인의 `AuthorizationManager`로 배치하는 식의 역할 분담이 실무에서 자주 쓰인다.

## 예제

다음은 리소스 소유자 여부를 확인하는 커스텀 `AuthorizationManager`를 구현하고, 이를 `SecurityFilterChain`에 적용하는 예시다.

```java
public class ResourceOwnerAuthorizationManager
        implements AuthorizationManager<RequestAuthorizationContext> {

    private final ResourceRepository resourceRepository;

    public ResourceOwnerAuthorizationManager(ResourceRepository resourceRepository) {
        this.resourceRepository = resourceRepository;
    }

    @Override
    public AuthorizationDecision check(Supplier<Authentication> authenticationSupplier,
                                        RequestAuthorizationContext context) {
        Authentication authentication = authenticationSupplier.get();
        if (authentication == null || !authentication.isAuthenticated()) {
            return new AuthorizationDecision(false);
        }

        String resourceId = context.getVariables().get("id");
        boolean isOwner = resourceRepository
                .findOwnerUsername(resourceId)
                .map(owner -> owner.equals(authentication.getName()))
                .orElse(false);

        return new AuthorizationDecision(isOwner);
    }
}
```

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http,
                                            ResourceRepository resourceRepository) throws Exception {
        http
            .authorizeHttpRequests(authorize -> authorize
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/resources/{id}")
                    .access(new ResourceOwnerAuthorizationManager(resourceRepository))
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .formLogin(Customizer.withDefaults());

        return http.build();
    }
}
```

`.access()`에 커스텀 `AuthorizationManager`를 전달하면, 해당 경로 패턴에 매칭되는 요청은 내장 규칙 대신 이 구현체의 판단을 그대로 따른다.

## 실무 포인트

레거시 `WebSecurityConfigurerAdapter` 코드를 마이그레이션할 때는 `configure(HttpSecurity http)` 안의 명령형 호출 체인을 그대로 옮기려 하지 말고, 람다 기반 DSL로 다시 작성하는 편이 안전하다. 특히 여러 개의 `WebSecurityConfigurerAdapter` 서브클래스를 `@Order`로 순서를 매겨 사용하던 구조였다면, 각각을 독립된 `SecurityFilterChain` 빈으로 변환하면서 `securityMatcher()`로 적용 범위를 명시적으로 지정해야 의도치 않게 여러 체인이 겹치는 문제를 피할 수 있다. `AccessDecisionVoter`를 직접 구현했던 코드가 있다면, 이를 그대로 옮길 수 있는 대응 인터페이스가 없으므로 `AuthorizationManager` 구현으로 새로 작성해야 한다는 점도 유념해야 한다.

인가 로직을 테스트할 때는 `spring-security-test`가 제공하는 `@WithMockUser`, `SecurityMockMvcRequestPostProcessors`를 활용해 다양한 권한 조합의 사용자로 요청을 재현하는 것이 기본이다. 커스텀 `AuthorizationManager`처럼 로직이 복잡해질수록, 필터 체인 전체를 띄우는 통합 테스트뿐 아니라 `AuthorizationManager` 구현체 자체를 단위 테스트로 분리해 검증하면 원인 파악이 훨씬 쉬워진다. `Authentication`과 판단 대상 객체(`RequestAuthorizationContext` 등)를 목(mock)으로 구성해 여러 입력 조합에 대한 `AuthorizationDecision` 결과를 직접 검증하는 방식이다.

## 3줄 요약

- Spring Security 6은 `WebSecurityConfigurerAdapter`를 완전히 제거하고 `SecurityFilterChain` 빈 기반의 컴포넌트 설정만을 지원한다.
- 인가 판단은 `AccessDecisionManager`/`Voter` 조합 대신 단일 `AuthorizationManager` 인터페이스로 통일됐고, 이를 직접 구현하면 `hasRole()`로 표현하기 어려운 복잡한 규칙을 필터 체인이나 메서드 시큐리티에 그대로 적용할 수 있다.
- 레거시 코드 마이그레이션 시에는 명령형 체인을 그대로 옮기기보다 DSL로 재작성하고, 커스텀 인가 로직은 필터 체인 통합 테스트와 `AuthorizationManager` 단위 테스트를 병행해 검증하는 것이 안전하다.

## 참고 자료

- [Spring Security Reference — Authorization Architecture](https://docs.spring.io/spring-security/reference/servlet/authorization/architecture.html)
- [Spring Security Reference — Authorize HTTP Requests](https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html)
- [Spring Security Reference — Method Security](https://docs.spring.io/spring-security/reference/servlet/authorization/method-security.html)
- [Spring Security Migration Guide](https://docs.spring.io/spring-security/reference/migration/index.html)
