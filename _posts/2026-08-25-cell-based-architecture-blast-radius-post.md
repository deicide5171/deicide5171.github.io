---
layout: single
title: "장애를 겪어도 전 세계 사용자가 함께 죽지 않게 — 셀 기반 아키텍처로 폭발 반경 제한하기"
date: 2026-08-25 13:45:00 +0530
categories: system-design
tags: ["cell-based-architecture", "blast-radius", "resilience", "multi-tenancy", "system-design"]
toc: true
toc_sticky: true
excerpt: "리전 단위 이중화로도 막지 못하는 소프트웨어 결함·설정 실수의 전파를, 사용자 집합을 물리적으로 나눈 셀 단위로 격리해 장애 반경을 제한하는 셀 기반 아키텍처의 설계 원칙을 정리한다."
---

멀티 리전 액티브-액티브 구성을 잘 갖춰놓은 서비스도 특정 배포 이후 전체 사용자가 동시에 영향을 받는 장애를 겪는 경우가 있다. 리전 이중화는 하드웨어 장애나 데이터센터 단위 재해에는 강하지만, 잘못된 설정 값이나 소프트웨어 버그처럼 **모든 리전에 동일하게 배포된 결함**에는 무력하다. 배포가 잘못됐다면 그 배포를 받은 모든 리전이 동시에 영향을 받기 때문이다.

셀 기반 아키텍처(cell-based architecture)는 이 문제에 다른 각도로 접근한다. 리전을 늘리는 대신, 전체 사용자 기반을 여러 개의 독립적인 "셀"로 쪼개고, 각 셀은 다른 셀과 거의 완전히 격리된 인프라 스택(컴퓨트, 데이터베이스, 큐, 캐시)을 갖는다. 배포도 셀 단위로 순차 진행해서, 특정 셀에서 문제가 생겨도 그 셀에 속한 사용자만 영향을 받고 나머지 셀은 정상 동작한다. AWS가 자사 아키텍처 가이드에서 강조하는 핵심 개념 중 하나이기도 하다.

## 핵심 개념 1: 리전 이중화와 셀 분리는 서로 다른 축의 방어

리전 이중화는 "물리적 장소" 축의 장애를 방어한다 — 화재, 정전, 네트워크 단절처럼 한 데이터센터가 통째로 사라져도 다른 리전이 트래픽을 받는다. 반면 셀 분리는 "논리적 결함 전파" 축의 장애를 방어한다 — 배포 실수, 특정 사용자의 비정상 트래픽 패턴, 특정 큐의 포이즌 메시지처럼 물리적 위치와 무관하게 소프트웨어 자체에 내재된 문제가 전체로 번지는 것을 막는다.

두 축은 직교하므로 함께 적용할 수 있다. 각 리전 안에 여러 셀을 두는 구성이 일반적이며, 이 경우 리전 장애와 셀 장애가 각각 별도로 격리된다.

## 핵심 개념 2: 폭발 반경(blast radius)이라는 설계 목표

셀 기반 아키텍처의 핵심 설계 목표는 "폭발 반경(blast radius)을 미리 정한 크기로 상한을 둔다"는 것이다. 셀이 없는 시스템에서는 장애의 영향 범위가 원인에 따라 들쭉날쭉하다. 반면 N개의 셀로 균등하게 나눈 시스템에서는 최악의 경우에도 영향받는 사용자 비율이 이론상 1/N을 넘지 않는다는 상한을 미리 보장할 수 있다.

| 항목 | 셀 없는 단일 스택 | 셀 기반(N=10) |
|---|---|---|
| 배포 버그의 최대 영향 범위 | 전체 사용자 | 최대 10% |
| 장애 시 디버깅 대상 규모 | 전체 트래픽 로그 | 해당 셀 로그로 축소 |
| 신규 셀 추가 시 확장성 | 스택 전체 수직 확장 필요 | 셀 단위 수평 확장 |
| 운영 복잡도 | 낮음(스택 1개) | 높음(셀 수만큼 중복 운영) |

## 핵심 개념 3: 셀 경계를 어디에 그을 것인가

셀을 나누는 기준(파티션 키)은 서비스 특성에 따라 다르지만, 흔히 쓰는 기준은 다음과 같다.

