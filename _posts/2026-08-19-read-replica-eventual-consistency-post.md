---
layout: single
title: "방금 쓴 데이터가 안 보이는 이유 — 읽기 전용 복제본과 Read-Your-Writes 설계"
date: 2026-08-19 12:45:00 +0530
categories: system-design
tags: ["read-replica", "eventual-consistency", "system-design", "sticky-routing", "session-affinity"]
toc: true
toc_sticky: true
excerpt: "읽기 전용 복제본을 도입한 뒤 방금 저장한 값이 화면에 안 보이는 문제를, DB 복제 메커니즘이 아니라 애플리케이션 라우팅·세션 설계 관점에서 어떻게 없앨지 정리한다."
---

## 왜 지금 이 문제인가

트래픽이 늘면 가장 먼저 손대는 것이 읽기 트래픽 분산이다. 쓰기는 Primary DB 하나로 보내고, 조회는 Read Replica 여러 대로 나누면 DB 부하가 눈에 띄게 줄어든다. 문제는 이 구조를 넣은 다음날부터 시작된다. 사용자가 프로필을 수정하고 저장 버튼을 눌렀는데, 곧바로 이어지는 화면에는 수정 전 값이 그대로 보인다. DB 장애도 아니고 코드 버그도 아니다. 쓰기는 Primary에 성공적으로 반영됐지만, 그 직후의 조회가 아직 값을 따라잡지 못한 Replica로 라우팅됐을 뿐이다.

이 현상은 DB 복제가 느려서라기보다, 애플리케이션이 "누가 방금 무엇을 썼는지"를 전혀 모른 채 읽기와 쓰기를 완전히 독립된 요청으로 취급하기 때문에 생긴다. 복제 지연 자체를 줄이는 것은 인프라·DB 엔진 영역의 과제고, 이 글에서 다루는 것은 그 지연이 0이 아니라는 전제 위에서 **애플리케이션이 사용자 경험을 어떻게 지킬 것인가**라는 시스템 설계 문제다. 즉 복제 지연을 없애는 글이 아니라, 복제 지연이 있어도 "내 화면"만큼은 일관되게 만드는 글이다.

## 핵심 개념 1: Read-Your-Writes 일관성이란

분산 시스템의 일관성 모델 중 실무에서 가장 자주 요구되는 것이 바로 **read-your-writes(RYW)** 다. "시스템 전체가 항상 최신 상태를 보여줘야 한다"는 강한 일관성이 아니라, "내가 쓴 값은 적어도 내가 다시 읽을 때는 보여야 한다"는 훨씬 실용적인 보장이다. 다른 사용자가 그 값을 아직 못 보는 것은 대체로 문제가 되지 않지만, 정작 값을 쓴 본인이 자신의 변경을 못 보면 "저장이 안 됐다"는 오해와 중복 제출로 이어진다.

RYW는 시스템 전체의 강한 일관성보다 비용이 훨씬 낮다. 모든 조회를 Primary로 보낼 필요 없이, "이 사용자가 방금 쓴 그 데이터에 한해서만" 최신성을 보장하면 되기 때문이다. 이 범위를 어떻게 좁혀서 구현하느냐가 이 글의 핵심이다.

## 핵심 개념 2: 세 가지 구현 전략 비교

<img src="/assets/images/posts/2026-08-19-read-replica-eventual-consistency-1.svg" alt="Read-Your-Writes 보장 전략 3가지 - Sticky Routing, 버전 토큰 추적, 쓰기 경로 캐시 우회 비교도" style="width:100%;">

| 전략 | 핵심 아이디어 | 장점 | 트레이드오프 |
|---|---|---|---|
| Sticky Routing(세션 고정) | 쓰기 발생 후 일정 TTL 동안 해당 세션의 조회를 Primary로 고정 | 구현이 단순하고 DB·드라이버 변경 불필요 | TTL 설정이 틀리면 여전히 stale read 가능, Primary 부하 증가 |
| 버전 토큰 추적 | 쓰기 응답에 커밋 시점 버전(LSN 등)을 담아 클라이언트가 다음 조회에 함께 전달 | Primary에 몰지 않고도 정확한 시점 보장 | DB·드라이버가 버전 조회를 지원해야 하고 프로토콜 변경 필요 |
| 쓰기 경로 캐시 우회 | 쓰기 API 응답 자체에 갱신된 값을 담아 그 화면만 즉시 반영 | 추가 대기·인프라 없이 즉각 반영 | 보장 범위가 "그 화면"으로 한정, 새로고침·다른 화면은 별도 처리 필요 |

