---
layout: single
title: "팔로워 100만 명에게 글 하나 배달하기 — 피드 팬아웃 설계와 셀럽 문제"
date: 2026-08-23 13:45:00 +0530
categories: system-design
tags: ["system-design", "fan-out", "timeline", "redis", "sns"]
toc: true
toc_sticky: true
excerpt: "SNS 피드의 핵심 설계 문제인 팬아웃 온 라이트와 팬아웃 온 리드의 트레이드오프를 비교하고, 셀럽 계정이 만드는 쓰기 폭발을 하이브리드 방식으로 푸는 법을 정리한다."
---

트위터(X)나 인스타그램의 홈 피드를 열면 내가 팔로우한 사람들의 최신 글이 시간순으로 즉시 나타난다. 겉보기에는 `SELECT ... WHERE author_id IN (팔로잉 목록) ORDER BY created_at DESC` 한 줄로 끝날 것 같지만, 팔로잉이 수백 명이고 사용자가 수천만 명인 규모에서 이 쿼리를 요청마다 실행하면 DB는 버티지 못한다. 그래서 피드 시스템의 본질적인 질문은 이것이다. **글과 타임라인을 합치는 비용을 쓸 때 낼 것인가, 읽을 때 낼 것인가.**

이 질문에 대한 두 가지 답이 **팬아웃 온 라이트(fan-out on write)**와 **팬아웃 온 리드(fan-out on read)**다. 대부분의 SNS는 읽기가 쓰기보다 압도적으로 많기 때문에 쓰기 시점에 비용을 내는 쪽이 유리하지만, 팔로워가 수백만 명인 셀럽 계정이 등장하는 순간 이 전제가 무너진다. 이 글에서는 두 방식의 트레이드오프와, 실무 시스템들이 채택한 하이브리드 해법을 정리한다.

## 팬아웃 온 라이트 — 쓸 때 밀어 넣는다 (push)

사용자가 글을 쓰면, 그 순간 작성자의 팔로워 전원의 타임라인 캐시(대개 Redis Sorted Set 같은 인메모리 리스트)에 글 ID를 밀어 넣는다. 각 사용자의 타임라인이 항상 "미리 계산된 상태"로 존재하므로, 읽기는 자기 캐시 하나를 조회하는 O(1)에 가까운 작업이 된다. 홈 피드 조회가 전체 트래픽의 대부분을 차지하는 서비스에서 읽기 지연을 극적으로 줄일 수 있어, 트위터가 초창기 확장 과정에서 채택한 방식으로 잘 알려져 있다.

대가는 쓰기 비용이다. 글 하나의 쓰기 작업량이 **팔로워 수에 비례**한다. 팔로워 100명인 사용자의 글은 100건의 캐시 삽입이면 되지만, 100만 팔로워를 가진 계정이 글을 하나 쓰면 100만 건의 삽입이 발생한다. 게다가 수개월간 접속하지 않은 휴면 사용자의 타임라인에도 꼬박꼬박 배달하게 되므로, 상당량의 쓰기가 아무도 읽지 않을 캐시를 채우는 데 낭비된다.

## 팬아웃 온 리드 — 읽을 때 모아 온다 (pull)

반대 방식은 쓰기 시점에는 글을 작성자의 저장소에 한 번만 기록하고, 사용자가 피드를 열 때 팔로잉 목록을 순회하며 각자의 최근 글을 모아 병합·정렬하는 것이다. 쓰기는 팔로워 수와 무관하게 O(1)이고, 휴면 사용자를 위한 낭비도 없으며, 팔로우/언팔로우가 즉시 피드에 반영된다는 부수적 장점도 있다.

문제는 읽기 비용이다. 팔로잉이 500명이면 요청 한 번에 500개 소스를 조회해 병합해야 하고, 이 작업이 사용자가 화면을 기다리는 동안 일어난다. 읽기:쓰기 비율이 100:1을 넘나드는 일반적인 SNS에서는 비싼 연산을 가장 빈번한 경로에 배치하는 셈이라, 순수 pull 방식만으로 대규모 피드를 운영하는 경우는 드물다.

