---
layout: single
title: "쓰고 나서 바로 읽었는데 없다 — 복제 지연 모니터링과 해소 전략"
date: 2026-08-26 12:35:00 +0530
categories: database
tags: ["database", "replication", "replication-lag", "postgresql", "mysql", "monitoring"]
toc: true
toc_sticky: true
excerpt: "쓰기는 프라이머리로, 읽기는 레플리카로 분산했더니 방금 쓴 데이터가 안 보인다는 버그가 발생한다. 복제 지연이 왜 생기고, 무엇을 측정하고, 어떻게 완화하는지 정리한다."
---

읽기 트래픽을 레플리카로 분산하는 구성은 DB 확장의 가장 흔한 첫걸음이다. 그런데 이 구성을 넣자마자 나오는 버그 리포트가 있다. "방금 저장한 글이 목록에 안 보여요"라거나 "결제 상태를 업데이트했는데 다음 화면에서 예전 값이 뜬다"는 식이다. 원인은 대부분 같다. 쓰기는 프라이머리에 즉시 반영되지만, 레플리카에는 복제 스트림을 통해 약간의 시간차를 두고 반영되기 때문이다. 이 시간차가 **복제 지연(replication lag)**이고, 읽기-쓰기 분리 아키텍처를 쓰는 이상 완전히 없앨 수는 없는 근본적인 트레이드오프다.

문제는 지연이 생긴다는 사실 자체가 아니라, 그 지연을 측정하지 않고 방치하는 것이다. 정상 상태에서 수 밀리초였던 지연이 트래픽 급증이나 긴 트랜잭션 하나 때문에 수십 초로 벌어지는 일이 실제로 일어나고, 이때 애플리케이션이 아무 대응도 하지 않으면 사용자에게 보이는 데이터 일관성이 예고 없이 깨진다. 이 글에서는 복제 지연이 어디서 발생하는지, 어떤 지표로 측정하는지, 애플리케이션 레벨에서 어떻게 완화하는지를 정리한다.

## 핵심 개념 1: 지연은 복제 파이프라인의 여러 단계에서 쌓인다

복제 지연은 하나의 원인이 아니라 파이프라인 여러 단계의 누적이다. PostgreSQL의 스트리밍 복제를 예로 들면, 프라이머리가 WAL을 생성하는 시점부터 레플리카가 그 WAL을 적용(replay)해 쿼리에 반영하는 시점까지 여러 구간을 거친다.

| 단계 | 무엇이 지연을 만드는가 |
|---|---|
| WAL 생성 | 대용량 트랜잭션·벌크 업데이트가 WAL을 한 번에 많이 만듦 |
| 네트워크 전송 | 레플리카가 지리적으로 멀거나 네트워크 대역폭이 부족함 |
| 레플리카 적용(replay) | 레플리카 I/O 부하, 단일 스레드 적용 병목(MySQL 구버전), 긴 쿼리로 인한 적용 대기 |
| 읽기 쿼리 라우팅 | 애플리케이션이 지연 상태를 모르고 무조건 레플리카로 읽기 요청을 보냄 |

MySQL은 레플리카가 릴레이 로그를 단일 스레드로 순차 적용하던 시절 이 병목이 특히 컸고, 지금은 멀티스레드 복제(병렬 적용)로 상당 부분 완화됐다. PostgreSQL은 스트리밍 복제 자체는 빠르지만, 레플리카에서 실행 중인 긴 읽기 쿼리가 `hot_standby_feedback` 설정에 따라 WAL 적용을 지연시킬 수 있다는 점이 특유의 함정이다.

## 핵심 개념 2: 지연은 "바이트 차이"가 아니라 "적용 시각 차이"로 봐야 한다

복제 지연을 측정할 때 흔한 실수는 프라이머리와 레플리카의 LSN(로그 위치) 차이만 보는 것이다. 이 값은 "얼마나 밀렸는지"의 근사치는 되지만, 실제로 사용자가 체감하는 지연은 "이 데이터가 언제 반영됐는가"라는 시간 개념이다. PostgreSQL은 `pg_stat_replication`에서 `write_lag`, `flush_lag`, `replay_lag`을 시간 단위로 직접 제공하고, MySQL은 `SHOW REPLICA STATUS`의 `Seconds_Behind_Source`(구 `Seconds_Behind_Master`)로 근사치를 제공한다.

