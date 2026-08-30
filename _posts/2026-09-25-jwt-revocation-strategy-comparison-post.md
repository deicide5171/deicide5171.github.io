---
layout: single
title: "무상태 토큰인데 로그아웃이 왜 어려울까 — JWT 즉시 폐기(Revocation) 전략 비교"
date: 2026-09-25 12:25:00 +0530
categories: backend
tags: ["JWT", "토큰폐기", "Redis", "인증", "SpringSecurity"]
toc: true
toc_sticky: true
excerpt: "계정 탈취를 감지해 즉시 로그아웃시키고 싶은데 JWT는 서버가 상태를 들고 있지 않아 만료 전까지 계속 유효하다는 근본 딜레마를, 블랙리스트·짧은 TTL+회전·토큰 버전 관리 세 가지 전략으로 비교해 정리했다."
---

## 왜 지금 JWT Revocation을 다시 봐야 하는가

JWT는 세션 저장소 조회 없이 서명 검증만으로 인증을 끝낼 수 있다는 "무상태(stateless)"가 핵심 장점으로 소개된다. 그런데 이 장점은 곧바로 심각한 딜레마를 낳는다 — 서버가 아무 상태도 들고 있지 않다면, 발급된 토큰을 "지금 당장 무효로 만들 방법"이 원천적으로 없다는 뜻이기 때문이다. 사용자가 로그아웃 버튼을 눌러도, 관리자가 계정을 정지시켜도, 비밀번호를 변경해도 서명이 유효하고 만료 시각이 지나지 않은 JWT는 검증을 통과한다. 계정 탈취가 의심되는 상황에서 즉시 접근을 차단해야 하는 보안 요구사항과, JWT의 무상태 철학은 정면으로 충돌한다. 실무에서는 결국 "완전한 무상태"를 일부 포기하고 서버 쪽에 최소한의 상태를 두는 절충안을 택하게 되는데, 그 절충을 어느 지점에서 할지에 따라 세 가지 전략으로 갈린다.

## 핵심 개념 1 — 블랙리스트: 폐기된 토큰만 별도로 기록한다

가장 직관적인 방법은 폐기하고 싶은 토큰(또는 그 식별자인 `jti` 클레임)을 Redis 같은 빠른 저장소에 만료 시각까지만 저장해두고, 매 요청마다 그 블랙리스트에 있는지 확인하는 것이다. 장점은 개념이 단순하고 "이 토큰 하나만 콕 집어 죽이기"가 정확히 가능하다는 것이다. 단점은 매 요청마다 Redis 조회가 추가되어 JWT가 원래 없애려던 "매 요청 상태 조회"가 사실상 부활한다는 점, 그리고 블랙리스트 저장소 자체가 새로운 장애 지점(SPOF)이 된다는 점이다. TTL을 토큰의 남은 유효기간과 맞춰두면 블랙리스트가 무한정 커지는 것은 막을 수 있다.

## 핵심 개념 2 — 짧은 TTL + Refresh Token 회전, 그리고 토큰 버전

두 번째 전략은 애초에 Access Token의 수명을 5~15분처럼 아주 짧게 줘서, 설령 즉시 폐기가 안 되더라도 피해 노출 시간을 최소화하는 접근이다. 대신 사용자는 별도의 Refresh Token으로 Access Token을 계속 재발급받는데, 이 Refresh Token은 DB에 저장해두고 사용할 때마다 새 값으로 교체(rotation)한다. 로그아웃이나 탈취 감지 시 이 Refresh Token 레코드를 DB에서 지우기만 하면, 이미 발급된 Access Token은 짧은 시간 안에 자연 소멸하고 더 이상 재발급도 불가능해진다. 세 번째 전략인 토큰 버전 관리는 사용자 레코드에 `tokenVersion` 필드를 두고 토큰 발급 시 그 값을 클레임에 포함시킨 뒤, 매 요청마다 DB(또는 캐시)의 현재 버전과 비교하는 방식이다. 비밀번호 변경이나 강제 로그아웃 시 버전을 1 증가시키면 그 순간 발급된 모든 토큰이 한꺼번에 무효화된다 — 특정 토큰 하나가 아니라 "그 사용자의 모든 토큰"을 한 번에 죽이고 싶을 때 유리하다.

| 전략 | 즉시성 | 매 요청 비용 | 적합한 시나리오 |
|---|---|---|---|
| 블랙리스트(jti) | 즉시 | Redis 조회 1회 | 특정 토큰 하나만 정밀 폐기 |
| 짧은 TTL + Refresh 회전 | 최대 TTL만큼 지연 | 없음(Access 검증은 서명만) | 일반적인 로그아웃, 낮은 인프라 부담 |
| 토큰 버전(tokenVersion) | 즉시 | 캐시 조회 1회 | 비밀번호 변경, 계정 전체 강제 로그아웃 |

## 코드 예제 — Spring Security 필터에서 토큰 버전 검증

```java
@Component
public class TokenVersionFilter extends OncePerRequestFilter {

    private final UserVersionCache versionCache; // Redis 등으로 구현

    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                     FilterChain chain) throws IOException, ServletException {
        Jws<Claims> jws = parseJwt(req);
        Long tokenVersion = jws.getBody().get("ver", Long.class);
        Long currentVersion = versionCache.getVersion(jws.getBody().getSubject());

        if (!tokenVersion.equals(currentVersion)) {
            res.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Token revoked");
            return;
        }
        chain.doFilter(req, res);
    }
}
```

## 실무 포인트

- **"즉시 폐기가 반드시 필요한가"부터 먼저 따져라.** 일반 로그아웃은 클라이언트에서 토큰을 지우는 것만으로 UX상 충분한 경우가 많다. 계정 탈취 대응처럼 서버 강제 차단이 꼭 필요한 시나리오에만 무거운 전략을 적용하는 것이 합리적이다.
- **블랙리스트와 토큰 버전을 혼동하지 마라.** 블랙리스트는 "이 토큰 하나"를, 토큰 버전은 "이 사용자의 모든 토큰"을 대상으로 한다. 여러 기기에서 로그인한 사용자를 한 기기만 로그아웃시키고 싶다면 블랙리스트나 세션 ID 기반 관리가 맞고, 계정 전체를 잠그고 싶다면 토큰 버전이 맞다.
- **Refresh Token 회전을 구현할 때는 재사용 탐지(reuse detection)도 함께 넣어야 한다.** 이미 사용되어 폐기된 Refresh Token이 다시 사용되면 토큰 탈취로 간주하고 해당 사용자의 모든 세션을 강제 종료하는 로직을 추가해야 회전의 보안 이점이 완성된다.

## 마무리 요약

- JWT의 무상태성은 발급 후 즉시 폐기를 원천적으로 어렵게 만들며, 실무에서는 서버 쪽에 최소한의 상태를 두는 절충이 불가피하다.
- 블랙리스트는 토큰 단위 정밀 폐기에, 짧은 TTL+Refresh 회전은 낮은 인프라 부담의 일반 로그아웃에, 토큰 버전 관리는 사용자 단위 전체 폐기에 각각 적합하다.
- Refresh Token 회전을 도입한다면 재사용 탐지 로직까지 함께 구현해야 탈취 대응 효과가 실제로 완성된다.

## 참고 자료

- [Auth0 - Blacklist JWTs](https://auth0.com/blog/blacklist-json-web-token-api-keys/)
- [OWASP - JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
