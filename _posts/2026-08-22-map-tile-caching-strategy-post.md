---
layout: single
title: "지도 타일, 서버까지 안 가고 끝내기 — CDN·브라우저·서비스워커 3단 캐시 전략"
date: 2026-08-22 13:20:00 +0530
categories: gis
tags: ["gis", "map-tile", "cdn", "service-worker", "caching", "web-performance"]
toc: true
toc_sticky: true
excerpt: "웹 지도는 화면 하나에 수십 개의 타일 요청이 몰리는 구조라, 브라우저·서비스워커·CDN 세 계층을 제대로 겹치지 않으면 타일 서버가 가장 먼저 무너진다."
---

## 왜 지금 타일 캐싱인가

웹 지도는 지도 라이브러리(OpenLayers, MapLibre, Mapbox GL 등)가 화면에 보이는 영역을 z/x/y 좌표의 타일 이미지 조각으로 쪼개 요청하는 구조다. 사용자가 화면을 조금만 이동하거나 확대해도 새로 필요한 타일이 한 번에 수십 개씩 발생한다. 이 요청이 매번 오리진 타일 서버까지 도달해 렌더링이나 DB 조회를 거친다면, 동시 접속자가 조금만 늘어나도 서버 부하가 급격히 커진다.

문제는 대부분의 타일이 "누구에게나 똑같은 응답"이라는 점이다. 서울 시청 앞 z=14 타일은 어느 사용자가 요청하든 내용이 같다(개인화된 오버레이가 없는 한). 이런 정적 성격 덕분에 타일은 캐싱에 매우 유리한 리소스인데도, 캐시 계층을 제대로 설계하지 않으면 이 이점을 살리지 못하고 매 요청을 오리진까지 흘려보내게 된다.

이 글은 기존에 다룬 PostGIS 벡터 타일 서빙이나 타일 생성 파이프라인이 아니라, **이미 만들어진 타일을 어떻게 여러 계층에서 재사용해 오리진 부담을 줄일 것인가**에 초점을 맞춘다.

## 핵심 개념 1: 캐시 계층과 각자의 역할

타일 요청은 보통 아래 순서로 계층을 거치며, 앞 계층에서 캐시 히트가 나면 뒤 계층까지 갈 필요가 없다.

<img src="/assets/images/posts/2026-08-22-map-tile-caching-strategy-1.svg" alt="지도 타일 캐시 계층 구조 - 브라우저 캐시, 서비스워커 캐시, CDN 엣지 캐시, 오리진 타일 서버 순서와 miss 시 흐름" style="width:100%;">

| 계층 | 저장 위치 | 강점 | 한계 |
|---|---|---|---|
| 브라우저 캐시 | 사용자 기기(디스크/메모리) | 응답 즉시, 네트워크 왕복 없음 | 사용자별 저장이라 재사용 범위가 좁음, 용량 제한 |
| 서비스워커 캐시 | 사용자 기기(Cache Storage API) | 오프라인 대응, 캐시 정책을 코드로 세밀 제어 | 최초 등록 전에는 효과 없음, 구현 복잡도 있음 |
| CDN 엣지 캐시 | 지역 PoP(여러 사용자 공유) | 여러 사용자가 같은 타일을 공유해 히트율이 가장 높음 | 캐시 무효화가 즉시 전파되지 않을 수 있음 |
| 오리진 타일 서버 | 원본 서버/DB | 항상 최신 데이터 | 부하·지연이 가장 크고, 장애 시 영향 범위가 큼 |

핵심은 브라우저·서비스워커는 "같은 사용자의 재방문"을, CDN은 "여러 사용자 간 공유"를 담당한다는 역할 분리다. 둘 다 필요하며 어느 하나만으로는 부족하다.

## 핵심 개념 2: 캐시 키와 무효화 설계

