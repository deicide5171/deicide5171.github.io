---
layout: single
title: "누가 대장을 할 것인가 — 분산 시스템 리더 선출 패턴 정리"
date: 2026-08-24 12:45:00 +0530
categories: system-design
tags: ["leader-election", "zookeeper", "etcd", "raft", "distributed-systems", "lease"]
toc: true
toc_sticky: true
excerpt: "분산 시스템에서 단 하나의 노드만 특정 작업을 수행하도록 보장하는 리더 선출의 원리를, ZooKeeper·etcd의 리스 기반 구현과 split-brain 방지 기법 중심으로 정리한다."
---

배치 스케줄러, 파티션 리밸런서, 단일 쓰기 노드를 요구하는 복제 시스템 — 분산 환경에서도 "이 작업은 딱 하나의 인스턴스만 해야 한다"는 요구는 끊임없이 등장한다. 인스턴스를 여러 대 띄워 가용성을 확보하면서도 동시에 정확히 하나만 활성 상태이길 바라는 이 모순적인 요구를 푸는 것이 리더 선출(leader election)이다.

문제는 "리더가 죽었는지"를 분산 환경에서 확실히 아는 방법이 없다는 데 있다. 네트워크 지연과 진짜 장애를 구분할 수 없기 때문에, 순진하게 하트비트만으로 리더를 교체하면 옛 리더가 살아있는데 새 리더도 선출되는 split-brain이 발생한다. 이 글에서는 ZooKeeper와 etcd가 이 문제를 어떻게 풀어왔는지, 그리고 리스(lease) 기반 패턴이 왜 사실상 표준이 됐는지 정리한다.

## 핵심 개념 1: 순수 하트비트의 한계와 리스 모델

가장 단순한 접근은 "일정 시간 하트비트가 없으면 죽은 것으로 간주하고 다음 노드가 리더가 된다"는 것이다. 그러나 네트워크가 일시적으로 끊긴 것뿐이라면, 원래 리더는 자신이 여전히 리더라고 믿은 채 계속 쓰기 작업을 수행하고, 동시에 새로 선출된 리더도 쓰기 작업을 수행하는 상황이 생긴다. 두 리더가 동시에 존재하는 split-brain이다.

이를 막는 표준 해법이 **리스(lease)**다. 리더는 "이 시각까지 내가 리더"라는 시간 제한이 있는 임대권을 조정 서비스로부터 발급받고, 만료 전에 갱신하지 못하면 자동으로 리더 자격을 잃는다. 여기서 중요한 것은 시계 동기화 오차와 GC 정지(stop-the-world) 같은 지연 요소까지 감안한 TTL 설계다. TTL이 너무 짧으면 정상 노드도 일시적 지연으로 리더를 잃고, 너무 길면 실제 장애 감지가 늦어진다.

## 핵심 개념 2: 펜싱 토큰 — 리스만으로는 부족하다

리스가 만료됐다고 옛 리더가 즉시 활동을 멈추는 것은 아니다. GC 정지나 스케줄링 지연으로 "리스가 만료된 줄 모르는 좀비 리더"가 뒤늦게 쓰기 요청을 보낼 수 있다. 이를 막는 장치가 **펜싱 토큰(fencing token)**이다. 조정 서비스는 리더가 바뀔 때마다 단조 증가하는 토큰(예: ZooKeeper의 znode 버전, etcd의 revision)을 발급하고, 실제 자원(스토리지, DB)은 "더 작은 토큰의 쓰기 요청은 거부"하는 규칙을 강제한다. 리스만으로는 논리적 보장이고, 펜싱 토큰이 있어야 물리적으로 좀비 리더의 쓰기를 차단할 수 있다.

<img src="/assets/images/posts/2026-08-24-leader-election-patterns-1.svg" alt="리스 기반 리더 선출 흐름도 — 세 노드와 조정 서비스, 리스 TTL 만료 시 펜싱 토큰과 함께 새 리더가 선출되는 과정" style="width:100%;">

## 핵심 개념 3: ZooKeeper vs etcd 구현 비교

