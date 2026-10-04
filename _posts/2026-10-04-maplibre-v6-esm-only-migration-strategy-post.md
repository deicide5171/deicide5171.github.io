---
layout: single
title: "MapLibre GL JS v6, UMD 번들이 사라졌다 — ESM 전환은 지금 해야 하는가"
date: 2026-10-04 12:45:00 +0530
categories: gis
tags: ["maplibre", "esm", "번들러", "마이그레이션", "웹지도"]
toc: true
toc_sticky: true
excerpt: "\"지도 라이브러리 버전만 올려주세요\"라는 요청이 MapLibre GL JS v6에서는 빌드 파이프라인 전체를 흔든다. UMD 번들과 CSP 전용 빌드가 사라지고 ESM 전용 배포로 바뀐 이 메이저 업그레이드를, 지금 당장 올려야 하는지 판단하는 기준과 실제 마이그레이션 순서로 정리했다."
---

## 왜 지금 이 판단이 불거지는가

"지도 라이브러리 버전만 최신으로 올려주세요." 평소라면 `package.json` 한 줄 바꾸고 끝날 요청이다. 그런데 2026년 7월 나온 MapLibre GL JS v6.0.0은 이 한 줄로 끝나지 않는다. v5까지 함께 배포되던 **UMD 번들(`maplibre-gl.js`)과 CSP 전용 빌드가 통째로 사라지고, ESM(`maplibre-gl.mjs`) 하나만 남았다.** `<script src="...maplibre-gl.js">`로 지도를 띄우던 레거시 페이지, 번들러 없이 CDN 스크립트 태그만으로 운영하던 랜딩 페이지, 워커 로딩에 `worker-src blob:`을 맞춰둔 CSP 정책까지 — 겉보기엔 사소한 버전 업이 실제로는 **빌드 파이프라인과 배포 방식 전체를 다시 점검해야 하는 마이그레이션**으로 번진다.

이 요구를 받은 빌더가 가장 먼저 해야 할 일은 코드를 고치는 게 아니라 **"우리 프로젝트가 지금 어떤 방식으로 MapLibre를 불러오고 있는가"를 정확히 진단하는 것**이다. 번들러를 쓰는 SPA인지, 서버 사이드에서 스크립트 태그를 직접 내려주는 레거시 페이지인지, 엄격한 CSP 정책 아래 운영되는 금융·공공 서비스인지에 따라 마이그레이션 난이도가 완전히 달라진다.

## 요구사항을 기술 문제로 번역하기

"버전 올려주세요"는 실제로는 세 가지 서로 다른 질문으로 쪼개진다. 첫째, **지금 번들러(Webpack, Vite, esbuild 등)가 ESM 전용 패키지를 문제없이 처리하는가.** 둘째, **CDN 스크립트 태그로 지도를 띄우는 페이지가 있다면 `type="module"`로 바꿀 수 있는 환경인가.** 셋째, **CSP 정책에서 `worker-src blob:`을 허용해 뒀던 이유가 MapLibre 때문이라면, 이 허용을 걷어내도 괜찮은가.** 이 세 질문에 대한 답이 모두 "그렇다"가 아니라면, v6 업그레이드는 단순 패치가 아니라 **일정과 테스트 계획이 필요한 프로젝트**로 다뤄야 한다.

여기에 더해 WebGL1 지원이 완전히 제거되고 WebGL2가 필수가 됐다는 사실도 확인 대상이다. 운영 중인 서비스의 사용자층에 구형 기기·구형 브라우저 비중이 유의미하게 있다면, v6는 그 사용자층에서 지도가 아예 뜨지 않는 결과로 이어질 수 있다.

## 전체 시스템에서의 위치

<img src="/assets/images/posts/2026-10-04-maplibre-v6-esm-only-migration-strategy-1.svg" alt="빌드 파이프라인에서 번들러 경로와 CDN 스크립트 태그 경로가 MapLibre v6의 ESM 전용 배포와 워커 로딩 방식 변경을 거쳐 최종적으로 WebGL2 렌더링 컨텍스트로 수렴하는 구조도" style="width:100%;">

MapLibre는 지도 애플리케이션 전체 스택에서 **렌더링 레이어 하나**를 차지하지만, 이 레이어를 어떻게 불러오느냐는 그 앞단의 빌드·배포 파이프라인 설계에 그대로 종속된다. 번들러를 쓰는 프로젝트라면 `import { Map } from 'maplibre-gl'` 같은 named import는 이미 ESM 친화적이라 영향이 작다. 반면 기본 import(`import maplibregl from 'maplibre-gl'`)를 쓰고 있었다면 네임스페이스 import(`import * as maplibregl from 'maplibre-gl'`)로 바꿔야 한다. CDN 스크립트 태그 경로는 영향이 가장 크다 — `<script>` 태그 자체를 `type="module"`로 바꾸고, 이 변경이 레거시 브라우저 호환성에 영향을 주는지부터 따져야 한다. 워커 로딩 방식도 바뀐다. v6는 워커를 실제 URL로 로드하므로 CSP의 `worker-src blob:` 허용이 더 이상 필요 없어지는데, 이는 보안 정책을 오히려 더 엄격하게 좁힐 기회이기도 하다.

## 선택의 트레이드오프 — 지금 올릴까, 미룰까

