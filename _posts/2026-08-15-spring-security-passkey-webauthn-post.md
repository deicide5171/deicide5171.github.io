---
layout: single
title: "Spring Security로 비밀번호 없는 로그인 만들기 — Passkey(WebAuthn) 인증"
date: 2026-08-15 11:25:00 +0530
categories: backend
tags: ["spring-security", "passkey", "webauthn", "java", "authentication"]
toc: true
toc_sticky: true
excerpt: "비밀번호 유출·피싱 문제를 근본적으로 없애는 패스키 로그인이 빠르게 확산되는 지금, Spring Security의 WebAuthn 지원으로 Spring Boot 서비스에 비밀번호 없는 로그인을 붙이는 방법을 정리한다."
---

## 왜 지금 패스키(Passkey)인가

비밀번호는 여전히 가장 흔한 침해 경로다. 유출된 비밀번호 재사용, 피싱 사이트로 유도된 입력, 약한 비밀번호에 대한 크리덴셜 스터핑까지 — 문제의 근본 원인은 "서버가 검증할 수 있는 비밀이 사용자 손에도 똑같이 존재한다"는 구조 자체에 있다. **패스키(Passkey)** 는 이 구조를 뒤집는다. 공개키 암호화를 이용해 개인키는 사용자의 기기(또는 보안 키) 밖으로 절대 나가지 않고, 서버는 오직 공개키로 서명을 검증만 한다.

주요 브라우저와 OS가 패스키 생성·저장을 표준 API로 지원하면서 채택이 빠르게 늘고 있고, Java 생태계에서도 Spring Security가 WebAuthn 기반 패스키 등록·인증을 정식 지원하기 시작했다. 기존 Spring Boot 서비스에 비밀번호 없는 로그인을 붙이는 진입 장벽이 눈에 띄게 낮아진 시점이다.

## 핵심 개념 1: WebAuthn 동작 원리

WebAuthn(Web Authentication API)은 브라우저, 인증기(Authenticator, 지문 센서나 보안 키), 서버(Relying Party) 세 주체가 공개키 기반 challenge-response로 신원을 증명하는 W3C 표준이다.

<img src="/assets/images/posts/2026-08-15-spring-security-passkey-webauthn-1.svg" alt="WebAuthn 로그인 흐름 - 브라우저, 인증기, Spring Security 서버 간 challenge 서명 검증 시퀀스" style="width:100%;">

핵심은 **비밀번호 자체가 존재하지 않는다**는 점이다. 등록 시 인증기가 공개키/개인키 쌍을 생성해 개인키는 기기 안 보안 영역(TPM, Secure Enclave 등)에 저장하고 공개키만 서버로 보낸다. 로그인 시 서버가 매번 새로운 challenge(난수)를 발급하고, 인증기는 지문·얼굴 인식 같은 생체 인증으로 개인키를 잠금 해제해 challenge에 서명한다. 서버는 등록 시 받은 공개키로 이 서명을 검증한다. 서명은 challenge마다 달라지므로 리플레이 공격도, 피싱 사이트에 잘못 입력하는 시나리오 자체도 성립하지 않는다(도메인이 다르면 인증기가 서명을 거부한다).

## 핵심 개념 2: Spring Security의 역할

Spring Security는 애플리케이션 서버(Relying Party) 쪽 로직 — 등록 challenge 발급, 공개키 저장, 로그인 challenge 발급, 서명 검증 — 을 표준화된 설정으로 제공한다. 개발자는 WebAuthn 프로토콜의 저수준 바이트 처리를 직접 구현할 필요 없이 Spring Security의 설정 DSL로 활성화하면 된다.

| 인증 방식 | 서버가 보관하는 비밀 | 피싱 내성 | 구현 복잡도 |
|---|---|---|---|
| 비밀번호 | 해시(유출 시 크래킹 위험) | 낮음 | 낮음 |
| OAuth2/OIDC (소셜 로그인) | 없음(IdP 위임) | IdP 의존 | 중간 |
| Passkey(WebAuthn) | 공개키만(무의미한 정보) | 높음(도메인 바인딩) | 중간~높음(초기 설정) |

## 예제: Spring Boot에 WebAuthn 활성화하기

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/webauthn/**", "/login/**").permitAll()
                .anyRequest().authenticated()
            )
            .webAuthn(webAuthn -> webAuthn
                .rpName("My Spring App")
                .rpId("example.com")           // 서비스 도메인과 반드시 일치해야 함
                .allowedOrigins("https://example.com")
            );
        return http.build();
    }

    @Bean
    public PublicKeyCredentialUserEntityRepository userEntityRepository() {
        return new InMemoryPublicKeyCredentialUserEntityRepository();
    }

    @Bean
    public UserCredentialRepository userCredentialRepository() {
        return new InMemoryUserCredentialRepository();
    }
}
```

`rpId`는 패스키가 어느 도메인에 바인딩되는지를 결정하는 값이라, 실제 서비스 도메인과 정확히 일치해야 한다. 이 값이 틀리면 등록·로그인 자체가 실패하거나, 개발 환경에서 만든 패스키를 운영 도메인에서 재사용할 수 없는 문제가 생긴다. 예제의 인메모리 리포지토리는 학습·테스트용이며, 운영 환경에서는 사용자당 공개키 credential을 영속 저장소(RDB 등)에 저장하는 구현체로 교체해야 한다.

## 실무 포인트

- **비밀번호를 완전히 없애기보다 병행 전략을 먼저 검토한다**: 기존 사용자 마이그레이션, 인증기를 분실했을 때의 계정 복구 경로가 없으면 패스키만으로는 잠금 위험이 크다. 초기에는 "패스키 우선, 비밀번호/이메일 인증 폴백"으로 시작하는 것이 현실적이다.
- **RP ID와 오리진 설정을 환경별로 분리한다**: 로컬 개발, 스테이징, 운영 도메인이 다르면 각 환경에서 별도로 등록한 패스키가 필요하다는 점을 사용자에게 안내해야 한다.
- **여러 인증기 등록을 허용한다**: 사용자가 노트북과 휴대폰 양쪽에서 로그인하려면 기기별로 별도의 패스키를 등록해야 한다. 등록 UI에서 이를 명확히 안내한다.
- **브라우저·OS 지원 현황을 계속 확인한다**: WebAuthn API 자체는 널리 지원되지만, 패스키 동기화(클라우드 백업) 동작은 플랫폼별 차이가 있어 사용자 경험이 조금씩 다를 수 있다.

## 3줄 요약

- 패스키는 개인키가 기기 밖으로 나가지 않는 공개키 challenge-response 구조로, 비밀번호 유출·피싱 문제를 구조적으로 없앤다.
- Spring Security는 WebAuthn 기반 등록·인증 흐름을 표준 설정 DSL로 제공해, RP ID·오리진만 정확히 설정하면 비밀번호 없는 로그인을 붙일 수 있다.
- 운영 도입 시에는 계정 복구 경로, 다중 인증기 등록, 환경별 도메인 설정을 함께 설계해야 안전하게 정착시킬 수 있다.

## 참고 자료

- [Spring Security Reference — Passkeys](https://docs.spring.io/spring-security/reference/servlet/authentication/passkeys.html)
- [W3C — Web Authentication API (WebAuthn) Level 3](https://www.w3.org/TR/webauthn-3/)
- [Baeldung — Integrating Passkeys into Spring Security](https://www.baeldung.com/spring-security-integrate-passkeys)
