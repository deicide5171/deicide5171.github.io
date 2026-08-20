---
layout: single
title: "CORS 에러는 왜 날까 — 원인과 해결법 총정리"
date: 2026-08-31 13:30:00 +0530
categories: frontend
tags: ["cors", "트러블슈팅", "웹개발", "브라우저", "네트워크"]
toc: true
toc_sticky: true
excerpt: "프론트엔드 개발자가 가장 많이 마주치는 CORS 에러가 왜 발생하는지, 브라우저 동작 원리부터 서버·프록시 해결법까지 정리했다."
---

## 왜 CORS는 프론트엔드 개발자를 가장 많이 괴롭히나

콘솔에 `Access-Control-Allow-Origin` 관련 에러가 뜨면 프론트엔드 코드를 아무리 고쳐도 해결되지 않는다. CORS(Cross-Origin Resource Sharing)는 **브라우저가 강제하는 보안 정책**이라, 문제의 원인도 해결도 대부분 서버 쪽에 있기 때문이다. 이 구조를 모르면 프론트엔드 코드만 붙잡고 시간을 낭비하게 된다.

## CORS가 발생하는 조건

브라우저는 요청의 출처(origin)가 응답을 받는 리소스의 출처와 **프로토콜·도메인·포트 중 하나라도 다르면** 교차 출처 요청으로 간주한다.

| 요청 출처 | 대상 URL | 교차 출처 여부 |
|---|---|---|
| `https://a.com` | `https://a.com/api` | 아니오(동일 출처) |
| `https://a.com` | `http://a.com/api` | 예(프로토콜 다름) |
| `https://a.com` | `https://api.a.com` | 예(서브도메인도 다른 출처) |
| `https://a.com:3000` | `https://a.com:8080` | 예(포트 다름) |

## 왜 서버가 정상 응답해도 브라우저가 막는가

서버는 사실 요청을 정상적으로 처리하고 응답까지 내려보낸다. 문제는 **브라우저가 그 응답을 자바스크립트 코드에 넘겨주지 않고 차단**한다는 점이다. 개발자 도구 Network 탭에서 응답 상태 코드가 200인데도 콘솔에는 CORS 에러가 뜨는 이유가 여기에 있다.

```text
1. 브라우저가 실제 요청 전에 OPTIONS 메서드로 "preflight" 요청을 보낸다
   (GET/POST 단순 요청이고 커스텀 헤더가 없으면 preflight 생략)
2. 서버가 Access-Control-Allow-Origin 등의 헤더로 허용 여부를 응답한다
3. 브라우저가 이 헤더를 확인해 실제 요청 진행 여부를 결정한다
4. 서버가 허용 헤더를 보내지 않으면, 응답은 왔어도 JS에서 접근이 차단된다
```

## 서버 쪽 해결 코드 예제 (Spring Boot)

```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("https://my-frontend.com")
                .allowedMethods("GET", "POST", "PUT", "DELETE")
                .allowedHeaders("*")
                .allowCredentials(true);
    }
}
```

`allowedOrigins("*")`로 전체 허용하면 편하지만, `allowCredentials(true)`와 와일드카드는 함께 쓸 수 없다는 점을 주의해야 한다.

## 실무 포인트

- **개발 환경에서 프론트 개발 서버의 프록시 기능(예: Vite의 `server.proxy`)을 쓰면 CORS 문제를 아예 우회할 수 있다.** 다만 이는 개발 편의를 위한 것이지 프로덕션 해결책은 아니다.
- **`no-cors` 모드로 fetch를 호출해서 억지로 우회하려는 시도는 응답 본문을 읽을 수 없게 만들 뿐 문제를 해결하지 못한다.**
- **인증 쿠키를 함께 보내야 한다면 프론트엔드에서 `credentials: 'include'`, 서버에서 `Access-Control-Allow-Credentials: true`를 반드시 함께 설정해야 한다.**

## 마무리 요약

- CORS는 브라우저가 강제하는 보안 정책이라 해결은 대부분 서버 설정에서 이뤄져야 한다.
- 서버가 정상 응답해도 허용 헤더가 없으면 브라우저가 JS의 응답 접근을 차단한다.
- allowedOrigins("*")와 allowCredentials(true)는 동시에 쓸 수 없다는 점을 기억해야 한다.

## 참고 자료

- [MDN - CORS](https://developer.mozilla.org/ko/docs/Web/HTTP/CORS)
- [Spring 공식 문서 - CORS](https://docs.spring.io/spring-framework/reference/web/webmvc-cors.html)
