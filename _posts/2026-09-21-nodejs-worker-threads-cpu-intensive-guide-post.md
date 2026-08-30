---
layout: single
title: "Node.js에서 CPU 집약적 작업 처리하기 — Worker Threads로 이벤트 루프 블로킹 피하기"
date: 2026-09-21 12:25:00 +0530
categories: backend
tags: ["nodejs", "workerthreads", "이벤트루프", "cpu집약작업", "멀티스레딩"]
toc: true
toc_sticky: true
excerpt: "이미지 리사이징이나 대용량 JSON 파싱 같은 무거운 연산이 Node.js 서버 전체를 멈추게 만드는 이유와, Worker Threads로 메인 이벤트 루프를 지키는 방법을 정리했다."
---

## 왜 API 하나가 서버 전체를 멈추게 만드나

Node.js는 단일 스레드 이벤트 루프로 동작한다는 것이 큰 장점이지만, 동시에 가장 흔히 오해되는 지점이기도 하다. I/O 작업(DB 조회, 파일 읽기, 네트워크 요청)은 논블로킹으로 처리되어 다른 요청을 막지 않지만, **CPU를 실제로 소모하는 연산**은 이 원칙에서 예외다.

```javascript
app.get('/resize-image', (req, res) => {
  const resized = heavyImageResize(req.file);  // CPU 집약적 동기 연산
  res.send(resized);
});
```

이미지 리사이징, 대용량 JSON 파싱, 복잡한 정규식 매칭, 암호화 해시 계산 같은 작업은 실행되는 동안 이벤트 루프를 통째로 점유한다. 이 요청 하나를 처리하는 동안 서버로 들어오는 다른 모든 요청(심지어 헬스체크조차)이 대기 상태에 걸린다. 사용자 입장에서는 "서버가 죽은 것처럼" 느껴지는 순간이다.

## 잘못된 접근: 그냥 async/await을 붙이면 해결될 거라는 착각

```javascript
app.get('/resize-image', async (req, res) => {
  const resized = await heavyImageResize(req.file);  // 여전히 동기 연산
  res.send(resized);
});
```

`async`/`await`을 붙였다고 이 연산이 저절로 다른 스레드에서 실행되는 것은 아니다. `async` 함수 안에서도 실제 계산 로직이 동기적으로 CPU를 쓰는 코드라면, 이벤트 루프는 여전히 그 계산이 끝날 때까지 다른 작업을 처리하지 못한다. `async`/`await`은 Promise 기반의 **비동기 I/O**를 다루기 위한 문법이지, CPU 연산 자체를 병렬화해주는 것이 아니라는 점을 혼동하면 안 된다.

## 올바른 접근: Worker Threads로 별도 스레드에 위임

Node.js는 `worker_threads` 모듈로 실제 OS 스레드를 만들어 CPU 집약적 작업을 메인 이벤트 루프와 분리할 수 있다.

```javascript
// main.js
const { Worker } = require('worker_threads');

function resizeImageInWorker(filePath) {
  return new Promise((resolve, reject) => {
    const worker = new Worker('./resize-worker.js', {
      workerData: { filePath }
    });
    worker.on('message', resolve);
    worker.on('error', reject);
  });
}

app.get('/resize-image', async (req, res) => {
  const resized = await resizeImageInWorker(req.file.path);
  res.send(resized);
});
```

```javascript
// resize-worker.js
const { workerData, parentPort } = require('worker_threads');
const result = heavyImageResize(workerData.filePath);
parentPort.postMessage(result);
```

Worker 스레드는 메인 스레드와 메모리를 공유하지 않고 메시지(`postMessage`)로 통신한다. 무거운 연산이 Worker 안에서 실행되는 동안, 메인 스레드의 이벤트 루프는 계속 다른 요청을 처리할 수 있다.

## Worker Threads vs 다른 대안 비교

| 방법 | 동작 방식 | 적합한 상황 |
|---|---|---|
| Worker Threads | 같은 프로세스 내 별도 스레드 | 단발성 CPU 작업, 메인 프로세스와 긴밀히 통신 |
| Child Process (`fork`) | 완전히 별도의 Node 프로세스 | 무거운 작업 격리, 크래시가 메인에 영향 없어야 할 때 |
| 클러스터(`cluster` 모듈) | 여러 워커 프로세스로 요청 자체를 분산 | 전체 서버 처리량 자체를 늘리고 싶을 때 |
| 외부 큐(Bull, BullMQ 등) | 별도 워커 프로세스/서버로 작업 위임 | 작업이 오래 걸리거나 재시도·우선순위 관리가 필요할 때 |

Worker Threads는 프로세스를 새로 띄우는 것보다 가볍지만, 결국 스레드 하나를 새로 만드는 비용이 있으므로 아주 짧은 연산마다 매번 새 Worker를 생성하면 오히려 오버헤드가 더 커질 수 있다. 반복적으로 발생하는 무거운 작업이라면 Worker 풀(pool)을 미리 만들어두고 재사용하는 것이 정석이다.

## 실무 포인트

- **Worker 풀 라이브러리를 활용하라.** `piscina` 같은 라이브러리는 Worker Threads를 직접 관리하는 번거로움 없이, 작업 큐와 스레드 풀을 자동으로 관리해준다.
- **Worker 간 데이터 전달 비용을 고려하라.** 기본적으로 메시지는 구조화 복제 알고리즘(structured clone)으로 직렬화되어 전달되므로, 매우 큰 데이터를 자주 주고받으면 그 자체가 병목이 될 수 있다. `SharedArrayBuffer`를 쓰면 이 복사 비용을 줄일 수 있다.
- **모든 무거운 작업을 Worker로 옮기는 것이 항상 정답은 아니다.** 요청량이 매우 많고 각 작업이 오래 걸린다면, 애초에 별도의 백그라운드 워커 서버와 메시지 큐(BullMQ 등)로 구조를 분리하는 편이 확장성 면에서 유리하다.
- **에러 처리를 빠뜨리지 마라.** Worker 내부에서 처리되지 않은 예외가 발생하면 `error` 이벤트로 전달되므로, 이를 무시하면 응답이 영원히 오지 않는 요청이 쌓일 수 있다.

## 마무리 요약

- Node.js의 논블로킹 I/O는 CPU 집약적 연산에는 적용되지 않으며, 무거운 동기 계산은 이벤트 루프 전체를 막는다.
- `async`/`await`은 비동기 I/O를 위한 문법일 뿐 CPU 연산을 병렬화해주지 않으므로, 실제 해법은 `worker_threads`로 별도 스레드에 작업을 위임하는 것이다.
- 반복적인 무거운 작업은 Worker 풀로 재사용하고, 작업 규모가 크다면 Child Process나 외부 큐 기반 구조까지 검토해야 한다.

## 참고 자료

- [Node.js 공식 문서 - Worker Threads](https://nodejs.org/api/worker_threads.html)
- [Node.js 공식 문서 - Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop)
