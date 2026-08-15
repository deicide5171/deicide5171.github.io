---
layout: single
title: "PR마다 AI가 먼저 본다 — CI 파이프라인에 LLM 코드 리뷰어 붙이기"
date: 2026-08-18 13:50:00 +0530
categories: ai
tags: ["ai코드리뷰", "ci-cd", "github-actions", "llm", "devops"]
toc: true
toc_sticky: true
excerpt: "사람 리뷰어가 보기 전에 LLM이 PR을 먼저 훑어 린트가 못 잡는 로직·보안 이슈를 잡아내도록, GitHub Actions에 AI 코드 리뷰 단계를 붙이는 파이프라인 설계와 운영 포인트를 정리한다."
---

## 왜 지금 AI 코드 리뷰 자동화인가

PR 개수가 늘어나면 리뷰어의 시간은 항상 병목이 된다. 오타·네이밍·포맷 같은 기계적인 지적에 리뷰 시간의 상당 부분이 쓰이고, 정작 로직 오류나 엣지 케이스 누락 같은 진짜 검토가 뒤로 밀리는 경우가 흔하다. 정적 분석·린터는 문법·스타일 문제는 잘 잡지만 "이 조건문이 의도한 비즈니스 규칙과 맞는가" 같은 의미론적 판단은 하지 못한다.

LLM 기반 코드 리뷰어를 CI 파이프라인에 넣으면 이 틈을 메울 수 있다. 사람 리뷰어가 PR을 열기 전에 AI가 먼저 diff를 읽고 잠재적 버그, 보안 이슈, 컨벤션 위반 후보를 코멘트로 남겨두면, 사람은 AI가 이미 걸러낸 지점부터 검토를 시작할 수 있다. 다만 이 파이프라인은 "AI가 최종 승인권을 갖는다"가 아니라 "사람 리뷰를 더 빠르게 만드는 전처리 단계"로 설계해야 한다는 점이 핵심이다.

<img src="/assets/images/posts/2026-08-18-ai-code-review-automation-1.svg" alt="PR 생성부터 병합까지 CI 파이프라인에 AI 코드 리뷰 단계를 끼워넣는 흐름도 - 린트, 테스트, AI 리뷰, 사람 리뷰, 병합 순서" style="width:100%;">

## 핵심 개념 1: 리뷰 자동화의 세 가지 통합 방식

AI 리뷰어를 CI에 붙이는 방법은 크게 세 가지로 나뉜다.

| 방식 | 동작 | 장점 | 한계 |
|---|---|---|---|
| 커밋된 GitHub Action(마켓플레이스) | PR 이벤트 트리거 시 서드파티 액션이 diff를 LLM API로 전송 | 설정이 가장 빠름 | 프롬프트·모델 커스터마이징 제한적 |
| 자체 스크립트 + LLM API 직접 호출 | 워크플로에서 diff 추출 → 프롬프트 구성 → API 호출 → PR 코멘트 등록 | 프롬프트·리뷰 기준을 팀 컨벤션에 맞게 세밀 조정 | 유지보수 비용, 토큰 사용량 직접 관리 필요 |
| 리뷰 봇 SaaS 연동 | 외부 서비스가 저장소 웹훅을 구독해 리뷰 수행 | 대시보드·이력 관리 제공 | 코드가 외부로 전송되는 데이터 흐름을 조직 정책과 맞춰야 함 |

셋 중 어떤 방식이든 공통으로 고려할 것은 "diff 전체를 매번 LLM에 보낼 것인가, 변경된 파일 단위로 보낼 것인가"다. 큰 PR은 컨텍스트 윈도우와 토큰 비용 문제로 파일 단위 분할 요청이 현실적인 경우가 많다.

## 핵심 개념 2: 리뷰 단계를 어디에 배치할 것인가

AI 리뷰는 기존 CI 단계와 순서가 겹치지 않게 배치하는 것이 중요하다.

