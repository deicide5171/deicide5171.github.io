# 데일리 기술 포스트 자동 생성 가이드

이 문서는 매일 자동으로 생성되는 기술 블로그 포스트의 **공식 스펙**이다.
자동화 에이전트(클라우드 루틴)는 이 파일이 저장소에 존재하면 아래 규칙을 최우선으로 따른다.
형식을 바꾸고 싶으면 이 파일만 수정하면 된다.

## 개요

- **실행 주기**: 매일 1회 (루틴 스케줄: UTC 06:30 = 한국시간 15:30 = 인도시간 12:00)
- **결과물**: 글 1편을 두 가지 형식으로 생성
  1. 깃헙 블로그용 마크다운 → `_posts/YYYY-MM-DD-<slug>-post.md`
  2. 네이버 블로그용 HTML → `_naver/YYYY-MM-DD-<slug>.html`
- **전달 방식**: `auto-post/YYYY-MM-DD` 브랜치에 커밋 후 master로 PR 생성
  - PR을 merge하면 깃헙 블로그(GitHub Pages)에 자동 게시된다
  - 네이버용 HTML은 `git pull` 후 브라우저로 열어 전체 복사 → 네이버 글쓰기에 붙여넣는다
- `_naver/`, `_docs/` 폴더는 언더스코어로 시작하므로 Jekyll 빌드에서 제외된다(블로그에 노출 안 됨)

## 주제 선정 규칙

4개 주제 축(필러)을 날짜 기준으로 순환한다.

| 인덱스 | 필러 | categories 값 |
|---|---|---|
| 0 | AI (모델, 에이전트, 활용법, 생태계) | `ai` |
| 1 | 아키텍처 및 시스템 설계 (분산 시스템, DB, 캐싱, MSA 등) | `system-design` |
| 2 | 핫한 IT 트렌드 (새 릴리스, 업계 이슈, 기술 뉴스 분석) | `it-trend` |
| 3 | 웹 개발 트렌드·핵심 개념 (프레임워크, 렌더링, 인증, 성능 등) | `web-dev` |

- **오늘의 필러** = `TZ=Asia/Seoul date +%j`(연중 일수) % 4
- 웹 검색이 가능하면 해당 필러의 최근 1~2주 이슈를 검색해 시의성 있는 주제를 고른다.
  검색이 불가능하면 실무에서 중요한 evergreen 개념을 다룬다.
- `_posts/`의 기존 파일명과 title을 확인해 **이미 다룬 주제는 피한다**.
- 확인되지 않은 수치·일정·소문은 단정적으로 쓰지 않는다.

## 형식 1: 깃헙 블로그용 마크다운

경로: `_posts/YYYY-MM-DD-<slug>-post.md` (slug는 짧은 영어 kebab-case)

```markdown
---
layout: single
title: "한국어 제목"
date: YYYY-MM-DD 12:00:00 +0900
categories: ai            # 필러에 해당하는 값 하나
tags: ["소문자", "핵심", "키워드", "3~6개"]
toc: true
toc_sticky: true
excerpt: "글 요약 한 문장"
---

본문...
```

본문 구조:

1. **도입** — 왜 지금 이 주제인가 (2~3문단)
2. **핵심 개념 설명** — `##` 섹션 2~4개, 표/비교 리스트 적극 활용
3. **코드 또는 설정 예제** — 언어 명시한 코드블록 1~2개
4. **실무 적용 포인트 / 주의사항**
5. **마무리 요약** — 3줄 이내 불릿
6. **참고 자료** — 공식 문서 위주 링크

분량: 한국어 기준 1,500~3,000자.

## 형식 2: 네이버 블로그용 HTML

경로: `_naver/YYYY-MM-DD-<slug>.html`

같은 주제를 네이버 독자용 문체(~습니다체, 조금 더 친근하게)로 다시 쓴 문서.
**마크다운 문법이 남아 있으면 안 된다.**

기술 규칙 (네이버 스마트에디터 붙여넣기 호환):

- 완전한 HTML 문서로 작성 (`<!DOCTYPE html>` + `<meta charset="utf-8">` 필수)
- `<body style="background-color:#ffffff; padding:20px;">` — 다크모드 브라우저에서도 동일하게 보이도록
- 본문 요소는 **전부 인라인 스타일만** 사용 — `<style>` 블록, class, script 금지
  (네이버 에디터에 붙여넣을 때 인라인 스타일만 살아남는다)
- 파일 맨 위에 HTML 주석으로 게시 방법 안내 (주석은 복사되지 않음)
- 구성 요소:
  - 제목: `<div style="font-size:26px; font-weight:bold;">` — 사용자가 제목칸으로 옮김
  - 요약 박스: 배경색 + 왼쪽 색 테두리(`border-left`)
  - 소제목: `font-size:21px` + `border-left:5px solid #03c75a`
  - 문단: `<p style="font-size:16px; line-height:1.8;">`, 3~4문장으로 짧게, 핵심 용어는 `<b>`
  - 코드: `<pre style="background-color:#f4f4f4; font-family:monospace; white-space:pre-wrap;">`
    (코드 안의 `<`, `>`는 `&lt;` `&gt;`로 이스케이프)
  - 표: `border-collapse:collapse` + 셀마다 `border:1px solid #ddd; padding:10px`
  - 섹션 사이 여백: `<p>&nbsp;</p>`
  - 마지막 줄: 해시태그 제안 (`#키워드` 나열, 네이버 태그칸에 옮겨 쓰는 용도)
- 외부 이미지·외부 리소스 사용 금지 (자체 완결 문서)

## 자동화 에이전트의 git 작업 규칙

1. `TODAY=$(TZ=Asia/Seoul date +%F)`
2. `git ls-remote origin "refs/heads/auto-post/${TODAY}"` 결과가 있으면 **아무것도 하지 않고 종료** (중복 실행 방지)
3. 브랜치 생성: `git checkout -b auto-post/${TODAY}`
4. 새로 만든 두 파일만 add → commit (메시지: `post: <제목> (auto)`)
5. `git push -u origin auto-post/${TODAY}`
6. master 대상 PR 생성 시도. 불가능하면 브랜치 push까지만 하고 보고
7. **금지**: master 직접 커밋/push, 기존 파일 수정·삭제, force push, `_config.yml` 변경

## 스케줄 변경 방법

루틴 관리: <https://claude.ai/code/routines>
Claude Code에서 "루틴 시간 바꿔줘"라고 요청해도 된다. (cron은 UTC 기준)
