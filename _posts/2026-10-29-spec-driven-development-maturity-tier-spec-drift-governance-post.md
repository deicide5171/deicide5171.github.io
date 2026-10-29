---
layout: single
title: "\"스펙만 써주면 에이전트가 코드는 다 짤게요\"라는 말의 함정 — Spec-Driven Development 성숙도 3단계와 Spec Drift 거버넌스"
date: 2026-10-29 12:40:00 +0530
categories: dev-strategy
tags: ["spec-driven-development", "spec-kit", "spec-drift", "거버넌스", "아키텍처의사결정"]
toc: true
toc_sticky: true
excerpt: "'스펙 먼저 쓰고 에이전트한테 시키자'는 도구 설치 문제가 아니라, 스펙을 어느 성숙도 단계로 운영할지 정하는 거버넌스 문제다. GitHub Spec Kit의 급성장과 Thoughtworks의 spec-first/spec-anchored/spec-as-source 구분을 기준으로 spec drift를 막는 설계를 정리했다."
---

## 왜 지금 이 판단이 필요한가

"우리 팀도 스펙 먼저 쓰고 에이전트한테 구현시키자. Spec Kit 깔면 되는 거 아니야?" 요즘 팀 리드에게서 자주 나오는 말이다. 그런데 이 말에는 숨은 전제가 하나 있다 — 스펙 문서를 만드는 일과 스펙을 *계속 맞는 상태로 유지하는* 일을 같은 문제로 취급한다는 것이다. 실제로는 전혀 다른 문제다. 도구를 설치해 스펙 한 장을 뽑아내는 것은 하루면 끝나지만, 그 스펙이 6개월 뒤에도 실제 코드를 설명하고 있을지는 전혀 다른 질문이다.

GitHub의 Spec Kit은 2026년 8월 21일 v1.0.0을, 9월 10일에는 v1.0.6을 내놓으며 스펙 주도 개발(SDD) 도구 중 가장 빠르게 퍼졌다. 그런데 Thoughtworks Technology Radar 2026은 엔지니어 Birgitta Böckeler의 3단계 구분을 인용하며 Spec Kit을 명확히 **spec-first** 단계로만 분류한다 — "시간이 지나도 spec-anchored는 아니다"라는 단서를 달아서다. 이 구분을 모르고 도구만 들이면, 몇 달 뒤 스펙 문서는 아무도 안 보는 장식품이 되고 실제 결정은 코드와 사람들의 기억 속에만 남는 "Spec Drift"가 조용히 시작된다.

## 세 가지 성숙도, 다른 신뢰 기준점

Böckeler의 구분은 "스펙이 산출물의 생애주기 어디까지 책임지는가"를 기준으로 나눈다. **spec-first**는 스펙을 일회성 뼈대로 쓴다 — 에이전트가 스펙을 읽고 코드를 생성하면, 그 이후부터는 사람이 코드를 직접 편집·소유하고 스펙은 다시 들여다보지 않는다. **spec-anchored**는 스펙이 시스템이 살아 있는 동안 계속 진실의 원천(source of truth)으로 남는다 — 코드가 바뀌면 스펙도 함께 갱신되고, 무엇이 왜 그렇게 만들어졌는지의 근거가 계속 추적 가능하다. **spec-as-source**는 스펙이 산출물로 직접 컴파일된다 — Tessl 같은 도구가 시도 중이지만 2026년 기준으로는 여전히 베타 수준이라 프로덕션에 걸기엔 이르다.

문제는 Spec Kit 같은 인기 도구가 spec-first만 자동으로 해주고, spec-anchored로 가는 길은 아무것도 대신해주지 않는다는 점이다. 업계에서는 이 간극을 "SpecFall"이라 부른다 — 스펙과 코드가 아무 경고 없이 조용히 어긋나는 현상이다. Thoughtworks는 여기에 더해 또 다른 함정도 지적한다. 에이전트가 스펙을 더 잘 지키게 하려고 프로젝트 지시문(instructions)을 계속 추가하다 보면 지시문 묶음 자체가 비대해지고, 오히려 에이전트의 성능이 저하되는 **컨텍스트 부패(context rot)**가 나타난다는 것이다.

## 세 단계 비교

<img src="/assets/images/posts/2026-10-29-spec-driven-development-maturity-tier-spec-drift-governance-1.svg" alt="spec-first, spec-anchored, spec-as-source 세 단계 구조 비교" style="width:100%;">