| 단계 | 역할 | AI 리뷰와의 관계 |
|---|---|---|
| 린트/포맷 검사 | 스타일 규칙 자동 강제 | AI 리뷰보다 먼저 실행 — 기계적 이슈는 여기서 이미 걸러짐 |
| 단위/통합 테스트 | 동작 정합성 검증 | AI 리뷰와 병렬 실행 가능(서로 독립적) |
| AI 코드 리뷰 | 로직·보안·컨벤션 관점 코멘트 생성 | 테스트 실패 여부와 무관하게 실행해 코멘트는 남기되, 병합 차단(merge block)은 별도 정책으로 결정 |
| 사람 리뷰 | 최종 승인 | AI 코멘트를 참고하되 최종 판단은 사람이 유지 |

AI 리뷰 단계를 병합 차단 조건으로 걸지, 코멘트만 남기고 통과시킬지는 팀의 신뢰 수준에 따라 점진적으로 올려가는 편이 안전하다.

## 예제: GitHub Actions에 AI 리뷰 단계 추가하기

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get PR diff
        id: diff
        run: |
          git diff origin/${{ github.base_ref }}...HEAD > pr.diff
          echo "diff_lines=$(wc -l < pr.diff)" >> "$GITHUB_OUTPUT"

      - name: Run LLM review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python scripts/ai_review.py \
            --diff-file pr.diff \
            --output review_comments.json

      - name: Post review as PR comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const comments = JSON.parse(fs.readFileSync('review_comments.json', 'utf8'));
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: comments.summary,
            });
```

`scripts/ai_review.py`는 diff를 프롬프트에 넣어 LLM API를 호출하고, 응답을 구조화된 코멘트(파일·라인·이슈 종류)로 변환하는 역할을 한다. 프롬프트에는 "이 저장소의 코딩 컨벤션", "보안 체크리스트(입력 검증, 시크릿 하드코딩 여부)" 같은 팀 고유 기준을 명시적으로 포함시켜야 범용적인 잔소리가 아니라 저장소 맥락에 맞는 리뷰가 나온다.

## 실무 포인트

- **오탐(false positive) 허용 기준을 먼저 정한다.** AI 리뷰는 사람보다 보수적으로 지적하는 경향이 있어, 코멘트가 너무 많으면 오히려 무시당한다. 심각도(critical/warning/nit)를 구분해 표시하고, nit은 접어서 보여주는 식의 절제가 필요하다.
- **민감 코드가 외부 API로 나가는 경로를 점검한다.** 사설 저장소의 코드를 외부 LLM API로 보내는 것이 조직 보안 정책과 충돌하지 않는지 먼저 확인하고, 필요하면 온프레미스·VPC 내 모델 호출로 대안을 검토한다.
- **AI 리뷰 결과를 병합 차단 조건으로 걸 때는 단계적으로 도입한다.** 처음에는 코멘트만 남기고, 팀이 신뢰를 쌓은 뒤에 "critical 이슈 발견 시 병합 차단" 같은 강한 정책으로 옮겨가는 편이 반발이 적다.
- **리뷰 프롬프트와 체크리스트를 저장소에 버전 관리한다.** 프롬프트가 코드 리뷰 기준 자체이므로, 다른 코드처럼 PR로 리뷰하고 이력을 남기는 것이 바람직하다.

## 3줄 요약

- AI 코드 리뷰는 사람 리뷰를 대체하는 게 아니라, 기계적 이슈를 먼저 걸러 사람이 더 중요한 판단에 집중하게 하는 전처리 단계로 설계해야 한다.
- CI에서는 린트 → 테스트 → AI 리뷰 → 사람 리뷰 순서로 배치하고, AI 리뷰의 병합 차단 여부는 팀 신뢰 수준에 맞춰 점진적으로 강화한다.
- 오탐 허용 기준, 코드 외부 전송 보안 정책, 프롬프트 버전 관리를 먼저 정하지 않으면 AI 리뷰는 금방 무시되는 코멘트 더미가 된다.

## 참고 자료

- [GitHub Actions 공식 문서 — Events that trigger workflows](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows)
- [GitHub — actions/github-script](https://github.com/actions/github-script)
- [Anthropic — Claude Code GitHub Actions](https://docs.claude.com/en/docs/claude-code/github-actions)
