---
layout: single
title: "네이티브 이미지 없이 JVM 시작 시간 줄이기 — AppCDS와 CRaC"
date: 2026-08-25 12:25:00 +0530
categories: backend
tags: ["jvm", "appcds", "crac", "startup-time", "spring-boot", "checkpoint-restore"]
toc: true
toc_sticky: true
excerpt: "GraalVM 네이티브 이미지로 전환하지 않고도 순수 JVM에서 시작 시간을 단축하는 AppCDS의 클래스 로딩 캐시 원리와 CRaC의 체크포인트/복원 방식을 비교 정리한다."
---

서버리스나 쿠버네티스 환경에서 파드를 스케일 아웃할 때마다 JVM이 클래스를 로딩하고 JIT 컴파일을 워밍업하는 데 수 초가 걸리면, 그 몇 초가 트래픽 급증 대응 속도를 그대로 깎아먹는다. 이 문제의 가장 화끈한 해법은 GraalVM 네이티브 이미지로 AOT 컴파일해 바이너리를 통째로 굽는 것이지만, 리플렉션·동적 프록시가 많은 기존 Spring 애플리케이션을 네이티브 이미지 호환으로 바꾸는 작업은 결코 가볍지 않다.

네이티브 이미지로 가지 않고도 **순수 JVM 위에서** 시작 시간을 단축하는 방법이 두 가지 있다. 클래스 로딩 단계를 캐시하는 AppCDS(Application Class-Data Sharing)와, 애플리케이션이 완전히 초기화된 상태 자체를 스냅숏으로 저장했다가 복원하는 CRaC(Coordinated Restore at Checkpoint)다. 이 글에서는 두 접근의 원리와 GraalVM 네이티브 이미지와의 차이를 정리한다.

## 핵심 개념 1: AppCDS — 클래스 로딩과 검증을 미리 끝내둔다

JVM 시작 시간의 상당 부분은 클래스 파일을 디스크에서 읽고, 파싱하고, 바이트코드를 검증하고, 메타스페이스에 적재하는 과정에서 소모된다. **CDS(Class-Data Sharing)**는 JDK 기본 클래스들을 미리 아카이브(`.jsa` 파일)로 만들어 여러 JVM 프로세스가 메모리 매핑으로 공유하는 기능이고, **AppCDS**는 이 범위를 애플리케이션 자신의 클래스와 의존 라이브러리 클래스까지 확장한 것이다.

애플리케이션을 한 번 실행해 실제로 로딩되는 클래스 목록을 기록한 뒤, 이를 바탕으로 애플리케이션 전용 CDS 아카이브를 만든다. 이후 실행에서는 이 아카이브를 메모리에 매핑하기만 하면 되므로 클래스 파싱·검증 비용이 크게 줄어든다. JDK 19부터는 `-XX:+AutoCreateSharedArchive` 옵션으로 이 아카이브 생성과 갱신을 JVM이 자동으로 관리해주기 시작해 운영 편의성이 크게 개선됐다.

## 핵심 개념 2: CRaC — 실행 중인 프로세스 자체를 스냅숏

CRaC는 접근 방식이 근본적으로 다르다. 클래스 로딩만 빠르게 하는 게 아니라, **애플리케이션이 완전히 부팅되고 워밍업까지 끝난 시점의 JVM 프로세스 전체 상태(메모리, 클래스, JIT 컴파일 결과 등)를 리눅스 체크포인트 기능(CRIU)으로 통째로 디스크에 저장**한다. 이후 컨테이너를 새로 띄울 때는 그 스냅숏을 복원(restore)하기만 하면, 마치 이미 한참 실행되어 워밍업이 끝난 프로세스가 그 자리에서 이어 실행되는 것처럼 동작한다.

이 방식은 클래스 로딩뿐 아니라 JIT가 핫 경로를 이미 최적화 컴파일해둔 상태, 커넥션 풀 초기화, 캐시 워밍업까지 전부 스냅숏에 포함되므로 이론상 AppCDS보다 훨씬 큰 폭의 시작 시간 단축이 가능하다. 다만 체크포인트 시점에 열려 있던 소켓, 파일 핸들, 스레드 상태를 애플리케이션이 직접 정리(체크포인트 전 hook)하고 복원 후 재개(post-restore hook)하는 협조가 필요해서, "Coordinated"라는 이름처럼 애플리케이션 코드가 이 생명주기에 개입해야 한다.

## 핵심 개념 3: 세 가지 접근 비교

