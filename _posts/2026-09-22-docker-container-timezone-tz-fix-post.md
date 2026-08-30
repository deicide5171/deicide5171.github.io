---
layout: single
title: "Docker 컨테이너 시간대가 안 맞을 때 — TZ 환경변수로 타임존 맞추기"
date: 2026-09-22 12:40:00 +0530
categories: infra
tags: ["도커", "타임존", "tz환경변수", "utc", "컨테이너설정"]
toc: true
toc_sticky: true
excerpt: "로컬에서는 멀쩡하던 로그 시각과 예약 작업 시간이 컨테이너로 배포하자마자 어긋나는 문제를, 컨테이너 기본 시간대가 UTC라는 사실과 TZ 환경변수 설정으로 해결하는 방법을 정리했다."
---

## 왜 로컬에선 멀쩡하던 시간이 컨테이너에서 틀어지나

로컬 개발 환경에서 스케줄러가 정확히 원하는 시각에 돌고, 로그에 찍히는 타임스탬프도 눈에 익은 시간으로 나온다. 그런데 같은 애플리케이션을 Docker 컨테이너로 패키징해서 배포하는 순간, 로그 시각이 9시간(한국 기준) 어긋나 있거나, 매일 자정에 돌아야 할 배치가 낮 시간에 실행되는 현상을 마주친다.

원인은 단순하다. **대부분의 공식 Docker 베이스 이미지는 기본 시간대가 UTC로 설정되어 있다.** 로컬 macOS나 Windows, 혹은 한국 시간대로 설정된 리눅스 서버에서 개발할 때는 OS의 로컬 타임존을 그대로 물려받아 문제를 못 느끼지만, 컨테이너는 격리된 환경이기 때문에 호스트의 타임존 설정을 자동으로 상속받지 않는다. 이 차이를 모르고 넘어가면 "로컬에서는 됐는데 서버에서는 왜 안 되지"라는 전형적인 함정에 빠진다.

## 잘못된 접근: 애플리케이션 코드에서 매번 오프셋을 더하기

시간이 어긋난다는 것을 발견하면, 급한 마음에 코드에서 시간 계산을 할 때마다 9시간을 더하거나 빼는 임시방편을 쓰는 경우가 있다.

```java
// 절대 이렇게 하지 말 것
LocalDateTime kstTime = LocalDateTime.now().plusHours(9);
```

이 방식은 당장은 동작하는 것처럼 보이지만 여러 함정을 남긴다. 코드베이스 전체에 하드코딩된 오프셋이 흩어지면서 유지보수가 불가능해지고, 서머타임이 있는 국가로 서비스를 확장하면 오프셋 값 자체가 틀리게 된다. 무엇보다 로그 라이브러리, DB 드라이버, 스케줄러 라이브러리 등 애플리케이션이 직접 건드리지 못하는 부분의 시간은 여전히 UTC로 남아 전체 시스템의 시간 기준이 뒤섞인다.

## 올바른 접근: 컨테이너 레벨에서 타임존을 명시하기

가장 확실한 해결책은 애플리케이션이 시간대를 신경 쓰지 않아도 되도록, 컨테이너 자체의 시스템 타임존을 원하는 값으로 맞추는 것이다. 방법은 이미지 종류에 따라 조금씩 다르다.

```dockerfile
# Debian/Ubuntu 계열 베이스 이미지
FROM eclipse-temurin:21-jre
ENV TZ=Asia/Seoul
RUN apt-get update && apt-get install -y tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean
```

```dockerfile
# Alpine 계열 베이스 이미지 (tzdata 패키지가 기본 미포함)
FROM eclipse-temurin:21-jre-alpine
RUN apk add --no-cache tzdata
ENV TZ=Asia/Seoul
```

Alpine 이미지는 용량을 줄이기 위해 `tzdata` 패키지 자체가 빠져 있는 경우가 많아 `ENV TZ=...`만 설정해서는 아무 효과가 없다는 점이 자주 놓치는 부분이다. `tzdata` 패키지를 먼저 설치해야 `TZ` 환경변수가 실제로 반영된다.

