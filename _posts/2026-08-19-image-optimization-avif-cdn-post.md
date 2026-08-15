---
layout: single
title: "AVIF·WebP로 이미지 용량 줄이기 — CDN 이미지 파이프라인 설계 전략"
date: 2026-08-19 13:30:00 +0530
categories: frontend
tags: ["avif", "webp", "cdn", "이미지최적화", "반응형이미지"]
toc: true
toc_sticky: true
excerpt: "페이지 용량의 절반 이상을 차지하는 이미지를 AVIF/WebP 포맷과 CDN 온더플라이 변환 파이프라인으로 줄이는 실전 전략을 정리한다."
---

## 왜 지금 이미지 최적화인가

많은 웹페이지에서 전체 전송 용량 중 이미지가 차지하는 비중은 여전히 절반 안팎으로 가장 크다. JS 번들을 아무리 쪼개고 캐싱을 잘 해도, 히어로 이미지 하나가 수 MB짜리 원본 JPEG로 나가면 LCP는 쉽게 무너진다. 다행히 최근 몇 년 사이 이 문제를 풀 수 있는 도구가 크게 늘었다. **AVIF**는 동일 화질 기준으로 JPEG 대비 상당한 용량 절감을 보여주는 코덱으로 주요 브라우저 대부분에서 지원되고 있고, **WebP**는 그보다 앞서 사실상 표준급 대체 포맷으로 자리 잡았다.

동시에 Cloudflare Images, Cloudinary, imgix, Vercel/Next.js Image Optimization 같은 **CDN 이미지 파이프라인** 서비스들이 "원본 하나만 올려두면 요청 시점에 최적 포맷으로 변환해 서빙"하는 방식을 기본값으로 밀어주면서, 직접 포맷별 파일을 미리 여러 개 만들어 둘 필요가 줄었다. 문제는 이런 자동화 뒤에서 실제로 어떤 판단(포맷 선택, 캐시 키, fallback)이 일어나는지 모르면, 변환 비용 폭증이나 캐시 미스 같은 함정에 부딪히기 쉽다는 점이다. 이 글은 이미지 포맷 선택 기준과 CDN 파이프라인 구조 자체에 집중한다.

## 핵심 개념 1 — 이미지 포맷 비교

| 포맷 | 압축 특성 | 브라우저 지원 | 인코딩 비용 | 적합한 상황 |
|---|---|---|---|---|
| JPEG | 손실 압축, 오래된 표준 | 사실상 전부 | 낮음 | 최종 fallback |
| WebP | JPEG 대비 용량 절감, 무손실도 지원 | 주요 브라우저 광범위 지원 | 중간 | 범용 대체 포맷 |
| AVIF | WebP보다 더 나은 압축률(특히 저비트레이트) | 최신 브라우저 위주(계속 확대 중) | 높음(인코딩 느림) | 정적·캐시 가능한 이미지 |

AVIF는 압축률이 좋은 대신 인코딩 연산이 무거워서, 요청마다 실시간으로 인코딩하면 오히려 응답 지연이나 서버 비용 증가로 이어질 수 있다. 그래서 실무에서는 "처음 요청 시 한 번만 변환해 엣지에 캐시하고, 이후 요청은 캐시에서 서빙"하는 구조를 쓴다. 반대로 자주 바뀌는 사용자 생성 이미지(썸네일 등)라면 WebP처럼 인코딩이 가벼운 포맷을 우선 검토할 만하다.

## 핵심 개념 2 — 포맷 협상과 반응형 서빙

브라우저는 요청 시 `Accept: image/avif,image/webp,image/*,*/*` 형태로 자신이 지원하는 포맷을 알려준다. 서버(또는 CDN)는 이 헤더를 보고 지원 우선순위(AVIF > WebP > JPEG)에 따라 실제로 내려줄 파일을 결정한다. 이 협상을 마크업 레벨에서 명시적으로 하고 싶다면 `<picture>` 요소로 포맷별 소스를 나열하면 되고, CDN이 자동 협상을 지원한다면 `<img>` 하나만 두고 CDN에 위임할 수도 있다.

