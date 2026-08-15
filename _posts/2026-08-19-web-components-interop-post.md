---
layout: single
title: "Web Components와 프레임워크 상호운용성 — React·Vue에서 커스텀 엘리먼트 제대로 쓰기"
date: 2026-08-19 12:30:00 +0530
categories: frontend
tags: ["web-components", "custom-elements", "react", "vue", "shadow-dom", "interop"]
toc: true
toc_sticky: true
excerpt: "디자인 시스템을 프레임워크 경계 없이 재사용하려는 수요가 커지면서, React·Vue에서 Web Components(커스텀 엘리먼트)를 안전하게 소비하는 법과 흔한 상호운용 함정을 정리한다."
---

## 왜 지금 Web Components 상호운용성인가

한 회사 안에서도 제품마다 React, Vue, 혹은 레거시 jQuery 화면이 섞여 있는 경우가 드물지 않다. 디자인 시스템 팀 입장에서는 버튼 하나, 날짜 선택기 하나를 프레임워크별로 각각 구현·유지보수하는 비용이 상당하다. **Web Components**(Custom Elements + Shadow DOM + HTML Templates)는 브라우저 표준이기 때문에 이 문제의 자연스러운 답으로 다시 주목받고 있다. 실제로 Adobe의 Spectrum, SAP의 UI5, Shoelace(현 Web Awesome) 같은 다수의 상용 디자인 시스템이 내부적으로 커스텀 엘리먼트를 표준 배포 형태로 채택했다.

다만 "프레임워크 독립적"이 "아무 마찰 없이 붙는다"는 뜻은 아니다. React는 오랫동안 커스텀 엘리먼트에 값을 넘길 때 모든 prop을 문자열 HTML 속성으로 취급해 객체·배열 prop과 궁합이 좋지 않았다. React 19에서는 커스텀 엘리먼트 인스턴스에 해당 프로퍼티가 실제로 존재하면 속성이 아닌 프로퍼티로 대입하도록 개선됐다. Vue는 `defineCustomElement` API로 SFC를 네이티브 커스텀 엘리먼트로 컴파일해 배포할 수 있어 상호운용에 더 유리한 편이다. 무엇이 표준 동작이고 무엇이 프레임워크별 보정인지 정리해 둘 시점이다.

## 핵심 개념 1: 속성(Attribute)과 프로퍼티(Property)는 다르다

Web Components를 프레임워크에서 다룰 때 가장 먼저 부딪히는 개념이다. HTML **속성**은 항상 문자열이고 마크업에 그대로 보인다. **프로퍼티**는 JS 객체 인스턴스의 필드로, 문자열이 아닌 어떤 값도 담을 수 있다. 커스텀 엘리먼트 저자는 보통 원시값(문자열·불리언·숫자)은 속성으로 반영(reflect)하고, 배열·객체·함수 같은 복합 데이터는 프로퍼티로만 받도록 설계한다.

| 데이터 종류 | 전달 방식 | JSX/템플릿에서 흔한 실수 |
|---|---|---|
| 문자열, 숫자, 불리언 | 속성(attribute) | 문제 대부분 없음 |
| 배열, 객체 | 프로퍼티(property) | `items="[1,2,3]"`처럼 문자열로 직렬화해 넘기는 실수 |
| 콜백 함수 | 프로퍼티(property) | JSX 속성으로 넘기면 함수가 문자열로 변환되어 무시됨 |
| 상태 변화 알림 | `CustomEvent` dispatch | `onChange` prop을 기대했다가 이벤트가 안 잡히는 문제 |

## 핵심 개념 2: 프레임워크별 처리 방식 비교

<img src="/assets/images/posts/2026-08-19-web-components-interop-1.svg" alt="React·Vue와 커스텀 엘리먼트 사이의 속성·프로퍼티·CustomEvent 데이터 흐름도" style="width:100%;">

| 항목 | React | Vue |
|---|---|---|
| 원시값 prop | 속성으로 전달, 대부분 정상 동작 | 속성으로 전달, 정상 동작 |
| 객체·배열 prop | React 19 이전은 문자열화 위험 → `ref`로 직접 프로퍼티 대입 권장 | 컴파일러가 프로퍼티로 자동 바인딩 |
| 커스텀 이벤트 수신 | `onXxx` 컨벤션이 자동 연결되지 않는 경우가 많아 `ref` + `addEventListener` 필요 | 네이티브 DOM 이벤트로 인식해 `@event-name`으로 바로 수신 |
| Shadow DOM 스타일 | 전역 CSS·CSS-in-JS 모두 침투 불가, `::part()` 필요 | 동일 |
| SSR | Declarative Shadow DOM 지원 여부는 프레임워크·번들러 설정에 따라 다름 | 동일하게 별도 확인 필요 |

