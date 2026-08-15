---
layout: single
title: "API 인증 전략 완전 비교 — OAuth2 vs JWT vs 세션, 언제 무엇을 써야 할까"
date: 2026-08-17 12:25:00 +0530
categories: backend
tags: ["oauth2", "jwt", "session", "api-authentication", "spring-security"]
toc: true
toc_sticky: true
excerpt: "OAuth2, JWT, 세션은 서로 다른 문제를 푸는 도구인데도 자주 뒤섞여 논의된다. 세 방식의 실제 동작 원리와 선택 기준을 정리한다."
---

## 왜 이 세 개념이 자꾸 섞이는가

API 인증을 설계할 때 "JWT 쓸까 세션 쓸까", "OAuth2 도입해야 하나" 같은 질문이 팀 안에서 반복된다. 문제는 이 셋이 같은 층위의 대안이 아니라는 점이다. **세션**과 **JWT**는 "사용자가 누구인지를 요청마다 어떻게 증명할 것인가"에 대한 답이고, **OAuth2**는 애초에 "제3자 애플리케이션에게 내 리소스에 대한 제한된 권한을 어떻게 위임할 것인가"를 다루는 인가(authorization) 프레임워크다. 인증(authentication)에 OAuth2를 쓰려면 그 위에 OpenID Connect(OIDC) 같은 계층을 얹어야 한다.

이 구분이 흐려지면 "소셜 로그인 붙였으니 인증은 끝났다"거나 "JWT는 무조건 최신 방식이라 세션보다 낫다" 같은 오해로 이어진다. 실제로는 셋 다 지금도 각자의 자리에서 널리 쓰이고 있고, 선택 기준은 유행이 아니라 서버 아키텍처(단일 서버냐 분산 서버냐), 클라이언트 형태(브라우저 SPA냐 모바일이냐 서버 간 통신이냐), 그리고 토큰 폐기·감사 요구사항이다.

<img src="/assets/images/posts/2026-08-17-api-auth-oauth2-jwt-session-1.svg" alt="세션, JWT, OAuth2 인증 방식별 흐름 비교도" style="width:100%;">

## 핵심 개념 1: 세션 기반 인증 (Stateful)

로그인 성공 시 서버가 세션을 생성해 서버 측 저장소(메모리, Redis 등)에 사용자 상태를 보관하고, 클라이언트에는 세션ID만 쿠키로 내려준다. 이후 요청마다 서버는 세션ID로 저장소를 조회해 사용자를 식별한다. 서버가 "누가 로그인해 있는지" 상태를 직접 들고 있다는 점에서 **stateful** 방식이다.

## 핵심 개념 2: JWT (Stateless 토큰)

JWT(JSON Web Token)는 사용자 정보와 만료 시각 등을 담은 클레임(claim)을 서버의 비밀키(또는 개인키)로 서명해 발급하는 토큰이다. 클라이언트는 이 토큰을 보관했다가 매 요청의 `Authorization` 헤더에 실어 보내고, 서버는 서명만 검증하면 되므로 별도 저장소 조회가 필요 없다. 이 무상태성(stateless) 덕분에 서버를 수평 확장할 때 세션 동기화 문제가 사라진다.

## 핵심 개념 3: OAuth2 (위임 인가)

OAuth2는 애초에 로그인 자체가 아니라 "A 서비스가 사용자를 대신해 B 서비스의 리소스에 제한된 권한으로 접근하도록 허가하는" 시나리오를 위한 표준이다. 사용자가 인가 서버에서 동의하면 authorization code가 발급되고, 클라이언트는 이를 access token으로 교환해 리소스 서버에 사용한다. "OAuth2로 로그인"이라 부르는 소셜 로그인은 대부분 OAuth2 위에 신원 증명 계층을 얹은 **OIDC**를 쓰는 것이며, access token과 별도로 신원 정보를 담은 ID 토큰(JWT 형식)이 발급된다.

## 비교표: 언제 무엇을 쓰는가

