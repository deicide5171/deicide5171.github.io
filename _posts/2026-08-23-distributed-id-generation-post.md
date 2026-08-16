---
layout: single
title: "시계가 1초만 뒤로 가도 ID가 겹친다 — Snowflake·ULID·UUIDv7 분산 ID 설계"
date: 2026-08-23 12:45:00 +0530
categories: system-design
tags: ["snowflake", "ulid", "uuidv7", "distributed-systems", "system-design"]
toc: true
toc_sticky: true
excerpt: "오토인크리먼트가 통하지 않는 분산 환경에서 유일하면서도 시간순 정렬이 되는 ID를 만드는 세 가지 방식 — Snowflake, ULID, UUIDv7 — 을 비교하고, 시계 역행과 정렬성 문제를 다루는 실전 설계를 정리한다."
---

서버 한 대, DB 한 대일 때 ID 발급은 고민거리가 아니다. `AUTO_INCREMENT`나 시퀀스가 알아서 유일하고 정렬된 번호를 내어준다. 문제는 쓰기를 받는 노드가 여러 개가 되는 순간 시작된다. 샤딩된 DB, 멀티 리전 쓰기, DB에 다녀오지 않고 애플리케이션에서 먼저 ID를 확정해야 하는 이벤트 파이프라인 — 이런 환경에서는 중앙 채번기가 단일 장애점이자 병목이 된다.

그렇다고 완전 랜덤인 UUIDv4를 기본키로 쓰면 다른 비용을 치른다. B-tree 인덱스는 정렬된 구조라, 랜덤한 키가 들어오면 삽입 위치가 트리 전체에 흩어지면서 페이지 분할과 버퍼 풀 캐시 미스가 늘어난다. 특히 기본키가 곧 클러스터드 인덱스인 MySQL InnoDB에서는 쓰기 성능 저하가 뚜렷하게 나타난다.

그래서 분산 ID 생성기의 요구사항은 세 가지로 정리된다. **조율 없이(coordination-free) 각 노드가 독립적으로 발급**할 것, **전역적으로 유일**할 것, 그리고 **대략 시간순으로 정렬(k-sorted)** 될 것. 이 글에서는 이 요구를 푸는 대표 방식인 Snowflake, ULID, UUIDv7을 비교하고, 셋 모두의 아킬레스건인 시계 역행 문제를 다룬다.

## Snowflake — 64비트에 시간·공간·순서를 담다

트위터가 공개한 Snowflake는 64비트 정수 하나에 세 가지 정보를 비트 단위로 욱여넣는다. 상위 41비트는 커스텀 에포크 기준 밀리초 타임스탬프(약 69년 분량), 가운데 10비트는 워커 ID(최대 1,024대), 하위 12비트는 같은 밀리초 안에서 증가하는 시퀀스(워커당 ms마다 4,096개)다. 타임스탬프가 최상위에 있으므로 정수 비교만으로 시간순 정렬이 되고, BIGINT 컬럼에 그대로 들어가 인덱스 효율도 좋다.

대신 Snowflake는 "워커 ID가 절대 겹치지 않는다"는 전제를 요구한다. 이 전제가 깨지면 같은 밀리초에 두 노드가 동일한 ID를 만들 수 있다. 워커 ID를 ZooKeeper나 etcd 같은 코디네이터로 임대(lease)받거나, Kubernetes StatefulSet의 순번(ordinal)을 쓰거나, 배포 시 환경변수로 고정 할당하는 운영 장치가 반드시 함께 설계되어야 한다.

## ULID과 UUIDv7 — 조율 없는 정렬 가능 ID

워커 ID 관리 자체가 부담이라면, 랜덤 비트를 넉넉히 써서 조율을 없애는 계열이 있다. **ULID**는 128비트를 48비트 밀리초 타임스탬프 + 80비트 랜덤으로 나누고, Crockford Base32로 26자 문자열로 인코딩한다. **UUIDv7**은 같은 아이디어를 UUID 규격 안에 담아 RFC 9562로 표준화한 것으로, 48비트 유닉스 밀리초 타임스탬프 뒤에 버전·배리언트 비트와 74비트 랜덤이 온다. 기존 UUID 타입 컬럼·라이브러리와 그대로 호환된다는 점이 가장 큰 실무적 장점이고, PostgreSQL 18부터는 `uuidv7()` 함수가 내장되어 DB 기본값으로도 쓸 수 있다.

