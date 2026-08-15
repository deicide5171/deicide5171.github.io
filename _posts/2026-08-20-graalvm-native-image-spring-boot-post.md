---
layout: single
title: "GraalVM 네이티브 이미지로 Spring Boot 콜드스타트 없애기"
date: 2026-08-20 13:25:00 +0530
categories: backend
tags: ["backend", "graalvm", "native-image", "spring-boot", "java", "serverless"]
toc: true
toc_sticky: true
excerpt: "JVM 워밍업 시간이 서버리스·컨테이너 스케일아웃의 병목이 되는 상황에서, GraalVM 네이티브 이미지로 Spring Boot를 AOT 컴파일해 콜드스타트를 없애는 방법과 한계를 정리한다."
---

전통적인 JVM 애플리케이션은 클래스를 우선 인터프리터로 실행하다가, 자주 호출되는 코드 경로를 JIT(Just-In-Time) 컴파일러가 뒤늦게 네이티브 코드로 최적화하는 방식으로 동작한다. 오래 떠 있는 서버 프로세스라면 이 워밍업 구간이 전체 수명 대비 짧아 크게 문제가 되지 않는다. 그러나 서버리스 함수나 오토스케일링으로 인스턴스가 수시로 뜨고 내려가는 환경에서는 사정이 다르다. 요청이 몰릴 때마다 새로 뜬 인스턴스가 클래스 로딩과 JIT 웜업을 처음부터 다시 거쳐야 하고, 그 구간 동안 응답 지연이 눈에 띄게 늘어난다.

이 문제의 근본 원인은 JVM이 "실행하면서 최적화 대상을 찾는" 런타임 중심 설계라는 데 있다. 스케일아웃 빈도가 잦을수록 이 설계의 비용이 누적되고, 결국 요청 처리량보다 인스턴스 기동 시간이 병목이 되는 역전 현상이 발생한다. GraalVM 네이티브 이미지는 이 구조 자체를 바꿔, 애플리케이션을 배포 전에 미리 네이티브 실행 파일로 컴파일해 두는 접근을 택한다. 이 글에서는 Spring Boot 애플리케이션을 네이티브 이미지로 빌드하는 과정과, 그 대가로 감수해야 하는 제약사항을 정리한다.

## 핵심 개념 1: AOT 컴파일과 JIT의 근본적 차이

JIT은 애플리케이션이 실행되는 동안 실제 호출 빈도와 타입 정보를 관찰해 최적화 대상을 동적으로 판단한다. 반면 AOT(Ahead-Of-Time) 컴파일은 빌드 시점에 도달 가능한 코드 전체를 정적으로 분석해 미리 네이티브 기계어로 컴파일해 버린다. GraalVM 네이티브 이미지는 이 AOT 방식을 택하면서, 애플리케이션이 실제로 사용할 가능성이 있는 클래스·메서드만을 빌드 시점에 그래프로 추적하는 "닫힌 세계(closed-world)" 가정을 전제로 한다. 즉 런타임에 새로운 클래스를 동적으로 로드하거나, 실행 도중 처음 보는 코드 경로가 나타나는 상황을 원칙적으로 허용하지 않는다. 그 대가로 실행 파일은 JVM 부트스트랩 과정 없이 곧바로 네이티브 코드로 시작되므로, 기동 시점의 지연이 구조적으로 크게 줄어든다.

## 핵심 개념 2: Spring Boot의 AOT 처리와 네이티브 이미지 빌드 과정

Spring 프레임워크는 원래 컴포넌트 스캔, 조건부 빈 등록, 프록시 생성처럼 런타임에 리플렉션으로 처리하던 작업이 많았다. 이는 닫힌 세계 가정과 정면으로 충돌하기 때문에, Spring Framework 6과 Spring Boot 3부터는 별도의 **Spring AOT 처리** 단계를 빌드 과정에 끼워 넣는다. 이 단계에서 스프링은 애플리케이션 컨텍스트를 미리 한 번 구동해 보면서 빈 정의와 프록시 대상을 분석하고, 그 결과를 네이티브 이미지 빌드에 필요한 힌트 메타데이터와 초기화 코드로 미리 생성해 둔다. 이후 GraalVM의 `native-image` 도구가 이 산출물과 애플리케이션 클래스 전체를 정적으로 분석해 하나의 독립 실행 파일로 컴파일한다. 개발자 입장에서는 평소처럼 Gradle이나 Maven의 네이티브 빌드 플러그인을 통해 이 과정 전체를 한 번의 빌드 명령으로 실행하게 된다.

