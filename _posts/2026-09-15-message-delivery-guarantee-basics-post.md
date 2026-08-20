---
layout: single
title: "메시지 전달 보장이 뭔가요 — at-least-once와 exactly-once"
date: 2026-09-15 12:45:00 +0530
categories: system-design
tags: ["전달보장", "atleastonce", "exactlyonce", "메시지큐", "입문"]
toc: true
toc_sticky: true
excerpt: "메시지 큐에서 메시지가 몇 번 전달되는지를 정하는 at-most/at-least/exactly-once 보장 수준을 처음 배우는 사람 기준으로 정리했다."
---

## 메시지가 딱 한 번 전달될까

메시지 큐로 "결제 완료" 같은 메시지를 주고받을 때, 네트워크 문제나 재시도로 **같은 메시지가 두 번 오거나, 아예 안 올 수도** 있다. 메시지가 몇 번 전달되는지를 정하는 것이 **전달 보장(delivery guarantee)**이다. 세 가지 수준이 있다.

## 세 가지 보장 수준

| 수준 | 의미 |
|---|---|
| at-most-once | 최대 한 번(유실 가능, 중복 없음) |
| at-least-once | 최소 한 번(중복 가능, 유실 없음) |
| exactly-once | 정확히 한 번(유실·중복 모두 없음) |

## 트레이드오프

```text
at-most-once:  빠르지만 메시지를 잃을 수 있다 (로그·지표 등)
at-least-once: 안 잃지만 중복이 올 수 있다 (가장 흔함)
exactly-once:  이상적이지만 구현이 복잡하고 비용이 크다
```

## 실무 포인트

- **대부분 at-least-once + 멱등성.** 실무에서는 유실을 막는 at-least-once를 쓰고, 중복이 와도 문제없게 **소비자를 멱등하게** 만든다. "이미 처리한 메시지면 무시" 로직으로 exactly-once 효과를 낸다.
- **exactly-once는 진짜 필요한지 따져라.** 완벽한 exactly-once는 구현이 어렵고 성능 비용이 크다. 대부분은 at-least-once + 멱등 처리로 충분하니, exactly-once를 무턱대고 요구하지 않는다.
- **메시지에 고유 ID를 붙여라.** 중복을 판별하려면 각 메시지에 고유 ID가 필요하다. 소비자가 처리한 ID를 기록해두고, 같은 ID가 또 오면 건너뛴다.

## 마무리 요약

- 전달 보장은 메시지가 최대/최소/정확히 몇 번 전달되는지를 정하는 수준이다.
- at-most(유실 가능)·at-least(중복 가능)·exactly(둘 다 없음)의 트레이드오프가 있다.
- 실무는 at-least-once + 멱등 소비자 조합이 흔하며, 메시지 고유 ID로 중복을 거른다.

## 참고 자료

- [Kafka 공식 문서 - Delivery Semantics](https://kafka.apache.org/documentation/#semantics)
