---
layout: single
title: "Spring Boot 3.4/3.5 신규 기능 총정리 — 지금 업그레이드해야 하는 이유"
date: 2026-08-20 12:25:00 +0530
categories: backend
tags: ["backend", "spring-boot", "java", "upgrade", "spring-framework"]
toc: true
toc_sticky: true
excerpt: "Spring Boot 3.4와 3.5에서 추가된 주요 기능과 설정 변화를 실무 관점에서 정리하고, 업그레이드 시 확인해야 할 체크리스트를 짚는다."
---

마이너 버전 업그레이드는 늘 후순위로 밀린다. 메이저 버전처럼 마이그레이션 가이드를 정독하고 릴리스 노트를 통째로 읽어야 할 부담은 없어 보이지만, 정작 "패치 버전만 올리면 되겠지"라는 생각으로 방치하다가 프로덕션 이슈를 만난 뒤에야 릴리스 노트를 뒤늦게 확인하는 경우가 흔하다. 실제 업무에서는 릴리스 주기가 촘촘하고, 각 마이너 버전 사이의 변경 사항이 누적되면 나중에 한 번에 건너뛰기가 더 부담스러워진다는 점도 미루는 이유 중 하나다.

Spring Boot 3.4/3.5대는 이런 관성을 그대로 따르기 어려운 릴리스에 가깝다. 로깅, 설정 구성, 예외 응답 포맷, Actuator 등 애플리케이션의 기본 골격에 해당하는 부분에서 실무 영향이 큰 변화가 다수 포함되어 있기 때문이다. 특히 구조화 로깅처럼 운영 환경의 로그 파이프라인과 직결되는 기능은, 도입 여부와 무관하게 일단 무엇이 바뀌었는지 파악해두는 편이 이후 트러블슈팅 시간을 줄여준다. 이 글에서는 두 버전대에서 실제로 다뤄진 대표적인 변화를 실무 관점에서 정리하고, 업그레이드 전에 점검할 항목을 함께 짚는다.

## 핵심 개념 1: 구조화 로깅(Structured Logging) 지원

Spring Boot 3.4대부터 별도의 커스텀 인코더나 외부 라이브러리 설정 없이, 애플리케이션 설정만으로 로그를 JSON 형식의 구조화된 포맷으로 출력할 수 있는 기능이 추가됐다. 기존에는 Logback이나 Log4j2 설정 파일에 JSON 인코더를 직접 구성하거나 logstash-logback-encoder 같은 외부 의존성을 추가해야 했지만, 이제는 `logging.structured.format` 계열 프로퍼티만 지정하면 표준 포맷(ECS, GELF 등) 중 하나로 즉시 출력할 수 있다. 컨테이너 환경에서 로그를 수집기(Fluentd, Filebeat 등)로 넘길 때 파싱 규칙을 별도로 관리하지 않아도 된다는 점에서, 클라우드 네이티브 운영 환경에 특히 유용한 변화다.

또한 사용자 정의 구조화 로깅 포맷을 직접 구현해 등록할 수 있는 확장 지점도 함께 제공되므로, 사내 표준 로그 스키마가 이미 있는 조직이라면 표준 포맷 대신 자체 포맷터를 붙이는 방향도 검토할 만하다.

## 핵심 개념 2: 프로파일별 설정과 `application.properties`/`.yml` 구성 개선

프로파일 특화 설정 파일(`application-{profile}.properties` 등)의 로딩 순서와 우선순위 관련 개선이 3.4/3.5대에 걸쳐 이어졌다. 특히 다중 문서(YAML의 `---` 구분자) 구조에서 프로파일 그룹(`spring.profiles.group`)과 조합될 때 발생하던 일부 모호한 우선순위 케이스가 정리되었고, 설정 값의 출처를 추적하기 위한 진단 정보도 개선되었다. 정확한 세부 동작은 버전별로 조금씩 다르므로, 여러 프로파일 설정 파일을 조합해 쓰는 프로젝트라면 업그레이드 후 실제 병합 결과를 로그나 Actuator의 환경 엔드포인트로 반드시 확인하는 편이 안전하다.

## 핵심 개념 3: ProblemDetail·Jackson 관련 개선