```sql
-- PostgreSQL: 프라이머리에서 각 레플리카의 지연을 시간 단위로 확인
SELECT
  application_name,
  client_addr,
  write_lag,
  flush_lag,
  replay_lag
FROM pg_stat_replication;
```

`replay_lag`이 실제로 "이 레플리카에서 지금 이 시각에 쿼리를 날리면 그 결과가 몇 초 전 프라이머리 상태와 같은가"에 가장 가까운 지표다. 모니터링 대시보드에는 이 값을 시계열로 쌓고, 임계치(예: 5초)를 넘으면 알림을 울리는 것이 기본이다.

## 예제: 애플리케이션에서 지연을 감안한 읽기 라우팅

```python
def get_order_status(order_id, just_wrote=False):
    if just_wrote:
        # 방금 이 요청 자신이 쓴 데이터라면 read-your-writes 보장을 위해
        # 프라이머리로 직접 읽거나, 세션 내 LSN을 레플리카에 넘겨 대기시킨다
        return primary_db.query(
            "SELECT status FROM orders WHERE id = %s", [order_id]
        )

    replica = pick_replica_with_low_lag(max_lag_seconds=2)
    if replica is None:
        # 모든 레플리카가 임계치를 넘으면 안전하게 프라이머리로 폴백
        return primary_db.query(
            "SELECT status FROM orders WHERE id = %s", [order_id]
        )
    return replica.query(
        "SELECT status FROM orders WHERE id = %s", [order_id]
    )
```

`pick_replica_with_low_lag`은 모니터링에서 수집한 `replay_lag` 값을 기준으로 지연이 임계치 이내인 레플리카만 후보로 삼는다. 결제·주문 상태처럼 방금 쓴 값을 즉시 읽어야 하는 화면(read-your-writes 요구)에서는 애초에 레플리카로 보내지 않고 프라이머리로 강제 라우팅하는 것이 가장 단순하고 확실한 해법이다.

## 실무 포인트

- **모든 읽기를 레플리카로 보내지 않는다**: read-your-writes가 요구되는 화면(내가 방금 한 작업의 결과 확인)은 프라이머리 직접 읽기로 고정하고, 목록 조회처럼 몇 초 지연을 감내할 수 있는 화면만 레플리카로 보낸다. 이 구분을 애플리케이션 레벨에서 명시적으로 관리해야 한다.
- **지연 급증의 원인을 구분해서 대응한다**: 트래픽 급증으로 인한 지연은 레플리카를 늘리거나 스펙을 올려 완화하지만, 벌크 배치 작업 하나가 WAL을 한 번에 쏟아내서 생긴 지연은 배치 작업을 청크 단위로 나누거나 저트래픽 시간대로 옮기는 것이 더 근본적인 해법이다.
- **알림 임계치는 서비스 SLA에 맞춰 정한다**: "지연 0초"를 목표로 하면 알림 피로만 쌓인다. 실제로 문제가 되는 지연 수준(예: 5초 이상이 1분 넘게 지속)을 기준으로 알림을 설정하고, 그 이하의 지연은 정상 동작의 일부로 받아들이는 편이 운영상 지속 가능하다.

## 3줄 요약

- 복제 지연은 WAL 생성부터 레플리카 적용까지 파이프라인 여러 단계의 누적이며, 읽기-쓰기 분리 구조에서는 근본적으로 사라지지 않는다.
- LSN 바이트 차이가 아니라 `replay_lag` 같은 시간 단위 지표로 측정해야 사용자가 체감하는 지연과 일치한다.
- read-your-writes가 필요한 읽기는 프라이머리로 고정하고, 지연이 임계치를 넘은 레플리카는 라우팅에서 제외하는 것이 애플리케이션 레벨의 기본 대응이다.

## 참고 자료

- [PostgreSQL 공식 문서: Monitoring Replication](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-REPLICATION-VIEW)
- [MySQL 공식 문서: Replica Server Options and Variables](https://dev.mysql.com/doc/refman/8.4/en/replica-server-options-variables.html)
- [AWS: Amazon RDS 복제 지연 모니터링 가이드](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Monitoring.html)
