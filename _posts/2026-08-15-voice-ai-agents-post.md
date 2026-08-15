---
layout: single
title: "다시 돌아온 음성 AI — Siri 재편과 에이전트 전쟁의 시작"
date: 2026-08-15 16:50:00 +0530
categories: ai
tags: ["voice-ai", "siri", "speech-to-text", "realtime", "ai-agent"]
toc: true
toc_sticky: true
excerpt: "구글 에이전트가 매장에 전화를 걸고 Siri가 재구성되는 등, 음성 인터페이스가 텍스트 기반 에이전트를 넘어 새로운 경쟁 전선으로 떠오르고 있다."
---

## 왜 지금 다시 음성인가

최근 몇 달 사이 음성 기반 AI 에이전트를 둘러싼 움직임이 눈에 띄게 늘고 있다. 구글의 에이전트가 실제 매장에 전화를 걸어 예약이나 재고 확인 같은 용무를 대신 처리하는 시연이 화제가 됐고, 애플은 Siri를 대규모로 재구성하고 있다는 보도가 이어지고 있다. 동시에 음성 AI 스타트업들의 펀딩 규모도 눈에 띄게 커지는 분위기다.

지금까지 AI 에이전트 논의의 중심은 텍스트였다. 챗봇 인터페이스, 함수 호출, MCP 같은 도구 연동 프로토콜 모두 텍스트 턴 교환을 전제로 설계됐다. 그런데 실제 사람들이 일상에서 가장 자연스럽게 쓰는 인터페이스는 여전히 말이다. 전화로 예약하고, 운전 중에 질문하고, 손이 자유롭지 않을 때 명령을 내리는 상황에서는 텍스트보다 음성이 압도적으로 편하다.

이 흐름이 다시 주목받는 이유는 단순한 유행이 아니라 기술적 조건이 어느 정도 갖춰졌기 때문이다. 실시간 스트리밍 음성 인식(STT)과 저지연 음성 합성(TTS), 그리고 이를 하나의 세션으로 묶는 실시간 API들이 실용적인 수준에 이르면서, "듣고-생각하고-말하는" 에이전트를 만드는 진입 장벽이 눈에 띄게 낮아졌다.

## 텍스트 에이전트 vs 음성 에이전트

같은 LLM을 백엔드로 쓰더라도 음성 인터페이스는 텍스트 인터페이스와 요구사항이 근본적으로 다르다.

| 구분 | 텍스트 에이전트 | 음성 에이전트 |
|---|---|---|
| 지연시간 허용치 | 수 초도 무방 | 수백 ms 이내 아니면 대화가 어색해짐 |
| 턴테이킹 | 명시적(엔터, 전송 버튼) | 암묵적(침묵, 억양, 끼어들기 감지 필요) |
| 오류 복구 | 스크롤해서 재확인 가능 | 되돌릴 수 없어 즉시 자연스럽게 정정해야 함 |
| 입력 형태 | 완결된 문장 단위 | 스트리밍 중 끊긴 발화, 잡음 포함 |
| 상태 표시 | 로딩 스피너 등 시각적 피드백 가능 | 침묵 자체가 신호가 되어 버벅임처럼 느껴짐 |

## 음성 에이전트의 핵심 난제

**지연시간(latency)** 이 가장 먼저 부딪히는 벽이다. 사람 사이의 자연스러운 대화는 응답까지 대략 200~300ms 안팎으로 여겨지는데, STT로 텍스트를 뽑고 LLM 추론을 거쳐 TTS로 다시 음성을 만드는 파이프라인 전체를 그 안에 욱여넣는 것은 쉽지 않다. 이 때문에 최근에는 STT→LLM→TTS를 순차로 잇는 대신, 오디오를 직접 다루는 음성-음성(speech-to-speech) 모델이나 부분 결과를 먼저 흘려보내는 스트리밍 구조가 함께 시도되고 있다.

**턴테이킹(turn-taking)** 도 만만치 않다. 사용자가 말을 끝냈는지, 잠시 생각 중인지, 끼어들려는 것인지를 침묵 길이만으로 판단하면 오작동이 잦다. 실제 서비스들은 억양, 발화 리듬, 문맥까지 함께 보는 턴 감지 로직을 두고, 사용자가 에이전트 발화 중간에 끼어드는 바지인(barge-in) 상황을 처리하는 로직을 별도로 구현한다.

