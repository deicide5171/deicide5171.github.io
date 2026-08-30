---
layout: single
title: "WebAssembly로 프론트엔드 성능 끌어올리기 — WASM과 JS 상호운용 내부 동작"
date: 2026-09-25 12:30:00 +0530
categories: frontend
tags: ["WebAssembly", "WASM", "프론트엔드성능", "메모리모델", "JS상호운용"]
toc: true
toc_sticky: true
excerpt: "이미지 편집이나 대용량 데이터 파싱처럼 JS만으로는 버거운 연산을 브라우저에서 처리해야 할 때, WebAssembly가 왜 JS보다 빠르게 실행되는지와 JS-WASM 경계를 넘나들 때 실제로 어떤 비용이 발생하는지 내부 동작을 정리했다."
---

## 왜 지금 프론트엔드에서 WebAssembly를 다시 봐야 하는가

이미지·비디오 편집, PDF 렌더링, 대용량 CSV 파싱, 암호화 연산처럼 CPU 집약적인 작업을 브라우저에서 직접 처리해야 하는 웹 애플리케이션이 늘고 있다. Figma의 캔버스 렌더링, Photoshop 웹 버전, ffmpeg.wasm 같은 사례가 이미 프로덕션에서 검증됐다. 이런 작업을 순수 JS로 구현하면 JIT 컴파일이 워밍업될 때까지의 지연, 동적 타입 체크 오버헤드, 예측 불가능한 GC 일시정지 때문에 일관된 성능을 내기 어렵다. WebAssembly(WASM)는 C/C++/Rust 같은 언어로 작성한 코드를 미리 컴파일된 바이트코드 형태로 브라우저에 전달해, JS 엔진의 인터프리트·최적화 과정을 건너뛰고 거의 네이티브에 가까운 속도로 실행할 수 있게 한다. 다만 WASM을 프론트엔드에 도입할 때 실무자들이 가장 많이 오해하는 지점은 "WASM이 항상 JS보다 빠르다"는 단순화인데, 실제로는 JS와 WASM 사이를 오가는 경계(boundary)에서 발생하는 비용을 이해해야 언제 도입할 가치가 있는지 판단할 수 있다.

## 핵심 개념 1 — WASM이 빠른 이유: 정적 타입과 선형 메모리

WASM이 JS보다 예측 가능하게 빠른 근본 이유는 두 가지다. 첫째, WASM은 애초에 정적 타입 스택 기반 명령어 집합으로 설계되어, JS 엔진이 런타임에 값의 타입을 추측하고 최적화 경로를 다시 컴파일하는(deoptimization) 과정 자체가 필요 없다. 둘째, WASM은 자신만의 "선형 메모리(linear memory)"라는 연속된 바이트 배열 위에서 동작한다. 이 메모리는 JS의 객체 그래프처럼 흩어진 참조 구조가 아니라 C의 배열처럼 연속된 공간이라, CPU 캐시 지역성이 뛰어나고 GC의 개입 없이 결정적으로 동작한다. 이 두 특성 덕분에 반복적인 수치 연산이나 메모리 접근 패턴이 일정한 작업에서 WASM은 JS 대비 몇 배의 성능 이득을 보인다.

## 핵심 개념 2 — JS-WASM 경계를 넘는 비용: 직렬화와 데이터 복사

WASM의 선형 메모리는 JS의 객체·문자열·배열과 직접 호환되지 않는다. JS에서 WASM 함수를 호출할 때 문자열이나 복잡한 객체를 넘기려면, 그 데이터를 WASM의 선형 메모리 안에 있는 바이트 형태로 인코딩해 복사해 넣어야 하고, 결과를 받을 때도 마찬가지로 역직렬화 과정을 거쳐야 한다. 이 경계를 넘는 호출이 잦고 데이터가 클수록 이 복사·직렬화 비용이 누적되어, 실제 계산 자체는 WASM이 훨씬 빠른데도 전체 처리 시간은 JS 구현과 별 차이가 없거나 오히려 느려지는 역설적인 상황이 생긴다. 그래서 WASM 도입의 핵심 설계 원칙은 "경계를 최대한 적게, 한 번에 큰 덩어리로 넘어라"는 것이다. 예를 들어 이미지를 픽셀 단위로 매번 JS와 주고받는 대신, 이미지 버퍼 전체를 한 번에 WASM 메모리로 복사해 넣고 그 안에서 모든 픽셀 연산을 끝낸 뒤 결과 버퍼 하나만 다시 꺼내오는 방식이 훨씬 효율적이다.