<img src="/assets/images/posts/2026-09-22-docker-container-timezone-tz-fix-1.svg" alt="컨테이너 기본 시간대가 UTC인 상태와 TZ 환경변수 설정 후 Asia/Seoul로 맞춰진 상태를 비교하는 다이어그램" style="width:100%;">

## docker-compose와 Kubernetes에서 설정하기

이미지를 다시 빌드하기 어려운 상황이라면, 실행 시점에 환경변수만 주입하는 방법도 있다. 단, 이 경우도 컨테이너 안에 `tzdata`가 설치되어 있어야 실제로 동작한다.

```yaml
# docker-compose.yml
services:
  app:
    image: my-app:latest
    environment:
      - TZ=Asia/Seoul
```

```yaml
# Kubernetes Deployment
env:
  - name: TZ
    value: "Asia/Seoul"
```

## UTC로 통일하고 표시 시점에만 변환하는 대안

사실 실무에서 더 널리 권장되는 방향은 컨테이너 시간대를 억지로 바꾸기보다, **내부적으로는 모든 시간을 UTC로 통일하고, 사용자에게 보여주는 시점(프론트엔드, 로그 뷰어)에서만 로컬 시간대로 변환**하는 것이다. DB에 저장하는 타임스탬프, 서버 간 통신에 쓰이는 시각, 로그 시스템의 타임스탬프를 전부 UTC로 맞추면 여러 리전에 서버를 두거나 여름시간이 있는 국가로 확장할 때도 혼란이 없다.

| 전략 | 장점 | 단점 |
|---|---|---|
| 컨테이너 TZ를 로컬 시간대로 설정 | 로그를 바로 읽기 편함, 별도 변환 코드 불필요 | 다중 리전 확장 시 일관성 깨짐 |
| 컨테이너는 UTC 유지, 표시 시점만 변환 | 시스템 전체 시간 기준이 단순·일관적 | 로그를 볼 때마다 변환이 필요 |

작은 단일 리전 서비스라면 TZ를 맞추는 쪽이 당장 편하지만, 장기적으로 여러 서비스가 로그를 교차 분석해야 하는 규모라면 UTC 통일 전략이 유지보수 측면에서 유리하다.

## 실무 포인트

- **베이스 이미지를 바꿀 때마다 타임존 설정이 유지되는지 재확인하라.** Alpine에서 Debian 계열로, 혹은 그 반대로 베이스 이미지를 바꾸면 `tzdata` 패키지 유무가 달라져 설정이 조용히 무효화될 수 있다.
- **애플리케이션 JVM 옵션에도 별도 타임존 설정이 있는지 확인하라.** Java는 `-Duser.timezone` 옵션이나 `TimeZone.setDefault()` 호출이 컨테이너의 `TZ` 환경변수보다 우선 적용될 수 있어, 두 설정이 어긋나 있으면 예상과 다른 결과가 나온다.
- **크론 표현식 기반 스케줄러는 특히 주의 깊게 검증하라.** Kubernetes CronJob, Spring `@Scheduled(cron=...)` 모두 실행 환경의 시간대를 기준으로 동작하므로, 배포 후 반드시 실제 실행 시각을 로그로 확인해야 한다.

## 마무리 요약

- 대부분의 Docker 베이스 이미지는 기본 시간대가 UTC이므로, 로컬 개발 환경과 달리 배포 후 시간이 어긋나는 문제가 자주 발생한다.
- 코드에서 오프셋을 하드코딩하는 대신, `TZ` 환경변수와 `tzdata` 패키지 설치로 컨테이너 레벨에서 시간대를 맞추는 것이 정석이다.
- 장기적으로는 컨테이너 시간대를 UTC로 유지하고 표시 시점에만 변환하는 전략이 다중 리전·서머타임 확장에 더 유리하다.

## 참고 자료

- [Docker 공식 문서 - Dockerfile ENV](https://docs.docker.com/reference/dockerfile/#env)
- [IANA Time Zone Database](https://www.iana.org/time-zones)
