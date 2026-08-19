---
layout: single
title: "네트워크가 끊겨도 작업은 이어진다 — 오프라인 퍼스트 PWA와 백그라운드 동기화"
date: 2026-08-30 13:30:00 +0530
categories: frontend
tags: ["frontend", "pwa", "offline-first", "background-sync", "service-worker", "indexeddb"]
toc: true
toc_sticky: true
excerpt: "네트워크 연결을 전제로 짠 앱은 지하철·엘리베이터에서 조용히 실패한다. 서비스 워커 캐싱 전략, IndexedDB에 임시 저장한 쓰기 작업, Background Sync API로 이어지는 오프라인 퍼스트 아키텍처를 정리한다."
---

대부분의 웹 앱은 "네트워크가 항상 연결돼 있다"는 암묵적 전제 위에 짜인다. 이 전제가 깨지는 순간 — 지하철 터널, 엘리베이터, 약한 와이파이 — 사용자는 로딩 스피너가 멈추지 않거나 "네트워크 오류"만 보게 된다. **오프라인 퍼스트(offline-first)** 설계는 이 전제를 뒤집는다. 네트워크를 "있으면 좋은 것"으로 취급하고, 앱의 핵심 기능이 네트워크 없이도 최소한 읽기는 되고, 쓰기는 나중에 반영되도록 만드는 접근이다.

이 글은 오프라인 퍼스트 PWA를 구성하는 세 조각 — 서비스 워커의 캐싱 전략, 오프라인 중 쓰기를 담아두는 로컬 저장소, 연결이 복구됐을 때 그 쓰기를 서버에 반영하는 Background Sync — 을 순서대로 정리한다.

## 핵심 개념 1: 서비스 워커 캐싱 전략 — 무엇을 캐시하고 언제 갱신할까

오프라인에서도 앱 셸(레이아웃, 스타일, 로고 같은 정적 자원)이 뜨려면 서비스 워커가 이를 캐시해 둬야 한다. 캐싱 전략은 리소스 성격에 따라 다르게 골라야 한다. 정적 자원(JS/CSS 번들, 아이콘)은 **Cache First**(캐시에 있으면 그대로 쓰고 없을 때만 네트워크)가 적합하고, 자주 바뀌는 API 응답은 **Network First**(네트워크를 우선 시도하고 실패하면 캐시로 폴백)가 맞으며, 최신성이 중요하지만 즉시 응답도 필요한 경우엔 **Stale-While-Revalidate**(캐시를 즉시 반환하면서 백그라운드로 네트워크 요청을 보내 다음 번을 위해 캐시를 갱신)를 쓴다.

| 전략 | 동작 | 적합한 리소스 |
|---|---|---|
| Cache First | 캐시 우선, 없으면 네트워크 | 정적 자원(JS/CSS/폰트/아이콘) |
| Network First | 네트워크 우선, 실패 시 캐시 | 자주 바뀌는 목록·피드 API |
| Stale-While-Revalidate | 캐시 즉시 반환 + 백그라운드 갱신 | 프로필 정보처럼 약간의 지연 허용 |
| Network Only | 항상 네트워크만 | 결제처럼 캐시되면 안 되는 요청 |

## 핵심 개념 2: 오프라인 쓰기 — IndexedDB에 낙관적으로 쌓아둔다

읽기는 캐싱으로 어느 정도 해결되지만, 오프라인 중 사용자가 "저장" 버튼을 누르는 쓰기 작업은 다른 문제다. 네트워크가 없으니 서버에 즉시 보낼 수 없고, 그렇다고 사용자에게 "네트워크가 없어 실패했습니다"라고 알리는 것도 오프라인 퍼스트의 취지에 어긋난다. 대신 그 쓰기 요청(무엇을, 어떤 데이터로)을 **IndexedDB**에 큐 형태로 저장해두고, 화면에는 낙관적으로 "저장됨" 상태를 즉시 보여준다.

이 단계에서 중요한 설계 결정은 각 작업에 **멱등성 키**를 부여하는 것이다. 연결이 복구된 뒤 큐에 쌓인 작업을 재생(replay)할 때, 네트워크가 불안정해 같은 요청이 중복 전송될 가능성이 있다. 서버가 같은 멱등성 키로 온 요청을 한 번만 처리하도록 설계해 두지 않으면, 오프라인 동안 한 번 누른 "좋아요"가 온라인 복귀 후 여러 번 반영되는 사고가 난다.

## 핵심 개념 3: Background Sync API — 연결 복구를 브라우저가 알려준다

큐에 쌓인 작업을 언제 재생할지 앱이 직접 폴링으로 확인할 수도 있지만, **Background Sync API**를 쓰면 브라우저가 네트워크 연결 복구 시점을 감지해 서비스 워커를 깨워준다. 페이지가 닫혀 있어도 서비스 워커가 백그라운드에서 동작해 큐에 쌓인 요청을 전송할 수 있다는 점이 이 API의 핵심 가치다 — 사용자가 앱을 다시 열 때까지 기다릴 필요가 없다.