- **사용자/테넌트 ID 해시**: 가장 일반적인 방식으로, 각 사용자를 결정론적으로 특정 셀에 배정한다. 신규 셀 추가 시 재배치(rebalancing) 전략이 필요하다.
- **지리적 그룹**: 국가·대륙 단위로 셀을 나누면 데이터 주권 규제 대응과 지연 시간 최적화도 함께 얻을 수 있다.
- **테넌트 등급**: 대형 고객을 전용 셀에 격리해, 한 대형 고객의 이상 트래픽이 다른 고객에게 전파되지 않게 한다.

중요한 것은 라우팅 계층(요청을 올바른 셀로 보내는 게이트웨이)이 셀 경계 밖에 있어야 한다는 점이다. 이 라우팅 계층 자체가 단일 장애점이 되지 않도록 가능한 한 단순하고, 상태가 없고(stateless), 그 자체로도 다중화돼 있어야 한다 — 라우팅 계층이 죽으면 셀 분리의 의미가 없어지기 때문이다.

## 예제: 셀 라우팅 게이트웨이의 기본 구조 (의사코드)

```python
# 셀 매핑 테이블: 셀 경계 밖의 경량 라우팅 계층에서 관리
# 배포 실수의 영향을 받지 않도록 이 테이블 자체는 별도 관리, 별도 배포 주기를 갖는다
CELL_MAP_VERSION = "v42"

def route_to_cell(tenant_id: str) -> str:
    cell_id = consistent_hash(tenant_id) % TOTAL_CELLS
    return f"cell-{cell_id}"

def handle_request(request):
    tenant_id = request.tenant_id
    cell = route_to_cell(tenant_id)

    # 각 셀은 완전히 독립된 엔드포인트, DB, 큐를 가진다
    cell_endpoint = CELL_ENDPOINTS[cell]
    return forward_request(cell_endpoint, request)

# 배포 시: 셀 단위 순차 배포(cell-1 -> 검증 -> cell-2 -> ...)
# 첫 셀에서 이상 지표 감지 시 나머지 셀 배포를 즉시 중단
def deploy_release(version: str):
    for cell in ALL_CELLS:
        deploy_to_cell(cell, version)
        if not health_check_passes(cell, wait_minutes=15):
            halt_remaining_deployment()
            raise DeploymentAborted(f"{cell} 배포 후 이상 감지")
```

## 실무 포인트

- **셀 단위 순차 배포가 셀 분리 효과의 핵심이다**: 셀로 인프라만 나누고 배포는 전체 셀에 동시에 밀어 넣으면 폭발 반경 제한 효과가 사라진다. 카나리 셀에서 충분히 검증한 뒤 나머지 셀로 단계적으로 넘어가는 배포 파이프라인이 반드시 함께 있어야 한다.
- **셀 간 데이터 공유는 최소화하고 명시적으로 설계한다**: 전역 사용자 검색, 전역 통계처럼 셀 경계를 넘나드는 기능이 있다면 그 데이터 흐름 자체가 셀 격리를 깨는 통로가 된다. 이런 기능은 별도의 집계 파이프라인으로 비동기 처리하고, 요청 경로 자체는 셀 경계를 넘지 않게 한다.
- **운영 복잡도 증가를 감안한다**: 셀 수만큼 모니터링 대시보드, 배포 파이프라인, 용량 계획이 늘어난다. 이 오버헤드를 감당할 만큼 장애 반경 제한의 이득이 큰 서비스(대규모 멀티테넌트 SaaS, 대량 트래픽 플랫폼)에 우선 적용하는 것이 현실적이다.

## 3줄 요약

- 리전 이중화는 물리적 장애를, 셀 분리는 소프트웨어 결함의 전파 범위를 방어하는 서로 다른 축의 대응이며 함께 적용할 수 있다.
- 셀 기반 아키텍처는 사용자 기반을 N개 셀로 나눠 최악의 경우에도 영향 범위를 1/N 이하로 상한을 두는 것이 핵심 목표다.
- 셀 단위 순차 배포와 셀 경계를 넘지 않는 요청 경로 설계가 없다면, 셀로 인프라만 나눠도 장애 반경 제한 효과는 얻을 수 없다.

## 참고 자료

- [AWS Well-Architected: Cell-based architecture](https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/what-is-a-cell-based-architecture.html)
- [AWS Builders' Library: Reducing the Scope of Impact with Cell-Based Architecture](https://aws.amazon.com/builders-library/)
- [Azure Architecture Center: Deployment Stamps pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/deployment-stamp)
