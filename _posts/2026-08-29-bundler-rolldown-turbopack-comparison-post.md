---
layout: single
title: "번들러 전쟁 2막 — Rolldown, Turbopack, Rspack이 노리는 것"
date: 2026-08-29 12:30:00 +0530
categories: frontend
tags: ["bundler", "rolldown", "turbopack", "rspack", "vite", "build-tools"]
toc: true
toc_sticky: true
excerpt: "esbuild·SWC로 시작된 네이티브 번들러 경쟁이 Rolldown, Turbopack, Rspack으로 이어지는 이유와 각각의 설계 목표·생태계 위치 차이를 정리한다."
---

몇 년 전만 해도 프론트엔드 빌드 성능 이야기는 "webpack이 느리니 esbuild나 SWC로 일부 단계를 대체하자"는 수준이었다. 지금은 상황이 다르다. Vite 생태계의 차기 번들러로 예고된 **Rolldown**, Next.js가 자체 개발 중인 **Turbopack**, ByteDance가 만든 webpack 호환 러스트 번들러 **Rspack**까지, 러스트로 작성된 네이티브 번들러들이 각자 다른 생태계의 기본값 자리를 노리고 있다.

이 셋을 그냥 "빠른 번들러"로 뭉뚱그리면 놓치는 게 많다. 셋은 각각 다른 문제를 풀려고 설계됐고, 그 설계 목표가 API 호환성·증분 빌드 전략·타깃 프레임워크에 그대로 반영돼 있다. 이 글에서는 세 번들러가 무엇을 노리고 있는지, 어떤 상황에서 어떤 선택이 자연스러운지를 정리한다.

## 핵심 개념 1: 같은 러스트, 다른 목표

세 번들러 모두 러스트로 작성돼 JS/TS로 작성된 기존 번들러보다 파싱·변환 단계가 빠르다는 공통점이 있지만, 노리는 자리는 다르다.

- **Rolldown**: Vite 팀(VoidZero)이 만드는 Rollup 호환 번들러로, Vite의 프로덕션 빌드(현재는 Rollup 사용)를 대체해 개발 서버(esbuild/SWC 기반)와 프로덕션 빌드 사이의 도구 이원화를 없애는 것이 목표다. Rollup의 플러그인 API와 최대한 호환되도록 설계돼, 기존 Rollup/Vite 플러그인 생태계를 그대로 흡수하려 한다.
- **Turbopack**: Vercel이 Next.js를 위해 만드는 번들러로, webpack을 대체하는 것이 1차 목표다. 함수 단위 캐싱과 결과 재사용에 특화된 증분 계산 엔진(Turbo Engine) 위에서 동작해, 변경된 부분만 재계산하는 것을 근본 설계로 삼는다.
- **Rspack**: ByteDance가 만든 webpack 호환 번들러로, "webpack 설정과 플러그인을 거의 그대로 두고 속도만 얻는다"는 이행 비용 최소화에 초점을 맞춘다. webpack의 방대한 기존 설정 자산을 재작성 없이 재사용하는 것이 핵심 가치다.

## 핵심 개념 2: 증분 빌드 전략의 차이

세 번들러의 체감 속도 차이는 상당 부분 **증분 빌드(incremental build)를 어떻게 구현했는가**에서 나온다. Turbopack은 "함수 호출과 그 인자를 캐시 키로 삼아, 입력이 바뀌지 않은 함수 호출은 결과를 재사용한다"는 범용 증분 계산 엔진을 기반으로 하기 때문에, 파일 하나를 고쳤을 때 다시 계산해야 하는 범위가 세밀하게 좁혀진다는 것이 설계 의도다. Rspack과 Rolldown은 각각 webpack, Rollup의 기존 아키텍처(모듈 그래프 기반 증분 재컴파일)를 러스트로 재작성하면서 성능을 끌어올리는 접근이라, 증분 전략의 뼈대는 원본 도구와 상대적으로 비슷하게 유지된다.

| 구분 | Rolldown | Turbopack | Rspack |
|---|---|---|---|
| 호환 대상 API | Rollup / Vite 플러그인 | webpack(부분) — 자체 최적화 우선 | webpack 설정·플러그인 |
| 1차 목표 생태계 | Vite | Next.js | 범용(자체 프레임워크 포함) |
| 증분 빌드 전략 | 모듈 그래프 기반(러스트화) | 함수 단위 캐싱 엔진(Turbo Engine) | 모듈 그래프 기반(러스트화) |
| 채택 시 이행 비용 | 낮음(Vite 사용자는 무감) | 중간(Next.js 내장, 설정 노출 적음) | 낮음(webpack 설정 재사용) |
| 개발 주체 | VoidZero(Vite 팀) | Vercel | ByteDance |