| 기준 | v5 유지 | v6로 즉시 업그레이드 |
|---|---|---|
| 번들러 기반 SPA (named import 사용) | 신규 기능 미반영 | 영향 적음 — 테스트만 거치면 됨 |
| CDN 스크립트 태그 레거시 페이지 | 안정적이지만 장기 지원 리스크 | `type="module"` 전환 공수 필요 |
| 엄격한 CSP 운영 환경(금융·공공) | 기존 정책 유지 | CSP 정책 재검토·재승인 필요 |
| 구형 기기·브라우저 사용자 비중 높음 | WebGL1까지 커버 | WebGL2 미지원 기기에서 지도 누락 |
| 렌더링 성능(글리프·헤일로 처리 등) | v5 수준 | GPU 단일 패스 최적화로 개선 |

결론적으로 **번들러 기반 프로젝트에서 named import를 이미 쓰고 있다면 v6 전환은 리스크가 낮고, 빠르게 올릴 가치가 있다.** 반대로 CDN 스크립트 태그 의존도가 높거나 CSP 승인 절차가 느린 조직(금융·공공 서비스 등)이라면, 전환 일정에 정책 재검토 시간을 별도로 확보해야 한다. 구형 기기 사용자 비중이 서비스 지표상 무시할 수 없는 수준이라면, v6 전환 전에 WebGL2 미지원 기기 비율부터 애널리틱스로 확인하는 것이 먼저다.

## 실제 프로젝트 진행 순서

1. **현재 MapLibre 로딩 방식을 전수 조사한다.** 번들러 import 방식(named/default/namespace), CDN 스크립트 태그 사용 여부, 워커 로딩과 관련된 CSP 설정을 코드베이스 전체에서 찾아 목록화한다.
2. **WebGL2 지원 현황을 사용자 애널리틱스로 확인한다.** 구형 기기 비중이 유의미하다면, v6 전환과 별개로 폴백 UI(정적 이미지 지도 등)를 먼저 설계해야 한다.
3. **Default import를 쓰는 코드부터 네임스페이스 import로 고친다.** 공식 마이그레이션 가이드가 제시하는 가장 흔한 깨짐 지점이며, 빌드는 성공해도 런타임에서 `undefined` 에러로 나타나는 경우가 많다.
4. **CDN 스크립트 태그 페이지를 `type="module"`로 전환하고 별도 QA를 거친다.** 특히 이 스크립트가 다른 레거시 스크립트와 로딩 순서에 의존하고 있었다면, 모듈 스크립트의 지연 실행 특성 때문에 순서가 깨질 수 있다.
5. **CSP의 `worker-src blob:` 허용을 제거하고 리그레션 테스트를 돌린다.** 이 허용이 MapLibre 외의 다른 코드에도 쓰이고 있었다면, 제거 전에 의존성을 먼저 확인해야 한다.
6. **`styleimagemissing` 이벤트 기반 코드를 `Map.setMissingStyleImageResolver`로 교체한다.** 커스텀 아이콘을 동적으로 채워 넣는 로직이 있었다면 이 변경을 놓치기 쉽다.

## 실무 포인트

**플러그인 생태계의 ESM 대응 여부를 먼저 확인한다.** `maplibre-gl-draw`, `maplibre-gl-geocoder` 같은 서드파티 플러그인이 아직 UMD 전제로 작성돼 있다면, 핵심 라이브러리만 올리고 플러그인에서 막히는 경우가 생긴다. 업그레이드 전에 사용 중인 플러그인 목록의 v6 호환성을 개별 확인해야 한다.

**`map.transform` 직접 접근 코드를 미리 찾아둔다.** v6는 Map이 Camera를 합성하는 구조로 바뀌면서 내부 transform을 더 이상 노출하지 않는다. 커스텀 레이어나 애니메이션 코드에서 이 내부 API에 직접 접근하고 있었다면 전환 시 가장 먼저 깨지는 지점이다.

**한 번에 전체 서비스를 올리지 않는다.** 지도가 핵심 기능인 서비스라면, 트래픽이 적은 페이지 하나에 먼저 v6를 적용해 WebGL2·CSP·번들 크기 영향을 관찰한 뒤 전체로 확장하는 점진적 롤아웃이 안전하다.

## 마무리

- MapLibre v6의 ESM 전용 배포는 단순 버전업이 아니라 번들러 import 방식, CDN 스크립트 태그, CSP 워커 정책을 모두 다시 점검해야 하는 마이그레이션이다.
- 번들러 기반 SPA에서 named import를 쓰고 있다면 전환 리스크가 낮고, CDN 의존·엄격한 CSP 환경·구형 기기 비중이 높은 서비스는 일정에 정책 재검토 시간을 별도로 확보해야 한다.
- Default import 교체, `map.transform` 직접 접근 코드, 서드파티 플러그인의 ESM 호환성을 먼저 점검한 뒤 트래픽이 적은 페이지부터 점진적으로 롤아웃하는 순서가 안전하다.

## 참고 자료

- [MapLibre GL JS v5 to v6 Migration Guide](https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/)
- [MapLibre Newsletter July 2026](https://maplibre.org/news/2026-08-02-maplibre-newsletter-jul-2026/)
- [MapLibre GL JS v6: Mandatory WebGL2 and ESM-only](https://geo.malagis.com/maplibre-gl-js-v6-mandatory-webgl-and-esm-only.html)
