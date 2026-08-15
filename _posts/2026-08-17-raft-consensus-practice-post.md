---
layout: single
title: "장애가 나도 멈추지 않는 분산 시스템 — Raft 합의 알고리즘의 리더 선출과 로그 복제"
date: 2026-08-17 13:40:00 +0530
categories: infra
tags: ["raft", "consensus", "distributed-systems", "leader-election", "log-replication"]
toc: true
toc_sticky: true
excerpt: "etcd, Kafka KRaft, Consul 같은 핵심 인프라가 공통으로 쓰는 Raft 합의 알고리즘을, 리더 선출과 로그 복제라는 두 축으로 나눠 실전 관점에서 정리한다."
---

## 왜 지금 Raft인가

분산 시스템에서 "노드 하나가 죽어도 서비스가 멈추지 않아야 한다"는 요구는 당연해 보이지만, 그 이면에는 항상 같은 질문이 숨어 있다. 여러 노드가 서로 다른 상태를 가질 수 있는 상황에서, 어떻게 **하나의 정답**에 합의할 것인가. 이 문제를 이해 가능한 형태로 정리한 것이 Raft 합의 알고리즘이다.

Raft는 원래 난해하기로 유명한 Paxos의 대안으로 "이해 가능성(understandability)"을 설계 목표로 삼아 등장했고, 지금은 etcd, Kafka의 KRaft 모드, Consul, CockroachDB 등 핵심 인프라 컴포넌트의 합의 계층으로 널리 쓰인다. 쿠버네티스 클러스터를 운영하거나 서비스 디스커버리를 다루다 보면 결국 "etcd가 리더를 잃으면 무슨 일이 일어나는가"라는 질문과 마주치는데, 이 질문에 답하려면 Raft의 리더 선출과 로그 복제 메커니즘을 알아야 한다. 이 글은 실무에서 장애 상황을 해석하는 데 필요한 핵심 동작 원리에 집중한다.

## 핵심 개념 1: 노드의 세 가지 상태와 Term

Raft 클러스터의 모든 노드는 항상 셋 중 하나의 상태에 있다.

| 상태 | 역할 | 전환 조건 |
|---|---|---|
| Follower | 리더의 명령을 수동적으로 따름 | 초기 상태, 또는 더 높은 term을 발견하면 복귀 |
| Candidate | 선거에 나서 투표를 요청 | Follower가 election timeout 동안 리더 신호를 못 받으면 전환 |
| Leader | 클라이언트 요청을 처리하고 로그를 복제 | Candidate가 과반 득표에 성공하면 전환 |

여기서 **term(임기)**은 논리적 시계 역할을 하는 단조 증가 정수다. 모든 메시지에는 term이 실려 있고, 노드는 자신보다 높은 term을 보면 무조건 Follower로 돌아간다. 이 규칙 하나만으로 "구 리더가 살아 돌아와 새 리더와 충돌하는" 상황을 term 비교로 정리할 수 있다.

## 핵심 개념 2: 리더 선출 — 왜 무작위 타임아웃을 쓰는가

Follower는 각자 무작위화된 election timeout(예: 150~300ms 사이에서 노드마다 다르게 선택)을 갖는다. 이 타임아웃이 지나도록 리더의 하트비트를 못 받으면 스스로 Candidate로 전환해 term을 올리고, 자신에게 투표한 뒤 다른 노드들에 `RequestVote` RPC를 보낸다. 과반(quorum) 투표를 얻으면 Leader가 된다.

타임아웃을 무작위화하는 이유는 단순하다. 모든 노드가 같은 시점에 타임아웃되면 동시에 Candidate가 되어 표가 갈리는 **split vote**가 반복될 수 있다. 노드마다 타임아웃 값을 흩뿌리면, 한 노드가 먼저 선거를 시작해 다른 노드들이 투표할 시간을 벌어주는 확률이 높아진다.

## 핵심 개념 3: 로그 복제와 커밋

리더로 선출되면 클라이언트 요청은 오직 리더만 받는다. 리더는 요청을 자신의 로그에 엔트리로 추가하고, `AppendEntries` RPC로 모든 Follower에 복제를 요청한다. **과반 노드가 해당 엔트리를 자신의 로그에 기록했다고 응답하면**, 그 엔트리는 "커밋"된 것으로 간주되어 상태 머신에 적용된다.