## 핵심 개념 3: "빠른 번들러"가 실제로 바꾸는 개발 경험

세 도구가 공통으로 노리는 최종 효과는 콜드 스타트 시간과 HMR(Hot Module Replacement) 반응 속도의 체감 개선이다. 대형 모노레포에서 webpack 기반 개발 서버가 수십 초씩 걸리던 콜드 스타트가 Turbopack이나 Rspack에서는 수 초 단위로 줄어드는 사례가 보고되는데, 이는 파싱·변환을 네이티브 코드로 병렬 처리하는 구조 덕분이다. 다만 이 이득은 프로젝트 규모와 의존성 그래프 복잡도에 따라 편차가 크므로, "무조건 몇 배 빠르다"는 수치를 프로젝트 특성과 무관하게 일반화하기는 어렵다.

또한 세 도구 모두 아직 각 생태계에서 완전한 기본값 자리를 확정 짓지는 않았다. Rolldown은 Vite의 차기 기본 번들러로 예고돼 점진적으로 안정화되는 단계이고, Turbopack은 Next.js 개발 서버에서 우선 적용되며 프로덕션 빌드까지 범위를 넓혀가는 중이다. Rspack은 webpack 호환을 표방하지만 일부 고급 플러그인·로더는 여전히 완전히 동작하지 않을 수 있어, 도입 전 실제 프로젝트의 플러그인 목록으로 호환성을 검증하는 과정이 필요하다.

## 예제: 프로젝트별 마이그레이션 진입점

```bash
# Rspack — 기존 webpack 설정을 최대한 그대로 두고 실행기만 교체
npm install --save-dev @rspack/cli @rspack/core
npx rspack build --config webpack.config.js   # 호환 레이어로 대부분의 설정 그대로 인식

# Vite + Rolldown — 실험적으로 Rollup 대신 Rolldown을 프로덕션 번들러로 사용
npm install --save-dev rolldown-vite
# vite.config.ts에서 별도 alias 없이 rolldown-vite 패키지가 vite를 대체

# Next.js + Turbopack — 개발 서버에 우선 적용
next dev --turbopack
```

각 도구 모두 "설정을 처음부터 새로 짜야 하는" 전면 재작성이 아니라 기존 설정·플러그인 자산 위에서 실행기만 교체하는 방향으로 마이그레이션 경로를 설계하고 있다는 공통점이 있다.

## 실무 포인트

- **플러그인·로더 호환성부터 검증한다**: 세 번들러 모두 "거의 호환"이라는 표현을 쓰지만 완전히 동일하지는 않다. 프로젝트에서 실제로 쓰는 플러그인 목록을 먼저 추려 각 도구의 호환성 문서·이슈 트래커에서 확인하는 것이 순서다.
- **벤치마크 수치보다 자신의 프로젝트로 직접 측정한다**: 공개된 벤치마크는 특정 프로젝트 구조·의존성 그래프를 기준으로 하므로, 실제 개선폭은 모노레포 구조, 코드 분할 전략에 따라 크게 달라진다.
- **안정화 단계를 확인하고 도입한다**: 세 도구 모두 빠르게 발전 중이라 마이너 버전 사이에도 동작 변화가 있을 수 있다. 프로덕션에 바로 적용하기보다 개발 서버부터 먼저 도입해 안정성을 확인하는 단계적 접근이 안전하다.

## 3줄 요약

- Rolldown은 Vite의 개발 서버와 프로덕션 빌드 도구 이원화를 없애려는 Rollup 호환 번들러, Turbopack은 함수 단위 캐싱 엔진으로 Next.js의 webpack을 대체하려는 번들러, Rspack은 webpack 설정·플러그인을 그대로 재사용하는 이행 비용 최소화 번들러다.
- 셋 다 러스트 기반 네이티브 파싱·변환으로 속도를 얻지만 증분 빌드 전략과 겨냥하는 생태계가 다르므로 "가장 빠른 것"이 아니라 "내 프로젝트 스택과 맞는 것"을 골라야 한다.
- 아직 세 도구 모두 발전 단계이므로, 전체 프로덕션 전환보다 개발 서버 단계에서 먼저 검증하는 점진적 도입이 안전하다.

## 참고 자료

- [Rolldown 공식 사이트](https://rolldown.rs/)
- [Turbopack 공식 문서](https://turbo.build/pack)
- [Rspack 공식 문서](https://rspack.dev/)
- [Vite 공식 블로그: Rolldown 로드맵](https://vite.dev/blog/)
