---
layout: single
title: "div로 만든 콤보박스가 스크린리더에서 무너지는 이유 — 복잡한 위젯 ARIA 패턴 실무"
date: 2026-08-29 13:30:00 +0530
categories: frontend
tags: ["aria", "accessibility", "combobox", "tree-view", "web-a11y", "wai-aria"]
toc: true
toc_sticky: true
excerpt: "콤보박스와 트리처럼 여러 위젯이 조합된 복합 컴포넌트에서 ARIA 역할·상태·키보드 인터랙션을 어떻게 맞춰야 스크린리더 사용자가 실제로 조작할 수 있는지 정리한다."
---

`<select>`나 `<input>` 같은 네이티브 폼 요소는 브라우저가 접근성 트리와 키보드 동작을 알아서 챙겨준다. 문제는 디자인 시스템이 요구하는 자동완성 콤보박스, 다단계 트리 뷰, 그리드형 데이터 테이블처럼 네이티브 HTML에 대응하는 요소가 없는 복합 위젯이다. 이런 컴포넌트는 결국 `div`와 `span`을 조합해 만들게 되고, 시각적으로는 그럴듯해도 스크린리더 사용자에게는 "그냥 텍스트 덩어리"로만 인식되는 경우가 흔하다.

WAI-ARIA는 이 간극을 메우기 위한 속성 집합이지만, `role`이나 `aria-*` 속성을 아무렇게나 붙인다고 접근성이 생기지 않는다. ARIA에는 "이 역할을 쓰려면 이런 상태·속성·키보드 동작이 함께 있어야 한다"는 패턴이 정해져 있고, 이를 어기면 오히려 스크린리더가 잘못된 정보를 읽어줘서 네이티브 대체 요소보다 못한 경험을 만들 수 있다. 이 글에서는 콤보박스와 트리 뷰를 예로, 복합 위젯에서 ARIA를 실무적으로 어떻게 맞춰야 하는지를 정리한다.

## 핵심 개념 1: ARIA의 첫 번째 규칙 — 쓰지 않아도 되면 쓰지 않는다

WAI-ARIA 명세 자체가 강조하는 원칙이 있다. "네이티브 HTML 요소나 속성으로 필요한 시맨틱과 동작을 이미 구현할 수 있다면, ARIA 역할·상태·속성을 추가하는 대신 그 네이티브 요소를 쓰라"는 것이다. `<button>` 하나로 될 것을 `<div role="button">`으로 만들면, 포커스 가능하게 `tabindex="0"`을 붙이고, 스페이스/엔터 키 입력을 직접 처리하는 JS까지 다 구현해야 네이티브 버튼과 동등해진다. 이 원칙 때문에 "정말 네이티브 요소로 대체 불가능한 위젯"에만 ARIA 패턴을 적용하는 것이 첫 판단 기준이다.

콤보박스, 트리 뷰처럼 네이티브 대응이 없는 위젯은 W3C의 **ARIA Authoring Practices Guide(APG)**가 역할·키보드 동작·속성 조합을 패턴으로 정의해 두고 있다. 직접 설계하기보다 이 패턴을 그대로 따르는 것이 검증된 시작점이다.

## 핵심 개념 2: 콤보박스 — role, 상태, 키보드가 세 박자로 맞아야 한다

자동완성 콤보박스는 겉보기엔 입력창 하나와 목록 하나지만, 접근성 트리에서는 다음 요소들이 정확히 연결돼야 스크린리더가 "이건 콤보박스이고, 지금 목록이 열려 있으며, 몇 번째 항목이 선택 후보인지"를 안내할 수 있다.

- 입력 요소에 `role="combobox"`, `aria-expanded`(목록이 열려 있는지), `aria-controls`(연결된 목록의 id), `aria-autocomplete`(자동완성 방식)
- 목록에 `role="listbox"`, 각 항목에 `role="option"`
- 현재 커서가 가리키는 항목을 `aria-activedescendant`로 입력 요소에서 참조(포커스는 입력창에 그대로 두고, 시각적 하이라이트만 목록에서 옮기는 방식)

키보드 동작도 정확히 맞아야 한다. 화살표 키로 옵션 간 이동, Enter로 선택 확정, Escape로 목록 닫기가 표준 패턴이며, 이 중 하나라도 빠지면 마우스 없이는 위젯을 완결하지 못하는 사용자가 생긴다.

```html
<label id="fruit-label">과일 검색</label>
<input
  type="text"
  role="combobox"
  aria-expanded="true"
  aria-controls="fruit-listbox"
  aria-autocomplete="list"
  aria-activedescendant="opt-2"
  aria-labelledby="fruit-label" />

<ul id="fruit-listbox" role="listbox">
  <li id="opt-1" role="option" aria-selected="false">사과</li>
  <li id="opt-2" role="option" aria-selected="true">바나나</li>
  <li id="opt-3" role="option" aria-selected="false">포도</li>
</ul>
```

