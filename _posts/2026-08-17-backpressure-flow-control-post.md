---
layout: single
title: "백프레셔(Backpressure) 설계 — 생산자가 소비자보다 빠를 때 시스템을 지키는 법"
date: 2026-08-17 12:45:00 +0530
categories: system-design
tags: ["백프레셔", "흐름제어", "리액티브스트림즈", "kafka", "시스템설계"]
toc: true
toc_sticky: true
excerpt: "생산자가 소비자보다 빠르게 데이터를 밀어낼 때 큐가 무한정 쌓이며 메모리를 잡아먹는 문제를, 백프레셔와 흐름 제어 전략으로 어떻게 설계로 풀어내는지 정리한다."
---

## 왜 지금 백프레셔인가

이벤트 기반 아키텍처와 스트리밍 파이프라인이 보편화되면서 "생산자와 소비자의 속도가 다르다"는 문제는 예외가 아니라 기본 전제가 됐다. 배치 작업이 갑자기 대량 이벤트를 쏟아내거나 다운스트림 서비스가 일시적으로 느려지는 상황은 어떤 시스템에서든 발생한다. 큐나 버퍼에 무제한으로 쌓기만 하면 결국 메모리 부족으로 프로세스가 죽거나 지연이 눈덩이처럼 불어난다.

레이트 리밋이 "외부에서 들어오는 요청 속도 자체를 제한"하는 것이라면, 백프레셔는 "이미 시스템 내부로 들어온 데이터가 다음 단계로 전달되는 속도를 소비자 처리 능력에 맞춰 조절"하는 것이다. 둘은 자주 혼동되지만 목적도 적용 위치도 다르다. 큐 depth가 계속 늘어나는데도 원인을 못 찾는 팀은 레이트 리밋만 걸어두고 내부 파이프라인의 흐름 제어는 손대지 않은 경우가 많다.

## 핵심 개념 1: 백프레셔란 무엇인가

백프레셔는 파이프라인의 하류(소비자)가 상류(생산자)에게 "지금은 그만 보내라"는 신호를 되돌려, 전체 처리 속도를 소비자 기준으로 맞추는 메커니즘이다.

| 구분 | 레이트 리밋 | 백프레셔 |
|---|---|---|
| 대상 | 외부 클라이언트 요청 속도 | 내부 파이프라인 단계 간 흐름 |
| 목적 | 남용·과금 방지 | 소비자 과부하·메모리 고갈 방지 |
| 신호 방향 | 클라이언트 → 서버 | 소비자 → 생산자 |
| 대표 구현 | 토큰 버킷, 슬라이딩 윈도우 | TCP 윈도우, Reactive Streams, 큐 depth 모니터링 |

레이트 리밋이 "문 앞에서 입장 인원을 조절"하는 것이라면, 백프레셔는 "이미 입장한 사람들이 다음 방으로 넘어가는 속도를 안쪽 상황에 맞춰 조절"하는 것에 가깝다. 두 메커니즘은 배타적이지 않고 함께 적용되는 경우가 많다.

## 핵심 개념 2: 흐름 제어 전략 네 가지

버퍼가 한계 용량에 도달했을 때 선택할 수 있는 전략은 크게 네 가지다. 정답은 데이터 성격(유실 허용 여부, 최신 값만 의미 있는지)과 지연 허용치에 달려 있다.

| 전략 | 동작 | 단점 |
|---|---|---|
| Drop(유실) | 초과 메시지를 버림 | 데이터 손실 |
| Block(대기) | 생산자 신호를 보내 생산을 멈춤 | 생산자 지연 증가 |
| 버퍼 확장 | 큐 용량을 늘려 폭주 흡수 | 메모리 사용량 증가 |
| 샘플링/병합 | 최신 값만 유지·이벤트 병합 | 중간 상태 손실 |

아래 그림은 생산자·소비자 속도 차이와, 버퍼가 한계에 도달했을 때 선택 가능한 네 가지 전략을 정리한 것이다.

<img src="/assets/images/posts/2026-08-17-backpressure-flow-control-1.svg" alt="생산자·소비자 속도 차이와 버퍼 오버플로우 시 선택 가능한 네 가지 흐름 제어 전략(Drop, Block, 버퍼 확장, 샘플링/병합) 개념도" style="width:100%;">

