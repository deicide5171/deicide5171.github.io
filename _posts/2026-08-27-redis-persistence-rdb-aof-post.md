---
layout: single
title: "레디스도 디스크에 씁니다 — RDB vs AOF 영속성 트레이드오프"
date: 2026-08-27 13:35:00 +0530
categories: database
tags: ["redis", "persistence", "rdb", "aof", "durability"]
toc: true
toc_sticky: true
excerpt: "Redis를 순수 캐시로만 쓰지 않고 세션 저장소나 큐로 쓴다면 재시작 시 데이터가 얼마나 살아남는지가 중요해진다. RDB와 AOF의 동작 방식과 선택 기준을 정리한다."
---

Redis를 순수 캐시로만 쓴다면 재시작 시 데이터가 날아가도 큰 문제가 안 될 수 있다(캐시 미스가 늘어날 뿐이니). 하지만 세션 저장소, 레이트 리밋 카운터, 간단한 큐로 쓴다면 이야기가 달라진다. 재시작·장애 시 데이터가 얼마나 살아남는지가 서비스 정합성에 직결된다. Redis는 이를 위해 두 가지 영속성 메커니즘을 제공한다. RDB(스냅샷)와 AOF(추가 전용 로그)다. 둘은 서로 다른 트레이드오프를 가지며, 함께 쓸 수도 있다.

## 핵심 개념 1: RDB — 특정 시점의 스냅샷

RDB(Redis Database)는 특정 시점의 전체 데이터셋을 이진 파일로 디스크에 저장하는 방식이다. `save 900 1`(900초 내 1개 이상 키 변경 시 저장) 같은 규칙이나 `BGSAVE` 명령으로 트리거된다. 저장 시 Redis는 `fork()`로 자식 프로세스를 만들고, 이 자식 프로세스가 부모의 메모리를 COW(Copy-on-Write)로 공유하며 스냅샷을 디스크에 쓴다. 부모 프로세스는 계속 요청을 처리하므로 스냅샷 저장 중에도 서비스 중단이 없다.

장점은 파일이 작고(압축된 이진 형식) 복구가 빠르다는 것이다. 단점은 마지막 스냅샷 이후의 변경사항은 장애 시 전부 유실된다는 점이다. `save 900 1`이라면 최악의 경우 15분치 데이터를 잃을 수 있다.

## 핵심 개념 2: AOF — 모든 쓰기 명령의 로그

AOF(Append Only File)는 Redis에 들어온 쓰기 명령을 순서대로 파일에 이어 붙이는(append) 방식이다. 재시작 시 이 로그를 처음부터 재생해 데이터를 복원한다. 핵심 설정은 `appendfsync`로, 언제 파일을 실제 디스크에 동기화할지를 결정한다.

| `appendfsync` 값 | 동작 | 데이터 손실 위험 | 성능 |
|---|---|---|---|
| `always` | 매 쓰기 명령마다 즉시 fsync | 사실상 없음 | 가장 느림 |
| `everysec` (기본값) | 1초마다 배치로 fsync | 최대 1초치 손실 | 손실과 성능의 균형 |
| `no` | OS에 맡김(커널이 알아서 flush) | 수 초~수십 초 손실 가능 | 가장 빠름 |

AOF 파일은 시간이 지나면 계속 커지므로(같은 키를 여러 번 갱신해도 명령이 계속 쌓임), Redis는 백그라운드에서 `BGREWRITEAOF`로 파일을 압축한다 — 현재 데이터셋을 재현하는 데 필요한 최소 명령 집합으로 다시 쓰는 것이다.

<img src="/assets/images/posts/2026-08-27-redis-persistence-rdb-aof-1.svg" alt="RDB는 특정 시점 전체 스냅샷을 저장하고 AOF는 모든 쓰기 명령을 순차 기록하며, 하이브리드 모드는 RDB 프리앰블 뒤에 AOF 증분 로그를 붙이는 구조 비교도" style="width:100%;">

## 예제: redis.conf 영속성 설정 (하이브리드 모드)

```conf
# redis.conf — RDB + AOF 하이브리드 영속성 설정

# RDB: 900초 내 1개, 300초 내 10개, 60초 내 10000개 키 변경 시 스냅샷
save 900 1
save 300 10
save 60 10000
dbfilename dump.rdb

# AOF 활성화 및 동기화 정책
appendonly yes
appendfsync everysec
appendfilename "appendonly.aof"

# Redis 4.0+ 하이브리드 방식: AOF 재작성 시 RDB 형식 프리앰블 사용
# (재시작 시 복구가 순수 AOF 재생보다 훨씬 빠름)
aof-use-rdb-preamble yes

# AOF 파일이 이 배율 이상 커지면 자동 재작성
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

`aof-use-rdb-preamble yes`는 AOF 재작성 시 파일 앞부분을 RDB 형식으로 압축해 넣고 그 뒤에 재작성 이후의 증분 명령만 AOF 형식으로 붙이는 하이브리드 방식이다. 순수 AOF 재생보다 복구가 훨씬 빠르면서도 재작성 이후의 손실 없는 로그는 유지한다.

## 실무 포인트

- **`fork()` 시 메모리 스파이크를 고려한다**: RDB 저장이나 AOF 재작성 모두 `fork()`를 쓰므로, 쓰기가 많은 인스턴스에서는 COW로 인해 순간적으로 메모리 사용량이 최대 2배 가까이 튈 수 있다. 메모리 여유가 빠듯한 인스턴스에서는 이 스파이크가 OOM을 유발할 수 있으므로 여유 메모리를 확보해야 한다.
- **RDB만으로는 부족한 워크로드를 먼저 식별한다**: 캐시 용도라면 RDB만으로 충분하고 오히려 AOF의 쓰기 오버헤드를 피하는 게 낫다. 세션·큐처럼 데이터 손실이 곧 사용자 경험 문제로 이어지는 워크로드는 AOF(`everysec` 이상)를 켜야 한다.
- **복제(replication)는 영속성을 대체하지 않는다**: 레플리카가 있어도 프라이머리가 디스크에 아무것도 안 쓴 상태로 죽으면 복제본에도 그 변경사항이 전파되지 않았을 수 있다. 영속성과 복제는 서로 다른 문제(디스크 내구성 vs 가용성)를 해결하는 별개의 메커니즘이므로 함께 설계해야 한다.

## 3줄 요약

- RDB는 특정 시점 전체 스냅샷이라 파일이 작고 복구가 빠르지만 마지막 스냅샷 이후 변경은 유실될 수 있다.
- AOF는 모든 쓰기 명령을 로그로 남겨 손실 창을 `appendfsync` 설정으로 좁힐 수 있지만 파일 크기와 쓰기 오버헤드가 더 크다.
- Redis 4.0+ 하이브리드 모드(RDB 프리앰블 + AOF 증분)로 두 방식의 장점을 조합하는 것이 실무 기본값에 가깝다.

## 참고 자료

- [Redis 공식 문서: Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis 공식 문서: appendfsync 설정](https://redis.io/docs/latest/operate/oss_and_stack/management/config-file/)