<img src="/assets/images/posts/2026-08-23-distributed-id-generation-1.svg" alt="Snowflake, ULID, UUIDv7의 비트 레이아웃 비교 — 세 방식 모두 상위 비트에 타임스탬프를 두어 시간순 근사 정렬이 가능하다" style="width:100%;">

| 구분 | Snowflake | ULID | UUIDv7 |
|---|---|---|---|
| 크기 | 64비트 정수 | 128비트 (26자 문자열) | 128비트 (UUID 타입) |
| 정렬성 | ms + 시퀀스로 촘촘함 | ms 단위 (모노토닉 옵션) | ms 단위 (선택적 확장) |
| 노드 간 조율 | 워커 ID 할당 필요 | 불필요 | 불필요 |
| 충돌 위험 | 워커 ID 중복 시 발생 | 80비트 랜덤으로 사실상 없음 | 74비트 랜덤으로 사실상 없음 |
| 표준화 | 사실상 표준(구현체 다양) | 커뮤니티 스펙 | IETF RFC 9562 |
| 저장 효율 | 가장 좋음(BIGINT) | 보통 | 보통(UUID 컬럼) |

선택 기준은 명확하다. **저장·인덱스 효율과 초고속 발급이 중요하고 워커 ID를 관리할 운영 역량이 있다면 Snowflake**, **표준 호환성과 무조율 운영이 우선이면 UUIDv7**, UUID 타입 제약 없이 URL에 넣기 좋은 문자열 ID가 필요하면 ULID가 어울린다. 반대로 단일 DB에 트래픽도 크지 않다면 그냥 시퀀스를 쓰는 편이 낫다 — 분산 ID는 공짜가 아니다.

## 시계 역행 — 정렬 가능한 ID의 아킬레스건

세 방식 모두 벽시계(wall clock)에 의존한다는 공통 약점이 있다. NTP가 어긋난 시계를 한 번에 되돌리는 스텝(step) 보정, VM 마이그레이션·서스펜드 후 복원 같은 상황에서 시계는 실제로 뒤로 간다. Snowflake에서 시계가 1초 역행하면, 이미 발급한 타임스탬프 구간을 다시 지나가며 **같은 (타임스탬프, 워커, 시퀀스) 조합이 재발급될 수 있다.** 랜덤 비트가 넉넉한 ULID·UUIDv7은 중복 확률은 무시할 수준이지만, 대신 정렬성이 깨진다.

그래서 Snowflake 구현체는 마지막 발급 타임스탬프를 기억했다가, 현재 시각이 그보다 과거면 **소폭 역행은 따라잡을 때까지 대기하고, 큰 역행은 발급을 거부**하는 방어 로직을 넣는다. 아래는 그 로직을 포함한 완결된 자바 구현이다.

```java
public class SnowflakeIdGenerator {

    private static final long EPOCH = 1704067200000L; // 2024-01-01T00:00:00Z
    private static final long WORKER_ID_BITS = 10L;
    private static final long SEQUENCE_BITS = 12L;
    private static final long MAX_WORKER_ID = (1L << WORKER_ID_BITS) - 1; // 1023
    private static final long SEQUENCE_MASK = (1L << SEQUENCE_BITS) - 1;  // 4095
    private static final long WORKER_ID_SHIFT = SEQUENCE_BITS;
    private static final long TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS;
    private static final long MAX_BACKWARD_MS = 5L; // 이내 역행은 대기로 흡수

    private final long workerId;
    private long lastTimestamp = -1L;
    private long sequence = 0L;

    public SnowflakeIdGenerator(long workerId) {
        if (workerId < 0 || workerId > MAX_WORKER_ID) {
            throw new IllegalArgumentException(
                "workerId는 0~" + MAX_WORKER_ID + " 범위여야 합니다: " + workerId);
        }
        this.workerId = workerId;
    }

    public synchronized long nextId() {
        long now = System.currentTimeMillis();

        if (now < lastTimestamp) {                    // 시계 역행 감지
            long backward = lastTimestamp - now;
            if (backward <= MAX_BACKWARD_MS) {
                now = waitUntil(lastTimestamp);       // 소폭: 따라잡을 때까지 대기
            } else {
                throw new IllegalStateException(      // 대폭: 발급 거부, 호출측 재시도
                    "시계 역행 " + backward + "ms — ID 발급 중단");
            }
        }

        if (now == lastTimestamp) {
            sequence = (sequence + 1) & SEQUENCE_MASK;
            if (sequence == 0) {                      // 같은 ms에서 4096개 소진
                now = waitUntil(lastTimestamp + 1);
            }
        } else {
            sequence = 0L;
        }

        lastTimestamp = now;
        return ((now - EPOCH) << TIMESTAMP_SHIFT)
                | (workerId << WORKER_ID_SHIFT)
                | sequence;
    }

    private long waitUntil(long target) {
        long now = System.currentTimeMillis();
        while (now < target) {
            now = System.currentTimeMillis();
        }
        return now;
    }
}
```

