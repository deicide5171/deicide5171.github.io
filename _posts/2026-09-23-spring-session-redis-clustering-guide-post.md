---
layout: single
title: "로드밸런서 뒤에서 로그인이 자꾸 풀릴 때 — Spring Session과 Redis로 세션 클러스터링하기"
date: 2026-09-23 13:45:00 +0530
categories: system-design
tags: ["세션클러스터링", "springsession", "redis", "확장성", "로드밸런싱"]
toc: true
toc_sticky: true
excerpt: "서버를 여러 대로 늘리자마자 사용자 로그인이 무작위로 풀리는 문제를, 세션이 각 서버 메모리에 갇혀 있다는 원인으로 진단하고 Spring Session과 Redis로 세션을 외부화하는 방법을 정리했다."
---

## 왜 서버를 늘리자마자 로그인이 자꾸 풀릴까

트래픽이 늘어 서버를 한 대에서 여러 대로 늘렸더니, 갑자기 사용자들이 "방금 로그인했는데 다시 로그인하라고 뜬다"는 불만을 쏟아낸다. 개발 환경에서는 재현이 잘 안 되다가 운영에서만 간헐적으로 발생하니 원인을 찾기가 더 까다롭다. 정확한 원인은 대부분 **세션이 각 서버의 로컬 메모리에만 저장돼 있기 때문**이다. 사용자의 요청이 로드밸런서를 거쳐 매번 다른 서버로 분산되는데, 로그인 처리는 서버 A가 했지만 다음 요청이 서버 B로 가면 B는 이 사용자의 세션을 전혀 모른다.

이 문제를 임시로 스티키 세션(같은 사용자를 항상 같은 서버로 보내는 로드밸런서 설정)으로 넘기는 팀이 많지만, 이는 근본 해결이 아니라 회피에 가깝다. 특정 서버가 배포나 장애로 재시작되면 그 서버에 붙어 있던 모든 사용자의 세션이 한 번에 날아가고, 서버 간 트래픽 쏠림도 그대로 남는다.

## 핵심 개념 1 — 세션을 애플리케이션 서버 바깥으로 꺼낸다

근본적인 해법은 세션 데이터를 각 서버의 메모리가 아니라, 모든 서버가 공유하는 외부 저장소에 두는 것이다. 이렇게 하면 어떤 서버가 요청을 받든 같은 세션 데이터에 접근할 수 있어 스티키 세션이 필요 없어지고, 서버가 재시작돼도 세션 저장소는 살아 있으니 로그인 상태가 유지된다. 이 외부 저장소로 Redis가 널리 쓰이는 이유는 세션처럼 자주 읽고 쓰는 짧은 수명의 데이터를 매우 빠르게 처리할 수 있기 때문이다.

<img src="/assets/images/posts/2026-09-23-spring-session-redis-clustering-guide-1.svg" alt="로드밸런서가 요청을 서버 A와 서버 B에 번갈아 분산할 때, 세션이 로컬 메모리에 있으면 로그인이 풀리지만 Redis에 중앙화하면 어느 서버가 받아도 같은 세션에 접근하는 구조를 비교하는 다이어그램" style="width:100%;">

## 핵심 개념 2 — Spring Session이 하는 일은 세션 구현체 교체다

Spring 애플리케이션에서 `HttpSession`은 원래 서블릿 컨테이너(Tomcat 등)가 메모리에서 관리한다. Spring Session은 이 기본 구현체를 가로채, 개발자가 기존에 쓰던 `session.setAttribute()` 같은 API는 그대로 두면서 실제 저장 위치만 Redis로 바꿔주는 역할을 한다. 즉 컨트롤러 코드를 거의 손대지 않고도 세션 저장소를 교체할 수 있다는 것이 이 라이브러리의 핵심 가치다.

## 예제 — Spring Boot에 Spring Session Redis 적용하기

```yaml
# application.yml
spring:
  session:
    store-type: redis
    timeout: 30m
  data:
    redis:
      host: redis-cluster.internal
      port: 6379
```

