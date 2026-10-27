---
layout: single
title: "\"이 앱, 구버전 쓰는 유저 안 끊기게 하면서 새 API 내보내주세요\" — Spring Framework 7 네이티브 버저닝으로 설계하기"
date: 2026-10-27 12:40:00 +0530
categories: stack
tags: ["springboot4", "springframework7", "api버저닝", "백엔드설계", "하위호환성"]
toc: true
toc_sticky: true
excerpt: "모바일 앱 강제 업데이트 없이 API를 바꿔야 한다는 요구는 결국 버전 공존 문제다. Spring Framework 7이 @RequestMapping에 추가한 네이티브 버저닝과 ApiVersionConfigurer를 기준으로, 헤더·경로·파라미터 전략의 트레이드오프와 도입 순서를 정리했다."
---

## 도입

"이번에 API를 바꿀 건데, 아직 구버전 앱 쓰는 유저가 30%나 돼요. 그 사람들 끊기면 안 돼요." 모바일 앱을 가진 백엔드라면 분기마다 듣는 요구다. 이 말은 결국 **같은 리소스에 대해 여러 버전의 API 계약을 동시에 서비스해야 한다**는 기술 문제로 번역된다. 그동안 Spring에는 이걸 위한 표준 장치가 없어서, 팀마다 `/v1/`, `/v2/` 같은 URL 접두어로 컨트롤러를 통째로 분리하거나, 커스텀 `HandlerInterceptor`로 헤더를 읽어 분기하는 식의 자체 구현을 쌓아왔다.

Spring Boot 4의 기반인 Spring Framework 7은 이 문제에 네이티브 지원을 추가했다. `@RequestMapping`과 그 축약 애너테이션(`@GetMapping`, `@PostMapping` 등)에 `version` 속성이 생겼고, `ApiVersionConfigurer`로 버전을 어디서 읽을지(헤더, 경로 세그먼트, 쿼리 파라미터, 미디어 타입) 선택할 수 있다. 이 글은 이 기능이 왜 지금 쓸모 있는지, 그리고 기존의 수동 버저닝 방식과 비교했을 때 어떤 트레이드오프가 있는지 정리한다. 다만 이 기능은 Spring Framework 7.1 기준 공식 문서에서 "아직 개발 중이며 안정화되지 않음"이라 명시하고 있으므로, 프로덕션 적용은 7.0.x 안정 버전을 기준으로 검증해야 한다.

## 전체 시스템에서의 위치

클라이언트 요청이 들어오면 API Version Resolver가 설정된 전략에 따라 버전 값을 추출하고, `SemanticApiVersionParser`가 이를 `major.minor.patch` 형태로 해석한다. 이 값으로 같은 경로에 매핑된 여러 핸들러 중 하나를 고르고, 지원하지 않는 버전이면 `InvalidApiVersionException`을 던진다.

<img src="/assets/images/posts/2026-10-27-spring-framework-7-api-versioning-design-1.svg" alt="클라이언트 요청이 API Version Resolver와 SemanticApiVersionParser를 거쳐 버전별 핸들러로 분기되고, 지원 종료 예정 버전에는 Deprecation 헤더가 붙는 전체 흐름도" style="width:100%;">

- **요청 진입점**: 클라이언트가 헤더(`API-Version: 1.2.0`)나 경로(`/v1/orders`), 쿼리 파라미터(`?api-version=1`) 중 설정된 방식으로 버전을 명시한다.
- **버전 해석**: `ApiVersionConfigurer`에 등록한 `ApiVersionResolver`가 요청에서 값을 뽑고, `SemanticApiVersionParser`가 비교 가능한 버전 객체로 변환한다.
- **핸들러 분기**: 같은 URL 패턴에 `version` 속성이 다른 여러 메서드가 매핑돼 있어도, 프레임워크가 요청 버전에 맞는 메서드 하나로 라우팅한다.
- **지원 종료 신호**: `ApiVersionDeprecationHandler`를 등록하면 지원 종료 예정 버전에 자동으로 `Deprecation` 헤더(RFC 9745)를 붙여 클라이언트에게 전환을 유도할 수 있다.

## 선택의 트레이드오프

| 전략 | 캐싱 친화성 | REST 원칙 부합 | 클라이언트 구현 난이도 | 적합한 상황 |
|---|---|---|---|---|
| 요청 헤더 (`API-Version`) | CDN 캐시 키에 헤더 포함 설정 필요 | 리소스 URI가 버전과 무관하게 유지됨 | 클라이언트가 커스텀 헤더를 매번 추가해야 함 | 내부 서비스 간 통신, 세밀한 버전 제어 |
| 경로 세그먼트 (`/v1/...`) | URL 자체가 캐시 키라 캐싱이 쉬움 | 같은 리소스가 여러 URI를 가져 엄밀한 REST 원칙과 어긋남 | 가장 직관적, 문서화·디버깅이 쉬움 | 외부 공개 API, 문서 기반 온보딩이 중요한 경우 |
| 쿼리 파라미터 (`?api-version=`) | URL이 달라져 캐싱에 영향 | URI는 유지되지만 쿼리로 리소스 의미가 바뀜 | 기존 호출에 파라미터만 추가하면 돼 적용 쉬움 | 점진적 전환, 레거시 클라이언트와의 호환 |
| 미디어 타입 (`Accept` 헤더) | 헤더 기반이라 캐시 설정 필요 | 콘텐츠 협상이라는 HTTP 원래 메커니즘과 가장 잘 맞음 | 클라이언트가 `Accept` 헤더 조작에 익숙해야 함 | API 게이트웨이 없이 엄격한 REST 설계를 지키려는 경우 |

