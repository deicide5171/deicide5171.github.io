---
layout: single
title: "Web Speech API로 음성 인식·음성 합성 기능 붙이기 — 서버 없이 시작하기"
date: 2026-09-21 12:30:00 +0530
categories: frontend
tags: ["webspeechapi", "음성인식", "speechrecognition", "speechsynthesis", "브라우저api"]
toc: true
toc_sticky: true
excerpt: "음성 검색이나 텍스트 읽어주기 기능을 붙이려 할 때 외부 STT/TTS API 연동부터 떠올리기 쉽지만, 브라우저 내장 Web Speech API로 별도 서버 비용 없이 프로토타입을 만드는 방법을 정리했다."
---

## 왜 항상 외부 API부터 떠올리게 되나

"검색창에 마이크 버튼을 달아서 말로 검색하게 하자", "글을 소리 내어 읽어주는 기능을 넣자" 같은 요구사항이 나오면, 대부분 Google Cloud Speech-to-Text나 OpenAI Whisper 같은 외부 API 연동부터 검토한다. 실제로 정확도와 다국어 지원이 중요한 프로덕션급 기능이라면 이런 전용 서비스가 맞다. 하지만 프로토타입 단계이거나, 브라우저가 지원하는 정도의 정확도로 충분한 보조 기능이라면, 서버 비용과 지연 없이 브라우저에 이미 내장된 **Web Speech API**만으로도 상당 부분을 구현할 수 있다.

Web Speech API는 두 개의 독립된 인터페이스로 구성된다. **SpeechRecognition**(음성을 텍스트로, STT)과 **SpeechSynthesis**(텍스트를 음성으로, TTS)다.

## 잘못된 접근: 두 API를 혼동하거나 브라우저 지원을 확인하지 않기

Web Speech API를 처음 접하면 흔히 두 가지 실수를 한다. 하나는 SpeechRecognition과 SpeechSynthesis를 같은 것으로 착각해 코드를 뒤섞는 것이고, 다른 하나는 브라우저 지원 여부를 확인하지 않고 바로 배포하는 것이다.

```javascript
// 잘못된 예: 지원 여부 확인 없이 바로 사용
const recognition = new SpeechRecognition();  // Firefox 등에서 undefined 에러
recognition.start();
```

`SpeechRecognition`은 표준화 과정에서 오랫동안 `webkitSpeechRecognition`이라는 접두사가 붙은 채로만 널리 지원되어 왔고, 브라우저마다 지원 수준이 크게 다르다. 이 차이를 확인하지 않고 그대로 배포하면 특정 브라우저 사용자에게는 기능 자체가 조용히 깨진다.

## 올바른 접근: 기능 감지와 폴백 준비

**1) 음성 인식(STT)**

```javascript
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
  showFallbackUI(); // 마이크 버튼 숨기고 텍스트 입력만 제공
} else {
  const recognition = new SpeechRecognition();
  recognition.lang = 'ko-KR';
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    const transcript = event.results[event.results.length - 1][0].transcript;
    searchInput.value = transcript;
  };

  recognition.onerror = (event) => {
    console.error('음성 인식 오류:', event.error);
  };

  micButton.addEventListener('click', () => recognition.start());
}
```

`lang` 속성으로 인식 언어를 명시하는 것이 중요하다. 이 값을 생략하면 브라우저 UI 언어를 기준으로 추측하는데, 한국어 사용자가 영어 UI 브라우저를 쓰는 경우 인식률이 크게 떨어진다. `interimResults: true`를 켜면 사용자가 말하는 도중에도 중간 결과를 실시간으로 받아 UI에 반영할 수 있어 체감 반응성이 좋아진다.

**2) 음성 합성(TTS)**

```javascript
function speak(text) {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'ko-KR';
  utterance.rate = 1.0;

  const voices = speechSynthesis.getVoices();
  const koreanVoice = voices.find(v => v.lang === 'ko-KR');
  if (koreanVoice) utterance.voice = koreanVoice;

  speechSynthesis.speak(utterance);
}
```

`speechSynthesis.getVoices()`는 페이지 로드 직후 호출하면 빈 배열을 반환하는 경우가 많다. 음성 목록이 비동기로 로드되기 때문인데, `voiceschanged` 이벤트를 구독해 목록이 실제로 채워진 뒤에 원하는 목소리를 찾도록 처리해야 한다.

```javascript
speechSynthesis.onvoiceschanged = () => {
  const voices = speechSynthesis.getVoices();
  // 이 시점에는 목록이 채워져 있다
};
```

## 브라우저 내장 API vs 외부 STT/TTS 서비스

| 항목 | Web Speech API | 외부 STT/TTS 서비스 |
|---|---|---|
| 비용 | 무료(브라우저 내장) | 사용량 기반 과금 |
| 정확도 | 브라우저·OS에 따라 편차 큼 | 상대적으로 안정적, 커스텀 튜닝 가능 |
| 오프라인 지원 | 브라우저·OS에 따라 다름 | 대부분 네트워크 필요 |
| 서버 인프라 | 불필요 | STT/TTS 서버 또는 API 키 관리 필요 |
| 브라우저 호환성 | 브라우저마다 지원 격차 큼 | 클라이언트 구현에 좌우되지 않음 |

가벼운 보조 기능이나 프로토타입에는 Web Speech API가 빠르고 비용이 들지 않지만, 다국어 정확도나 커스텀 도메인 용어 인식이 중요한 프로덕션 기능이라면 외부 서비스로 전환하는 것이 결국 더 안정적이다.

## 실무 포인트

- **마이크 권한 요청은 사용자 제스처(클릭)와 함께 이뤄져야 한다.** 페이지 로드와 동시에 자동으로 `recognition.start()`를 호출하면 대부분의 브라우저가 권한 요청을 차단한다.
- **`onend` 이벤트로 인식 세션 종료를 감지하고 UI 상태를 되돌려라.** 사용자가 말을 멈추면 자동으로 세션이 끝나므로, 마이크 버튼 활성 표시를 계속 켜둔 채로 방치하지 않도록 처리한다.
- **HTTPS 환경에서만 대부분 동작한다.** `getUserMedia` 기반 마이크 접근과 마찬가지로, 로컬 개발(`localhost`)이 아닌 배포 환경에서는 HTTPS가 필수다.
- **긴 텍스트를 TTS로 읽힐 때는 문장 단위로 끊어서 큐에 넣는 것이 안전하다.** 매우 긴 문자열을 통째로 `speak()`에 넘기면 일부 브라우저에서 중간에 끊기거나 멈추는 버그가 보고된 적이 있다.

## 마무리 요약

- Web Speech API는 SpeechRecognition(STT)과 SpeechSynthesis(TTS)로 구성되며, 브라우저 내장 기능이라 별도 서버 비용 없이 프로토타입을 빠르게 만들 수 있다.
- 브라우저 지원 격차가 크므로 기능 감지와 폴백 UI, `lang` 속성 명시가 필수다.
- 정확도와 안정성이 중요한 프로덕션 기능은 결국 외부 STT/TTS 서비스로 전환을 검토해야 한다.

## 참고 자료

- [MDN - Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [MDN - SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