## 핵심 개념 3: 네이티브 이미지의 제약사항

닫힌 세계 가정은 성능의 원천이자 동시에 제약의 원천이다. 리플렉션으로 클래스를 동적으로 조회하거나, JDK 동적 프록시로 인터페이스를 즉석에서 구현하거나, 클래스패스에서 리소스를 런타임에 스캔하는 코드는 정적 분석기가 그 대상을 미리 알 수 없으므로 기본적으로 누락되기 쉽다. 이런 경우 별도의 리플렉션 설정(`reflect-config.json` 등 GraalVM Reachability Metadata)으로 "이 클래스와 메서드는 리플렉션 대상이니 포함하라"고 명시적으로 알려주어야 한다. Spring Boot와 주요 스타터는 이미 상당수의 힌트를 라이브러리 차원에서 제공하지만, 팀에서 직접 작성한 리플렉션 기반 코드나 서드파티 라이브러리는 이 힌트가 없을 수 있어 개별 검증이 필요하다.

## 예제

```bash
# Gradle 네이티브 이미지 빌드 (GraalVM 네이티브 빌드 도구 플러그인 적용 시)
./gradlew nativeCompile

# 빌드된 실행 파일 직접 구동
./build/native/nativeCompile/myapp
```

```groovy
// build.gradle
plugins {
    id 'org.springframework.boot' version '3.x.x'
    id 'org.graalvm.buildtools.native' version '0.1x.x'
}

graalvmNative {
    binaries {
        main {
            buildArgs.add('--enable-preview')
        }
    }
}
```

```xml
<!-- pom.xml: Spring Boot 3 프로젝트에 기본 포함되는 native 프로파일 예시 -->
<profiles>
  <profile>
    <id>native</id>
    <build>
      <plugins>
        <plugin>
          <groupId>org.graalvm.buildtools</groupId>
          <artifactId>native-maven-plugin</artifactId>
        </plugin>
      </plugins>
    </build>
  </profile>
</profiles>
```

## 실무 포인트

- **빌드 시간이 상당히 늘어난다**: 정적 분석과 네이티브 컴파일 단계가 추가되므로, 일반 JAR 빌드보다 빌드 시간이 눈에 띄게 길어진다. 로컬 반복 개발보다는 CI 파이프라인의 배포 단계에 native-image 빌드를 배치하는 편이 실용적이다.
- **리플렉션 힌트 설정은 선택이 아니라 필수 검증 항목이다**: 자체 개발 코드나 힌트 메타데이터가 없는 라이브러리를 쓴다면, 네이티브 빌드 이후 반드시 통합 테스트를 돌려 런타임에서만 드러나는 `ClassNotFoundException` 류의 실패를 걸러내야 한다.
- **모든 라이브러리가 네이티브 이미지와 호환되는 것은 아니다**: 도입 전에 사용 중인 주요 의존성이 GraalVM Reachability Metadata Repository에 등록되어 있는지, 또는 자체적으로 네이티브 지원을 공식 표방하는지 먼저 확인하는 편이 시행착오를 줄인다.

## 3줄 요약

- JVM은 런타임에 최적화 대상을 찾는 JIT 구조라서 서버리스·오토스케일링 환경에서는 매 기동마다 워밍업 지연이 반복된다.
- GraalVM 네이티브 이미지는 애플리케이션을 빌드 시점에 정적으로 분석해 하나의 실행 파일로 AOT 컴파일하며, Spring Boot는 별도의 Spring AOT 처리 단계로 런타임 리플렉션 의존을 최소화해 이를 지원한다.
- 다만 닫힌 세계 가정 때문에 리플렉션·동적 프록시 등은 별도 힌트 설정이 필요하고, 빌드 시간 증가와 라이브러리 호환성 문제를 실무 도입 전에 검증해야 한다.

## 참고 자료

- [Spring Boot 공식 문서 — GraalVM Native Image Support](https://docs.spring.io/spring-boot/reference/packaging/native-image/introducing-graalvm-native-images.html)
- [Spring Framework 공식 문서 — Ahead of Time Processing](https://docs.spring.io/spring-framework/reference/core/aot.html)
- [GraalVM 공식 문서 — Native Image](https://www.graalvm.org/latest/reference-manual/native-image/)
- [GraalVM Reachability Metadata Repository](https://github.com/oracle/graalvm-reachability-metadata)
</content>