```java
// build.gradle 의존성만 추가하면 별도 설정 클래스 없이도 자동 구성된다
// implementation 'org.springframework.session:spring-session-data-redis'
// implementation 'org.springframework.boot:spring-boot-starter-data-redis'

@RestController
public class LoginController {

    @PostMapping("/login")
    public ResponseEntity<Void> login(HttpSession session, @RequestBody LoginRequest req) {
        // 기존 코드와 완전히 동일 — 실제로는 Redis에 저장된다
        session.setAttribute("userId", authenticate(req));
        return ResponseEntity.ok().build();
    }
}
```

의존성만 추가하면 Spring Boot 오토 컨피규레이션이 `HttpSession` 구현체를 Redis 기반으로 자동 교체해준다. 기존에 `session.setAttribute()`와 `session.getAttribute()`로 작성된 코드는 수정할 필요가 없다는 점이 이 방식의 가장 큰 장점이다.

## 흔한 실수와 함정

| 함정 | 결과 | 대응 |
|---|---|---|
| 세션에 큰 객체를 통째로 저장 | 직렬화 비용 증가, Redis 메모리 압박 | 세션엔 최소한의 식별자만 두고 상세 데이터는 별도 조회 |
| 세션 저장 객체가 Serializable 미구현 | 런타임 직렬화 예외 발생 | 세션에 담는 모든 클래스에 Serializable 구현 |
| Redis를 단일 인스턴스로만 구성 | Redis 장애 시 전체 서비스 로그인 불가 | Redis Sentinel이나 Cluster로 이중화 |
| 세션 타임아웃과 JWT 만료시간 불일치 | 세션은 살아있는데 토큰만 만료되는 등 혼란 | 두 값을 정책적으로 통일 |

세 번째 함정이 특히 치명적이다. 세션 클러스터링을 도입한 이유가 특정 애플리케이션 서버 장애로부터 로그인 상태를 보호하기 위함인데, 정작 그 세션이 저장된 Redis 자체가 단일 장애점이 되면 본말이 전도된다. Redis Sentinel로 자동 페일오버를 구성하거나, 트래픽 규모가 크다면 Redis Cluster로 샤딩까지 고려해야 한다.

## 실무 포인트

- **세션에는 최소한의 데이터만 담아라.** 사용자 전체 프로필처럼 자주 안 바뀌는 큰 데이터는 세션이 아니라 별도 캐시나 DB 조회로 가져오고, 세션에는 사용자 ID나 권한 요약 정도만 두는 것이 직렬화 비용과 네트워크 부하를 줄인다.
- **세션 저장소와 캐시 저장소를 같은 Redis 인스턴스로 섞어 쓰지 마라.** 캐시는 메모리 부족 시 오래된 키를 지워도(eviction) 되지만, 세션이 같은 인스턴스에 있으면 캐시 정리 정책 때문에 세션이 갑자기 사라질 수 있다. 별도 Redis 인스턴스나 최소한 별도 논리 DB 번호로 분리해야 한다.
- **세션 무효화(로그아웃) 흐름을 명확히 테스트하라.** 여러 서버에 걸쳐 세션이 공유되므로, 로그아웃 시 실제로 Redis의 해당 세션 키가 삭제되는지, 다른 탭에서도 즉시 반영되는지 확인이 필요하다.

## 마무리 요약

- 로드밸런서 뒤에서 로그인이 풀리는 문제는 대부분 세션이 각 서버 로컬 메모리에 갇혀 있기 때문이며, 스티키 세션은 회피책일 뿐 근본 해결이 아니다.
- Spring Session은 기존 HttpSession API는 그대로 두고 실제 저장 위치만 Redis로 바꿔주므로 컨트롤러 코드 변경 없이 세션을 외부화할 수 있다.
- Redis 자체가 단일 장애점이 되지 않도록 Sentinel이나 Cluster로 이중화하고, 세션과 캐시 데이터를 같은 인스턴스에 섞지 않아야 한다.

## 참고 자료

- [Spring Session 공식 문서](https://docs.spring.io/spring-session/reference/)
- [Redis 공식 문서 - Sentinel](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/)
