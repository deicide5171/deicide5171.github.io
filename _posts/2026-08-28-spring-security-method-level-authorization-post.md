---
layout: single
title: "URL만 지켜서는 부족하다 — Spring Security 메서드 레벨 인가(@PreAuthorize) 실전"
date: 2026-08-28 13:25:00 +0530
categories: backend
tags: ["backend", "spring-security", "preauthorize", "method-security", "authorization"]
toc: true
toc_sticky: true
excerpt: "URL 단위 인가로는 표현할 수 없는 '이 리소스는 소유자만' 같은 세밀한 규칙을 @PreAuthorize·@PostAuthorize와 커스텀 PermissionEvaluator로 메서드 레벨에 적용하는 Spring Security 실전 패턴을 정리한다."
---

`SecurityFilterChain`에서 `authorizeHttpRequests()`로 URL 패턴별 접근 제어를 설정하는 방식은 "이 경로는 ADMIN 권한만"처럼 역할 기반의 큰 틀은 잘 표현하지만, "이 게시글은 작성자 본인이거나 관리자만 수정할 수 있다"처럼 **리소스의 실제 소유 관계를 확인해야 하는 규칙**은 표현할 방법이 없다. URL만 보고는 그 뒤에 오는 게시글 ID가 누구 것인지 알 수 없기 때문이다. 이런 규칙은 결국 서비스 메서드 안에서 `if (post.getAuthorId().equals(currentUser.getId()))` 같은 코드로 직접 확인하게 되는데, 이 검증 로직이 비즈니스 로직 여기저기 흩어지면 빠뜨리는 지점이 생기기 쉽다.

Spring Security의 **메서드 레벨 인가**는 이 문제를 어노테이션 하나로 해결한다. `@PreAuthorize`, `@PostAuthorize` 같은 어노테이션을 서비스 메서드에 붙이면, 메서드 실행 전후로 인가 규칙이 AOP(관점 지향 프로그래밍)로 자동 적용되어 비즈니스 로직과 권한 검증 코드가 분리된다. 이 글에서는 메서드 레벨 인가의 핵심 어노테이션과, 소유권 검증처럼 복잡한 규칙을 위한 커스텀 `PermissionEvaluator` 패턴을 정리한다.

## 핵심 개념 1: @PreAuthorize vs @PostAuthorize — 언제 검증하는가

`@PreAuthorize`는 메서드가 **실행되기 전에** SpEL(Spring Expression Language) 표현식을 평가해 통과하지 못하면 메서드 자체를 실행하지 않고 `AccessDeniedException`을 던진다. 메서드 인자로 넘어온 값(예: 게시글 ID)을 기준으로 판단할 수 있는 규칙에 적합하다. `@PostAuthorize`는 메서드가 **실행된 후** 반환값을 기준으로 판단한다. "이 메서드가 반환하는 게시글 객체의 작성자가 현재 사용자와 같은가"처럼, 인자만으로는 알 수 없고 실제 조회 결과가 있어야 판단 가능한 경우에 쓴다. 다만 `@PostAuthorize`는 이미 메서드가 실행된 뒤에 걸러내므로, 데이터 조회 자체는 이미 일어났다는 점(성능·부작용 측면)을 감안해야 한다.

```java
@PreAuthorize("hasRole('ADMIN')")
public void deleteAnyPost(Long postId) { ... }

@PreAuthorize("#postId != null and @postSecurity.isOwner(#postId, authentication.name)")
public void updatePost(Long postId, PostUpdateRequest request) { ... }

@PostAuthorize("returnObject.authorId == authentication.name or hasRole('ADMIN')")
public Post getPost(Long postId) { ... }
```

## 핵심 개념 2: 커스텀 PermissionEvaluator — SpEL을 넘어서는 복잡한 규칙

SpEL 표현식 안에 소유권 검증 로직을 직접 풀어쓰면(`#post.authorId == authentication.name`) 표현식이 금방 복잡해지고 재사용도 어렵다. Spring Security는 이를 위해 `hasPermission()`이라는 특별한 SpEL 함수와 `PermissionEvaluator` 인터페이스를 제공한다. 실제 권한 판단 로직을 별도의 빈으로 분리해두면, 여러 메서드에서 같은 규칙을 어노테이션 한 줄로 재사용할 수 있다.