| 구분 | 팬아웃 온 라이트 (push) | 팬아웃 온 리드 (pull) |
|---|---|---|
| 쓰기 비용 | 팔로워 수에 비례 (높음) | O(1) (낮음) |
| 읽기 비용 | 캐시 1회 조회 (낮음) | 팔로잉 수만큼 조회·병합 (높음) |
| 최신성 | 팬아웃 지연만큼 늦음 | 항상 최신 |
| 유리한 상황 | 읽기가 압도적으로 많을 때 | 팔로워가 매우 많은 계정, 휴면 사용자 |
| 취약한 상황 | 셀럽 계정, 휴면 사용자 낭비 | 팔로잉이 많은 활성 사용자의 읽기 |

## 셀럽 문제와 하이브리드 — 계정마다 전략을 달리한다

push 방식의 최악 사례는 명확하다. 수백만 팔로워를 가진 계정이 글을 쓰는 순간 수백만 건의 캐시 쓰기가 쏟아지고, 이런 계정 몇 개가 동시에 활동하면 팬아웃 큐가 밀리면서 모든 사용자의 피드 반영이 지연된다. 이것이 이른바 **셀럽 문제(celebrity problem)**다.

실무의 해법은 두 방식의 결합이다. **팔로워 수가 임계값 이하인 일반 계정의 글은 push로 팔로워 타임라인에 미리 배달하고, 임계값을 넘는 셀럽 계정의 글은 push를 생략한 채 읽기 시점에 pull로 가져와 캐시된 타임라인과 병합**한다. 사용자 대부분이 팔로우하는 셀럽은 소수이므로 읽기 시점의 pull 대상은 몇 개 계정에 그치고, 쓰기 폭발은 구조적으로 차단된다. 트위터가 대규모 트래픽을 다루며 공개한 타임라인 아키텍처가 이 접근으로 널리 알려져 있다.

<img src="/assets/images/posts/2026-08-23-feed-timeline-fanout-1.svg" alt="일반 사용자의 글은 비동기 팬아웃 워커를 거쳐 팔로워 타임라인 캐시에 푸시되고, 셀럽의 글은 저장소에만 기록된 뒤 읽기 시점에 병합기가 캐시와 셀럽 글을 합쳐 최종 타임라인을 만드는 하이브리드 구조도" style="width:100%;">

## 예제 — Redis Sorted Set 기반 하이브리드 팬아웃

아래는 하이브리드 전략의 골격을 보여주는 파이썬 예제다. 글 ID를 작성 시각을 점수로 하는 Sorted Set에 쌓고, 셀럽 여부에 따라 push를 생략한다.

```python
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

CELEB_THRESHOLD = 100_000   # 이 팔로워 수를 넘으면 push 생략
TIMELINE_MAX = 800          # 타임라인 캐시에 보관할 글 개수 상한

def fanout_on_write(author_id: str, post_id: str, created_at: float) -> None:
    """글 작성 이벤트를 받아 팔로워 타임라인에 푸시한다. 비동기 워커에서 실행."""
    followers = int(r.get(f"user:{author_id}:follower_count") or 0)
    if followers >= CELEB_THRESHOLD:
        return  # 셀럽은 푸시하지 않는다 — 읽기 시점에 pull로 병합
    for follower_id in r.sscan_iter(f"user:{author_id}:followers"):
        key = f"timeline:{follower_id}"
        pipe = r.pipeline()
        pipe.zadd(key, {post_id: created_at})            # 멱등: 재실행돼도 안전
        pipe.zremrangebyrank(key, 0, -(TIMELINE_MAX + 1))  # 캐시 크기 제한
        pipe.execute()

def read_timeline(user_id: str, count: int = 50) -> list[str]:
    """푸시된 캐시와 셀럽 글을 읽기 시점에 병합한다."""
    merged = r.zrevrange(f"timeline:{user_id}", 0, count - 1, withscores=True)
    for celeb_id in r.smembers(f"user:{user_id}:celeb_followings"):
        merged += r.zrevrange(f"posts:{celeb_id}", 0, count - 1, withscores=True)
    merged.sort(key=lambda item: item[1], reverse=True)
    return [post_id for post_id, _score in merged[:count]]
```

