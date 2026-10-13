---
layout: single
title: "지도 정보를 에이전트에 붙이는 두 가지 길 — Grounding with Google Maps vs MCP 툴콜"
date: 2026-10-13 12:45:00 +0530
categories: gis
tags: ["지리공간ai", "groundingwithgooglemaps", "mcp", "지오코딩", "장소데이터"]
toc: true
toc_sticky: true
excerpt: "'근처 맛집을 알려주세요'라는 요구에 LLM이 존재하지 않는 가게 이름과 주소를 지어내는 문제는, 지도 데이터를 어떻게 모델에 연결할 것인가의 설계 문제다. Gemini API의 Grounding with Google Maps와 ArcGIS·자체 PostGIS MCP 서버라는 두 접근의 구조적 차이와 선택 기준을 정리했다."
---

## 왜 지금 이 판단이 중요한가

"지금 내 주변에서 평점 높은 식당을 추천해주세요." 이 요구를 LLM에게 그대로 던지면 모델은 학습 데이터에 남아 있는 평균적인 지식으로 그럴듯한 이름과 주소를 만들어낸다. 실제로 존재하지 않는 가게 이름, 몇 년 전에 폐업한 곳, 심지어 좌표만 비슷한 엉뚱한 건물의 주소가 섞여 나온다. 위치 기반 응답에서 환각(hallucination)은 다른 분야보다 피해가 크다 — 사용자가 실제로 그 주소로 찾아가기 때문이다.

이 문제를 푸는 방식이 2026년 들어 갈라졌다. 하나는 Google이 Gemini API에 내장한 **Grounding with Google Maps**로, 모델 호출 한 번에 2억 5천만 개 이상의 실제 장소 데이터(주소, 영업시간, 리뷰, 사진)를 자동으로 주입해 응답을 사실에 묶어준다. 다른 하나는 Esri의 ArcGIS MCP나 자체 PostGIS 위에 짠 MCP 서버처럼, 에이전트가 **명시적인 도구 호출**로 지오코딩·공간질의를 직접 실행하는 방식이다. 둘 다 "지도 데이터를 LLM에 붙인다"는 같은 목표를 겨누지만, 작동 방식과 통제권이 완전히 다르다. 빌더가 내려야 할 판단은 "어느 쪽이 더 좋은가"가 아니라 "이 앱이 그라운딩의 자동화를 받아들일 수 있는가, 아니면 데이터 주권과 커스텀 로직이 더 중요한가"다.

## 핵심 개념 — 두 메커니즘은 완전히 다른 층위에서 동작한다

Grounding with Google Maps는 `tools`에 `googleMaps`를 선언하기만 하면 모델이 응답을 생성하는 **도중에** 내부적으로 장소 데이터를 조회해 반영한다. 에이전트 코드 입장에서는 도구 호출 루프가 보이지 않는다 — 모델이 알아서 하고, 결과에는 지도 위젯을 띄울 수 있는 컨텍스트 토큰이 함께 돌아온다. 반면 MCP 방식은 에이전트가 "이 도구를 이 인자로 호출하겠다"는 명시적 결정을 내리고, 결과를 받아 다음 추론에 반영하는 일반적인 도구 호출 루프를 그대로 따른다.

| 구분 | Grounding with Google Maps | MCP 툴콜(ArcGIS MCP / 자체 PostGIS MCP) |
|---|---|---|
| 호출 시점 | 모델 생성 과정에 자동 개입 | 에이전트가 명시적으로 호출 |
| 데이터 출처 | Google 장소 데이터베이스 고정 | 서버 구현에 따라 임의(자체 DB 포함) |
| 커스텀 로직 | 불가(블랙박스) | 공간 연산·필터링 자유롭게 구현 |
| 멀티 모델 호환 | Gemini 계열 전용 | MCP 지원 호스트라면 모델 무관 |
| 통합 난이도 | tools 선언 한 줄 | 서버 구축·배포·인증 필요 |
| 투명성 | 호출 로그를 에이전트가 직접 못 봄 | 모든 호출·결과를 애플리케이션이 제어 |

## 전체 시스템에서의 위치

"근처 맛집 추천" 같은 요구는 입력(사용자 위치·질의) → 장소 데이터 연결 → 모델 추론 → 응답(텍스트+지도)이라는 파이프라인으로 흐른다. 두 접근은 이 흐름에서 "장소 데이터 연결"이 일어나는 지점이 다르다.

<img src="/assets/images/posts/2026-10-13-grounding-google-maps-vs-mcp-tool-calling-1.svg" alt="Grounding with Google Maps는 모델 추론 내부에서 장소 데이터가 주입되고, MCP 방식은 에이전트 루프가 별도 MCP 서버를 명시적으로 호출한 뒤 결과를 추론에 되먹이는 구조 비교도" style="width:100%;">