| 구분 | ZooKeeper | etcd |
|---|---|---|
| 합의 알고리즘 | ZAB | Raft |
| 선출 메커니즘 | 임시 순차 znode 중 최소 번호가 리더 | Lease + campaign API |
| 세션/리스 갱신 | 클라이언트 세션 타임아웃 | Lease TTL, keepalive 스트림 |
| 펜싱 토큰 | znode 버전(zxid) | revision 번호 |
| 대표 라이브러리 | Curator LeaderLatch/LeaderSelector | etcd clientv3 concurrency.Election |

Kubernetes 자체도 컨트롤러 매니저·스케줄러의 다중 인스턴스 중 하나만 활성화하기 위해 `client-go`의 leaderelection 패키지로 이 패턴을 그대로 쓴다. Endpoints 또는 Lease 오브젝트에 리더 정보와 갱신 시각을 기록하는 방식이다.

## 예제: etcd concurrency 패키지로 리더 선출 (Go)

```go
package main

import (
	"context"
	"log"

	clientv3 "go.etcd.io/etcd/client/v3"
	"go.etcd.io/etcd/client/v3/concurrency"
)

func main() {
	cli, _ := clientv3.New(clientv3.Config{Endpoints: []string{"localhost:2379"}})
	defer cli.Close()

	// 세션 TTL 10초 — 이 시간 내에 keepalive가 안 오면 리스 만료
	session, _ := concurrency.NewSession(cli, concurrency.WithTTL(10))
	defer session.Close()

	election := concurrency.NewElection(session, "/services/order-scheduler/")

	ctx := context.Background()
	if err := election.Campaign(ctx, "node-a"); err != nil {
		log.Fatal(err)
	}
	log.Println("리더로 선출됨:", session.Lease())

	// 리더인 동안에만 수행할 작업
	// session이 만료되거나 Resign()이 호출되면 리더십 상실
}
```

## 실무 포인트

- **리스 TTL은 네트워크 지연 분포를 보고 정한다**: p99 왕복 지연과 GC 정지 시간을 감안하지 않고 TTL을 짧게 잡으면, 정상 노드가 순간적인 지연만으로 리더를 잃고 재선출이 반복되는 진동(flapping) 현상이 생긴다.
- **애플리케이션 계층에서 펜싱을 강제해야 한다**: 조정 서비스가 토큰을 발급해도, 실제 쓰기 대상(DB, 스토리지)이 토큰을 검증하지 않으면 무용지물이다. "리더가 됐다"와 "안전하게 쓸 수 있다"는 별개의 보장임을 코드로 명시해야 한다.
- **Redis 기반 락(Redlock류)을 리더 선출 대용으로 쓸 때는 신중해야 한다**: 순수 락과 합의 기반 리스는 안전성 모델이 다르다. 강한 일관성이 필요한 리더 선출에는 합의 프로토콜(ZAB/Raft) 기반 조정 서비스를 쓰는 것이 안전한 기본값이다.

## 3줄 요약

- 분산 리더 선출의 핵심 난제는 네트워크 지연과 진짜 장애를 구분할 수 없다는 것이며, 이를 리스(lease)의 TTL로 관리한다.
- 리스 만료만으로는 좀비 리더의 지연된 쓰기를 막을 수 없어, 단조 증가하는 펜싱 토큰으로 실제 자원 쪽에서 오래된 리더의 요청을 거부해야 한다.
- ZooKeeper는 ZAB와 임시 순차 znode, etcd는 Raft와 Lease API로 같은 문제를 풀며, Kubernetes 컨트롤러도 동일한 패턴을 그대로 사용한다.

## 참고 자료

- [etcd 공식 문서: Distributed Locks and Leader Election](https://etcd.io/docs/latest/dev-guide/api_concurrency_reference_v3/)
- [Apache Curator 공식 문서: Leader Election Recipes](https://curator.apache.org/curator-recipes/leader-election.html)
- [Kubernetes client-go leaderelection 패키지](https://pkg.go.dev/k8s.io/client-go/tools/leaderelection)
- [Martin Kleppmann: How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
