---
layout: single
title: "Node.js Streams와 백프레셔 — 대용량 파일 처리에서 메모리를 지키는 파이프라인 설계"
date: 2026-09-25 13:25:00 +0530
categories: backend
tags: ["Nodejs", "Streams", "백프레셔", "pipeline", "메모리관리"]
toc: true
toc_sticky: true
excerpt: "수 GB짜리 CSV를 fs.readFile로 통째로 읽어 처리하다 프로세스가 메모리 부족으로 죽는 문제를, Node.js Streams가 데이터를 청크 단위로 흘려보내면서도 느린 소비자를 위해 자동으로 속도를 늦추는 백프레셔 메커니즘으로 정리했다."
---

## 왜 지금 Node.js 백프레셔를 다시 봐야 하는가

Node.js에서 대용량 파일을 다뤄본 적 있다면 `fs.readFile`로 수 GB짜리 로그 파일이나 CSV를 읽으려다 프로세스가 메모리 부족(OOM)으로 죽는 경험을 했을 가능성이 높다. `readFile`은 파일 전체를 메모리에 올린 뒤에야 콜백을 호출하기 때문에, 파일 크기가 곧 그대로 메모리 사용량이 된다. Streams API는 파일을 작은 청크(chunk) 단위로 나눠 순차적으로 흘려보내며 처리해 이 문제를 해결하지만, 스트림을 잘못 연결하면 또 다른 문제가 생긴다 — 데이터를 생산하는 쪽(Readable)이 소비하는 쪽(Writable)보다 훨씬 빠르면, 아직 처리되지 못한 청크들이 내부 버퍼에 계속 쌓이며 결국 똑같이 메모리를 다 써버리는 것이다. 백프레셔(backpressure)는 이 상황에서 생산 속도를 소비 속도에 맞춰 자동으로 조절하는 메커니즘으로, Node.js Streams의 진짜 가치는 청크 단위 처리 자체가 아니라 이 흐름 제어에 있다.

## 핵심 개념 1 — write()의 반환값이 신호를 보낸다

Writable 스트림의 `write()` 메서드는 데이터를 쓴 뒤 boolean을 반환한다. 이 값이 `false`라면 "내부 버퍼가 highWaterMark(기본 16KB)를 넘어섰으니 지금은 그만 보내라"는 명시적 신호다. 이 신호를 무시하고 계속 `write()`를 호출하면, Node.js는 데이터를 거부하지 않고 내부 버퍼에 계속 쌓아두기 때문에(버퍼링) 결국 메모리가 무한정 늘어난다. 올바른 처리는 `write()`가 `false`를 반환하면 쓰기를 멈추고, Writable이 버퍼를 비워 다시 받을 준비가 됐음을 알리는 `'drain'` 이벤트가 발생할 때까지 기다렸다가 재개하는 것이다. 이것이 백프레셔의 가장 원초적인 형태이며, 스트림을 수동(manual)으로 직접 다룰 때 반드시 지켜야 하는 규약이다.

## 핵심 개념 2 — pipe()와 pipeline()이 이 규약을 대신 지켜준다

매번 `write()`의 반환값과 `'drain'` 이벤트를 손으로 처리하는 것은 번거롭고 실수하기 쉽다. `readable.pipe(writable)`는 이 규약을 내부적으로 자동화한다 — Writable의 버퍼가 가득 차면 Readable을 자동으로 일시정지(`pause()`)시키고, 버퍼가 비면 다시 재개(`resume()`)시킨다. 다만 `pipe()`는 스트림 체인 중간에서 에러가 발생했을 때 나머지 스트림들을 자동으로 정리(destroy)해주지 않는다는 결함이 있어, 에러 발생 시 파일 디스크립터가 닫히지 않고 새어나가는(leak) 원인이 될 수 있다. 이 때문에 최신 Node.js에서는 `stream.pipeline()`(또는 프로미스 버전 `pipeline`)을 쓰는 것이 권장된다. `pipeline()`은 백프레셔 처리는 `pipe()`와 동일하게 수행하면서, 체인의 어느 지점에서든 에러가 나면 관련된 모든 스트림을 자동으로 정리해 리소스 누수를 막아준다.