세 전략은 서로 배타적이지 않다. 실무에서는 대부분 조합해서 쓴다. 쓰기 API 응답에는 갱신된 값을 그대로 담아 화면을 즉시 채우고(전략 3), 이어지는 후속 조회 요청 몇 건에 한해서는 세션을 짧게 Primary에 고정한다(전략 1). 버전 토큰 추적(전략 2)은 정확도가 가장 높지만 인프라·프로토콜 변경 비용이 있어, RYW 위반이 곧바로 사고로 이어지는 결제·잔액 같은 도메인에 우선 적용하는 경우가 많다.

## 핵심 개념 3: 라우팅 계층에서의 구현 위치

이 로직을 어디에 둘지도 설계 선택이다. 애플리케이션 코드 안에 라우팅 규칙을 넣으면(예: 서비스 레이어에서 직접 Primary/Replica 커넥션을 선택) 팀이 로직을 완전히 통제할 수 있지만, 서비스가 늘어날수록 같은 규칙을 반복 구현해야 한다. 반대로 DB 프록시나 커넥션 미들웨어(예: ProxySQL류 도구, 또는 커스텀 라우팅 프록시) 계층에 두면 애플리케이션 코드는 신경 쓸 필요가 없지만, "이 요청이 방금 쓴 세션의 후속 조회인지" 같은 애플리케이션 맥락을 프록시에 전달할 방법이 필요하다. 정답은 도메인 민감도에 달려 있다 — 결제·재고처럼 오류 비용이 큰 도메인은 애플리케이션 레벨에서 명시적으로 제어하고, 게시글 목록처럼 잠깐의 지연이 무해한 도메인은 프록시 레벨의 일괄 규칙에 맡기는 식이다.

## 예제: 세션 고정 라우팅 구현 (TypeScript/Express 미들웨어)

```typescript
// 쓰기 요청 이후 일정 시간 동안 이 세션의 조회를 Primary로 고정한다
const STICKY_WINDOW_MS = 5000; // 복제 지연 관측치보다 여유 있게 설정

function stickyRoutingMiddleware(req, res, next) {
  const session = req.session;

  // 이번 요청이 쓰기(POST/PUT/PATCH/DELETE)라면 타임스탬프 기록
  if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method)) {
    res.on("finish", () => {
      if (res.statusCode < 400) {
        session.lastWriteAt = Date.now();
      }
    });
  }

  // 최근 쓰기 이력이 있으면 이번 요청은 Primary로 라우팅
  const withinWindow =
    session.lastWriteAt && Date.now() - session.lastWriteAt < STICKY_WINDOW_MS;

  req.dbTarget = withinWindow ? "primary" : "replica";
  next();
}
```

`STICKY_WINDOW_MS`는 임의로 정하는 값이 아니라 실제 복제 지연 모니터링 지표(예: replication lag 메트릭의 p99)를 근거로 설정해야 한다. 확인되지 않은 값을 그대로 하드코딩하면 트래픽 패턴이 바뀔 때 다시 stale read가 재발할 수 있다.

## 실무 포인트

- **모든 읽기에 같은 보장을 적용하지 않는다.** RYW가 필요한 대상은 "방금 이 사용자가 쓴 데이터"로 한정된다. 무관한 목록·통계 조회까지 Primary로 몰면 Replica를 둔 목적 자체가 사라진다.
- **TTL·윈도우 값은 실측 지연 지표에 근거해 정한다.** 복제 지연은 트래픽·시간대에 따라 달라지므로, 고정값보다는 모니터링 지표를 참고해 주기적으로 재검토하는 편이 안전하다.
- **세션 고정은 상태를 어딘가에 저장해야 한다.** 서버가 여러 대라면 세션 저장소(Redis 등)를 공유하지 않으면 라우팅 결정이 인스턴스마다 달라질 수 있다.
- **모바일 앱처럼 세션 개념이 약한 클라이언트**에서는 버전 토큰 방식이 더 잘 맞는 경우가 많다. 클라이언트가 마지막으로 받은 버전을 명시적으로 들고 다닐 수 있기 때문이다.

## 3줄 요약

- Read-Your-Writes는 시스템 전체의 강한 일관성이 아니라 "내가 쓴 값은 내가 본다"는 좁고 실용적인 보장이다.
- Sticky Routing, 버전 토큰 추적, 쓰기 경로 캐시 우회는 서로 배타적이지 않으며 도메인 민감도에 따라 조합해서 적용한다.
- TTL·라우팅 규칙은 실측 복제 지연 지표에 근거해 설정하고, 정기적으로 재검토해야 재발을 막을 수 있다.

## 참고 자료

- [Martin Kleppmann — Designing Data-Intensive Applications, Ch.5 Replication](https://dataintensive.net/)
- [AWS Database Blog — Read-after-write consistency for Aurora Read Replicas](https://aws.amazon.com/blogs/database/)
- [PostgreSQL Documentation — Replication and LSN](https://www.postgresql.org/docs/current/wal-internals.html)
