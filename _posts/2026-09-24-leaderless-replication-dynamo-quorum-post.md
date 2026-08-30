---
layout: single
title: "리더 없는 복제(Leaderless Replication) — Dynamo 스타일 Quorum 합의 설계"
date: 2026-09-24 12:45:00 +0530
categories: system-design
tags: ["Dynamo", "Quorum", "리더리스복제", "분산시스템", "결과적일관성"]
toc: true
toc_sticky: true
excerpt: "리더 노드 장애가 곧 쓰기 불가로 이어지는 리더-팔로워 복제의 구조적 약점을, 어떤 노드로든 읽고 쓸 수 있게 하면서도 Read/Write Quorum 수식으로 일관성을 지키는 Dynamo 스타일 리더리스 복제로 정리했다."
---

## 왜 지금 리더리스 복제를 다시 봐야 하는가

전통적인 리더-팔로워(마스터-슬레이브) 복제는 모든 쓰기가 리더 한 곳으로 몰린다는 근본적인 제약을 갖는다. 리더가 죽으면 새 리더를 선출하기까지 그 짧은 시간 동안 시스템은 쓰기를 받을 수 없고, 리더 선출 로직 자체도 스플릿 브레인 같은 별도의 복잡성을 안고 있다. Amazon의 Dynamo 논문에서 대중화된 리더리스(leaderless) 복제 모델은 이 문제를 "애초에 리더라는 특별한 역할을 두지 않는다"는 방식으로 우회한다. 클라이언트는 여러 복제본 중 아무 노드에나 읽고 쓸 수 있으며, 그 대신 "몇 개의 복제본에 쓰기·읽기가 성공해야 그 결과를 신뢰할 것인가"를 수치로 정의하는 Quorum 메커니즘으로 일관성을 관리한다. Cassandra, Riak, DynamoDB 같은 시스템이 이 모델을 채택하고 있다.

## 핵심 개념 1 — N, W, R: 복제본 수와 성공 기준을 숫자로 표현하기

리더리스 복제 시스템은 보통 세 개의 숫자로 동작을 정의한다. N은 데이터가 복제되는 노드의 총 개수, W는 쓰기가 성공한 것으로 간주하기 위해 응답을 받아야 하는 최소 노드 수, R은 읽기가 성공한 것으로 간주하기 위해 응답을 받아야 하는 최소 노드 수다. 클라이언트는 쓰기 요청을 N개 노드 모두에 보내지만, 그중 W개로부터만 성공 응답을 받으면 쓰기가 완료됐다고 판단한다. 마찬가지로 읽기는 N개 중 R개의 응답을 모아 그중 가장 최신 버전(보통 타임스탬프나 버전 벡터 기준)을 클라이언트에 반환한다.

## 핵심 개념 2 — W + R > N 이면 최소 하나는 최신 값을 포함한다

Quorum 설계의 핵심 수학적 보장은 `W + R > N`을 만족시키면, 어떤 쓰기와 어떤 읽기를 골라도 두 집합(쓰기가 성공한 노드 집합과 읽기가 응답한 노드 집합)이 최소 하나의 노드에서 겹친다는 것이다. 이 겹치는 노드는 반드시 최신 쓰기를 반영하고 있으므로, 읽기 응답들 중에는 항상 최신 값이 하나는 포함돼 있다는 것이 보장된다. 예를 들어 N=3일 때 W=2, R=2로 설정하면 2+2=4 > 3이 성립해 이 보장을 얻을 수 있다. 반대로 이 부등식을 만족하지 않는 조합(예: W=1, R=1)을 쓰면 성능은 더 좋아지지만 최신 값을 놓칠 가능성이 생기는 결과적 일관성(eventual consistency) 쪽으로 더 기울게 된다.

| 설정 | 쓰기 지연 | 읽기 지연 | 일관성 보장 |
|---|---|---|---|
| N=3, W=3, R=1 | 높음(모든 복제본 대기) | 낮음 | 강함(모든 읽기가 최신) |
| N=3, W=2, R=2 | 중간 | 중간 | Quorum 보장(W+R>N) |
| N=3, W=1, R=1 | 낮음 | 낮음 | 약함(최신 값을 놓칠 수 있음) |

## 예제 — Quorum 읽기에서 최신 버전 선택하기 (의사코드)

```python
def quorum_read(key, N, R):
    responses = []
    for node in select_replica_nodes(key, N):
        try:
            responses.append(node.get(key))  # {value, version_vector}
        except Timeout:
            continue
        if len(responses) >= R:
            break

    if len(responses) < R:
        raise QuorumNotReachedException()

    # 버전 벡터를 비교해 가장 최신인 값(들)을 선택
    # 동시 쓰기로 인한 충돌(conflicting versions)이 있다면 애플리케이션이 병합해야 함
    return resolve_latest(responses)
```

`resolve_latest`가 단순 타임스탬프 비교라면 Last-Write-Wins 방식이고, 버전 벡터로 인과관계를 추적한다면 진짜 동시 쓰기 충돌을 감지해 애플리케이션이나 CRDT 병합 로직에 넘길 수 있다.

## 실무 포인트

- **W, R 값은 도메인의 읽기/쓰기 비율과 지연시간 요구사항에 맞춰 조정하라.** 쓰기가 드물고 읽기가 많은 서비스라면 W를 높이고 R을 낮춰 읽기 지연을 최소화하는 것이 유리하고, 반대의 경우 R을 높이는 것이 유리하다.
- **Quorum이 강한 일관성을 완전히 대체하지 못한다는 점을 이해하라.** W+R>N은 "최신 값이 응답 후보에 포함된다"는 것만 보장할 뿐, 클라이언트가 그 최신 값을 정확히 골라내는 병합 로직까지 자동으로 해결해주지는 않는다.
- **일시적으로 노드가 다운됐을 때의 동작(Sloppy Quorum, Hinted Handoff)을 함께 설계하라.** 원래 담당 노드가 잠시 응답하지 않을 때 다른 노드가 대신 쓰기를 받아뒀다가 나중에 전달하는 방식까지 고려해야 실제 가용성이 이론적 수치만큼 나온다.

## 마무리 요약

- 리더리스 복제는 특정 리더 노드에 쓰기가 집중되는 구조적 약점을 없애고, 클라이언트가 임의의 복제본에 읽고 쓸 수 있게 한다.
- N, W, R 세 숫자로 쓰기·읽기 성공 기준을 정의하며, W+R>N을 만족하면 읽기 응답 집합에 항상 최신 값이 하나는 포함된다는 수학적 보장을 얻는다.
- Quorum은 최신 값의 존재를 보장할 뿐 자동으로 골라주지는 않으므로, 버전 벡터 기반 충돌 해결과 Sloppy Quorum 같은 장애 대응 메커니즘을 함께 설계해야 한다.

## 참고 자료

- [Amazon - Dynamo: Amazon's Highly Available Key-value Store (논문)](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)
- [Apache Cassandra - Consistency](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html)
