---
layout: single
title: "Spring Boot 3.5 지원이 끝났다 — Spring Boot 4 마이그레이션, 지금 해야 하는가"
date: 2026-10-18 12:40:00 +0530
categories: stack
tags: ["springboot4", "hibernate7", "jackson3", "마이그레이션", "jpa"]
toc: true
toc_sticky: true
excerpt: "그냥 버전만 올려주세요"라는 요구는 Spring Boot 4에서는 통하지 않는다. Framework 7·Hibernate 7·Jackson 3가 한 묶음으로 따라오는 의존성 체인을 이해하고, 지금 올릴지 유예할지, 올린다면 무엇부터 검증할지를 정리했다.
---

## 왜 지금 이 판단이 필요한가

"Spring Boot 3.5 오픈소스 지원이 2026년 6월 30일에 끝났으니 4로 올려주세요." 팀 안에서 이런 요청이 나오면 버전 숫자 하나 바꾸는 일처럼 들리지만, 실제로는 전혀 다른 크기의 작업이다. Spring Boot 4는 Spring Framework 7, Hibernate 7.2, Jackson 3를 한 묶음으로 끌고 올라가는 메이저 업그레이드이고, 이 셋 중 하나라도 팀의 코드·설정·의존 라이브러리와 어긋나면 컴파일은 되는데 런타임에서 조용히 깨지는 상황이 생긴다.

문제는 이 깨짐이 "배포하자마자 500 에러"처럼 눈에 띄는 형태로 오지 않는다는 점이다. 설정 프로퍼티가 조용히 무시되거나, 특정 JSON 필드가 직렬화에서 빠지거나, 보안 필터 체인이 의도와 다르게 요청을 막는 식으로 나타난다. 그래서 빌더에게 중요한 질문은 "4로 올릴 수 있는가"가 아니라 "지금 올려야 하는가, 올린다면 어떤 순서로 무엇을 먼저 검증해야 깨지는 지점을 배포 전에 잡아낼 수 있는가"다.

## 핵심 개념 1 — 하나가 아니라 의존성 체인이 함께 올라간다

Spring Boot 버전을 올린다는 것은 Boot 자체 코드만 바뀌는 게 아니라, Boot가 고정한 BOM(Bill of Materials)에 묶인 Framework·Hibernate·Jackson·서블릿 컨테이너 버전이 전부 함께 바뀐다는 뜻이다. Boot 4는 Spring Framework 7을 전제로 하고, Framework 7은 Jakarta EE 11 베이스라인과 JSpecify 기반 null-safety 어노테이션을 도입했다. 즉 `javax.*` 잔재가 남아 있던 레거시 라이브러리나, `@Nullable` 어노테이션을 커스텀으로 쓰던 코드는 Boot 설정 파일 한 줄 건드리지 않아도 Framework 레이어에서 깨질 수 있다. Java 최소 버전도 21로 올라가므로, 아직 Java 17에 머물러 있는 프로젝트는 런타임 교체부터 선행해야 한다.

Hibernate도 7.2 계열로 올라가면서 Boot 3.5의 Hibernate 6과 영속성 계층의 세부 동작이 달라진다. ORM 매핑 자체를 바꾸지 않았더라도, 2차 캐시 설정이나 배치 사이즈 관련 설정 키 이름이 바뀐 경우 조용히 기본값으로 되돌아가 N+1이 재발하는 식의 회귀가 생길 수 있다.

## 핵심 개념 2 — 조용히 깨지는 지점은 대부분 Jackson과 보안 필터다

가장 흔하게 보고되는 함정은 두 가지다. 첫째, Boot 4는 Jackson 3를 기본 JSON 코덱으로 바꾼다. Jackson 3는 패키지 네임스페이스 자체가 달라져서, `com.fasterxml.jackson.databind` 기준으로 커스텀 `Serializer`나 `Mixin`을 짜둔 코드, 또는 Jackson 2 전용 애너테이션을 직접 참조하는 서드파티 라이브러리가 컴파일 단계에서 막히거나, 일부 설정 조합에서는 컴파일은 통과하되 런타임에 특정 모듈이 로드되지 않아 날짜 포맷이나 커스텀 직렬화가 조용히 기본 동작으로 되돌아간다. 의존 라이브러리가 아직 Jackson 3를 지원하지 않는다면 Jackson 2 호환 모드로 당분간 우회하는 선택지도 검토해야 한다.

둘째, 설정 프로퍼티가 로드되지 않거나 보안 필터가 의도와 다르게 요청을 막는 사례가 다수 보고된다. Spring Boot Properties Migrator를 업그레이드 전에 먼저 돌려서 이름이 바뀌거나 제거된 프로퍼티 목록을 받아보는 것이 사실상 필수 단계가 됐다. 임베디드 서버로 Undertow를 쓰던 프로젝트는 Boot 4에서 Undertow 옵션 자체가 제거됐으므로 Tomcat이나 Jetty로 전환해야 한다 — 이건 설정값 하나로 끝나지 않고 커넥터 레벨 튜닝(스레드 풀, 커넥션 타임아웃)을 전부 다시 잡아야 하는 작업이다.

## 전체 시스템에서의 위치