| 방식 | 백프레셔 처리 | 에러 시 리소스 정리 | 권장 여부 |
|---|---|---|---|
| `write()` 반환값 + `'drain'` 수동 처리 | 개발자가 직접 구현 | 개발자가 직접 구현 | 세밀한 제어가 꼭 필요할 때만 |
| `readable.pipe(writable)` | 자동 | 자동으로 되지 않음(누수 위험) | 레거시 코드에서만 유지 |
| `stream.pipeline()` | 자동 | 자동 정리 | 신규 코드의 기본 선택 |

## 코드 예제 — pipeline으로 대용량 CSV를 변환하며 처리

```javascript
const { pipeline } = require('node:stream/promises');
const fs = require('node:fs');
const { Transform } = require('node:stream');

const upperCaseTransform = new Transform({
  transform(chunk, encoding, callback) {
    callback(null, chunk.toString().toUpperCase());
  }
});

async function processLargeFile() {
  await pipeline(
    fs.createReadStream('huge-input.csv'),   // 청크 단위로 읽음(메모리 상수)
    upperCaseTransform,                       // 중간 변환도 청크 단위로 처리
    fs.createWriteStream('output.csv')        // 쓰기 속도에 맞춰 자동으로 읽기 속도 조절
  );
  console.log('완료 — 파일 크기와 무관하게 메모리 사용량 일정');
}

processLargeFile().catch(console.error); // 중간 에러 시 모든 스트림 자동 정리
```

## 실무 포인트

- **`highWaterMark`를 무작정 크게 키우는 것은 해결책이 아니다.** 버퍼 크기를 키우면 순간적인 처리량은 늘 수 있지만, 그만큼 메모리 사용량의 상한선도 함께 올라간다. 기본값을 유지한 채 백프레셔가 제대로 동작하는지 먼저 확인하고, 실제 처리량이 부족할 때만 프로파일링을 근거로 조정해야 한다.
- **비동기 Transform 스트림에서 콜백을 빠뜨리면 파이프라인 전체가 멈춘다.** `transform()` 메서드 안에서 비동기 작업을 하다가 에러 처리 경로에서 `callback()` 호출을 누락하면, 그 스트림은 다음 청크를 영원히 기다리며 파이프라인이 조용히 멈춰버린다. 모든 코드 경로에서 콜백이 호출되는지 항상 확인해야 한다.
- **Express나 Fastify에서 대용량 파일 업로드/다운로드를 처리할 때도 같은 원리가 적용된다.** 요청 본문(req)이나 응답(res) 객체 자체가 스트림이므로, 이를 버퍼에 전부 담았다가 처리하는 대신 그대로 `pipeline()`에 연결하면 대용량 파일도 일정한 메모리로 처리할 수 있다.

## 마무리 요약

- Node.js Streams는 청크 단위 처리로 대용량 데이터를 메모리에 다 올리지 않고 다룰 수 있게 하지만, 생산 속도가 소비 속도를 앞지르면 내부 버퍼가 쌓이며 같은 메모리 문제가 재발할 수 있다.
- 백프레셔는 `write()`의 반환값과 `'drain'` 이벤트로 생산 속도를 소비 속도에 맞추는 흐름 제어이며, `pipe()`가 이를 자동화하지만 에러 시 리소스 정리를 해주지 않는다는 결함이 있다.
- `stream.pipeline()`은 백프레셔 자동 처리와 에러 시 전체 스트림 정리를 함께 제공하므로, 신규 코드에서는 `pipe()` 대신 기본으로 사용하는 것이 안전하다.

## 참고 자료

- [Node.js 공식 문서 - Stream (Backpressuring in Streams)](https://nodejs.org/en/learn/modules/backpressuring-in-streams)
- [Node.js 공식 문서 - stream.pipeline()](https://nodejs.org/api/stream.html#streampipelinesource-transforms-destination-callback)
