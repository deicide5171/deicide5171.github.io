---
layout: single
title: "이벤트 버블링과 이벤트 위임 — 자바스크립트 이벤트 기초"
date: 2026-09-04 13:30:00 +0530
categories: frontend
tags: ["이벤트", "버블링", "이벤트위임", "javascript", "입문"]
toc: true
toc_sticky: true
excerpt: "클릭 이벤트가 왜 부모 요소에도 전달되는지(버블링)와, 이를 활용한 이벤트 위임 패턴을 예제로 정리했다."
---

## 자식을 클릭했는데 부모의 핸들러가 실행되는 이유

버튼을 클릭했는데 그 버튼을 감싼 `div`에 걸어둔 클릭 핸들러까지 실행되는 것을 보고 당황하는 경우가 있다. 이는 버그가 아니라 **이벤트 버블링(event bubbling)** 때문이다. 어떤 요소에서 이벤트가 발생하면, 그 이벤트는 부모 → 조부모 → ... 순으로 위로 전파된다. 물방울이 아래에서 위로 올라오는 것처럼 보인다고 해서 버블링이라 부른다.

## 버블링의 흐름

```text
<div id="parent">        <- 3. 여기까지 이벤트가 올라온다
  <button id="child">    <- 1. 여기를 클릭하면
    클릭
  </button>              <- 2. 이벤트가 위로 전파되며
</div>

button 클릭 -> button의 핸들러 실행 -> parent의 핸들러도 실행
```

부모 요소에 클릭 핸들러가 있으면, 자식을 클릭해도 그 핸들러가 실행된다. 이걸 막고 싶으면 `event.stopPropagation()`으로 전파를 멈출 수 있다.

## 버블링을 활용한 이벤트 위임

버블링은 단점이 아니라 오히려 유용하게 쓸 수 있다. 리스트 항목 100개에 각각 클릭 핸들러를 다는 대신, **부모 하나에만 핸들러를 달고 어떤 자식이 클릭됐는지 판별**하는 것이 이벤트 위임이다.

```javascript
// 나쁜 방법: 항목마다 핸들러 100개
document.querySelectorAll('.item').forEach(item => {
  item.addEventListener('click', handleClick);
});

// 좋은 방법: 부모에 하나만 (이벤트 위임)
document.querySelector('.list').addEventListener('click', (e) => {
  const item = e.target.closest('.item');
  if (item) {
    console.log('클릭된 항목:', item.dataset.id);
  }
});
```

## 이벤트 위임의 장점

| 장점 | 설명 |
|---|---|
| 성능 | 핸들러 하나로 수많은 자식을 처리 |
| 동적 요소 대응 | 나중에 추가된 항목도 자동으로 처리됨 |
| 메모리 절약 | 핸들러 수가 적어 메모리 사용 감소 |

`e.target`은 실제로 클릭된 요소를, `e.currentTarget`은 핸들러가 달린 요소(부모)를 가리킨다. 이 둘의 차이를 알면 이벤트 위임을 정확히 쓸 수 있다.

## 실무 포인트

- **동적으로 추가되는 요소에는 이벤트 위임이 거의 필수다.** AJAX로 나중에 그려지는 목록 항목에 직접 핸들러를 달면, 나중에 추가된 항목에는 핸들러가 없다. 부모에 위임해두면 언제 추가된 항목이든 자동으로 처리된다.
- **`stopPropagation()`을 습관적으로 쓰지 마라.** 버블링을 막으면 그 위에서 이벤트 위임으로 처리하려던 로직이 동작하지 않을 수 있다. 정말 전파를 막아야 하는 경우에만 신중히 써야 한다.
- **`e.target.closest()`로 정확한 대상을 찾아라.** 클릭된 것이 자식 안의 아이콘일 수도 있으므로, `closest('.item')`으로 실제 처리할 요소를 찾아 올라가는 것이 안전하다.

## 마무리 요약

- 이벤트 버블링은 이벤트가 발생 요소에서 부모로 위로 전파되는 현상이다.
- 이벤트 위임은 버블링을 이용해 부모 하나에만 핸들러를 달고 어떤 자식이 클릭됐는지 판별하는 패턴이다.
- 동적 요소 대응과 성능 측면에서 이벤트 위임이 유리하며, `stopPropagation()` 남용은 피해야 한다.

## 참고 자료

- [MDN - 이벤트 버블링과 캡처링](https://developer.mozilla.org/ko/docs/Learn/JavaScript/Building_blocks/Events)
- [javascript.info - 이벤트 위임](https://ko.javascript.info/event-delegation)