| 기준 | spec-first | spec-anchored | spec-as-source |
|---|---|---|---|
| 스펙의 생애주기 | 생성 시점에만 유효한 뼈대 | 시스템 생애 내내 진실의 원천 | 스펙이 곧 산출물 |
| 사후 동기화 장치 | 없음 — 자연 발산 | CI가 코드·스펙 diff를 지속 검증 | 컴파일 과정 자체가 동기화 |
| 필요 인프라 | 도구 설치만으로 충분 | 소유권·순서 메타데이터, diff 게이트 | 대부분 베타, 자체 구축 위험 큼 |
| 대표 도구 | GitHub Spec Kit | 사내 자체 구축(표준 도구 미성숙) | Tessl 등(2026년 기준 베타) |
| 적합한 조직 | 1인 또는 짧은 프로토타입 | 다인 팀 + 세션을 넘나드는 작업 | 아직 대부분 조직에 이름 |

전환점을 가르는 질문은 하나다 — "이 작업이 여러 사람, 여러 세션에 걸쳐 이어지고, 나중에 누군가 감사 가능한 인수인계 문서가 필요한가?" 답이 "그렇다"면 spec-first로는 이미 부족하다. 세션이 끊기고 작성자가 바뀌는 순간, 스펙이 최신 상태라는 보장이 없으면 다음 사람은 틀린 전제로 코드를 짜게 된다.

## 도입 순서와 막히는 지점

작은 팀, 짧은 프로토타입이라면 Spec Kit 같은 도구로 spec-first부터 시작하는 것이 합리적이다. 문제는 그다음이다 — 팀 인원이 늘고, 하나의 기능이 여러 에이전트 세션과 여러 날에 걸쳐 진행되기 시작하면, 스펙이 조용히 낡아가는 것을 막을 장치가 전혀 없다는 걸 깨닫는다. 이 시점에 spec-anchored로 전환해야 하는데, 업계에 보편적으로 쓸 수 있는 "spec-anchoring 도구"는 아직 없다. 직접 구축해야 한다 — CI 파이프라인에 코드 변경분과 스펙 문서를 비교하는 체크를 추가하고, 스펙 섹션마다 소유자와 최종 검증 시점을 메타데이터로 남긴다.

```yaml
# .github/workflows/spec-drift-check.yml (개념 예시)
- name: Spec vs Code Drift Check
  run: |
    # 변경된 코드 파일이 참조하는 스펙 섹션의 최종 수정일과
    # 코드 커밋 시각을 비교해, 스펙이 더 오래됐으면 리뷰를 블로킹한다.
    python3 scripts/check_spec_freshness.py \
      --spec-dir docs/specs \
      --max-staleness-days 14
```

가장 자주 막히는 지점은 두 가지다. 첫째, Spec Kit 같은 도구의 셸 실행 단계가 로컬 사용자 권한으로 그대로 돌기 때문에, 여러 팀이 같은 저장소에서 자동화를 돌리려면 자체 샌드박스·권한 레이어를 따로 얹어야 한다는 점이다. 둘째, 에이전트의 스펙 준수율을 높이려고 지시문을 무한정 누적하면 컨텍스트 부패로 오히려 성능이 떨어지므로, 지시문은 주기적으로 가지치기하고 정말 필요한 제약만 남겨야 한다. spec-as-source는 매력적으로 들리지만 2026년 기준 도구 생태계가 베타 단계이므로, 지금 전면 도입하기보다는 핵심이 아닌 작은 모듈에서 실험하는 정도로 접근하는 것이 안전하다.

## 정리

- "스펙 먼저 쓰자"는 도구 선택이 아니라 성숙도 선택이다 — Spec Kit 같은 인기 도구는 spec-first만 자동화해주고 그 이후는 책임지지 않는다.
- 다인 팀·여러 세션에 걸친 작업·감사 가능한 인수인계가 필요해지는 순간이 spec-anchored로 전환해야 하는 신호다.
- spec-anchoring을 지원하는 표준 도구는 아직 없으므로 CI 기반 drift 체크와 소유권 메타데이터를 직접 설계해야 하며, spec-as-source는 2026년 기준 아직 성급한 베팅이다.

## 참고 자료

- Thoughtworks Technology Radar, Vol. 33 (2026) — <https://www.thoughtworks.com/radar>
- GitHub, Spec Kit 저장소 릴리스 노트 — <https://github.com/github/spec-kit/releases>
- Birgitta Böckeler, "Spec-driven development" 관련 기고 — <https://martinfowler.com/articles/>
