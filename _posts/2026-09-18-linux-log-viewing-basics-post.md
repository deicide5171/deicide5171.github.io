---
layout: single
title: "리눅스에서 로그 보기 — tail, grep으로 원인 찾기"
date: 2026-09-18 12:40:00 +0530
categories: infra
tags: ["리눅스", "로그", "tail", "grep", "입문"]
toc: true
toc_sticky: true
excerpt: "서버 문제가 생겼을 때 로그 파일을 tail·grep으로 확인해 원인을 찾는 기본 명령을 처음 서버를 다루는 사람 기준으로 정리했다."
---

## 서버가 이상할 때 어디를 보나

서버에서 문제가 생기면 가장 먼저 볼 곳은 **로그**다. 하지만 로그 파일은 수만 줄이라 그냥 열면 못 본다. 리눅스에는 로그를 효율적으로 보는 명령들이 있다. 몇 가지만 익히면 원인을 빠르게 찾을 수 있다.

## 자주 쓰는 명령

| 명령 | 하는 일 |
|---|---|
| `tail -f app.log` | 마지막 줄부터 실시간으로 보기 |
| `grep ERROR app.log` | ERROR가 든 줄만 뽑기 |
| `less app.log` | 페이지 단위로 넘겨 보기 |
| `tail -n 100 app.log` | 마지막 100줄만 |

## 조합 활용

```text
# 실시간으로 에러만 보기
tail -f app.log | grep ERROR

# 에러 앞뒤 3줄까지 함께 (맥락 파악)
grep -C 3 "NullPointer" app.log

# 특정 시간대 로그만
grep "2026-09-18 14:" app.log
```

## 실무 포인트

- **`tail -f`로 실시간 감시.** 문제를 재현하며 `tail -f`로 로그가 실시간으로 찍히는 것을 보면, 어느 동작에서 무슨 로그가 나오는지 바로 알 수 있다. 종료는 Ctrl+C다.
- **`grep`으로 노이즈를 걸러라.** 로그가 많으면 `grep`으로 관심 키워드(ERROR, 특정 요청 ID 등)만 뽑아 본다. `-i`(대소문자 무시), `-C`(앞뒤 맥락) 옵션이 유용하다.
- **컨테이너는 방식이 다르다.** 도커는 `docker logs -f 컨테이너`, 쿠버네티스는 `kubectl logs -f 파드`로 본다. 파일 로그가 아니라 표준출력을 보는 방식이라 경로를 찾지 말고 이 명령을 쓴다.

## 마무리 요약

- 서버 문제의 첫 단서는 로그이며, `tail`·`grep`·`less`로 효율적으로 본다.
- `tail -f`로 실시간 감시, `grep`으로 키워드 필터, `-C`로 앞뒤 맥락을 본다.
- 컨테이너 환경은 `docker logs`·`kubectl logs`로 표준출력 로그를 확인한다.

## 참고 자료

- [Linux grep man page](https://man7.org/linux/man-pages/man1/grep.1.html)
