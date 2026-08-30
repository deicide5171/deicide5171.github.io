---
layout: single
title: "소셜 로그인 redirect_uri mismatch 에러 잡기 — OAuth2 콜백 URL 설정 가이드"
date: 2026-09-23 12:25:00 +0530
categories: backend
tags: ["oauth2", "소셜로그인", "springsecurity", "redirecturi", "인증"]
toc: true
toc_sticky: true
excerpt: "구글·카카오 로그인 연동 중 redirect_uri_mismatch 에러로 막힐 때, 콘솔에 등록한 URL과 실제 요청 URL이 어디서 어긋나는지 찾아 해결하는 방법을 Spring Security OAuth2 클라이언트 기준으로 정리했다."
---

## 왜 로컬에서는 되던 로그인이 배포하면 막힐까

로컬 개발 환경에서는 잘 되던 구글·카카오 소셜 로그인이 스테이징이나 운영 서버에 배포하자마자 `redirect_uri_mismatch` 에러 화면으로 막힌다. 화면에는 "등록된 리디렉션 URI와 일치하지 않습니다" 정도의 메시지만 뜨고, 정작 어떤 URL이 왜 어긋났는지는 알려주지 않아 답답하다.

이 에러는 OAuth2 인가 서버(구글, 카카오 등)가 보안을 위해 **인가 요청에 담긴 redirect_uri가 사전에 개발자 콘솔에 등록해둔 값과 문자 그대로 정확히 일치하는지** 검사하기 때문에 발생한다. 여기서 "정확히"라는 게 핵심이다 — 프로토콜, 호스트, 포트, 경로, 심지어 끝에 슬래시(`/`) 하나까지 완전히 같아야 한다.

## 핵심 개념 1 — OAuth2 인가 코드 흐름에서 redirect_uri의 역할

일반적인 인가 코드(Authorization Code) 흐름에서 redirect_uri는 두 번 등장한다. 애플리케이션이 사용자를 인가 서버로 보낼 때 "인가가 끝나면 여기로 돌려보내달라"고 담아 보내는 값, 그리고 인가 서버가 실제로 그 주소로 리다이렉트할 때 쓰는 값이다. 인가 서버는 콘솔에 등록된 화이트리스트와 요청에 담긴 이 값을 비교해, 등록되지 않은 임의의 주소로 인가 코드가 새어나가는 것을 막는다.

<img src="/assets/images/posts/2026-09-23-oauth2-redirect-uri-mismatch-fix-1.svg" alt="사용자를 OAuth2 인가 서버로 보낼 때 담긴 redirect_uri와 개발자 콘솔에 등록된 값이 프로토콜, 호스트, 경로, 슬래시까지 정확히 일치해야 인가 코드가 발급되는 검증 과정을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 환경마다 다른 값을 하드코딩하면 반드시 어긋난다

로컬은 `http://localhost:8080/login/oauth2/code/google`, 스테이징은 `https://staging.example.com/...`, 운영은 `https://example.com/...`처럼 환경마다 호스트가 다르다. 이 값을 코드에 하드코딩해두면 배포 환경이 바뀔 때마다 콘솔 등록값과 어긋나는 사고가 반복된다.

## 예제 — Spring Security OAuth2 클라이언트 설정

```yaml
# application.yml
spring:
  security:
    oauth2:
      client:
        registration:
          google:
            client-id: ${GOOGLE_CLIENT_ID}
            client-secret: ${GOOGLE_CLIENT_SECRET}
            # {baseUrl}이 요청 시점의 실제 호스트로 자동 치환된다
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
            scope: [email, profile]
```

Spring Security의 `{baseUrl}` 플레이스홀더를 쓰면, 실제 요청이 들어온 호스트를 기준으로 redirect_uri를 자동으로 만들어준다. 다만 이 값도 결국 구글 콘솔에 등록해둔 값과 최종적으로 일치해야 하므로, 콘솔에는 로컬용과 스테이징용, 운영용 URL을 **모두** 승인된 리디렉션 URI 목록에 추가해둬야 한다.

```
# 구글 클라우드 콘솔 - 승인된 리디렉션 URI에 각 환경별로 모두 등록
http://localhost:8080/login/oauth2/code/google
https://staging.example.com/login/oauth2/code/google
https://example.com/login/oauth2/code/google
```

## 흔한 원인 체크리스트

| 원인 | 확인 방법 |
|---|---|
| http와 https 프로토콜 불일치 | 리버스 프록시 뒤에서 실제로 https로 들어오는지, `{baseUrl}`이 http로 계산되진 않는지 확인 |
| 포트 번호 누락/추가 | 콘솔엔 `:8080` 없이 등록했는데 실제 요청엔 포트가 붙는 경우 |
| 경로 끝 슬래시 유무 | `/callback`과 `/callback/`은 다른 값으로 취급됨 |
| 로드밸런서 뒤 X-Forwarded 헤더 미반영 | 프록시 뒤에서 서버가 자신을 http://internal-ip로 인식해 `{baseUrl}`이 잘못 계산됨 |
| www 유무 불일치 | example.com과 www.example.com은 다른 호스트 |

특히 로드밸런서나 리버스 프록시 뒤에 배포하는 경우가 가장 까다롭다. 실제 사용자는 `https://example.com`으로 접속했지만, 프록시가 내부적으로 `http`로 애플리케이션 서버에 전달하면 Spring이 계산하는 `{baseUrl}`이 `http://example.com`이 되어버려 콘솔에 등록한 `https` 값과 어긋난다. 이 경우 `server.forward-headers-strategy: native` 설정을 켜서 `X-Forwarded-Proto` 헤더를 신뢰하도록 만들어야 한다.

## 실무 포인트

- **에러 화면의 힌트를 놓치지 마라.** 대부분의 인가 서버는 개발자 도구용으로 실제 요청에 담긴 redirect_uri 값을 URL 파라미터나 에러 상세 정보에 노출한다. 이 값을 콘솔 등록값과 문자 단위로 비교하면 원인을 빠르게 좁힐 수 있다.
- **모든 배포 환경의 URL을 처음부터 콘솔에 등록해두는 습관을 들여라.** 나중에 스테이징 환경을 추가할 때마다 이 에러를 다시 겪는 팀이 많다.
- **로컬 개발 시 HTTPS 터널링 도구를 쓴다면 매번 바뀌는 임시 도메인도 등록해야 한다.** ngrok 같은 도구는 재시작할 때마다 주소가 바뀌므로, 고정 서브도메인 옵션을 쓰는 것이 반복 등록의 번거로움을 줄여준다.

## 마무리 요약

- redirect_uri_mismatch는 인가 서버가 요청에 담긴 URL과 콘솔에 등록된 URL을 프로토콜·호스트·경로·슬래시까지 완전히 일치하는지 검사하다 실패했을 때 발생한다.
- 환경마다 다른 호스트를 하드코딩하지 말고 `{baseUrl}` 같은 동적 플레이스홀더를 쓰되, 모든 환경의 URL을 콘솔에 빠짐없이 등록해야 한다.
- 프록시 뒤에 배포한 경우 X-Forwarded-Proto 헤더를 신뢰하도록 설정하지 않으면 프로토콜 불일치로 같은 에러가 반복된다.

## 참고 자료

- [Spring Security 공식 문서 - OAuth2 Login](https://docs.spring.io/spring-security/reference/servlet/oauth2/login/core.html)
- [RFC 6749 - The OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749)