<img src="/assets/images/posts/2026-10-18-spring-boot-4-migration-decision-1.svg" alt="요청이 들어와 Jakarta EE 11 기반 Framework 7, Jackson 3 직렬화, Hibernate 7을 거쳐 DB까지 가는 의존성 체인에서 각 레이어가 어떤 버전 변화를 겪는지 보여주는 구조도" style="width:100%;">

요청 하나가 처리되는 경로를 레이어별로 쪼개 보면, Boot 4 업그레이드가 어디를 건드리는지가 선명해진다. HTTP 요청은 서블릿 컨테이너(Tomcat/Jetty, Undertow 제거됨)를 거쳐 Spring MVC·WebFlux(Framework 7, Jakarta EE 11 베이스라인)로 들어오고, 컨트롤러 응답은 Jackson 3가 직렬화하며, 영속성 계층은 Hibernate 7.2가 담당한다. 이 네 레이어가 전부 한 번의 버전 업그레이드로 동시에 바뀌기 때문에, 문제가 생겼을 때 "어느 레이어가 원인인가"를 좁히는 것 자체가 디버깅의 절반을 차지한다.

## 선택의 트레이드오프

| 선택지 | 장점 | 단점 | 적합한 상황 |
|---|---|---|---|
| 지금 바로 4로 마이그레이션 | 최신 보안 패치·기능 확보, 기술부채 선제 해소 | 의존 라이브러리 호환성 전수 점검 필요, 단기 작업량 큼 | 의존 라이브러리가 적고 테스트 커버리지가 높은 서비스 |
| 3.5 상용 지원 구매로 유예 | 당장의 마이그레이션 리스크 회피 | 비용 발생, 결국 한 번은 거쳐야 할 작업을 미루는 것 | 레거시 라이브러리 의존도가 높고 당장 변경 여력이 없는 팀 |
| 모듈 단위 점진적 업그레이드 | 영향 범위를 줄여 디버깅 쉬움 | 과도기 동안 두 버전 체계를 동시에 유지해야 함 | 멀티모듈/마이크로서비스로 이미 분리돼 있는 조직 |

모놀리식 단일 모듈이고 테스트 스위트가 얇다면 세 번째 선택지는 사실상 불가능하다 — 이 경우엔 두 번째(유예)와 첫 번째(즉시 전수 점검 후 이행) 중 하나를 골라야 하며, 유예를 고르더라도 Jackson 3·Jakarta EE 11 호환성 점검은 미리 시작해 두는 편이 나중의 작업량을 줄인다.

## 실제 프로젝트 진행 순서

1. **Properties Migrator를 먼저 돌려 깨질 설정 키 목록을 확보한다.** 업그레이드 전에 이름이 바뀌거나 제거된 프로퍼티를 코드 수정 없이 먼저 파악할 수 있다.
2. **의존 라이브러리의 Jackson 3·Jakarta EE 11 지원 여부를 전수 조사한다.** 지원하지 않는 라이브러리가 있다면 대체재를 찾거나 Jackson 2 호환 모드를 임시로 켠다.
3. **Undertow를 쓰고 있다면 Tomcat/Jetty 전환과 커넥터 튜닝을 먼저 끝낸다.** 이 단계를 Boot 4 업그레이드와 동시에 하면 원인 추적이 훨씬 어려워진다.
4. **전체 테스트 스위트, 특히 직렬화·보안 필터 관련 테스트를 그린으로 만든 뒤에만 스테이징에 배포한다.** 단위 테스트만으로는 Jackson 직렬화 회귀를 못 잡는 경우가 많아 통합 테스트 비중을 늘려야 한다.
5. **스테이징에서 실제 트래픽 패턴으로 보안 필터·2차 캐시 동작을 모니터링한 뒤 운영에 반영한다.**

```gradle
// build.gradle — Spring Boot 4 라인으로 올릴 때의 버전 고정 예
plugins {
    id 'org.springframework.boot' version '4.0.7'
}

dependencies {
    implementation 'org.hibernate.orm:hibernate-core:7.2.19.Final'
    // Jackson 3 미지원 라이브러리가 있다면 호환 모듈을 임시로 추가
    // implementation 'com.fasterxml.jackson.core:jackson-databind:2.x' (과도기 한정)
}
```

## 마무리 요약

- Spring Boot 4 업그레이드는 Boot 단독이 아니라 Framework 7·Hibernate 7·Jackson 3가 한 번에 바뀌는 의존성 체인 업그레이드다.
- 가장 조용히, 가장 흔하게 깨지는 지점은 Jackson 3 네임스페이스 변경과 보안 필터·프로퍼티 로딩 변경이다 — Properties Migrator를 선행 실행하는 것이 사실상 필수다.
- 테스트 커버리지와 라이브러리 의존도에 따라 즉시 이행·유예·모듈 단위 점진 전환 중 전략을 다르게 골라야 한다.

## 참고 자료

- Spring 공식 블로그, Spring Boot 4.0 및 Spring Framework 7 마이그레이션 가이드
- Hibernate 공식 문서, 7.0~7.2 마이그레이션 가이드
- Spring Boot Properties Migrator 공식 문서