| 구분 | AppCDS | CRaC | GraalVM 네이티브 이미지 |
|---|---|---|---|
| 접근 방식 | 클래스 로딩 결과 캐시 | 프로세스 전체 상태 스냅숏 | AOT 컴파일로 바이너리 생성 |
| 시작 시간 개선 폭 | 중간 (수백ms~1초대 단축) | 큼 (수 초 → 수십ms대 가능) | 큼 (수십ms대) |
| 기존 코드 호환성 | 거의 그대로 사용 | 체크포인트 hook 대응 필요 | 리플렉션·동적 클래스 로딩 제약 큼 |
| JIT 최적화 활용 | 시작 후 다시 JIT 필요 | 스냅숏에 포함되어 유지 | 인터프리터/제한적 JIT (버전에 따라 다름) |
| 런타임 형태 | 여전히 JVM | 여전히 JVM(스냅숏 복원) | 별도 네이티브 바이너리 |

세 방식은 서로 배타적이지 않다. Spring Boot는 `spring-context-support`의 CRaC 통합과 AppCDS를 함께 쓸 수 있고, GraalVM으로 완전히 전환하기 어려운 레거시 애플리케이션이라면 CRaC가 "JVM을 유지하면서 네이티브 이미지에 근접한 시작 시간"을 얻는 현실적인 절충안이 된다.

## 예제: AppCDS 아카이브 생성과 CRaC 체크포인트/복원

```bash
# 1) AppCDS: 클래스 로딩 목록 기록 (앱을 한 번 정상 실행)
java -XX:ArchiveClassesAtExit=app-cds.jsa -jar app.jar &
# 애플리케이션에 트래픽을 흘려 주요 경로 클래스가 로딩되게 한 뒤 종료

# 2) AppCDS: 아카이브를 사용해 실제 구동
java -XX:SharedArchiveFile=app-cds.jsa -jar app.jar

# 3) CRaC: 체크포인트 생성 (Spring Boot 3.2+ + CRaC 지원 JDK)
java -XX:CRaCCheckpointTo=/checkpoint/app -jar app.jar
# 워밍업 트래픽 후 체크포인트 트리거 (jcmd 또는 SIGUSR2)
jcmd <pid> JDK.checkpoint

# 4) CRaC: 체크포인트로부터 복원 (수십 ms 내 기동)
java -XX:CRaCRestoreFrom=/checkpoint/app
```

## 실무 포인트

- **CRaC 도입 전 체크포인트-복원 훅을 반드시 점검한다**: DB 커넥션, 파일 디스크립터, 랜덤 시드처럼 체크포인트 시점의 상태를 그대로 복원하면 안 되는 리소스가 있다. Spring의 `org.crac.Resource` 인터페이스로 체크포인트 전 연결을 끊고 복원 후 재연결하는 로직을 명시적으로 구현해야 한다.
- **AppCDS 아카이브는 배포 파이프라인의 일부로 관리한다**: 애플리케이션 코드나 의존성 버전이 바뀌면 아카이브도 다시 만들어야 하므로, 빌드 단계에 아카이브 생성을 포함시키지 않으면 배포마다 수동으로 갱신을 잊기 쉽다.
- **컨테이너 이미지 크기와 시작 시간을 함께 본다**: CRaC 스냅숏 파일은 힙 크기에 비례해 커질 수 있어 이미지 크기와 콜드 스타트 시 스냅숏 로딩 시간 사이의 트레이드오프도 함께 측정해야 한다.

## 3줄 요약

- AppCDS는 클래스 로딩·검증 단계만 캐시해 시작 시간을 줄이는 저위험·저효과 접근이고, CRaC는 워밍업이 끝난 프로세스 전체를 스냅숏해 복원하는 고효과·고관리비용 접근이다.
- CRaC는 체크포인트 시점의 소켓·파일 상태를 애플리케이션이 직접 정리·재개해야 하는 협조형 생명주기가 필요하다.
- 두 방식 모두 GraalVM 네이티브 이미지로 전환하기 어려운 기존 JVM 애플리케이션에서 시작 시간을 줄이는 현실적인 대안이며, 서로 병행해서 쓸 수 있다.

## 참고 자료

- [OpenJDK 공식 문서: Application Class-Data Sharing](https://docs.oracle.com/en/java/javase/21/vm/class-data-sharing.html)
- [CRaC 프로젝트 공식 사이트](https://crac.jdk.org/)
- [Spring Framework 공식 문서: Support for Checkpoint/Restore](https://docs.spring.io/spring-boot/reference/features/checkpoint-restore.html)
