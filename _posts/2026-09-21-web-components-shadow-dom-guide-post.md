---
layout: single
title: "Web Components로 프레임워크 독립적인 버튼 만들기 — Shadow DOM 스타일 격리"
date: 2026-09-21 12:30:00 +0530
categories: frontend
tags: ["webcomponents", "shadowdom", "커스텀엘리먼트", "프레임워크독립", "웹표준"]
toc: true
toc_sticky: true
excerpt: "React용 버튼, Vue용 버튼을 따로 만들어야 하는 문제를, 브라우저 표준 Web Components와 Shadow DOM으로 프레임워크에 상관없이 재사용 가능하게 만드는 방법을 정리했다."
---

## 왜 프레임워크마다 컴포넌트를 다시 만들게 되나

회사에 디자인 시스템 팀이 있고, 여러 프로젝트가 React·Vue·바닐라 자바스크립트로 각각 다른 프레임워크를 쓴다고 하자. "브랜드 버튼 컴포넌트"를 한 번만 만들어 전사에서 재사용하고 싶지만, React 컴포넌트는 Vue 프로젝트에서 그대로 쓸 수 없다. 결국 같은 버튼을 프레임워크 개수만큼 중복 구현하게 되고, 디자인이 바뀔 때마다 여러 곳을 동시에 고쳐야 하는 유지보수 부담이 생긴다.

**Web Components**는 이 문제를 프레임워크에 의존하지 않는 브라우저 네이티브 표준으로 해결한다. `<my-button>`처럼 커스텀 태그를 한 번 정의해두면, React든 Vue든 순수 HTML이든 어디서나 그냥 HTML 태그처럼 갖다 쓸 수 있다.

## 잘못된 접근: 그냥 클래스 이름만 신경 쓴 컴포넌트

Web Components를 모르는 상태에서 "재사용 가능한 컴포넌트"를 만들려고 하면, 결국 CSS 클래스 이름 충돌을 조심하며 `<div class="my-button">` 같은 마크업을 여러 프로젝트에 복사해 붙이는 방식으로 흘러간다.

```html
<div class="my-button primary">확인</div>
<style>
.my-button { padding: 8px 16px; border-radius: 4px; }
</style>
```

이 방식은 그 프로젝트의 전역 CSS와 클래스 이름이 충돌할 위험이 항상 있다. 다른 팀이 무심코 `.my-button`이라는 클래스를 다른 용도로 써버리면 스타일이 깨진다. 컴포넌트의 스타일이 외부에 새어나가거나, 반대로 외부 스타일이 컴포넌트 내부로 침투하는 것을 막을 방법이 근본적으로 없다.

## 올바른 접근: Custom Elements + Shadow DOM

```javascript
class MyButton extends HTMLElement {
  connectedCallback() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        button {
          padding: 8px 16px;
          border-radius: 4px;
          background: var(--brand-color, #2563eb);
          color: white;
          border: none;
        }
      </style>
      <button><slot></slot></button>
    `;
  }
}

customElements.define('my-button', MyButton);
```

```html
<my-button>확인</my-button>
```

`attachShadow({ mode: 'open' })`로 만든 **Shadow DOM**은 그 요소 내부의 스타일과 마크업을 외부와 완전히 격리한다. `<style>` 블록 안의 `button` 선택자는 오직 이 컴포넌트 내부의 `<button>`에만 적용되며, 페이지의 다른 전역 CSS와 절대 충돌하지 않는다. 반대로 페이지의 전역 CSS도 이 Shadow DOM 내부로 새어 들어가지 못한다. `<slot>`은 사용하는 쪽에서 태그 사이에 넣은 콘텐츠(`확인`)를 그 위치에 그대로 표시해주는 역할을 한다.

## CSS 커스텀 속성으로 외부에서 스타일 조정하기

Shadow DOM이 스타일을 완전히 격리한다고 해서 외부에서 전혀 커스터마이징할 수 없는 것은 아니다. CSS 커스텀 속성(변수)은 Shadow DOM 경계를 넘어 상속된다.

```html
<my-button style="--brand-color: #16a34a;">저장</my-button>
```

컴포넌트 내부에서 `var(--brand-color, #2563eb)`처럼 커스텀 속성을 참조하도록 만들어두면, 사용하는 쪽에서 이 변수 값만 바꿔 색상을 조정할 수 있다. 완전히 닫힌 블랙박스가 아니라, 정해진 "인터페이스"를 통해서만 외부와 소통하는 구조가 되는 셈이다.

## React·Vue 프로젝트에서 쓸 때 주의할 점

| 프레임워크 | 사용 방식 | 주의점 |
|---|---|---|
| 순수 HTML | 태그 그대로 사용 | 문제 없음 |
| React | JSX에서 태그처럼 사용 | 커스텀 이벤트는 `addEventListener`로 직접 등록 필요 |
| Vue | 템플릿에서 태그처럼 사용 | `compilerOptions.isCustomElement` 설정 필요 |

React는 18 버전대까지 Web Components의 커스텀 이벤트를 JSX의 `onXxx` prop으로 자동 바인딩하지 못하는 경우가 있어, `ref`를 얻어 `addEventListener`로 직접 등록해야 하는 상황이 종종 생긴다. Vue는 커스텀 엘리먼트를 Vue 컴포넌트로 착각해 컴파일하지 않도록 별도 설정이 필요하다.

## 실무 포인트

- **Shadow DOM 내부의 접근성(a11y)을 직접 챙겨야 한다.** 시맨틱 태그와 ARIA 속성을 컴포넌트 내부 마크업에 명시적으로 넣어야 하며, Shadow DOM이 자동으로 접근성을 보장해주지 않는다.
- **폼 요소로 쓸 컴포넌트는 `ElementInternals` API를 검토하라.** 커스텀 엘리먼트를 실제 `<form>` 제출에 참여시키려면 이 API로 폼 연동을 명시적으로 구현해야 한다.
- **디자인 시스템처럼 여러 프레임워크에 걸쳐 쓰일 컴포넌트에 적합하다.** 반대로 하나의 React 프로젝트 안에서만 쓰이는 컴포넌트라면, Web Components의 추가 복잡도보다 일반 React 컴포넌트가 더 실용적일 수 있다.
- **번들 크기와 브라우저 지원을 확인하라.** 대부분의 최신 브라우저가 지원하지만, 폴리필이 필요한 구형 환경이 있는지 프로젝트 요구사항에 맞춰 점검한다.

## 마무리 요약

- Web Components는 프레임워크에 의존하지 않는 브라우저 표준 컴포넌트 모델로, 여러 프레임워크에 걸쳐 재사용해야 하는 디자인 시스템에 특히 유용하다.
- Shadow DOM은 스타일과 마크업을 완전히 격리해 전역 CSS 충돌 문제를 근본적으로 없애며, CSS 커스텀 속성으로 제한적인 외부 커스터마이징 통로를 열어둔다.
- React·Vue에서 쓸 때는 커스텀 이벤트 바인딩, 컴파일러 설정 같은 프레임워크별 주의점을 별도로 챙겨야 한다.

## 참고 자료

- [MDN - Web Components](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
- [web.dev - Shadow DOM v1](https://web.dev/articles/shadowdom-v1)
