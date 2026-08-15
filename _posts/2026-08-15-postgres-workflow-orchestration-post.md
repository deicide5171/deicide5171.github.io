---
layout: single
title: "Postgres 하나로 워크플로우를 오케스트레이션한다는 것"
date: 2026-08-15 14:40:00 +0530
categories: system-design
tags: ["postgresql", "워크플로우", "오케스트레이션", "분산시스템", "dbos"]
toc: true
toc_sticky: true
excerpt: "별도 오케스트레이션 미들웨어 없이 PostgreSQL 트랜잭션으로 워크플로우 상태·재시도·복구를 처리하는 접근을 정리한다."
---

## 왜 지금 이 이야기가 나오는가

Airflow, Temporal, Step Functions 같은 워크플로우 오케스트레이터는 여러 서비스를 넘나드는 장기 실행 작업을 안정적으로 관리하기 위해 등장했다. 그런데 이런 시스템은 그 자체로 또 하나의 분산 시스템이다. 오케스트레이터의 상태 저장소, 스케줄러, 워커 큐가 각자 장애 지점이 되고, "오케스트레이터는 살아있는데 실제 작업 상태를 못 믿겠다"는 상황도 드물지 않다.

2026년 QCon SF를 비롯한 여러 발표에서 DBOS 등이 제시한 흐름은 이 문제를 다른 각도로 접근한다. 워크플로우의 단계와 상태를 별도 시스템이 아니라 이미 신뢰하고 있는 PostgreSQL 트랜잭션 위에 얹는 방식이다. 워크플로우 실행 이력, 재시도 카운터, 체크포인트를 애플리케이션이 이미 쓰고 있는 DB 테이블에 기록하면, 오케스트레이터 자체의 정합성을 걱정할 일이 줄어든다는 주장이다.

이 흐름이 흥미로운 이유는 "새 도구를 배포하지 않고 기존 인프라의 신뢰성을 재사용한다"는 발상 때문이다. 다만 모든 워크플로우에 맞는 만능 해법은 아니며, 언제 이 접근이 유효하고 언제 여전히 전용 오케스트레이터가 나은지 구분하는 것이 실무에서는 더 중요하다.

## 핵심 개념: DB 트랜잭션이 오케스트레이션 레이어가 되는 방식

전통적인 오케스트레이터는 워크플로우 정의, 실행 상태, 재시도 로직을 별도 컨트롤 플레인이 관리한다. 반면 이 접근에서는 각 워크플로우 단계를 하나의 DB 트랜잭션(또는 트랜잭션 묶음)으로 표현하고, 단계 실행 결과와 다음 단계로의 전이를 같은 테이블에 원자적으로 기록한다. 프로세스가 죽더라도 마지막으로 커밋된 상태를 DB에서 그대로 읽어와 재개할 수 있다는 것이 핵심이다.

| 구분 | 별도 오케스트레이터(Airflow류) | Postgres 기반 접근 |
|---|---|---|
| 상태 저장 위치 | 오케스트레이터 전용 메타데이터 DB | 애플리케이션이 이미 쓰는 Postgres |
| 장애 지점 | 오케스트레이터 자체가 추가 장애 지점 | 기존 DB 신뢰성에 편승 |
| 재시도·멱등성 | 오케스트레이터 프레임워크가 제공 | 트랜잭션 격리 수준·유니크 제약으로 직접 구현 |
| 가시성(모니터링 UI) | 대체로 풍부한 대시보드 제공 | SQL 쿼리·자체 구축 필요 |
| 운영 부담 | 오케스트레이터 클러스터 운영 필요 | 기존 DB 운영에 흡수 |
| 적합한 규모 | 수백~수천 개 태스크의 복잡한 DAG | 서비스 단위의 국소적 장기 트랜잭션 |

기존 오케스트레이터의 대표적 불만은 두 가지로 요약된다. 첫째, 실패 처리가 복잡하다. 재시도 정책, 데드레터 큐, 보상 트랜잭션을 오케스트레이터 DSL로 표현해야 하고, 이 DSL과 실제 비즈니스 로직 사이에 괴리가 생기기 쉽다. 둘째, 가시성 부족이다. "이 워크플로우가 지금 어느 단계에서 멈춰 있는가"를 알기 위해 오케스트레이터 UI와 애플리케이션 로그를 오가며 대조해야 하는 경우가 많다. Postgres 기반 접근은 상태가 애플리케이션과 같은 DB에 있으므로 SQL 한 줄로 현재 상태를 조회할 수 있다는 점을 장점으로 내세운다.

