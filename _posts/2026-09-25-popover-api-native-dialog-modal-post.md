---
layout: single
title: "Popover API와 <dialog> — JS 없이 네이티브로 만드는 모달·팝오버 상태관리"
date: 2026-09-25 13:30:00 +0530
categories: frontend
tags: ["PopoverAPI", "dialog", "웹접근성", "탑레이어", "네이티브HTML"]
toc: true
toc_sticky: true
excerpt: "모달·드롭다운·툴팁을 만들 때마다 z-index 경쟁과 포커스 트랩, 바깥 클릭 감지 로직을 라이브러리에 의존해 처리하던 문제를, 브라우저가 내부적으로 관리하는 top layer 위에서 동작하는 Popover API와 <dialog>가 어떻게 이를 대체하는지 정리했다."
---

## 왜 지금 Popover API를 다시 봐야 하는가

모달이나 드롭다운, 툴팁을 직접 구현해본 프론트엔드 개발자라면 공통적으로 겪는 세 가지 골칫거리가 있다. 첫째는 z-index 경쟁 — 어떤 요소를 다른 모든 요소 위에 확실히 띄우려면 z-index 값을 계속 올려야 하고, 여러 라이브러리가 섞이면 이 값들이 충돌한다. 둘째는 포커스 트랩과 접근성 — 모달이 열려 있을 때 키보드 포커스가 모달 밖으로 나가지 않게 막고, Esc로 닫고, 닫힐 때 포커스를 원래 위치로 되돌리는 로직을 매번 직접 짜거나 Radix UI 같은 라이브러리에 의존해야 했다. 셋째는 "바깥 영역 클릭 시 닫기" 감지다. Popover API와 `<dialog>` 요소는 이 문제들을 브라우저 엔진 내부의 새로운 렌더링 계층인 "top layer"에서 처리하도록 표준화해, 상당 부분을 JS 없이 해결한다.

## 핵심 개념 1 — Top Layer: DOM 트리 순서와 무관하게 항상 맨 위

기존에는 요소를 화면 맨 위에 띄우려면 결국 DOM의 stacking context 규칙과 z-index 값에 의존해야 했다. 부모 요소에 `overflow: hidden`이 걸려 있으면 자식 모달이 그 안에 잘려 보이지 않는 문제도 흔했다. Top layer는 이런 문제를 근본적으로 없앤다 — `popover` 속성이 붙은 요소나 `showModal()`로 연 `<dialog>`는 일반 DOM 렌더링 트리와 완전히 분리된 별도의 레이어에서 그려지며, 이 레이어는 항상 문서의 다른 모든 콘텐츠보다 위에 렌더링된다. 부모의 `overflow`나 `z-index` 설정이 top layer의 요소에는 아예 영향을 주지 못한다. 이 덕분에 개발자는 "이 요소를 다른 것보다 위에 어떻게 띄울까"라는 고민 자체를 할 필요가 없어진다.

## 핵심 개념 2 — 선언적 상호작용: HTML 속성만으로 열고 닫기

Popover API의 또 다른 핵심은 상태 관리를 위한 JS 이벤트 리스너를 최소화한다는 점이다. `popovertarget` 속성을 가진 버튼은 대상 팝오버 요소의 id를 가리키기만 하면 클릭 시 자동으로 열리고 닫힌다. 여기에 더해 브라우저가 기본으로 제공하는 "light dismiss" 동작 — 팝오버가 열린 상태에서 바깥을 클릭하거나 Esc를 누르면 자동으로 닫히는 로직 — 이 별도 구현 없이 내장되어 있다. `<dialog>`도 마찬가지로, `showModal()`로 열면 배경에 자동으로 `::backdrop` 가상 요소가 생기고 포커스가 다이얼로그 내부로 트랩되며 Esc로 닫힌다. 이 모든 접근성 동작이 라이브러리 코드 없이 브라우저 표준 구현으로 제공된다는 것이 핵심 가치다.

| 항목 | 기존 JS 라이브러리 기반 모달 | Popover API / dialog |
|---|---|---|
| 렌더링 위치 | DOM stacking context, z-index 의존 | top layer(항상 최상단) |
| 포커스 트랩 | 라이브러리가 직접 구현 | 브라우저 네이티브 제공(dialog) |
| 바깥 클릭 닫기 | 이벤트 리스너 직접 부착 | light dismiss 내장 |
| 접근성(ARIA) | 개발자가 role, aria 속성 직접 관리 | 기본 시맨틱에 상당 부분 내장 |

## 코드 예제 — JS 없이 동작하는 팝오버와 다이얼로그

```html
<!-- Popover API: 버튼과 팝오버를 속성만으로 연결 -->
<button popovertarget="user-menu">메뉴</button>
<div id="user-menu" popover>
  <a href="/profile">프로필</a>
  <a href="/logout">로그아웃</a>
</div>

<!-- dialog: 모달로 열되 배경 클릭 시 닫히는 동작을 추가하려면 소량의 JS만 필요 -->
<dialog id="confirm-dialog">
  <p>정말 삭제하시겠습니까?</p>
  <button id="confirm-btn">삭제</button>
  <form method="dialog"><button>취소</button></form>
</dialog>

<script>
  const dialog = document.getElementById('confirm-dialog');
  document.getElementById('open-btn').addEventListener('click', () => dialog.showModal());

  // 배경(::backdrop) 클릭 시 닫기 — 이 정도는 여전히 JS가 필요하다
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });
</script>
```

## 실무 포인트

- **Popover API와 `<dialog>`는 목적이 다르다.** `<dialog>`의 `showModal()`은 배경을 비활성화하고 상호작용을 완전히 막는 진짜 "모달"에 적합하고, Popover API는 드롭다운·툴팁·비모달 알림처럼 배경과 동시에 상호작용 가능한 UI에 적합하다. 삭제 확인처럼 반드시 응답을 받아야 하는 흐름에 Popover를 쓰면 접근성 문제가 생긴다.
- **브라우저 지원 범위를 반드시 확인하라.** Popover API는 비교적 최신 표준으로, 구형 브라우저나 특정 WebView 환경에서는 폴리필이 필요할 수 있다. 프로젝트의 타깃 브라우저 매트릭스를 먼저 확인하고 도입해야 한다.
- **완전히 JS를 없앨 수 있는 것은 아니다.** 애니메이션 트랜지션, 복잡한 위치 계산(Popover는 CSS Anchor Positioning과 결합해야 정교한 위치 지정이 가능), 다단계 폼 흐름 같은 요구사항에는 여전히 JS 로직이 필요하다. 기본 열기/닫기/포커스 관리를 표준에 맡기고, 그 위에 필요한 만큼만 커스텀 로직을 얹는 것이 실용적인 접근이다.

## 마무리 요약

- Popover API와 `<dialog>`는 브라우저의 top layer라는 별도 렌더링 계층에서 동작해, z-index 경쟁과 stacking context 문제를 근본적으로 없앤다.
- 포커스 트랩, Esc로 닫기, 바깥 클릭 시 자동 닫힘(light dismiss) 같은 접근성 동작이 브라우저 네이티브로 내장되어 있어 라이브러리 의존도를 크게 줄인다.
- 두 API는 용도가 다르므로(비모달 vs 진짜 모달) 요구사항에 맞게 선택하고, 정교한 위치 지정이나 애니메이션에는 여전히 소량의 JS/CSS가 필요하다는 점을 감안해야 한다.

## 참고 자료

- [MDN - Popover API](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API)
- [MDN - HTMLDialogElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement)
