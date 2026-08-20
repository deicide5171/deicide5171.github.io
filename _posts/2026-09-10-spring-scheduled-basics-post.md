---
layout: single
title: "@Scheduled 입문 — 스프링에서 정해진 시간에 작업 실행하기"
date: 2026-09-10 12:25:00 +0530
categories: backend
tags: ["scheduled", "스케줄링", "spring", "배치", "입문"]
toc: true
toc_sticky: true
excerpt: "매일 자정 정산, 10분마다 정리 같은 반복 작업을 스프링의 @Scheduled로 실행하는 방법을 처음 배우는 사람 기준으로 정리했다."
---

## 매일 자정에 자동으로 실행하고 싶다면

"매일 자정에 정산", "10분마다 임시 파일 정리" 같은 반복 작업은 사람이 직접 돌릴 수 없다. 스프링의 **`@Scheduled`**는 **메서드에 애너테이션만 붙이면 정해진 시간·주기로 자동 실행**해준다. 별도 스케줄러 서버 없이 애플리케이션 안에서 동작한다.

## 세 가지 실행 방식

| 속성 | 의미 |
|---|---|
| `fixedRate` | 시작 시각 기준 N밀리초마다 |
| `fixedDelay` | 이전 작업 끝난 뒤 N밀리초 후 |
| `cron` | 크론 표현식으로 특정 시각 |

## 사용 예시

```java
@Component
public class CleanupJob {

    // 10분(600,000ms)마다 실행
    @Scheduled(fixedRate = 600000)
    public void cleanTemp() {
        // 임시 파일 정리
    }

    // 매일 0시 0분 0초 실행 (cron)
    @Scheduled(cron = "0 0 0 * * *")
    public void dailySettle() {
        // 정산 처리
    }
}
```

`@EnableScheduling`을 설정 클래스에 붙여야 스케줄링이 켜진다.

## 실무 포인트

- **작업이 겹치지 않게 하라.** `fixedRate`는 이전 작업이 안 끝났어도 다음 실행 시각이 되면 시작한다. 작업이 오래 걸리면 겹칠 수 있으니, 겹침이 곤란하면 `fixedDelay`를 쓰거나 실행 중복을 막는 장치를 둔다.
- **서버가 여러 대면 중복 실행된다.** 앱을 여러 인스턴스로 띄우면 각 인스턴스가 같은 스케줄을 돌려 작업이 중복된다. 분산 환경에선 ShedLock 같은 도구로 한 번만 실행되게 잠금을 건다.
- **예외 처리를 꼭 하라.** 스케줄 메서드에서 예외가 나면 조용히 실패하고 다음 주기로 넘어갈 수 있다. 내부에서 try-catch로 잡아 로그를 남겨야 실패를 알아챌 수 있다.

## 마무리 요약

- `@Scheduled`는 메서드에 애너테이션을 붙여 정해진 주기·시각에 자동 실행하는 기능이다.
- `fixedRate`·`fixedDelay`·`cron`으로 실행 방식을 정하고 `@EnableScheduling`으로 켠다.
- 작업 겹침·다중 인스턴스 중복·예외 처리를 고려해야 안정적으로 동작한다.

## 참고 자료

- [Spring 공식 문서 - Scheduling](https://docs.spring.io/spring-framework/reference/integration/scheduling.html)