**실시간 스트리밍 STT/TTS** 자체도 텍스트 API와는 다른 설계를 요구한다. 오디오를 청크 단위로 계속 흘려보내면서 중간 결과(interim transcript)를 갱신하고, 최종 확정(final transcript) 시점을 판단해야 하며, 네트워크 지연이나 패킷 손실에도 대화가 끊기지 않도록 버퍼링·재연결 전략을 신경 써야 한다.

## 코드 예제

실시간 음성 세션은 대체로 WebSocket 기반으로 오디오 청크를 스트리밍하고 이벤트를 주고받는 형태다. 개념을 보여주는 의사코드 예시다.

```python
import asyncio
import websockets
import json

async def voice_agent_session(ws_url: str, api_key: str):
    async with websockets.connect(
        ws_url,
        extra_headers={"Authorization": f"Bearer {api_key}"}
    ) as ws:
        # 세션 초기화: 음성, 턴 감지 방식 등 설정
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": "default",
                "turn_detection": {"type": "server_vad", "threshold": 0.5},
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
            }
        }))

        async def send_audio_chunks(audio_stream):
            async for chunk in audio_stream:
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": chunk,  # base64 인코딩된 PCM 청크
                }))

        async def receive_events():
            async for message in ws:
                event = json.loads(message)
                if event["type"] == "response.audio.delta":
                    # 부분 오디오를 즉시 재생 큐에 흘려보냄
                    play_audio_chunk(event["delta"])
                elif event["type"] == "input_audio_buffer.speech_started":
                    # 사용자가 말을 시작 -> 에이전트 발화 중이면 즉시 중단(barge-in)
                    stop_playback()

        await asyncio.gather(
            send_audio_chunks(microphone_stream()),
            receive_events(),
        )
```

턴 감지를 서버 VAD(음성 활동 감지)에 맡기고, `speech_started` 이벤트가 오면 재생 중이던 에이전트 음성을 즉시 멈추는 바지인 처리가 실무에서 자주 빠지는 부분이다.

## 실무 포인트와 주의사항

- **엔드투엔드 지연 측정을 습관화한다.** 마이크 입력부터 스피커 출력까지 전체 왕복 시간을 로깅해두지 않으면, 어느 구간(네트워크, STT, LLM, TTS)이 병목인지 나중에 알기 어렵다.
- **부분 실패를 가정한 설계를 한다.** 네트워크가 잠깐 끊기거나 STT가 잘못 알아들었을 때, 사용자에게 "다시 말씀해 주시겠어요?" 같은 자연스러운 복구 발화를 준비해두는 편이 무음이나 오류음보다 낫다.
- **개인정보·음성 데이터 처리 정책을 미리 정한다.** 통화·음성 녹음은 텍스트보다 민감하게 다뤄지는 경우가 많으므로, 저장 여부와 보존 기간을 서비스 설계 초기에 명확히 해두는 편이 안전하다.
- **비용 구조를 텍스트 에이전트와 다르게 본다.** 음성 스트리밍은 세션 유지 시간, 오디오 처리량 기준으로 과금되는 경우가 많아 텍스트 토큰 기준 비용 모델과 다르게 접근해야 한다.

## 3줄 요약

- 텍스트 중심이던 AI 에이전트 경쟁이 실시간 음성 인터페이스로 확장되고 있으며, Siri 재편이나 매장 통화 자동화 같은 사례가 이를 보여준다.
- 음성 에이전트는 지연시간, 턴테이킹, 실시간 스트리밍 STT/TTS라는 텍스트 에이전트에 없던 난제를 안고 있어 별도의 설계가 필요하다.
- 개발자 입장에서는 엔드투엔드 지연 측정, 부분 실패 복구, 음성 데이터 정책, 비용 구조 차이를 미리 챙기는 것이 실무 도입의 핵심이다.

## 참고 자료

- [OpenAI Realtime API 문서](https://platform.openai.com/docs/guides/realtime)
- [Google Cloud Speech-to-Text 스트리밍 인식 문서](https://cloud.google.com/speech-to-text/docs/streaming-recognize)
- [Apple Developer - Siri and Voice](https://developer.apple.com/design/human-interface-guidelines/siri)
- [W3C Web Speech API 명세](https://wicg.github.io/speech-api/)