Grounding 경로에서는 애플리케이션이 Gemini API에 위치 좌표(선택적)와 질의만 넘기면, 장소 조회·랭킹·신뢰도 판단이 모두 Google 쪽 블랙박스 안에서 끝난다. MCP 경로에서는 애플리케이션(또는 에이전트 런타임)이 직접 지오코딩 서버나 PostGIS 공간 질의 서버를 호출하고, 그 결과를 프롬프트에 되먹인 뒤 모델이 최종 응답을 만든다. 전자는 장소 데이터 레이어 전체를 Google에 위임하는 것이고, 후자는 그 레이어를 애플리케이션이 소유하되 구축 비용을 떠안는 것이다.

## 선택의 트레이드오프

**Grounding with Google Maps를 쓰면 좋은 경우**: 여행·로컬 추천처럼 "정확한 영업시간과 리뷰"가 핵심이고, 커스텀 공간 연산(반경 내 폴리곤 교차, 자체 보유 매장 데이터와의 조인)이 필요 없는 소비자 앱. 개발 속도가 최우선이고 Gemini 계열 모델에 이미 종속돼 있다면 추가 인프라 없이 당일 적용이 가능하다.

**MCP 툴콜을 쓰면 좋은 경우**: 자체 매장·재고·배차 데이터처럼 Google이 모르는 사내 데이터를 공간 질의와 결합해야 하거나, 여러 LLM 제공자를 오가며 써야 하거나(모델 종속 회피), 호출 로그를 감사 가능한 형태로 남겨야 하는 B2B·내부 도구 성격의 서비스. ArcGIS MCP는 이미 검증된 지오코딩·라우팅 커버리지를 가져다 쓰고 싶을 때, 자체 PostGIS MCP 서버는 데이터 주권과 세밀한 공간 연산이 중요할 때 택한다.

**쓰면 안 되는 경우**: Grounding은 Google 장소 데이터베이스에 없는 비공개 시설(사내 사무실, 미등록 창고)에는 애초에 적용할 수 없다. MCP 자체 구축은 트래픽이 적고 빠른 검증이 목적인 프로토타입 단계에서는 과한 투자다 — 이 경우 Grounding이나 기존 Places API 직접 호출로 먼저 검증하는 편이 낫다.

## 실무 설정 예제

```python
import google.generativeai as genai

model = genai.GenerativeModel(
    "gemini-2.5-pro",
    tools=[{"google_maps": {}}],  # 그라운딩 도구 선언, 기본값은 off
)

response = model.generate_content(
    "서울 강남역 근처 평점 4.5 이상 디저트 카페 추천해줘",
    tool_config={"google_maps": {"lat": 37.4979, "lng": 127.0276}},
)
# response에는 그라운딩된 텍스트와 지도 위젯용 context_token이 함께 반환된다
```

```sql
-- 자체 PostGIS MCP 서버 쪽 공간 질의 (사내 매장 데이터 + 반경 검색)
SELECT store_name, rating, ST_Distance(geom, ST_MakePoint(127.0276, 37.4979)::geography) AS dist_m
FROM stores
WHERE ST_DWithin(geom, ST_MakePoint(127.0276, 37.4979)::geography, 800)
ORDER BY rating DESC, dist_m ASC
LIMIT 5;
```

## 실제 프로젝트 진행 순서

1. **먼저 "Google이 모르는 데이터가 꼭 필요한가"부터 답한다.** 사내 데이터·커스텀 공간 연산이 전혀 없다면 Grounding을 먼저 붙여보고, 응답 품질과 비용을 실측한다.
2. **Grounding으로 시작했다면 context_token으로 지도 위젯까지 렌더링되는지 검증한다.** 텍스트만 쓰고 위젯을 버리면 Grounding의 절반 가치를 놓치는 것이다.
3. **사내 데이터 결합이 필요해지는 순간 MCP 서버로 분리한다.** 처음부터 자체 MCP를 구축하지 말고, Grounding 결과와 사내 데이터를 애플리케이션 레이어에서 합치는 중간 단계를 먼저 시도해본 뒤 비용이 맞지 않으면 전용 서버로 넘어간다.
4. **MCP로 전환할 때는 ArcGIS MCP 같은 관리형 옵션과 자체 PostGIS 서버 중 커버리지·비용·데이터 주권을 비교해 고른다.** 둘 다 과하면 둘을 병행하는 하이브리드(일반 장소는 Grounding, 사내 매장은 MCP)도 실무에서 흔한 패턴이다.

## 마무리 요약

- Grounding with Google Maps는 모델 추론 내부에서 자동으로 장소 데이터를 주입하는 블랙박스형 접근이고, MCP 툴콜은 에이전트가 명시적으로 호출·제어하는 투명한 접근이다.
- 사내 데이터·멀티 모델 호환·호출 감사가 중요하면 MCP, 개발 속도와 정확한 공개 장소 정보가 중요하면 Grounding을 택한다.
- 두 방식은 배타적이지 않다 — 일반 장소는 Grounding, 사내 데이터는 MCP로 병행하는 하이브리드 설계가 실무에서 흔하다.

## 참고 자료

- [Grounding with Google Maps — Gemini API 공식 문서](https://ai.google.dev/gemini-api/docs/google-maps-grounding)
- [Model Context Protocol 공식 사이트](https://modelcontextprotocol.io)
- [PostGIS 공식 문서 — 공간 질의 함수](https://postgis.net/docs/)