React·Vue 모두 결국 "속성 대신 프로퍼티를 명시적으로 대입"하고 "onXxx 대신 실제 DOM 이벤트 리스너로 커스텀 이벤트를 받는다"는 원칙은 같다. 차이는 이 처리를 프레임워크가 자동으로 해주는지, 개발자가 `ref`로 직접 손을 대야 하는지에 있다.

## 예제 1: React에서 커스텀 엘리먼트에 안전하게 값 전달하기

```jsx
import { useEffect, useRef } from 'react';

function DatePickerField({ value, onDateChange }) {
  const elRef = useRef(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;

    // 배열·객체 등 non-string 값은 속성이 아니라 프로퍼티로 직접 대입한다
    el.value = value;

    const handleChange = (e) => onDateChange(e.detail.date);
    el.addEventListener('date-change', handleChange);
    return () => el.removeEventListener('date-change', handleChange);
  }, [value, onDateChange]);

  return <my-date-picker ref={elRef} />;
}
```

`value`를 JSX 속성(`value={value}`)으로 바로 넘기지 않는 이유는, 커스텀 엘리먼트가 `value`를 객체(예: `{ year, month, day }`)로 기대할 경우 문자열로 직렬화되어 전달될 위험이 있기 때문이다. 이벤트도 `onDateChange` 같은 React 컨벤션 prop이 아니라 실제 `CustomEvent`(`date-change`)를 리스닝해야 한다.

## 예제 2: Vue에서 SFC를 커스텀 엘리먼트로 배포하고 소비하기

```js
// 1. 커스텀 엘리먼트로 컴파일해 등록 (배포 측)
import { defineCustomElement } from 'vue';
import DatePicker from './DatePicker.ce.vue';

const MyDatePickerElement = defineCustomElement(DatePicker);
customElements.define('my-date-picker', MyDatePickerElement);
```

```html
<!-- 2. 다른 Vue 앱에서 그대로 소비 (사용 측) -->
<template>
  <my-date-picker :value="date" @date-change="date = $event.detail.date" />
</template>
```

`defineCustomElement`로 감싸면 Vue의 반응형 prop이 커스텀 엘리먼트의 프로퍼티로 자동 매핑되고, 내부에서 `emit`한 이벤트도 표준 `CustomEvent`로 변환되어 나간다. 소비 측은 이 컴포넌트가 Vue로 만들어졌는지 몰라도 `:value`/`@date-change` 문법 그대로 사용할 수 있다.

## 실무 포인트

- **프로퍼티가 필요한 값은 JSX/템플릿 속성 문법에 의존하지 않는다.** 배열·객체·함수는 `ref`를 통해 DOM 프로퍼티로 직접 대입하는 래퍼 컴포넌트로 감싸는 편이 안전하다.
- **Shadow DOM 안쪽 스타일링은 `::part()`와 CSS 커스텀 프로퍼티로 노출된 부분만 조정 가능하다.** Tailwind 유틸리티나 CSS-in-JS는 Shadow 경계를 넘지 못하므로, 테마 변수가 얼마나 열려 있는지 먼저 문서로 확인한다.
- **커스텀 이벤트 이름과 `event.detail` 스키마를 팀 컨벤션으로 문서화한다.** 프레임워크마다 이벤트 수신 방식(`addEventListener` vs `@event`)이 달라 소비 측에서 헷갈리기 쉽다.
- **SSR을 쓴다면 Declarative Shadow DOM 지원 여부를 프레임워크·번들러별로 개별 확인한다.** 표준 자체는 성숙했지만 메타프레임워크의 SSR 파이프라인 지원 여부는 버전·설정에 따라 다를 수 있다.

## 3줄 요약

- Web Components는 프레임워크 독립적 디자인 시스템 배포 수단으로 다시 주목받고 있지만, "속성은 문자열, 프로퍼티는 복합 데이터"라는 원칙을 프레임워크별로 다르게 보정해줘야 한다.
- React는 `ref` + 프로퍼티 직접 대입과 `addEventListener`로 커스텀 엘리먼트를 감싸는 패턴이 여전히 필요하고, Vue는 `defineCustomElement`로 이 과정을 상당 부분 자동화해 준다.
- Shadow DOM 스타일 경계(`::part()`)와 커스텀 이벤트 스키마를 팀 컨벤션으로 미리 문서화해야 상호운용 마찰을 줄일 수 있다.

## 참고 자료

- [MDN — Using custom elements](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_custom_elements)
- [Vue.js — Vue와 Web Components](https://vuejs.org/guide/extras/web-components.html)
- [React — Web Components (react.dev)](https://react.dev/reference/react-dom/components#custom-html-elements)
