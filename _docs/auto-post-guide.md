# 데일리 기술 포스트 자동 생성 가이드 (v2 — 배치 모드)

이 문서는 자동 생성되는 기술 블로그 포스트의 **공식 스펙**이다.
자동화 에이전트(클라우드 루틴)는 이 파일이 저장소에 존재하면 아래 규칙을 최우선으로 따른다.
형식·규칙을 바꾸고 싶으면 이 파일만 수정하면 된다.

## 개요

- **하루 목표: 10편** (필러 5개 × 2라운드, 필러당 2편). 각 편은 두 가지 형식으로 생성한다.
  1. 깃헙 블로그용 마크다운 → `_posts/YYYY-MM-DD-<slug>-post.md`
  2. 네이버 블로그용 HTML → `_naver/YYYY-MM-DD-<slug>.html`
- **실행 스케줄** (로컬 = Asia/Kolkata 기준):
  - 평일(월~금): 저녁 21:00 (UTC 15:30) 자동 실행 — 업무 시간 사용량 보호
  - 주말: 자동 실행 없음 — 주간 토큰 리셋 전 남은 사용량은 사용자가 수동 실행으로 소진
    (Claude에게 "블로그 배치 실행해줘" 요청 또는 claude.ai/code/routines 에서 Run)
  - 검증: 매일 22:00 로컬에 PR 상태 확인 (로컬 예약 작업)
  - 주간 현황 리마인더: 일요일 19:00 로컬 (이번 주 생성 편수 + 잔여 사용량 확인 안내)
- **날짜 기준**: `TZ=Asia/Kolkata date +%F` — 파일명·브랜치·"오늘" 판정 모두 이 값 사용
  (평일 21시 실행이 한국시간으로는 자정을 넘기 때문에 KST를 쓰면 날짜가 밀린다. 반드시 Kolkata 기준.)
- **전달 방식**: 하루 1개 브랜치 `auto-post/YYYY-MM-DD` + master 대상 PR 1개에 모든 편 누적
- **사용량 거버너**: rate limit 등으로 더 진행할 수 없으면, 진행 중인 편까지 마무리·push하고 중단한다.
  우선순위 순서(아래 필러 순서)대로 만들기 때문에 중요한 것부터 남는다.
- `_naver/`, `_docs/` 폴더는 Jekyll 빌드에서 제외된다(블로그에 노출 안 됨)

## 필러 (하루 10편 = 아래 5개 필러를 2라운드, 이 순서대로 생성)

- **1라운드**: 필러 1→5 순서로 각 1편
- **2라운드**: 다시 필러 1→5 순서로 각 1편 (1라운드 및 기존 글과 **다른 주제**)
- 중간에 중단되더라도 라운드 순서 덕분에 모든 필러가 고르게 먼저 채워진다

| 순서 | 필러 | categories 값 | 내용 |
|---|---|---|---|
| 1 | AI | `ai` | 모델·에이전트·활용법·생태계 최신 이슈 |
| 2 | 아키텍처·시스템 설계 | `system-design` | 분산 시스템, DB, 캐싱, MSA, 확장성 패턴 |
| 3 | 웹 개발 최신 트렌드 | `web-dev` | JS, Java, Spring, React, Next.js, Vite 중 가장 뉴스가치 있는 것 (최근 3회와 다른 기술 선택) |
| 4 | GIS | `gis` | 지도 API, 공간 데이터, 좌표계, 타일링, 공간 DB(PostGIS), 위성영상 등 |
| 5 | 추천 지식 | `dev-insight` | 이 블로그의 기존 글(웹, Flutter, 네이버클라우드, GIS, AI)을 참고해 저자가 다음으로 배우면 좋을 지식을 추천 이유와 함께 정리 (예: 테스팅 전략, 네트워크 심화, DB 인덱스 내부, 보안, Docker/CI, 자료구조 심화) |

- 웹 검색이 가능하면 각 필러의 최근 1~2주 이슈로 시의성을 확보하고, 불가능하면 evergreen 핵심 개념을 다룬다.
- `_posts/`의 기존 파일명·title과 겹치는 주제는 피한다. 확인 안 된 수치·일정은 단정하지 않는다.

## 중복 방지 & 이어쓰기 (배치 재개)

