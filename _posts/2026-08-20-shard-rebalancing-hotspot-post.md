---
layout: single
title: "샤드 재분배의 역설 — 데이터는 고르게 나눠도 트래픽은 쏠린다"
date: 2026-08-20 12:45:00 +0530
categories: system-design
tags: ["샤드재분배", "핫스팟", "컨시스턴트해싱", "부하분산", "분산시스템"]
toc: true
toc_sticky: true
excerpt: "샤드별 데이터량을 균등하게 재분배해도 특정 샤드에만 트래픽이 몰리는 핫스팟은 그대로 남을 수 있다. 재분배 알고리즘과 핫스팟 감지·완화 전략을 정리한다."
---

## 왜 재분배만으로는 부족한가

샤딩을 도입한 팀이 흔히 겪는 순서가 있다. 서비스가 자라면서 한두 샤드의 디스크 사용량이 눈에 띄게 커지면 "재분배(rebalancing)"를 실행해 데이터를 다시 고르게 나눈다. 여기서 많은 팀이 문제가 끝났다고 생각하지만, 실제로는 절반만 해결된 것이다.

재분배가 맞추는 것은 **저장 용량의 균형**이다. 반면 서비스 장애로 이어지는 것은 대체로 **트래픽의 편중**이며, 이 둘은 종종 일치하지 않는다. 특정 유저·상품·리전에 요청이 몰리는 "핫키(hot key)"가 있으면, 데이터량은 균등해도 그 키를 담은 샤드 하나만 CPU와 커넥션이 포화될 수 있다. 재분배 배치를 돌린 다음 날에도 알림이 계속 울리는 이유다.

이 글은 샤딩 키 설계 자체보다, **재분배 알고리즘**과 **저장 균형만으로 잡히지 않는 트래픽 핫스팟의 감지·완화**에 집중한다.

<img src="/assets/images/posts/2026-08-20-shard-rebalancing-hotspot-1.svg" alt="샤드 재분배 후에도 남는 핫스팟 - 데이터량 균등화와 트래픽 쏠림의 차이, 핫샤드 분할 완화 흐름" style="width:100%;">

## 핵심 개념 1: 데이터 핫스팟과 트래픽 핫스팟은 다른 문제다

| 구분 | 데이터 핫스팟 | 트래픽 핫스팟 |
|---|---|---|
| 원인 | 파티션에 row 누적 등 분포 왜곡 | 인기 상품·유명인 계정 등 read/write 집중 |
| 관측 지표 | 디스크 사용량, row 수 | QPS, CPU, p99 레이턴시, 커넥션 수 |
| 재분배로 해결되는가 | 대체로 해결됨 | **해결 안 됨** — 핫키가 옮겨간 샤드가 새 핫스팟이 될 뿐 |
| 필요한 대응 | 정기 재분배, 크기 모니터링 | 핫키 격리, 캐싱, 샤드 추가 분할 |

같은 지표(디스크 사용률)로만 감시하면 트래픽 핫스팟을 놓친다. 저장 용량은 평평한데 특정 샤드 p99 레이턴시만 튀는 그래프가 전형적인 신호다.

## 핵심 개념 2: 재분배 알고리즘 비교

| 방식 | 재분배 시 이동량 | 특징 |
|---|---|---|
| 단순 모듈러 해싱(`key % N`) | N이 바뀌면 거의 전체 데이터 이동 | 구현은 쉽지만 확장 시 재앙에 가까움 |
| 컨시스턴트 해싱 | 인접 구간 데이터만 이동 | 이동량이 작아 온라인 재분배에 적합 |
| 가상 노드(Virtual Node) 세분화 | 가상 노드 단위로 세밀하게 이동 | 물리 샤드 간 부하를 더 균등하게 맞출 수 있음 |
| 범위 기반 분할(Range Split) | 분할 대상 범위만 이동 | 핫샤드 하나만 골라 쪼갤 수 있어 완화에 유용 |

실무에서는 컨시스턴트 해싱과 가상 노드를 함께 쓰는 조합이 흔하다. 가상 노드가 늘수록 재분배 단위가 잘게 쪼개져 쏠림이 줄지만, 관리 비용도 늘어난다.

