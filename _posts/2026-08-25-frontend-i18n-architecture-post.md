---
layout: single
title: "번역 파일만 바꾸면 끝? 프론트엔드 i18n 아키텍처 제대로 설계하기"
date: 2026-08-25 12:30:00 +0530
categories: frontend
tags: ["i18n", "icu-messageformat", "localization", "frontend-architecture", "react", "translation-pipeline"]
toc: true
toc_sticky: true
excerpt: "단순 키-값 치환 방식의 다국어 지원이 복수형·성별·숫자 서식에서 무너지는 이유를 ICU MessageFormat으로 짚고, 번역 파이프라인과 지연 로딩 구조를 정리한다."
---

다국어 지원을 처음 붙일 때 가장 흔한 접근은 `{ "welcome": "환영합니다" }` 같은 키-값 JSON 파일을 언어별로 두고, 코드에서 키로 조회해 치환하는 방식이다. 짧은 문장 몇 개를 번역할 때는 이걸로 충분해 보이지만, 서비스가 커지면 반드시 부딪히는 벽이 있다. "1개 남았습니다"와 "3개 남았습니다"를 하나의 템플릿으로 처리하려던 복수형 처리, 언어마다 다른 날짜·통화 서식, 그리고 무엇보다 "번역 파일을 누가, 언제, 어떻게 갱신하는가"라는 운영 프로세스의 문제다.

i18n(internationalization)을 진지하게 설계한다는 것은 문자열을 언어별로 바꿔치기하는 문제가 아니라, **문법 규칙이 언어마다 다르다는 것을 시스템으로 흡수하는 문제**에 가깝다. 이 글에서는 ICU MessageFormat이 이 문제를 어떻게 표준화하는지, 그리고 번역 리소스를 실제 서비스에 어떻게 안전하게 흘려보내는지를 정리한다.

## 핵심 개념 1: 단순 치환이 무너지는 지점

문자열 치환만으로 다국어를 처리하면 복수형에서 가장 먼저 무너진다. 영어는 단수/복수 두 가지지만, 한국어는 복수형이 없고, 폴란드어나 아랍어는 형태가 3~6가지로 갈린다. `count === 1 ? '항목' : '항목들'` 같은 코드를 언어마다 분기로 짜면 새 언어를 추가할 때마다 프로그래머가 그 언어의 복수 규칙을 알아야 하는 이상한 구조가 된다.

성별에 따라 문장이 갈리는 언어(예: 프랑스어의 형용사 성 일치), 숫자·통화·날짜의 로캘별 서식(1,234.56 vs 1.234,56), 문장 내 단어 순서가 언어마다 달라 단순 문자열 조립이 아예 불가능한 경우(RTL 언어 포함)까지 고려하면, "번역 파일만 바꾸면 된다"는 가정은 초기 단계를 벗어나는 순간 깨진다.

## 핵심 개념 2: ICU MessageFormat이 표준화하는 것

ICU MessageFormat은 이런 언어별 문법 변주를 번역 문자열 안에 선언적으로 표현하는 표준 문법이다. 프로그램 코드에는 언어별 분기가 전혀 없고, **번역 파일 안에** 복수형·선택 분기 규칙이 담긴다.

```
{count, plural,
  =0 {항목이 없습니다}
  one {항목이 {count}개 있습니다}
  other {항목이 {count}개 있습니다}
}
```

영어 번역자는 같은 키에 대해 `one {# item}`과 `other {# items}`를 다르게 쓰고, 아랍어 번역자는 자기 언어의 복수 규칙(zero/one/two/few/many/other)에 맞게 분기를 채운다. 코드는 `count` 값만 넘기면 되고, 어떤 분기를 고를지는 각 로캘의 CLDR(Common Locale Data Repository) 복수 규칙에 따라 포맷터가 알아서 처리한다. `select`(성별 등 임의 카테고리 분기), `selectordinal`(1st/2nd/3rd 같은 서수) 구문도 같은 원리로 지원된다.

## 핵심 개념 3: 번역 리소스를 서비스에 흘려보내는 파이프라인

번역 문자열의 문법을 표준화했다면, 다음 문제는 그 리소스가 개발-번역-배포 사이를 어떻게 오가느냐다.