여기에 화면 크기별로 다른 해상도를 내려주는 반응형 이미지(`srcset`/`sizes`)까지 결합하면, "포맷 × 너비" 조합만큼 변형(variant)이 늘어난다. 이 조합 전체를 미리 생성해두는 대신, 첫 요청 시 온더플라이로 변환하고 엣지에 캐시하는 방식이 저장 공간과 빌드 시간 양쪽에서 유리하다.

## 예제 1 — `<picture>`로 포맷 fallback 명시하기

```html
<picture>
  <source type="image/avif" srcset="/img/hero-800.avif 800w, /img/hero-1600.avif 1600w">
  <source type="image/webp" srcset="/img/hero-800.webp 800w, /img/hero-1600.webp 1600w">
  <img src="/img/hero-800.jpg" srcset="/img/hero-800.jpg 800w, /img/hero-1600.jpg 1600w"
       sizes="(max-width: 600px) 100vw, 800px"
       alt="제품 히어로 이미지" width="800" height="450" loading="eager" fetchpriority="high">
</picture>
```

브라우저는 `<source>`를 위에서부터 검사해 지원하는 첫 번째 포맷을 선택하고, 아무것도 지원하지 않으면 마지막 `<img>`로 자연스럽게 떨어진다. LCP 후보가 되는 이미지라면 `loading="lazy"` 대신 `fetchpriority="high"`로 우선순위를 올리는 편이 낫다.

## 예제 2 — CDN 온더플라이 변환 요청(예시 규칙)

```
# 원본 1장 → 요청 파라미터로 포맷/너비/품질 지정
GET /cdn-cgi/image/format=auto,width=800,quality=80/uploads/hero.jpg
```

`format=auto`는 CDN이 요청 브라우저의 Accept 헤더를 보고 AVIF/WebP/JPEG 중 적합한 포맷을 골라주는 옵션이다(구체적 파라미터명은 CDN 제품마다 다르므로 반드시 해당 서비스 공식 문서를 확인해야 한다). 이 방식의 핵심은 **원본은 하나만 관리하고, 변형은 요청 시점에 만들어 캐시한다**는 것이다.

## 실무 포인트

- **이미 압축된 이미지를 재압축하지 않는다.** 원본이 저품질 JPEG인데 AVIF로 다시 인코딩해도 화질은 개선되지 않고 아티팩트만 늘 수 있다. 가능하면 무손실에 가까운 원본을 별도 보관한다.
- **캐시 키에 포맷과 너비를 반드시 포함한다.** 그렇지 않으면 서로 다른 변형이 같은 캐시 엔트리를 덮어써 엉뚱한 이미지가 나가는 사고로 이어질 수 있다.
- **AVIF 인코딩 시간을 실시간 경로에서 피한다.** 트래픽이 몰리는 시점에 캐시 미스가 겹치면 변환 큐가 밀려 응답이 느려질 수 있으므로, 신규 이미지 업로드 시 주요 변형을 미리 워밍(warm)해두는 것도 방법이다.
- **외부 이미지를 코드에서 직접 링크(핫링크)하지 않는다.** 저작권·트래픽 비용 문제가 있으니 반드시 자체 CDN이나 스토리지를 경유해 서빙한다.
- **LCP 이미지는 지연 로딩 대상에서 제외한다.** `loading="lazy"`를 뷰포트 안 첫 화면 이미지에 걸면 오히려 로딩이 늦어질 수 있다.

## 3줄 요약

- AVIF는 WebP보다 압축률이 좋지만 인코딩이 무겁고, WebP는 그 중간 지점의 범용 대체 포맷이라 각각의 트레이드오프를 이해하고 골라야 한다.
- `<picture>` 요소나 CDN의 `format=auto` 방식으로 브라우저 지원 포맷을 자동 협상하면 포맷별 파일을 수작업으로 관리하지 않아도 된다.
- 온더플라이 변환 + 엣지 캐시 구조에서는 캐시 키에 포맷·너비를 포함하고, 첫 요청 지연을 줄이기 위한 워밍 전략을 함께 고려해야 한다.

## 참고 자료

- [web.dev — AVIF image format](https://web.dev/articles/compress-images-avif)
- [MDN — Responsive images (picture, srcset)](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Responsive_images)
- [Cloudflare Images — Image Resizing 문서](https://developers.cloudflare.com/images/)