| RPC | 트리거 | 핵심 역할 |
|---|---|---|
| RequestVote | election timeout 경과 | 후보가 과반 지지를 확보하는지 확인 |
| AppendEntries | 새 요청 발생 또는 하트비트 주기 | 로그 복제 및 리더 생존 신호(빈 엔트리도 하트비트로 사용) |

"과반 복제 = 커밋" 규칙 덕분에, 소수 노드가 죽거나 네트워크가 분할돼도 과반이 살아있는 쪽에서는 서비스가 계속된다. 반대로 과반을 확보 못한 소수파는 새 리더도 뽑지 못하고 쓰기도 커밋할 수 없다 — 이것이 Raft가 일관성을 지키는 핵심 트레이드오프다.

<img src="/assets/images/posts/2026-08-17-raft-consensus-practice-1.svg" alt="Raft 상태 전이도와 로그 복제 흐름 - Follower/Candidate/Leader 전환 및 AppendEntries를 통한 커밋 확정 과정" style="width:100%;">

## 예제: RequestVote / AppendEntries 처리 의사코드

```text
// Candidate가 되었을 때
function startElection(node):
    node.state = CANDIDATE
    node.currentTerm += 1
    node.votedFor = node.id
    votes = 1  // 자기 자신에게 투표

    for peer in otherNodes:
        reply = sendRequestVote(peer, node.currentTerm, node.lastLogIndex, node.lastLogTerm)
        if reply.term > node.currentTerm:
            node.state = FOLLOWER   // 더 높은 term 발견 시 즉시 물러남
            return
        if reply.voteGranted:
            votes += 1

    if votes > totalNodes / 2:
        node.state = LEADER
        sendHeartbeats(node)

// Leader가 로그 엔트리를 복제할 때
function replicateEntry(leader, entry):
    leader.log.append(entry)
    acked = 1
    for peer in followers:
        response = sendAppendEntries(peer, leader.currentTerm, entry)
        if response.success:
            acked += 1

    if acked > totalNodes / 2:
        commitIndex = entry.index   // 과반 확보 시 커밋
        applyToStateMachine(entry)
```

## 실무 포인트

- **election timeout 설정은 네트워크 지연을 감안한다.** 너무 짧으면 불필요한 재선출이 잦고, 너무 길면 실제 장애 복구가 느려진다. etcd 같은 구현체는 환경별 권장값을 문서로 안내하므로 임의로 숫자를 정하기보다 해당 구현체의 가이드를 따르는 편이 안전하다.
- **과반(quorum) 계산이 클러스터 크기 설계의 기준이 된다.** 5노드는 2노드가 죽어도 과반(3)을 유지하지만, 3노드는 1노드만 죽어도 마진이 사라진다. 짝수 노드는 과반 기준이 애매해지므로 홀수 개 구성이 일반적이다.
- **네트워크 분할 시 소수파는 쓰기를 멈춘다.** 이는 버그가 아니라 설계다. 클라이언트가 소수파에 붙어 있으면 타임아웃·에러를 받으므로, 클라이언트 측 리더 탐색·재시도 로직이 필요하다.
- **로그 압축(snapshot)도 함께 이해해야 한다.** 로그가 무한히 쌓이지 않도록 실제 구현체는 주기적으로 상태 머신 스냅샷을 찍고 오래된 로그를 정리한다.

## 3줄 요약

- Raft는 term이라는 논리적 시계와 Follower/Candidate/Leader 상태 전이로 리더 선출을 이해 가능한 형태로 단순화한다.
- 리더만 쓰기를 받아 로그에 기록하고, 과반 노드가 복제를 확인해야 커밋되는 구조 덕분에 소수 노드 장애에도 데이터 일관성이 유지된다.
- etcd·Kafka KRaft 등 실제 구현을 운영할 때는 election timeout·클러스터 크기(홀수 개수)·클라이언트 재시도 로직을 함께 설계해야 한다.

## 참고 자료

- [Raft 공식 사이트 — The Raft Consensus Algorithm](https://raft.github.io/)
- Diego Ongaro, John Ousterhout, "In Search of an Understandable Consensus Algorithm" (Raft 원 논문)
- [etcd — Raft 기반 합의 구현 문서](https://etcd.io/docs/latest/learning/)