| 단계 | 역할 | 흔한 도구/패턴 |
|---|---|---|
| 추출(extraction) | 코드에서 번역 대상 문자열과 키를 스캔해 소스 언어 파일 생성 | `formatjs`의 CLI, 커스텀 babel/AST 스캐너 |
| 번역 관리 | 번역가/에이전시가 키별로 번역 입력, 리뷰, 승인 | TMS(Translation Management System, 예: Phrase, Lokalise) |
| 검증 | 플레이스홀더 누락, ICU 문법 오류, 미번역 키 검출 | CI 단계에서 lint 실행 |
| 배포 | 번역 파일을 빌드에 포함하거나 런타임에 CDN에서 로드 | 정적 번들 vs 동적 fetch |

정적 번들 방식은 빌드 시점에 모든 언어 파일을 포함해 배포하므로 런타임 요청이 없어 빠르지만, 지원 언어가 늘수록 번들 크기가 커진다. 런타임 동적 로딩은 현재 로캘의 번역 파일만 필요할 때 fetch하므로 초기 번들은 가볍지만, 로딩 지연과 캐시 무효화 전략이 추가로 필요하다. 대부분의 실무는 **로캘 단위 코드 스플리팅**으로 절충한다 — 현재 언어의 번역 파일만 별도 청크로 분리해 지연 로딩하는 방식이다.

## 예제: React + FormatJS로 ICU 메시지 처리

```jsx
import { IntlProvider, FormattedMessage, useIntl } from 'react-intl';

const messages = {
  ko: {
    itemCount: '{count, plural, =0 {항목이 없습니다} other {항목이 #개 있습니다}}',
  },
  en: {
    itemCount: '{count, plural, =0 {No items} one {# item} other {# items}}',
  },
};

function ItemBadge({ count }) {
  return (
    <FormattedMessage id="itemCount" values={{ count }} />
  );
}

// 로캘 단위 지연 로딩: 현재 로캘의 메시지 청크만 fetch
async function loadMessages(locale) {
  const module = await import(`./locales/${locale}.json`);
  return module.default;
}

function App({ locale }) {
  const [msgs, setMsgs] = useState(null);
  useEffect(() => { loadMessages(locale).then(setMsgs); }, [locale]);
  if (!msgs) return <Spinner />;
  return (
    <IntlProvider locale={locale} messages={msgs}>
      <ItemBadge count={3} />
    </IntlProvider>
  );
}
```

## 실무 포인트

- **키를 문자열 내용이 아니라 의미 단위로 설계한다**: "welcome_message" 같은 의미 기반 키를 쓰면 원문이 바뀌어도 키가 안정적으로 유지돼 번역 관리 시스템에서의 이력 추적이 쉬워진다. 원문 텍스트 자체를 키로 쓰면 오타 하나 고칠 때마다 새 키로 인식되는 문제가 생긴다.
- **CI에 ICU 문법 검증과 플레이스홀더 일치 검사를 반드시 넣는다**: 번역가가 `{count}` 플레이스홀더를 실수로 지우거나 오타를 내면 런타임에서야 발견되는데, 이때는 이미 배포된 뒤인 경우가 많다.
- **날짜·숫자·통화 서식은 직접 조립하지 않는다**: `Intl.NumberFormat`, `Intl.DateTimeFormat` 같은 브라우저 내장 API나 그 위의 라이브러리를 쓰고, 문자열 연결로 서식을 만들지 않는다. 로캘별 자릿수 구분자, 통화 기호 위치는 직접 구현하면 반드시 놓치는 케이스가 나온다.

## 3줄 요약

- 다국어 지원은 문자열 치환이 아니라 언어마다 다른 복수형·성별·서식 문법을 시스템으로 흡수하는 문제이며, ICU MessageFormat이 이를 선언적 문법으로 표준화한다.
- 번역 리소스는 추출-번역 관리-검증-배포로 이어지는 파이프라인이며, CI 단계의 문법·플레이스홀더 검증이 런타임 장애를 막는 핵심 방어선이다.
- 번들 크기와 로딩 지연 사이에서는 로캘 단위 코드 스플리팅으로 절충하는 것이 실무에서 가장 흔한 선택이다.

## 참고 자료

- [ICU 공식 문서: Formatting Messages (MessageFormat)](https://unicode-org.github.io/icu/userguide/format_parse/messages/)
- [FormatJS 공식 문서](https://formatjs.io/docs/getting-started/installation/)
- [Unicode CLDR: Language Plural Rules](https://cldr.unicode.org/index/cldr-spec/plural-rules)