Spring Framework 6.x 계열과 맞물려, 예외를 RFC 9457 `ProblemDetail` 형식으로 응답할 때의 직렬화 동작이 다듬어졌다. 커스텀 필드를 `properties`에 추가하는 방식과 Jackson 모듈 등록 방식이 보다 예측 가능해졌고, 전역 예외 처리기(`@ExceptionHandler`, `ResponseEntityExceptionHandler`)를 사용하는 REST API에서 에러 응답 포맷을 통일하기가 이전보다 수월해졌다. Jackson 관련 자동 구성 쪽에서도 직렬화 옵션을 세밀하게 제어할 수 있는 프로퍼티가 일부 추가되었으므로, 표준화된 에러 응답 스펙을 API 문서에 명시하는 팀이라면 이 부분을 확인해볼 가치가 있다.

## 핵심 개념 4: Actuator·헬스체크 개선

Actuator의 헬스 인디케이터 쪽에서도 그룹별 상세도(detail) 노출 제어, 개별 컴포넌트 상태를 조합하는 방식과 관련한 다듬기가 이어졌다. 쿠버네티스 liveness/readiness 프로브와 연동해 헬스 엔드포인트를 쓰는 구성이 일반화된 만큼, 특정 헬스 인디케이터의 실패가 전체 상태에 반영되는 방식이 바뀌면 프로브 임계값이나 알림 조건에도 영향을 줄 수 있다. 업그레이드 후에는 `/actuator/health`의 실제 응답 구조를 스테이징 환경에서 한 번 비교해보는 것이 좋다.

## 예제

구조화 로깅을 활성화하는 설정 예시다.

```properties
# application.properties
logging.structured.format.console=ecs
logging.structured.format.file=ecs
```

`ecs` 대신 조직에서 이미 사용 중인 로그 수집 표준에 맞는 포맷을 지정하거나, 커스텀 포맷터 빈을 등록해 대체할 수 있다.

```yaml
# application.yml — 프로파일별 병합 예시
spring:
  profiles:
    group:
      production: "prod-db,prod-logging"
---
spring:
  config:
    activate:
      on-profile: prod-logging
logging:
  structured:
    format:
      console: ecs
```

## 실무 포인트

- **로그 파이프라인 담당자와 먼저 논의한다**: 구조화 로깅 포맷을 실제로 켜기 전에, 로그 수집기 쪽 파싱 규칙이 이미 텍스트 로그 기준으로 짜여 있는지부터 확인해야 한다.
- **프로파일 병합 결과를 직접 검증한다**: 여러 프로파일 파일과 그룹을 조합해 쓰는 프로젝트는, 업그레이드 후 Actuator 환경 엔드포인트나 로그로 최종 병합된 설정 값을 반드시 재확인한다.
- **에러 응답 포맷 계약을 재점검한다**: `ProblemDetail` 기반 API를 제공 중이라면, 클라이언트(특히 프런트엔드나 외부 연동사)와 공유한 에러 응답 스키마가 여전히 동일하게 나오는지 통합 테스트로 확인한다.
- **헬스체크 프로브 설정을 스테이징에서 먼저 검증한다**: 쿠버네티스 liveness/readiness와 연동된 헬스 엔드포인트는, 업그레이드 후 응답 구조 변화가 프로브 실패로 이어지지 않는지 별도 확인이 필요하다.
- **의존성 호환성을 함께 확인한다**: Spring Framework, Jackson 등 연관 라이브러리 버전이 함께 올라가므로, 사내 공용 라이브러리나 스타터가 특정 버전에 고정되어 있지 않은지 점검한다.

## 3줄 요약

- Spring Boot 3.4/3.5대는 구조화 로깅, 프로파일 설정 병합, ProblemDetail·Jackson 직렬화, Actuator 헬스체크 등 애플리케이션 기본 골격에 영향을 주는 변화를 다수 포함한다.
- 구조화 로깅은 별도 인코더 설정 없이 프로퍼티만으로 JSON 로그를 출력할 수 있게 해주지만, 로그 수집 파이프라인과의 호환 여부를 먼저 확인해야 한다.
- 업그레이드 전에는 프로파일 병합 결과, 에러 응답 포맷, 헬스체크 응답 구조를 스테이징 환경에서 직접 검증하는 체크리스트를 거치는 것이 안전하다.

## 참고 자료

- [Spring Boot 공식 문서](https://docs.spring.io/spring-boot/)
- [Spring Blog — 릴리스 공지](https://spring.io/blog)
- [Spring Boot GitHub 릴리스 노트](https://github.com/spring-projects/spring-boot/releases)