`aria-activedescendant`를 쓰는 이유는 실제 DOM 포커스를 입력창에 유지하면서, "지금 어떤 옵션이 선택 후보인지"만 스크린리더에 알리기 위해서다. 포커스를 매번 목록 항목으로 옮기면 IME(한글 입력 등)와 충돌하거나 타이핑이 끊기는 문제가 생기기 쉽다.

## 핵심 개념 3: 트리 뷰 — 계층 구조와 확장 상태를 함께 전달한다

트리 뷰(폴더 구조, 조직도 등)는 콤보박스와 다른 종류의 복잡성을 갖는다. 항목이 부모-자식 계층을 이루고, 각 항목이 확장/축소 가능한 상태를 갖기 때문이다. APG 트리 뷰 패턴은 다음을 요구한다.

- 트리 컨테이너에 `role="tree"`, 각 항목에 `role="treeitem"`
- 자식을 가진 항목에 `aria-expanded`(펼쳐진 상태) — 자식이 없는 리프 노드에는 이 속성 자체를 넣지 않는다
- 중첩된 하위 트리를 `role="group"`으로 감싸 계층 관계를 명시
- 방향키로 항목 간 이동, 오른쪽 화살표로 확장(또는 첫 자식으로 이동), 왼쪽 화살표로 축소(또는 부모로 이동)

여기서 실무자가 자주 놓치는 부분은 **포커스 관리 방식**이다. 트리의 모든 `treeitem`에 `tabindex="0"`을 주면 Tab 키 한 번에 트리 전체를 순서대로 훑어야 해서 항목이 많을수록 탐색이 비효율적이다. APG는 "roving tabindex" 패턴을 권장하는데, 트리 전체에서 오직 현재 포커스된 항목 하나만 `tabindex="0"`을 갖고 나머지는 `tabindex="-1"`로 두어, Tab은 트리에 진입/이탈할 때만 쓰고 트리 내부 이동은 화살표 키가 전담하게 만드는 방식이다.

| 구분 | 콤보박스 | 트리 뷰 |
|---|---|---|
| 핵심 역할 | combobox + listbox/option | tree + treeitem + group |
| 상태 표현 | aria-expanded, aria-activedescendant | aria-expanded(확장 가능한 노드만) |
| 주요 키보드 동작 | ↑↓ 이동, Enter 확정, Esc 닫기 | ↑↓ 형제 이동, →← 확장/축소·계층 이동 |
| 포커스 전략 | 입력창 고정 + activedescendant | roving tabindex |
| 흔한 실수 | 목록으로 포커스 이동시켜 IME 충돌 | 모든 항목에 tabindex="0" 부여 |

## 실무 포인트

- **APG 예제를 그대로 시작점으로 삼는다**: 콤보박스·트리 모두 W3C APG에 정확한 예제 코드가 공개돼 있다. 처음부터 직접 설계하기보다 이 예제의 역할·속성·키보드 처리 로직을 그대로 이식하고, 디자인에 맞춰 스타일만 입히는 순서가 실수를 줄인다.
- **스크린리더로 직접 조작해서 검증한다**: `aria-*` 속성이 문법적으로 맞아도 실제 스크린리더(NVDA, VoiceOver)로 방향키만으로 끝까지 조작해보면 놓친 부분이 바로 드러난다. 자동화 접근성 검사 도구는 속성 존재 여부는 잡아도 "실제로 조작 가능한가"까지는 검증하지 못한다.
- **상태 변경 시 관련 속성을 함께 갱신하는 것을 잊지 않는다**: `aria-expanded`를 토글할 때 `aria-selected`나 `aria-activedescendant` 갱신을 빠뜨리면, 시각적으로는 선택됐는데 스크린리더는 이전 상태를 그대로 읽는 불일치가 생긴다. 상태를 다루는 함수 하나에서 관련 ARIA 속성을 한꺼번에 갱신하도록 코드를 구조화하는 것이 안전하다.

## 3줄 요약

- 네이티브 HTML로 대체 불가능한 복합 위젯(콤보박스, 트리 뷰)에서만 ARIA 역할·상태·키보드 패턴을 적용하는 것이 첫 판단 기준이다.
- 콤보박스는 `aria-expanded`·`aria-activedescendant`로 입력창 포커스를 유지한 채 선택 후보를 전달해야 하고, 트리 뷰는 확장 가능한 노드에만 `aria-expanded`를 두고 roving tabindex로 포커스를 관리해야 한다.
- W3C ARIA Authoring Practices Guide의 검증된 패턴을 그대로 시작점으로 삼고, 실제 스크린리더로 방향키만으로 조작해보는 검증이 자동화 도구가 놓치는 문제를 잡아낸다.

## 참고 자료

- [W3C ARIA Authoring Practices Guide: Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- [W3C ARIA Authoring Practices Guide: Tree View Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/)
- [MDN: ARIA 첫 번째 규칙(Using ARIA)](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Techniques)