```java
@Component
public class PostPermissionEvaluator implements PermissionEvaluator {

    private final PostRepository postRepository;

    @Override
    public boolean hasPermission(Authentication auth, Object targetDomainObject, Object permission) {
        if (!(targetDomainObject instanceof Post post)) return false;
        return checkPermission(auth, post, (String) permission);
    }

    @Override
    public boolean hasPermission(Authentication auth, Serializable targetId, String targetType, Object permission) {
        Post post = postRepository.findById((Long) targetId).orElse(null);
        if (post == null) return false;
        return checkPermission(auth, post, (String) permission);
    }

    private boolean checkPermission(Authentication auth, Post post, String permission) {
        String username = auth.getName();
        boolean isAdmin = auth.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        return switch (permission) {
            case "read" -> true; // 읽기는 누구나
            case "write", "delete" -> isAdmin || post.getAuthorId().equals(username);
            default -> false;
        };
    }
}
```

```java
@PreAuthorize("hasPermission(#postId, 'Post', 'write')")
public void updatePost(Long postId, PostUpdateRequest request) { ... }
```

`hasPermission()`을 쓰면 실제 판단 로직이 `PostPermissionEvaluator` 한 곳에 모이고, 어노테이션은 "무슨 권한이 필요한가"만 선언적으로 표현하게 된다. 권한 규칙이 바뀌어도 평가자 클래스 하나만 고치면 되는 것이 SpEL에 로직을 직접 풀어쓰는 방식과의 결정적 차이다.

<img src="/assets/images/posts/2026-08-28-spring-security-method-level-authorization-1.svg" alt="컨트롤러에서 서비스 메서드 호출 시 AOP 프록시가 가로채 PreAuthorize의 SpEL 표현식을 평가하고, hasPermission 함수는 별도의 PermissionEvaluator 빈에 실제 판단을 위임하는 구조" style="width:100%;">

## 핵심 개념 3: URL 레벨과 메서드 레벨은 서로 대체가 아니라 보완 관계다

URL 레벨 인가(`SecurityFilterChain`의 `authorizeHttpRequests`)와 메서드 레벨 인가는 방어 층위가 다르다. URL 레벨은 "이 엔드포인트 자체에 접근할 수 있는 최소 자격이 있는가"를 빠르게 걸러내는 **1차 방어선**이고, 메서드 레벨은 그 요청이 실제 처리되는 도메인 객체까지 내려가서 "이 특정 리소스에 대해 이 사용자가 이 작업을 할 수 있는가"를 판단하는 **2차 정밀 검증**이다. URL 레벨만 있으면 인증된 사용자라면 누구나 남의 리소스에 접근 가능한 API가 만들어질 위험이 있고, 메서드 레벨만 믿고 URL 레벨을 생략하면 인증 자체가 안 된 요청까지 서비스 계층까지 흘러들어와 불필요한 부하를 유발한다.

## 실무 포인트

- **SpEL 표현식에 복잡한 로직을 직접 쓰지 말 것**: 표현식이 한 줄을 넘어가기 시작하면 커스텀 `PermissionEvaluator`나 별도의 `@Component` 빈을 참조하는 SpEL(`@postSecurity.isOwner(...)`)로 옮겨야 테스트 가능성과 가독성이 유지된다.
- **`@PostAuthorize`의 부작용을 인지할 것**: 반환값 기준 검증이라 메서드 내부의 DB 조회나 외부 API 호출은 권한 검증과 무관하게 이미 실행된다. 조회 자체에 비용이 크거나 부작용이 있는 메서드에는 `@PreAuthorize`로 사전에 걸러낼 방법을 우선 찾아야 한다.
- **메서드 시큐리티 활성화를 잊지 말 것**: `@EnableMethodSecurity`(Spring Security 6 기준)를 설정 클래스에 선언하지 않으면 `@PreAuthorize` 등은 조용히 무시된다. 통합 테스트에서 인가 거부가 실제로 발생하는지 검증하는 테스트 케이스를 반드시 포함해야 이 실수를 배포 전에 잡을 수 있다.

## 3줄 요약

- `@PreAuthorize`는 메서드 실행 전 인자 기준으로, `@PostAuthorize`는 실행 후 반환값 기준으로 인가를 판단하며 판단 시점이 다르다.
- 복잡한 소유권 검증 로직은 SpEL에 직접 풀어쓰지 않고 `hasPermission()`과 커스텀 `PermissionEvaluator`로 분리해야 재사용성과 테스트 가능성이 유지된다.
- URL 레벨 인가는 빠른 1차 방어선, 메서드 레벨 인가는 리소스 단위 2차 정밀 검증으로 서로 다른 층위를 담당하므로 둘 다 필요하다.

## 참고 자료

- [Spring Security 공식 문서: Method Security](https://docs.spring.io/spring-security/reference/servlet/authorization/method-security.html)
- [Spring Security 공식 문서: Expression-Based Access Control](https://docs.spring.io/spring-security/reference/servlet/authorization/expression-based.html)
- [Spring Security Javadoc: PermissionEvaluator](https://docs.spring.io/spring-security/site/docs/current/api/org/springframework/security/access/PermissionEvaluator.html)