## 흔한 함정 — 팬아웃을 요청 경로에서 동기로 실행한다

초기 구현에서 자주 보이는 안티패턴은 글 작성 API 핸들러 안에서 팔로워 루프를 그대로 도는 것이다. 팔로워가 적을 때는 문제가 없다가, 특정 사용자의 팔로워가 늘어나는 순간 글 작성 응답 시간이 팔로워 수에 비례해 길어지고, 클라이언트 타임아웃 → 재시도 → 중복 팬아웃으로 이어지며 장애가 증폭된다.

올바른 구조는 글 작성 API는 **원본 저장 + 이벤트 발행까지만** 책임지고 즉시 응답한 뒤, 팬아웃은 메시지 큐(Kafka, SQS 등) 뒤의 워커가 비동기로 처리하는 것이다. 이때 워커 재시도에 대비해 팬아웃 연산 자체를 멱등하게(ZADD처럼 같은 멤버 재삽입이 무해하게) 설계해야 중복 배달이 생기지 않는다. 피드가 "쓰자마자 팔로워에게 보이는" 강한 일관성이 아니라 몇 초 수준의 최종적 일관성을 갖는 것은 이 구조의 의도된 트레이드오프다.

## 실무 포인트

- **임계값은 고정 상수가 아니라 튜닝 대상이다**: 팬아웃 큐 지연, 캐시 메모리, 읽기 지연 지표를 보며 조정한다. 팔로워 수 외에 계정의 게시 빈도를 함께 고려하는 변형도 있다.
- **휴면 사용자는 push 대상에서 제외한다**: 최근 N일간 접속하지 않은 사용자의 타임라인은 푸시를 생략하고, 복귀 시점에 pull로 재구성하면 쓰기 낭비를 크게 줄일 수 있다.
- **캐시는 소스 오브 트루스가 아니다**: 타임라인 캐시는 언제든 원본(글 저장소 + 팔로우 그래프)에서 재생성 가능해야 한다. 글 삭제·차단 시 수백만 캐시를 일일이 지우는 대신, 읽기 시점 필터링으로 보정하는 편이 현실적이다.
- **처음부터 하이브리드로 시작할 필요는 없다**: 셀럽 규모의 계정이 없는 서비스라면 순수 push(또는 소규모라면 단순 pull 쿼리)로 충분하며, 하이브리드는 쓰기 폭발이 실측될 때 도입해도 늦지 않다.

## 3줄 요약

- 피드 설계의 핵심은 글과 타임라인의 병합 비용을 쓰기 시점(push)에 낼지 읽기 시점(pull)에 낼지의 선택이며, 읽기가 많은 SNS에서는 push가 기본값이 된다.
- push는 쓰기 비용이 팔로워 수에 비례하므로 셀럽 계정에서 무너지고, 실무 해법은 일반 계정은 push·셀럽은 pull로 처리해 읽기 시점에 병합하는 하이브리드다.
- 팬아웃은 반드시 요청 경로 밖의 비동기 워커에서 멱등하게 수행해야 하며, 타임라인 캐시는 원본에서 언제든 재생성 가능한 파생 데이터로 취급해야 한다.

## 참고 자료

- [InfoQ: Timelines at Scale (Raffi Krikorian, Twitter)](https://www.infoq.com/presentations/Twitter-Timeline-Scalability/)
- [High Scalability: The Architecture Twitter Uses to Deal with 150M Active Users](http://highscalability.com/blog/2013/7/8/the-architecture-twitter-uses-to-deal-with-150m-active-users.html)
- [Redis Docs: Sorted Sets](https://redis.io/docs/latest/develop/data-types/sorted-sets/)
- [Designing Data-Intensive Applications (Martin Kleppmann) — 1장 트위터 사례](https://dataintensive.net/)