| 기준 | 세션 | JWT | OAuth2(+OIDC) |
|---|---|---|---|
| 해결하는 문제 | 자체 서비스 로그인 상태 유지 | 자체 서비스 로그인 상태 유지(무상태) | 제3자 위임·소셜 로그인 |
| 서버 상태 | 필요(세션 스토어) | 불필요 | 인가 서버가 상태 보유 |
| 즉시 무효화(로그아웃) | 쉬움(세션 삭제) | 어려움(만료까지 유효, 블랙리스트 필요) | 인가 서버의 토큰 폐기(revocation)에 의존 |
| 수평 확장 | 세션 공유 인프라 필요 | 서버 간 공유 상태 없이 확장 용이 | 별도 인가 서버 인프라 필요 |
| 적합한 상황 | 단일 서비스, 모놀리식, 전통적 웹 앱 | MSA, 모바일 API, 서버 간 인증 | 소셜 로그인, 제3자 API 연동, SSO |

## 예제 1: Spring Security 세션 기반 설정

```java
@Configuration
@EnableWebSecurity
public class SessionSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
                .maximumSessions(1) // 계정당 동시 세션 1개로 제한
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/login", "/public/**").permitAll()
                .anyRequest().authenticated()
            )
            .formLogin(Customizer.withDefaults());
        return http.build();
    }
}
```

## 예제 2: JWT 검증 필터 (개념 구조)

```java
public class JwtAuthFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                     FilterChain chain) throws ServletException, IOException {
        String token = extractBearerToken(req);
        if (token != null && jwtValidator.isValid(token)) {
            Claims claims = jwtValidator.parseClaims(token);
            var auth = new UsernamePasswordAuthenticationToken(
                claims.getSubject(), null, mapAuthorities(claims));
            SecurityContextHolder.getContext().setAuthentication(auth);
        }
        chain.doFilter(req, res); // DB·세션 저장소 조회 없이 서명 검증만으로 통과
    }
}
```

## 실무 포인트

- **JWT 만료 시간은 짧게, 갱신은 refresh token으로**: access token을 짧게(수 분~수십 분) 만료시키고 별도 refresh token으로 재발급하는 구조가 유출 피해를 줄인다. refresh token은 탈취·재사용 탐지가 가능한 저장소에서 관리해야 한다.
- **로그아웃·강제 만료가 중요하면 순수 JWT만으로는 부족하다**: 세션처럼 즉시 무효화하려면 블랙리스트(짧은 TTL의 Redis 등)를 함께 두거나, 세션 기반으로 되돌리는 것이 오히려 단순할 수 있다.
- **OAuth2/OIDC는 표준 라이브러리를 직접 구현하지 말 것**: authorization code, PKCE, 리다이렉트 URI 검증 등 세부 사양이 많아 직접 구현 시 취약점이 생기기 쉽다. Spring Security의 OAuth2 Client/Resource Server 지원처럼 검증된 구현을 쓴다.
- **혼합 전략도 흔하다**: 브라우저 세션은 쿠키 기반 세션으로, 서버 간 통신이나 모바일 API는 JWT로, 소셜 로그인 진입점만 OAuth2/OIDC로 처리하는 조합이 실제 서비스에서 자주 쓰인다.

## 3줄 요약

- 세션과 JWT는 같은 문제(자체 로그인 상태 유지)에 대한 stateful·stateless 두 해법이고, OAuth2는 애초에 제3자 위임 인가를 위한 별개의 표준이다.
- 즉시 로그아웃·감사가 중요하면 세션이, 수평 확장·서버 간 인증이 중요하면 JWT가 유리하며 정답은 상황에 따라 갈린다.
- OAuth2로 "로그인"을 구현하려면 OIDC 계층이 필요하고, 세부 구현은 직접 만들기보다 검증된 라이브러리를 쓰는 것이 안전하다.

## 참고 자료

- [Spring Security Reference — Session Management](https://docs.spring.io/spring-security/reference/servlet/authentication/session-management.html)
- [Spring Security Reference — OAuth2](https://docs.spring.io/spring-security/reference/servlet/oauth2/index.html)
- [OAuth 2.0 (RFC 6749)](https://datatracker.ietf.org/doc/html/rfc6749)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [IETF — JSON Web Token (RFC 7519)](https://datatracker.ietf.org/doc/html/rfc7519)