이미 API 게이트웨이나 로드밸런서 레벨에서 버저닝을 처리하고 있다면, 애플리케이션 레벨에서 또 버저닝 로직을 두는 것은 중복 설계다. 그 경우 Spring의 네이티브 버저닝은 게이트웨이가 넘겨준 버전 정보를 해석하는 역할로만 좁혀 쓰는 편이 낫다. 반대로 게이트웨이가 없고 애플리케이션이 직접 다양한 클라이언트를 상대한다면, 기존 클라이언트와의 호환성을 가장 덜 해치는 전략(보통 쿼리 파라미터나 헤더)부터 시작하는 것이 안전하다.

## 실제 프로젝트 진행 순서

1. **기존 버저닝 방식을 전수 감사한다.** URL 접두어로 컨트롤러를 분리했는지, 커스텀 인터셉터로 헤더를 읽었는지부터 파악해야 마이그레이션 범위가 보인다.
2. **`ApiVersionConfigurer`로 전략을 선택한다.** 기존 클라이언트가 이미 특정 방식(예: URL 접두어)에 맞춰져 있다면, 호환성을 위해 같은 방식을 유지하는 쪽이 안전하다.
3. **버전 포맷이 표준 semver와 다르면 커스텀 `ApiVersionResolver`를 작성한다.** 기본 `SemanticApiVersionParser`는 `major.minor.patch` 형식을 전제하므로, 사내 표준이 다르면 파서부터 맞춰야 한다.
4. **지원 종료 예정 버전에 `ApiVersionDeprecationHandler`를 붙여 점진적으로 전환한다.** 강제 차단보다 `Deprecation` 헤더로 먼저 알리고 전환 기간을 주는 편이 리스크가 적다.
5. **7.0.x 안정 버전 기준으로 동작을 검증한다.** 공식 문서가 7.1에서 아직 안정화되지 않았다고 명시하므로, 프로덕션 적용 전 실제 배포 대상 버전에서 재현 테스트를 거친다.
6. **API 게이트웨이와의 역할 분담을 명확히 한다.** 게이트웨이가 이미 라우팅 레벨 버저닝을 하고 있다면 애플리케이션 레벨 버저닝과 책임이 겹치지 않도록 경계를 문서화한다.

```java
// 버전별로 분기되는 핸들러 — 같은 경로에 version 속성만 다르게 매핑
@RestController
@RequestMapping("/orders")
class OrderController {

    @GetMapping(path = "/{id}", version = "1.0.0")
    OrderV1Response getOrderV1(@PathVariable String id) { /* 기존 응답 포맷 */ return null; }

    @GetMapping(path = "/{id}", version = "2.0.0")
    OrderV2Response getOrderV2(@PathVariable String id) { /* 변경된 응답 포맷 */ return null; }
}

// 버전 해석 전략 설정 — 요청 헤더 기반
@Configuration
class WebConfig implements WebMvcConfigurer {
    @Override
    public void configureApiVersioning(ApiVersionConfigurer configurer) {
        configurer.useRequestHeader("API-Version")
                  .setVersionRequired(true)
                  .setDeprecationHandler((request, response, parsed) ->
                      response.setHeader("Deprecation", "version=\"1.0.0\""));
    }
}
```

## 실무 포인트

- 네이티브 버저닝이 생겼다고 해서 기존 URL 접두어 방식을 당장 걷어낼 필요는 없다. 이미 운영 중인 외부 공개 API라면 클라이언트 영향이 더 큰 쪽이 전환 비용이다.
- JSpecify 기반 null-safety나 Jakarta EE 11 베이스라인 같은 Spring Boot 4의 다른 변경과 동시에 마이그레이션 계획을 세우면, 한 번의 업그레이드 작업에서 여러 리스크가 겹쳐 디버깅이 어려워진다. 버저닝 전환은 별도 단계로 분리하는 편이 안전하다.
- `setVersionRequired(true)`로 버전 명시를 강제하면 기존 클라이언트가 버전 없이 보내던 요청이 전부 실패할 수 있으므로, 전환 초기에는 기본 버전을 지정해 하위 호환을 유지하는 설정부터 시작한다.

## 마무리

- API 버전 공존 요구는 Spring Framework 7의 `version` 속성과 `ApiVersionConfigurer`로 네이티브하게 풀 수 있게 됐다.
- 전략 선택은 캐싱·REST 원칙·클라이언트 구현 난이도의 트레이드오프이며, 이미 게이트웨이가 버저닝을 처리 중이라면 중복 설계를 피해야 한다.
- 적용 순서는 기존 방식 감사 → 전략 선택 → 커스텀 파서 필요 여부 확인 → Deprecation 핸들러로 점진적 전환 → 안정 버전 기준 검증이다.

## 참고 자료

- [First-Class API Versioning in Spring Boot 4](https://www.danvega.dev/blog/spring-boot-4-api-versioning)
- [Spring Framework 7.1 Reference — API Version](https://docs.spring.io/spring/reference/7.1/web/webmvc/mvc-config/api-version.html)
- [Explore Spring Framework 7 Features — API Versioning](https://nljug.org/foojay/explore-spring-framework-7-features-api-versioning/)