UUIDv7 쪽은 DB에 맡기는 것이 가장 간단하다.

```sql
-- PostgreSQL 18 이상: 시간순 정렬되는 UUID를 기본값으로
CREATE TABLE orders (
    id         uuid PRIMARY KEY DEFAULT uuidv7(),
    user_id    bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

한 가지 더 짚을 점: 노드 간 시계는 애초에 완벽히 맞지 않으므로, 이 계열 ID의 정렬성은 어디까지나 **근사 정렬(k-sorted)**이다. "ID 순서 = 이벤트의 엄밀한 발생 순서"를 요구하는 로직(예: ID 대소 비교로 인과 관계 판단)은 설계 자체가 잘못된 것이고, 그런 요구에는 단일 시퀀서나 논리적 시계(Lamport clock)가 필요하다.

## 실무 포인트

- **흔한 함정 — 컨테이너 환경에서 워커 ID를 랜덤 생성**: 재시작할 때마다 워커 ID를 무작위로 뽑는 구현이 의외로 많다. 1,024개 공간에서 수십 개 파드가 랜덤 선택을 반복하면 생일 역설로 중복 확률이 금방 올라가고, 중복된 두 파드는 조용히 같은 ID를 발급한다. StatefulSet 순번, 코디네이터 임대, 배포 파이프라인의 고정 할당 중 하나로 반드시 유일성을 보장해야 한다.
- **JS로 내려보낼 때는 문자열로**: 자바스크립트 `Number`는 53비트 정밀도라 64비트 Snowflake ID를 JSON 숫자로 내리면 하위 자릿수가 소리 없이 손실된다. API 응답에서는 항상 문자열로 직렬화한다.
- **ID에 담긴 정보 노출을 감안한다**: 타임스탬프 기반 ID는 생성 시각을, Snowflake는 워커 수까지 유추할 단서를 노출한다. 발급량 추정 같은 정보 노출이 민감한 도메인이라면 외부 공개용 불투명 ID를 따로 두는 설계를 검토한다.

## 3줄 요약

- 분산 환경의 ID는 조율 없이 발급되면서 유일하고 대략 시간순(k-sorted)이어야 하며, Snowflake(64비트·워커 ID 필요), ULID·UUIDv7(128비트·무조율)이 대표 답안이다.
- 저장 효율과 발급 속도가 우선이면 Snowflake, 표준 호환과 운영 단순함이 우선이면 UUIDv7이 무난한 기본값이다.
- 시계 역행은 중복·정렬 깨짐의 주범이므로, 소폭 역행은 대기하고 대폭 역행은 발급을 거부하는 방어 로직과 워커 ID 유일성 보장이 반드시 함께 가야 한다.

## 참고 자료

- [RFC 9562: Universally Unique IDentifiers (UUIDs)](https://www.rfc-editor.org/rfc/rfc9562)
- [ULID Specification (GitHub)](https://github.com/ulid/spec)
- [Twitter Snowflake (GitHub Archive)](https://github.com/twitter-archive/snowflake)
- [PostgreSQL 문서: UUID Functions](https://www.postgresql.org/docs/current/functions-uuid.html)
