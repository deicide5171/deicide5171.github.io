---
layout: single
title: "Bounded-Load 일관 해싱 — 균등 분배를 수학적으로 보장하는 확장판"
date: 2026-09-26 13:45:00 +0530
categories: system-design
tags: ["일관된해싱", "BoundedLoads", "핫스팟방지", "부하분산", "해시링"]
toc: true
toc_sticky: true
excerpt: "일관된 해싱으로 서버 확장은 쉬워졌지만 특정 서버에 요청이 몰리는 핫스팟은 여전히 남는 문제를, 각 서버가 받는 부하 상한을 수학적으로 강제해 균등 분배를 보장하는 Consistent Hashing with Bounded Loads 알고리즘으로 정리했다."
---

## 왜 지금 일관된 해싱을 다시 봐야 하는가

일관된 해싱은 "서버 수가 바뀌어도 재배치되는 키가 최소화된다"는 문제를 훌륭하게 풀지만, 정작 "부하가 균등하게 분배되는가"는 별도의 보장이 없다. 가상 노드(virtual node)를 충분히 늘리면 통계적으로 평균적인 부하는 고르게 퍼지지만, 이는 어디까지나 키의 분포가 균일한 해시 함수를 따른다는 가정 위에서다. 실제 트래픽에서는 특정 키(인기 상품, 유명인 프로필, 바이럴 콘텐츠)에 요청이 극단적으로 몰리는 경우가 흔하고, 이런 핫키가 해시 링 위에서 우연히 같은 구간에 몰리면 그 구간을 담당하는 서버 하나가 나머지보다 훨씬 많은 부하를 받는다. Google 연구팀이 제안한 Consistent Hashing with Bounded Loads(CHBL)는 이 통계적 우연에 기대는 대신, 각 서버가 받을 수 있는 부하에 수학적 상한을 강제해 핫스팟을 원천적으로 막는다.

## 핵심 개념 1 — 평균 부하에 여유 계수를 곱한 상한선

CHBL의 핵심 아이디어는 단순하다. 현재 전체 요청 수를 서버 수로 나눈 평균 부하에 여유 계수 c(보통 1.25 정도)를 곱해 각 서버의 용량 상한으로 삼는다. 키를 해시 링에서 찾을 때, 원래대로라면 시계방향으로 가장 가까운 첫 서버에 배정하지만, CHBL에서는 그 서버가 이미 상한에 도달했는지 먼저 확인한다. 상한에 도달했다면 그 서버는 건너뛰고 링을 계속 시계방향으로 돌며 아직 여유가 있는 다음 서버를 찾는다. 이 과정을 통해 어떤 서버도 평균 부하의 c배를 초과해 받지 않는다는 것이 수학적으로 보장된다.

## 핵심 개념 2 — 여유 계수가 만드는 트레이드오프

여유 계수 c를 1에 가깝게(엄격하게) 잡을수록 부하는 더 균등해지지만, 그만큼 원래 해시된 서버가 아닌 "우회한" 서버로 가는 요청이 늘어나 캐시 지역성이 깨진다. 예를 들어 캐시 서버 앞단에 CHBL을 적용했다면, 특정 키가 원래 서버 A에 캐시돼 있어야 하는데 A가 상한에 도달해 요청이 서버 B로 우회하면 B에는 그 키의 캐시가 없어 캐시 미스가 발생한다. 반대로 c를 크게(느슨하게) 잡으면 캐시 지역성은 잘 유지되지만 부하 상한의 효과가 약해져 핫스팟 완화 효과도 줄어든다. 실무에서는 c=1.25 전후에서 시작해 실제 트래픽 패턴을 보며 조정하는 것이 일반적이다.

| 방식 | 부하 상한 보장 | 캐시 지역성 | 알고리즘 복잡도 |
|---|---|---|---|
| 기본 일관된 해싱 | 없음(통계적 균등만 기대) | 최상(항상 같은 서버) | O(log N) 탐색 |
| 가상 노드 증가 | 여전히 없음(핫키엔 무력) | 최상 | O(log N) 탐색, 메모리 증가 |
| Bounded Loads | 수학적으로 c배 이내 보장 | 상한 도달 시 저하 | O(log N) + 우회 탐색 |

## 코드 예제 — Bounded Load 조회 로직 의사코드

```python
def get_server_bounded(key: str, ring: SortedRing, load_tracker: dict, c: float = 1.25) -> str:
    total_load = sum(load_tracker.values())
    num_servers = len(load_tracker)
    capacity = max(1, int(c * total_load / num_servers)) if total_load > 0 else float('inf')

    candidate = ring.find_first_clockwise(hash(key))
    visited = set()
    while load_tracker[candidate] >= capacity:
        visited.add(candidate)
        candidate = ring.next_clockwise(candidate)
        if candidate in visited:  # 모든 서버가 상한에 도달한 극단적 경우
            break

    load_tracker[candidate] += 1
    return candidate
```

실제 구현(예: Google의 그물망 로드밸런서, Envoy의 ring hash 필터 일부 확장)에서는 부하 카운터를 요청 완료 시 감소시키는 슬라이딩 윈도우 방식과 결합해, 순간적인 상한 초과와 만성적인 핫스팟을 구분해 다룬다.

## 실무 포인트

- **여유 계수 c는 서비스 특성에 맞춰 실험적으로 결정해야 한다.** 캐시 적중률이 결정적인 서비스는 c를 크게, 부하 균등이 더 중요한 서비스(예: 커넥션 풀 분배)는 c를 작게 잡는 편이 유리하다.
- **부하 카운터의 감소 시점 설계가 실질적인 효과를 좌우한다.** 요청이 끝나자마자 감소시키지 않고 일정 시간 윈도우로 누적하면, 순간적인 버스트에는 더 안정적으로 대응할 수 있다.
- **모든 서버가 동시에 상한에 도달하는 극단적 상황을 반드시 처리해야 한다.** 이 경우 우회 탐색이 링을 한 바퀴 돌게 되므로, 안전장치로 임계 상황에서는 상한을 무시하고 라운드로빈으로 폴백하는 로직이 필요하다.

## 마무리 요약

- 기본 일관된 해싱은 재배치 최소화는 보장하지만 부하 균등은 통계적 우연에 의존하므로, 핫키가 몰리면 특정 서버가 과부하될 수 있다.
- Bounded Loads는 평균 부하에 여유 계수를 곱한 상한을 각 서버에 강제하고, 상한 도달 시 링을 따라 다음 서버로 우회시켜 수학적으로 부하 편차를 제한한다.
- 여유 계수는 부하 균등과 캐시 지역성 사이의 트레이드오프이며, 모든 서버가 동시에 상한에 도달하는 극단 상황에 대한 폴백 로직도 함께 설계해야 한다.

## 참고 자료

- [Google Research — Consistent Hashing with Bounded Loads](https://research.google/blog/consistent-hashing-with-bounded-loads/)
- [Vimeo Engineering — Consistent Hashing with Bounded Loads 실전 적용기](https://medium.com/vimeo-engineering-blog/)