다만 Background Sync API(One-off Sync)는 브라우저 지원이 제한적이다(Chromium 계열은 지원하지만 Safari는 미지원). 이 때문에 실무에서는 Background Sync를 지원하는 브라우저에서는 그것을 우선 사용하고, 지원하지 않는 브라우저에서는 페이지가 포그라운드로 돌아오는 시점(`online` 이벤트, 페이지 visibility 변경)에 큐를 수동으로 재생하는 폴백을 함께 구현해야 한다.

<img src="/assets/images/posts/2026-08-30-pwa-offline-first-background-sync-1.svg" alt="오프라인 상태에서 사용자 쓰기 작업이 IndexedDB 큐에 저장되고, 네트워크 연결이 복구되면 Background Sync API가 서비스 워커를 깨워 큐를 서버에 재생하는 흐름을 보여주는 다이어그램" style="width:100%;">

## 예제: 서비스 워커 등록과 Background Sync

```javascript
// service-worker.js — sync 이벤트로 큐 재생
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-pending-writes') {
    event.waitUntil(replayQueuedWrites());
  }
});

async function replayQueuedWrites() {
  const db = await openDB('offline-queue', 1);
  const pending = await db.getAll('writes');

  for (const item of pending) {
    try {
      const res = await fetch(item.url, {
        method: item.method,
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': item.idempotencyKey, // 중복 반영 방지
        },
        body: JSON.stringify(item.payload),
      });
      if (res.ok) {
        await db.delete('writes', item.id); // 성공한 항목만 큐에서 제거
      }
    } catch {
      // 여전히 오프라인이면 이 항목은 큐에 남아 다음 sync를 기다린다
    }
  }
}
```

```javascript
// app.js — 오프라인 쓰기 요청을 큐에 저장하고 sync 등록 요청
async function saveNote(note) {
  const db = await openDB('offline-queue', 1);
  await db.add('writes', {
    url: '/api/notes',
    method: 'POST',
    payload: note,
    idempotencyKey: crypto.randomUUID(),
  });

  updateUIOptimistically(note); // 즉시 "저장됨"으로 표시

  const registration = await navigator.serviceWorker.ready;
  if ('sync' in registration) {
    await registration.sync.register('sync-pending-writes');
  }
  // 미지원 브라우저는 'online' 이벤트에서 동일 재생 함수를 직접 호출하는 폴백 필요
}
```

## 실무 포인트

- **캐시 버전 관리를 소홀히 하면 오래된 앱 셸이 영구히 고정된다.** 서비스 워커가 캐시한 정적 자원은 명시적으로 무효화하지 않으면 계속 재사용된다. 캐시 이름에 빌드 해시나 버전을 포함시키고, 새 서비스 워커 활성화 시 이전 버전 캐시를 정리하는 로직을 반드시 넣어야 배포한 새 코드가 사용자에게 반영된다.
- **낙관적 UI와 실패 알림 사이의 균형을 설계하라.** 오프라인 중 "저장됨"으로 낙관적으로 표시했다가 온라인 복귀 후 서버 검증(재고 소진, 권한 만료 등)으로 실제 반영이 실패하면, 사용자에게 그 실패를 뒤늦게라도 명확히 알리는 처리가 빠지면 신뢰가 무너진다.
- **모든 기능을 오프라인 대응할 필요는 없다.** 결제, 실시간 경매처럼 최신 서버 상태를 반드시 확인해야 하는 기능은 오프라인에서 아예 비활성화하고 안내 메시지를 보여주는 것이 낙관적 처리보다 안전하다. 오프라인 퍼스트는 "모든 것을 오프라인으로"가 아니라 "오프라인이어도 되는 것과 안 되는 것을 구분"하는 설계다.

## 3줄 요약

- 오프라인 퍼스트는 리소스 성격에 맞는 서비스 워커 캐싱 전략(Cache First, Network First, Stale-While-Revalidate)으로 읽기를 보장하는 데서 시작한다.
- 오프라인 중 쓰기 작업은 멱등성 키와 함께 IndexedDB 큐에 저장하고 낙관적으로 UI를 갱신하며, Background Sync API로 연결 복구 시점에 서비스 워커가 자동으로 큐를 재생하게 만든다.
- Background Sync API는 브라우저 지원이 제한적이므로 `online` 이벤트 기반 수동 재생 폴백이 필요하고, 결제처럼 최신 상태 확인이 필수인 기능은 오프라인 대응 대상에서 의도적으로 제외해야 한다.

## 참고 자료

- [MDN: Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [MDN: Background Synchronization API](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API)
- [web.dev: Offline Cookbook](https://web.dev/articles/offline-cookbook)
- [web.dev: IndexedDB best practices](https://web.dev/articles/indexeddb-best-practices)