타일 URL 자체가 캐시 키가 되므로, `z/x/y` 외에 스타일 버전이나 불필요한 쿼리 파라미터가 섞이면 같은 타일인데도 캐시가 분산되어 히트율이 떨어진다. 반대로 스타일이나 데이터가 바뀌었는데 캐시 키가 그대로면 사용자가 오래된 타일을 계속 보게 된다. 이 두 문제를 함께 풀려면 **URL 버저닝**이 실용적이다. 예를 들어 스타일이 바뀔 때마다 `/tiles/v3/{z}/{x}/{y}.png`처럼 경로에 버전을 올리면, 이전 캐시는 자연히 미스가 나며 새 버전으로 교체되고 강제 무효화 API 호출 없이도 깔끔하게 전환된다.

## 예제 1: CDN·브라우저 캐시 헤더 설정

```nginx
location ~ ^/tiles/v3/\d+/\d+/\d+\.png$ {
    # 타일 내용은 버전 경로가 바뀌지 않는 한 절대 변하지 않으므로 immutable 지정
    add_header Cache-Control "public, max-age=604800, immutable";
    add_header Vary "Accept-Encoding";
}
```

`immutable`은 브라우저가 만료 전까지 재검증 요청조차 보내지 않게 해, 조건부 요청(If-None-Match 등) 트래픽까지 줄여준다. 단, 이 헤더는 URL 버저닝과 반드시 함께 써야 한다. 버전 없이 같은 경로에 내용만 바꾸면 클라이언트가 갱신을 영영 모르게 된다.

## 예제 2: 서비스워커로 오프라인 타일 캐시

```javascript
const TILE_CACHE = 'map-tiles-v3';

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/tiles/v3/')) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached; // 캐시 히트 시 네트워크 요청 없이 즉시 반환

        const response = await fetch(event.request);
        if (response.ok) {
          cache.put(event.request, response.clone());
        }
        return response;
      })
    );
  }
});
```

캐시 이름에 버전(`map-tiles-v3`)을 넣어두면, 서비스워커 갱신 시 이전 버전 캐시를 통째로 정리하기 쉽다. 용량이 무한하지 않으므로, 최근 뷰포트 중심으로 캐시 크기를 제한하는 정책(LRU 등)을 함께 두는 것이 안전하다.

## 실무 포인트

- **캐시 계층 순서를 명시적으로 설계한다**: 브라우저 → 서비스워커 → CDN → 오리진 순으로 미스가 전파되도록, 각 계층의 TTL을 뒤로 갈수록 같거나 길게 맞춘다. 앞 계층 TTL이 뒤 계층보다 길면 오래된 타일이 더 오래 남는 역전 현상이 생길 수 있다.
- **개인화 오버레이는 별도 레이어로 분리한다**: 사용자 위치 마커나 선택 상태처럼 개인화된 요소를 타일 이미지에 합성해버리면 그 타일은 캐시 공유가 불가능해진다. 베이스 타일과 오버레이 레이어를 분리해 베이스만 최대한 캐시한다.
- **CDN 무효화는 최후 수단으로만 쓴다**: 강제 퍼지(purge) API는 전파 지연이나 요금이 들 수 있어, 급한 수정이 아니면 URL 버저닝으로 자연 교체를 유도하는 편이 예측 가능하다.
- **모니터링 없이 튜닝하지 않는다**: 계층별 히트율은 실제 트래픽 패턴에 따라 달라지므로, 캐시 정책을 조정하기 전에 CDN·서비스워커 각각의 히트율 지표부터 확인한다.

## 3줄 요약

- 타일은 대부분 정적이고 공유 가능한 응답이라, 브라우저·서비스워커·CDN 세 계층에 순서대로 캐시를 겹치면 오리진 타일 서버까지 도달하는 요청을 크게 줄일 수 있다.
- 캐시 키에 불필요한 파라미터가 섞이지 않게 하고, 스타일이 바뀔 때는 URL 버저닝으로 무효화를 자연스럽게 처리하는 것이 핵심이다.
- 개인화 오버레이는 베이스 타일과 분리하고, 계층별 TTL 순서와 히트율을 함께 점검해야 캐시 전략이 실제로 효과를 낸다.

## 참고 자료

- [MDN — HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
- [MDN — Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [MapLibre GL JS — Style Specification (sources/tiles)](https://maplibre.org/maplibre-style-spec/sources/)
