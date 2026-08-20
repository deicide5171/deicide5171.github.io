---
layout: single
title: "JWT가 뭔가요 — 토큰 구조와 세션과의 차이"
date: 2026-09-02 13:25:00 +0530
categories: backend
tags: ["jwt", "인증", "토큰", "입문", "백엔드기초"]
toc: true
toc_sticky: true
excerpt: "JWT의 세 부분 구조가 각각 무엇을 담는지, 그리고 전통적인 세션 방식과 근본적으로 어떻게 다른지 기초부터 정리했다."
---

## 왜 서버가 로그인 상태를 기억하지 않아도 되는가

전통적인 세션 방식에서는 사용자가 로그인하면 서버가 세션 정보를 메모리나 DB에 저장하고, 클라이언트에게는 세션 ID만 쿠키로 준다. 매 요청마다 서버는 그 ID로 저장된 세션을 찾아 "누구인지"를 확인한다. **JWT(JSON Web Token)** 방식은 이 저장 단계를 없앤다. 사용자 정보 자체를 토큰 안에 담아 클라이언트에게 주고, 서버는 그 토큰이 위조되지 않았는지만 검증한다.

## JWT의 세 부분 구조

JWT는 `.`으로 구분된 세 덩어리로 이뤄진다.

| 부분 | 담는 내용 | 예시 |
|---|---|---|
| Header | 서명 알고리즘 정보 | `{"alg": "HS256", "typ": "JWT"}` |
| Payload | 사용자 정보(claims) | `{"sub": "user123", "exp": 1735689600}` |
| Signature | 위조 검증용 서명 | Header+Payload를 비밀키로 서명한 값 |

```text
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.abc123signature
    ↑ Header            ↑ Payload            ↑ Signature
```

**중요한 점: Payload는 암호화가 아니라 단순 Base64 인코딩이다.** 누구나 디코딩해서 내용을 읽을 수 있으므로, 비밀번호나 개인정보를 JWT에 담으면 안 된다.

## 세션 방식과의 비교

| 항목 | 세션 | JWT |
|---|---|---|
| 서버 저장 | 필요(메모리·Redis·DB) | 불필요(토큰 자체에 정보 포함) |
| 수평 확장 | 세션 공유 저장소 필요 | 서버마다 독립적으로 검증 가능 |
| 즉시 무효화 | 서버에서 세션 삭제하면 즉시 무효 | 어렵다(토큰 만료 전까지 유효) |
| 크기 | 세션 ID만 전송(작음) | 정보를 담아 상대적으로 큼 |

## 코드 예제: JWT 생성과 검증

```java
// 생성
String token = Jwts.builder()
        .subject("user123")
        .expiration(new Date(System.currentTimeMillis() + 3600_000)) // 1시간
        .signWith(secretKey)
        .compact();

// 검증
Claims claims = Jwts.parser()
        .verifyWith(secretKey)
        .build()
        .parseSignedClaims(token)
        .getPayload();
String userId = claims.getSubject();
```

서명 검증에 성공하면 그 토큰의 내용은 발급 이후 변경되지 않았다는 것이 보장된다. 이것이 서버가 세션을 따로 저장하지 않아도 되는 이유다.

## 실무 포인트

- **JWT의 가장 큰 실무 난제는 "즉시 로그아웃"이다.** 토큰은 만료 시각까지 유효하므로, 강제 로그아웃이나 탈취된 토큰 차단이 필요하면 별도의 블랙리스트(무효화 목록)를 서버에 둬야 한다. 이렇게 되면 결국 서버 상태를 관리해야 해서 JWT의 무상태 장점이 줄어든다.
- **액세스 토큰은 짧게(수 분~1시간), 리프레시 토큰은 길게 발급하는 패턴이 표준적이다.** 액세스 토큰이 탈취되더라도 피해 시간이 짧아진다.
- **JWT를 localStorage에 저장하면 XSS 공격에 노출된다.** HttpOnly 쿠키에 저장하는 것이 더 안전하지만, 이 경우 CSRF 방어를 함께 고려해야 한다. 어느 쪽도 완벽하지 않으므로 서비스 특성에 맞게 트레이드오프를 선택해야 한다.

## 마무리 요약

- JWT는 사용자 정보를 토큰 자체에 담아 서버가 세션을 저장하지 않아도 되게 만드는 인증 방식이다.
- Payload는 암호화가 아니라 인코딩이므로 민감 정보를 담으면 안 된다.
- 즉시 무효화가 어렵다는 것이 JWT의 근본적인 한계이며, 짧은 액세스 토큰 + 리프레시 토큰 조합이 표준적인 대응이다.

## 참고 자료

- [JWT 공식 사이트](https://jwt.io/introduction)
- [RFC 7519 - JSON Web Token](https://datatracker.ietf.org/doc/html/rfc7519)