| 항목 | 순수 JS | WebAssembly |
|---|---|---|
| 실행 방식 | JIT 컴파일 + 인터프리트 | 사전 컴파일된 바이트코드 |
| 메모리 모델 | 객체 그래프, GC 관리 | 선형 메모리(연속 바이트 배열) |
| 타입 시스템 | 동적 타입, 런타임 추론 | 정적 타입 |
| DOM 접근 | 직접 접근 가능 | 불가능(JS 경유 필수) |
| 데이터 전달 비용 | 없음(같은 힙) | 경계마다 복사·직렬화 필요 |

## 코드 예제 — 큰 덩어리로 경계를 넘기는 패턴

```javascript
// 나쁜 예: 픽셀마다 WASM 함수를 호출 — 경계 비용이 누적된다
for (let i = 0; i < pixels.length; i++) {
  result[i] = wasmModule.processPixel(pixels[i]); // 호출마다 오버헤드
}

// 좋은 예: 버퍼 전체를 한 번에 WASM 선형 메모리로 복사
const { memory, process_buffer } = wasmModule.instance.exports;
const inputPtr = wasmModule.instance.exports.alloc(pixels.length);
new Uint8Array(memory.buffer, inputPtr, pixels.length).set(pixels);

process_buffer(inputPtr, pixels.length); // 단 한 번의 경계 호출

const result = new Uint8Array(memory.buffer, inputPtr, pixels.length).slice();
```

```rust
// Rust로 작성한 WASM 함수 예시 — 선형 메모리 위에서 직접 반복 처리
#[no_mangle]
pub extern "C" fn process_buffer(ptr: *mut u8, len: usize) {
    let slice = unsafe { std::slice::from_raw_parts_mut(ptr, len) };
    for byte in slice.iter_mut() {
        *byte = 255 - *byte; // 예: 색상 반전
    }
}
```

## 실무 포인트

- **DOM 조작이 필요한 로직은 WASM으로 옮기지 마라.** WASM은 DOM에 직접 접근할 수 없어 결국 JS를 경유해야 하므로, DOM 업데이트가 잦은 UI 로직은 경계 비용만 늘리는 역효과가 난다. WASM은 순수 연산 로직에만 국한하는 것이 원칙이다.
- **번들 크기와 초기 로딩 비용을 반드시 측정하라.** .wasm 파일 자체의 다운로드·컴파일·인스턴스화 시간이 있으므로, 작은 연산 하나를 위해 수백 KB짜리 WASM 모듈을 로드하면 오히려 손해다. 반복 실행되는 무거운 연산에만 투입 가치가 있다.
- **Rust의 wasm-bindgen이나 AssemblyScript 같은 도구가 직렬화 보일러플레이트를 자동 생성해주지만, 내부적으로 여전히 복사가 일어난다는 사실은 변하지 않는다.** 편의 도구를 쓰더라도 경계를 넘는 횟수와 데이터 크기는 개발자가 직접 설계 관점에서 통제해야 한다.

## 마무리 요약

- WebAssembly는 정적 타입과 선형 메모리 덕분에 반복 수치 연산에서 JS보다 예측 가능하고 빠른 성능을 낸다.
- JS와 WASM 사이 경계를 넘을 때마다 데이터 직렬화·복사 비용이 발생하므로, 잦은 소량 호출보다 드문 대량 호출로 설계해야 실제 이득을 볼 수 있다.
- DOM 조작 로직은 WASM으로 옮기지 말고, 순수 연산 로직에만 투입하는 것이 원칙이다.

## 참고 자료

- [MDN - WebAssembly Concepts](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Concepts)
- [Rust and WebAssembly - wasm-bindgen](https://rustwasm.github.io/docs/wasm-bindgen/)
