---
layout: single
title: "AI 코딩 도구 규칙 파일 관리하기 — Cursor·Windsurf·Copilot 커스텀 지침 비교"
date: 2026-09-21 12:50:00 +0530
categories: ai
tags: ["cursorrules", "ai코딩", "코딩어시스턴트", "프롬프트엔지니어링", "생산성"]
toc: true
toc_sticky: true
excerpt: "Cursor, Windsurf, GitHub Copilot 등 AI 코딩 도구마다 다른 규칙 파일 형식을 정리하고, 팀 단위로 일관된 지침을 유지하는 실전 방법을 설명한다."
---

## 왜 지금 "규칙 파일"이 중요해졌나

AI 코딩 어시스턴트를 팀 단위로 쓰기 시작하면 금방 같은 불만이 나온다. "왜 이 프로젝트에서는 자꾸 이런 스타일로 코드를 짜주지?", "이전에 분명히 이렇게 하지 말라고 했는데 새 대화창에서는 또 그런다." 원인은 단순하다. LLM은 대화가 끝나면 그 세션의 맥락을 잊는다. 매번 프로젝트 컨벤션, 금지 패턴, 선호하는 라이브러리를 다시 설명해야 한다면 AI 도구가 주는 생산성 이득의 상당 부분이 그 반복 설명에 소모된다.

이 문제를 해결하기 위해 나온 것이 프로젝트 루트에 두는 "규칙 파일(rules file)"이다. Cursor의 `.cursorrules`(최근에는 `.cursor/rules/` 디렉터리 방식), Windsurf의 `.windsurfrules`, GitHub Copilot의 `.github/copilot-instructions.md`가 대표적이다. 개념은 같다. 도구가 코드를 제안하거나 채팅에 답하기 전에 이 파일을 시스템 프롬프트에 자동으로 끼워 넣어, 매번 설명하지 않아도 일관된 맥락을 유지시킨다.

문제는 도구마다 파일 위치, 문법, 우선순위 규칙이 제각각이라는 점이다. 여러 도구를 함께 쓰는 팀(개인은 Cursor, 페어는 Copilot)이라면 규칙을 중복 관리하다 서로 어긋나는 사고가 난다.

## 도구별 규칙 파일 비교

| 도구 | 파일 위치 | 형식 | 특징 |
|---|---|---|---|
| Cursor | `.cursor/rules/*.mdc` (구 `.cursorrules`) | Markdown + frontmatter | 파일 패턴별로 규칙을 분리 적용 가능 |
| Windsurf | `.windsurfrules` | 순수 텍스트/Markdown | 단일 파일, 글자 수 제한 있음 |
| GitHub Copilot | `.github/copilot-instructions.md` | Markdown | 저장소 전체에 적용, VS Code·JetBrains 공용 |
| Claude Code | `CLAUDE.md` | Markdown | 하위 디렉터리마다 중첩 가능 |

가장 눈에 띄는 차이는 "적용 범위를 얼마나 세밀하게 나눌 수 있는가"다. Cursor의 `.mdc` 방식은 `globs` 필드로 "이 규칙은 `*.test.ts` 파일에만 적용" 같은 조건을 걸 수 있다. 반면 Windsurf와 Copilot의 단일 파일 방식은 프로젝트 전역에 한 번에 적용되므로, 프론트엔드/백엔드가 섞인 모노레포에서는 규칙이 서로 충돌하기 쉽다.

## 잘못된 접근과 그 결과

흔히 저지르는 실수는 규칙 파일에 "좋은 코드를 작성해줘", "베스트 프랙티스를 따라줘" 같은 추상적인 문장만 채우는 것이다. 이런 지침은 LLM 입장에서 실행 가능한 제약이 아니라 일반론이라 사실상 무시된다. 결과는 규칙 파일이 있어도 없는 것과 비슷한 결과물이 나오는 것이다.

또 다른 실수는 규칙 파일을 한 번 쓰고 방치하는 것이다. 프로젝트가 React 17에서 19로 올라가거나 상태 관리 라이브러리를 바꿨는데 규칙 파일은 옛날 컨벤션을 그대로 담고 있으면, AI가 이미 폐기한 패턴을 계속 제안해 오히려 리뷰 비용이 늘어난다.

## 올바른 접근

효과적인 규칙 파일은 추상적 원칙이 아니라 **구체적이고 검증 가능한 제약**을 담는다.

```markdown
- 새 API 엔드포인트는 항상 `src/api/` 아래 도메인별 폴더에 만든다.
- 상태 관리는 Zustand만 사용한다. Redux, Context API로 전역 상태를 만들지 않는다.
- 컴포넌트 파일명은 PascalCase, 훅 파일명은 use로 시작하는 camelCase를 쓴다.
- 테스트 없이 새 유틸 함수를 추가하지 않는다. 같은 폴더에 `*.test.ts`를 함께 만든다.
```

이런 식으로 "무엇을 하지 말라"와 "무엇을 대신 하라"를 짝지어 쓰면 모델이 실제로 지킬 확률이 크게 올라간다. 또한 규칙을 하나의 거대한 파일에 몰아넣기보다, Cursor처럼 도구가 지원한다면 도메인별로 분리(`api-rules.mdc`, `test-rules.mdc`)하는 편이 유지보수에 유리하다.

## 실무 포인트

- **여러 도구를 함께 쓴다면 진실의 원천을 하나로 만들어라.** `CLAUDE.md`나 `AGENTS.md` 하나를 기준 문서로 두고, 나머지 도구의 규칙 파일에는 "자세한 내용은 CLAUDE.md 참고"처럼 요약 + 링크 형태로 동기화하는 방법이 관리 부담을 줄인다.
- **규칙 파일도 코드 리뷰 대상으로 삼아라.** 컨벤션이 바뀌면 규칙 파일 수정 PR을 같이 올리도록 팀 문화를 만들지 않으면 금방 낡은 문서가 된다.
- **금지 패턴에는 이유를 한 줄이라도 붙여라.** "Moment.js 쓰지 마라"보다 "Moment.js는 번들 크기 문제로 금지, date-fns 사용"이 모델의 판단 정확도를 높인다.
- **글자 수 제한이 있는 도구는 우선순위부터 적어라.** Windsurf처럼 규칙 파일 길이 제한이 있는 도구는 뒤쪽 내용이 잘릴 수 있으므로, 가장 중요한 제약을 맨 앞에 배치한다.

## 마무리 요약

- AI 코딩 도구는 세션 간 기억이 없으므로, 프로젝트 컨벤션을 담은 규칙 파일이 반복 설명 비용을 줄여준다.
- Cursor·Windsurf·Copilot·Claude Code는 파일 위치와 세분화 방식이 다르므로, 여러 도구를 함께 쓴다면 기준 문서 하나를 두고 동기화하는 전략이 필요하다.
- 추상적인 원칙보다 "하지 말 것 + 대신 할 것"이 짝을 이루는 구체적 규칙이 실제로 더 잘 지켜진다.

## 참고 자료

- [Cursor Docs - Rules](https://docs.cursor.com/context/rules)
- [GitHub Docs - Repository custom instructions for Copilot](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