1. `TODAY=$(TZ=Asia/Kolkata date +%F)`
2. `git fetch origin` 후 `refs/heads/auto-post/${TODAY}` 존재 확인
   - 있으면: 해당 브랜치를 checkout하고 **이어쓰기 모드** — `_posts/${TODAY}-*.md`들의 `categories`를 세어 필러별 현재 편수를 파악하고, **필러당 2편이 될 때까지 부족한 것만** 라운드 순서대로 생성
   - 없으면: master에서 새 브랜치 생성 (master에 이미 오늘 날짜 글이 있으면 그 편수도 포함해서 계산)
3. 모든 필러가 2편씩(총 10편) 있으면 "오늘 배치 완료됨"만 보고하고 종료

## 형식 1: 깃헙 블로그용 마크다운

경로: `_posts/YYYY-MM-DD-<slug>-post.md` (slug는 짧은 영어 kebab-case)

```markdown
---
layout: single
title: "한국어 제목"
date: YYYY-MM-DD HH:MM:00 +0530
categories: ai            # 필러 값 하나
tags: ["소문자", "핵심", "키워드", "3~6개"]
toc: true
toc_sticky: true
excerpt: "글 요약 한 문장"
---
```

- `date`의 시각: 1라운드는 12:50(ai) / 12:40(system-design) / 12:30(web-dev) / 12:20(gis) / 12:10(dev-insight), 2라운드는 같은 매핑에 +1시간(13:50/13:40/13:30/13:20/13:10) — 목록에서 최신 라운드의 AI가 맨 위에 오도록
- 본문 구조: 도입(왜 지금, 2~3문단) → 핵심 개념(## 섹션 2~4개, 표·비교 활용) → 코드/설정 예제 1~2개(언어 명시) → 실무 포인트/주의사항 → 마무리 요약(3줄 불릿) → 참고 자료(공식 문서 위주)
- 분량: 한국어 1,500~3,000자

## 형식 2: 네이버 블로그용 HTML

경로: `_naver/YYYY-MM-DD-<slug>.html` — 같은 주제를 네이버 독자용(~습니다체)으로 다시 쓴 문서. 마크다운 문법 금지.

- 완전한 HTML 문서: `<!DOCTYPE html>` + `<html lang="ko">` + `<meta charset="utf-8">` + `<title>`
- `<body style="background-color:#ffffff; padding:20px;">`
- 본문 요소는 **전부 인라인 스타일만** (`<style>` 블록·class·script 금지 — 네이버 에디터엔 인라인만 살아남음)
- 맨 위 HTML 주석으로 게시 방법 안내 (브라우저로 열기 → 전체선택·복사 → 네이버 글쓰기에 붙여넣기 → 제목은 제목칸, 해시태그는 태그칸으로)
- 구성: 제목 줄(26px bold) → 날짜·카테고리 메타(회색 14px) → 요약 박스(배경 #f0f7f4 + border-left 4px #03c75a) → 소제목(21px + border-left 5px #03c75a) → 문단(16px, line-height 1.8, 3~4문장, 핵심 `<b>`) → 코드 `<pre>`(배경 #f4f4f4, monospace, `<`·`>` 이스케이프) → 표(border-collapse + 셀 border) → 여백 `<p>&nbsp;</p>` → 주의 박스(배경 #fff7f0 + 주황 border-left) → 해시태그 줄(#03c75a)
- 외부 이미지·리소스 금지. 기존 `_naver/` 최신 파일과 스타일 일관성 유지.

## git 작업 규칙 (배치)

1. 브랜치: `auto-post/${TODAY}` (위 이어쓰기 규칙대로 checkout/생성)
2. **편 단위로 커밋·push**: 한 필러의 MD+HTML 페어를 완성할 때마다
   `git add <두 파일> && git commit -m "post: <제목> (auto)" && git push -u origin auto-post/${TODAY}`
   — 중간에 중단돼도 완성분은 남는다
3. 모든 작업 후 master 대상 PR 확인: 없으면 생성(제목 `daily posts: ${TODAY} (N편)`), 이미 있으면 push만으로 자동 반영됨
4. rate limit·오류로 중단 시: 마지막 완성 편까지 push됐는지 확인하고, 생성 편수/남은 필러를 보고
5. **금지**: master 직접 커밋/push, 기존 파일 수정·삭제, force push, `_config.yml` 변경
6. 완료 보고 후 가능하면 PushNotification으로 "N편 생성 완료 + PR 링크" 알림

## 스케줄 변경 방법

루틴 관리: <https://claude.ai/code/routines> (평일/주말 루틴 2개, cron은 UTC 기준)
배치 크기를 줄이려면 이 문서의 필러 표에서 줄을 빼면 된다.