## 핵심 개념 3: 계층별로 보는 백프레셔 사례

- **TCP 윈도우**: 수신 측 버퍼 여유 공간을 송신 측에 알려, 처리 가능한 만큼만 데이터를 보내게 한다.
- **Reactive Streams(Java)**: `Publisher`-`Subscriber` 사이에 `request(n)`으로 "지금 n개까지 받을 수 있다"를 주고받는 Pull 기반 표준이다. Project Reactor, RxJava, Akka Streams가 구현한다.
- **Node.js 스트림**: `writable.write()`가 버퍼 한계를 넘으면 `false`를 반환하고, `drain` 이벤트를 기다린 뒤 이어 쓰도록 규약한다.
- **Kafka 컨슈머 랙**: 프로듀서 오프셋과 컨슈머 오프셋의 차이(랙)가 벌어지는 것은 컨슈머가 못 따라가고 있다는 신호다. 직접적인 흐름 제어 프로토콜은 아니지만 컨슈머 증설·최적화 판단 근거로 쓰인다.

## 예제 1: Project Reactor에서 오버플로우 전략 지정하기

```java
Flux<Integer> fastProducer = Flux.range(1, 1_000_000)
    .onBackpressureBuffer(
        1000,
        dropped -> log.warn("버퍼 초과로 유실: {}", dropped),
        BufferOverflowStrategy.DROP_OLDEST
    );

fastProducer
    .publishOn(Schedulers.boundedElastic())
    .subscribe(value -> slowConsumer(value));
```

`onBackpressureBuffer`는 버퍼 크기와 초과 시 전략을 명시적으로 지정한다. 아무 전략 없이 `subscribe`만 걸면 소비자가 느릴 때 `OverflowException`으로 스트림이 종료될 수 있으므로, 데이터 성격에 맞는 전략을 반드시 지정해야 한다.

## 예제 2: Node.js에서 write() 반환값으로 흐름 제어하기

```javascript
function writeWithBackpressure(writable, chunks) {
  let i = 0;
  function writeNext() {
    let ok = true;
    while (i < chunks.length && ok) {
      ok = writable.write(chunks[i++]); // false면 버퍼 가득 참
    }
    if (i < chunks.length) {
      writable.once('drain', writeNext);
    }
  }
  writeNext();
}
```

`write()`가 `false`를 반환했는데 계속 밀어 넣으면 대기열이 무제한으로 쌓인다. `drain`을 기다렸다가 이어 쓰는 패턴이 핵심이며, `pipe()`는 이를 내부적으로 자동 처리한다.

## 실무 포인트

- **큐 depth·컨슈머 랙을 반드시 모니터링한다**: 지표 없이는 언제 한계에 도달하는지 알 수 없다.
- **데이터 성격별로 전략을 다르게 가져간다**: 결제처럼 유실이 치명적이면 Block이나 버퍼 확장을, 실시간 위치 값처럼 최신 값만 중요하면 샘플링/병합을 택한다.
- **버퍼 확장은 임시방편이다**: 생산·소비 속도 차이가 구조적이라면 소비자 스케일 아웃이나 처리 로직 최적화가 필요하다.
- **서킷 브레이커와 조합을 고려한다**: 소비자가 응답 불능이면 백프레셔만으로 부족하고, 회로 차단과 함께 설계하는 것이 안전하다.

## 3줄 요약

- 백프레셔는 소비자가 상류로 "속도를 늦춰라" 신호를 보내는 메커니즘으로, 외부 요청을 제한하는 레이트 리밋과 목적·방향이 다르다.
- 버퍼 한계 도달 시 선택 가능한 전략은 Drop, Block, 버퍼 확장, 샘플링/병합 네 가지이며 유실 허용 여부에 따라 골라야 한다.
- Reactive Streams의 `request(n)`, Node.js의 `write()` 반환값과 `drain` 이벤트는 실제 코드에서 백프레셔를 구현하는 대표적인 방식이다.

## 참고 자료

- [Reactive Streams Specification](https://www.reactive-streams.org/)
- [Project Reactor — Backpressure](https://projectreactor.io/docs/core/release/reference/#reactive.backpressure)
- [Node.js — Backpressuring in Streams](https://nodejs.org/en/learn/modules/backpressuring-in-streams)