## 핵심 개념 3: 핫스팟을 어떻게 감지하는가

핫스팟은 평균값만 보면 보이지 않는다. 전체 평균 QPS가 안정적이어도 샤드 하나가 나머지 대비 몇 배의 트래픽을 받을 수 있다. 다음 지표를 **샤드 단위로 분해해서** 봐야 한다.

- 샤드별 QPS·초당 커넥션 수의 표준편차 또는 최댓값/평균값 비율
- 샤드별 p99 레이턴시 — 데이터량은 같아도 레이턴시만 튀면 트래픽 편중 신호
- 특정 키에 대한 접근 빈도 상위 N개(top-K) 추적 — 캐시 계층이나 프록시에서 샘플링으로 근사 가능

임계치 기반 알림(예: 특정 샤드 QPS가 평균의 3배 이상)을 걸어두면 새로운 핫스팟을 조기에 알 수 있다.

## 예제: 컨시스턴트 해싱에 가상 노드 추가하기 (Python)

```python
import bisect
import hashlib

class ConsistentHashRing:
    def __init__(self, virtual_nodes=150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_shard(self, shard_id: str):
        for i in range(self.virtual_nodes):
            h = self._hash(f"{shard_id}#{i}")
            self.ring[h] = shard_id
            bisect.insort(self.sorted_keys, h)

    def get_shard(self, data_key: str) -> str:
        h = self._hash(data_key)
        idx = bisect.bisect(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]

# 핫샤드 B 분할: shard_id="B"를 제거하고 "B1", "B2"를
# add_shard로 등록하면 담당 구간이 세분화된다.
```

## 예제: 핫키 완화를 위한 키 salting

특정 키 하나에 트래픽이 쏠릴 때는 샤드를 더 쪼개도 소용없다. 이럴 땐 키 자체를 여러 파티션으로 흩뿌리는 salting이 필요하다.

```python
import random

def write_hot_counter(base_key: str, value: int, salt_range=10):
    salt = random.randint(0, salt_range - 1)
    salted_key = f"{base_key}:{salt}"
    redis_client.incrby(salted_key, value)  # 각기 다른 샤드에 분산 기록

def read_hot_counter(base_key: str, salt_range=10) -> int:
    keys = [f"{base_key}:{s}" for s in range(salt_range)]
    return sum(int(v or 0) for v in redis_client.mget(keys))
```

쓰기가 집중되는 카운터 값에 흔히 쓰는 패턴이며, 읽기 비용과 일관성 요구 수준을 따져 salt 개수를 정해야 한다.

## 실무 포인트

- **재분배와 핫스팟 완화는 별개 작업이다.** 정기 재분배와 별개로 샤드별 QPS·레이턴시를 상시 모니터링해야 한다.
- **핫샤드는 옮기지 말고 쪼갠다.** 다른 노드로 옮기면 그 노드가 새 핫스팟이 될 뿐이다. 범위 분할·가상 노드 재배치로 부하 자체를 나눠야 한다.
- **이중 쓰기(dual write) 기간을 계획한다.** 재분배 도중 구/신 위치를 함께 참조하는 시점이 생기므로 정합성을 사전에 설계해야 한다.
- **자동 재분배는 신중히 도입한다.** 순간 스파이크에도 트리거될 수 있으므로 지속 시간 조건을 함께 건다.

## 3줄 요약

- 저장 용량을 맞추는 재분배와 트래픽 쏠림을 해소하는 핫스팟 완화는 서로 다른 문제다.
- 컨시스턴트 해싱·가상 노드·범위 분할은 재분배 이동량을 줄이는 방법이고, 핫샤드는 옮기기보다 쪼개는 쪽이 근본적이다.
- 한 샤드로 옮겨도 사라지지 않는 핫키 트래픽은 salting이나 캐싱 계층으로 별도로 다뤄야 한다.

## 참고 자료

- [Vitess Docs — Resharding](https://vitess.io/docs/user-guides/configuration-basic/sharding/)
- [Amazon DynamoDB — Adaptive Capacity와 핫 파티션 대응](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html)
- [Redis Cluster — Resharding 공식 문서](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/)