## 실무 예제: 워크플로우 단계를 테이블로 표현하기

아래는 개념을 단순화한 예시다. 실제 DBOS류 라이브러리는 이보다 정교한 멱등성 키, 함수 버전 관리 등을 제공하지만, 핵심 아이디어는 다음과 비슷하다.

```sql
CREATE TABLE workflow_step (
    workflow_id   UUID NOT NULL,
    step_name     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending', -- pending/running/done/failed
    attempt       INT NOT NULL DEFAULT 0,
    result        JSONB,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workflow_id, step_name)
);
```

```python
def run_step(conn, workflow_id, step_name, fn):
    with conn.transaction():
        row = conn.execute(
            "SELECT status, attempt FROM workflow_step "
            "WHERE workflow_id=%s AND step_name=%s FOR UPDATE",
            (workflow_id, step_name),
        ).fetchone()

        if row and row["status"] == "done":
            return row  # 이미 완료된 단계는 재실행하지 않음(멱등성)

        conn.execute(
            "UPDATE workflow_step SET status='running', attempt=attempt+1 "
            "WHERE workflow_id=%s AND step_name=%s",
            (workflow_id, step_name),
        )

        result = fn()  # 실제 비즈니스 로직 실행

        conn.execute(
            "UPDATE workflow_step SET status='done', result=%s "
            "WHERE workflow_id=%s AND step_name=%s",
            (result, workflow_id, step_name),
        )
```

핵심은 단계 실행과 상태 갱신이 같은 트랜잭션 경계 안에 있다는 것이다. 프로세스가 중간에 죽어도 `status`는 `running`으로 남고, 재기동 시 이 값을 보고 재시도 여부를 판단할 수 있다.

## 실무 포인트와 주의사항

이 접근이 잘 맞는 상황은 대체로 이렇다. 워크플로우가 이미 같은 Postgres를 쓰는 서비스 내부에 국한되고, 단계 수가 많지 않으며(수 개에서 수십 개 수준), 크론잡·백그라운드 작업 같은 국소적 장기 트랜잭션을 다룰 때다. 이럴 때는 별도 오케스트레이터를 붙이는 것보다 기존 DB 트랜잭션 보장을 재사용하는 편이 운영 부담을 줄여준다는 주장이 설득력이 있다.

반대로 여전히 전용 오케스트레이터가 유리한 경우도 있다. 수백 개 이상의 태스크가 얽힌 복잡한 DAG, 여러 조직·여러 DB에 걸친 워크플로우, 사람이 승인해야 하는 장기 대기 단계(며칠~몇 주), 풍부한 UI 기반 모니터링과 SLA 알림이 필요한 경우다. 또한 Postgres 트랜잭션 자체가 오래 걸리는 락을 유발하면 오히려 DB 전체의 처리량을 떨어뜨릴 수 있으므로, 트랜잭션 범위와 격리 수준 설계를 신중히 해야 한다. 확정적인 벤치마크 수치나 특정 버전의 로드맵은 아직 발표마다 다르게 언급되고 있어, 도입 전에는 각 라이브러리의 공식 문서와 최신 릴리스 노트를 직접 확인하는 것이 안전하다.

## 3줄 요약

- 워크플로우 상태·재시도·복구를 별도 오케스트레이터가 아니라 PostgreSQL 트랜잭션 위에서 관리하는 접근이 주목받고 있다.
- 기존 DB의 신뢰성을 재사용해 운영 부담과 장애 지점을 줄일 수 있지만, 가시성(모니터링 UI)은 직접 구축해야 하는 트레이드오프가 있다.
- 국소적이고 규모가 크지 않은 워크플로우에는 적합하지만, 대규모 DAG나 장기 대기·승인 단계가 있는 경우에는 여전히 전용 오케스트레이터가 낫다.

## 참고 자료

- [DBOS 공식 문서](https://docs.dbos.dev/)
- [PostgreSQL 공식 문서 - Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [QCon San Francisco](https://qconsf.com/)
- [Apache Airflow 공식 문서](https://airflow.apache.org/docs/)
