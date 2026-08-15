---
layout: single
title: "API Gateway vs Service Mesh, 트래픽 관리는 어디서 해야 하나"
date: 2026-08-15 17:40:00 +0530
categories: system-design
tags: ["apigateway", "servicemesh", "istio", "envoy", "msa", "트래픽관리"]
toc: true
toc_sticky: true
excerpt: "API Gateway는 엣지에서, Service Mesh는 서비스 간 트래픽에서 각각 무엇을 책임지는지 구분하고 언제 함께 써야 하는지 정리한다."
---

## 왜 지금 이 논의가 다시 나오는가

MSA로 서비스를 쪼개기 시작하면 트래픽 관리 문제가 두 층에서 동시에 터진다. 하나는 외부에서 들어오는 요청을 어떻게 인증하고 라우팅할 것인가이고, 다른 하나는 서비스가 늘어나면서 서비스 간 호출을 어떻게 안전하고 관측 가능하게 유지할 것인가이다. 이 두 문제를 하나의 도구로 해결하려다 보면 API Gateway에 서비스 간 통신까지 떠넘기거나, Service Mesh를 도입해놓고도 엣지 라우팅 문제는 여전히 풀지 못하는 상황이 생긴다.

특히 쿠버네티스와 사이드카 패턴이 보편화되면서 Istio, Linkerd 같은 Service Mesh 도입 사례가 늘었고, 동시에 Kong, Envoy Gateway, Gateway API 같은 엣지 게이트웨이도 계속 진화하고 있다. 두 영역의 기능이 일부 겹쳐 보이다 보니 "그럼 게이트웨이 하나로 다 되는 거 아닌가" 하는 질문이 자연스럽게 나온다. 이 글에서는 두 도구가 실제로 어떤 책임을 나눠 맡는지, 그리고 언제 하나만으로 충분하고 언제 함께 써야 하는지를 정리해본다.

## API Gateway와 Service Mesh의 책임 범위

API Gateway는 클러스터 경계, 즉 엣지에서 동작하는 단일 진입점이다. 외부 클라이언트의 요청을 받아 인증·인가를 처리하고, 요청을 적절한 백엔드 서비스로 라우팅하며, 레이트리밋이나 API 버전 관리 같은 정책을 적용한다. 반면 Service Mesh는 클러스터 내부, 서비스와 서비스 사이의 통신을 다룬다. 각 서비스 옆에 사이드카 프록시를 붙여 서비스 간 트래픽에 mTLS를 자동 적용하고, 회로 차단(circuit breaking)이나 재시도, 세밀한 트래픽 분할(카나리, 섀도잉)을 관측 가능한 형태로 제공한다.

| 구분 | API Gateway | Service Mesh |
|---|---|---|
| 트래픽 위치 | 남북(North-South), 외부→내부 | 동서(East-West), 서비스 간 |
| 주 관심사 | 인증/인가, 레이트리밋, 라우팅 | mTLS, 회로 차단, 재시도, 관측성 |
| 배치 단위 | 클러스터 엣지에 1개(또는 소수) | 각 서비스마다 사이드카 |
| 대표 도구 | Kong, Envoy Gateway, AWS API Gateway | Istio, Linkerd, Consul Connect |
| 실패 시 영향 | 전체 진입점 장애로 확산 가능 | 개별 서비스 간 통신에 국한 |

## 언제 무엇을 쓰는가

서비스가 몇 개 안 되고 서비스 간 호출 패턴이 단순하다면 API Gateway만으로 충분한 경우가 많다. 엣지에서 인증과 레이트리밋만 잘 잡아도 초기 단계의 요구사항은 대부분 해결된다. 반대로 서비스 수가 늘고 서비스 간 호출이 복잡해지며, mTLS 강제나 세밀한 트래픽 분할, 장애 격리가 필요해지는 시점부터 Service Mesh 도입을 검토할 만하다. 다만 사이드카를 모든 서비스에 붙이는 구조는 그 자체로 운영 복잡도를 크게 늘리므로, 실제로 그 정도 트래픽 제어가 필요한지부터 확인하는 편이 안전하다.

둘을 함께 쓰는 조합도 흔하다. API Gateway가 엣지에서 외부 트래픽을 받아 인증·라우팅을 처리한 뒤 클러스터 내부로 넘기고, 그 이후 서비스 간 호출은 Service Mesh가 mTLS와 회로 차단으로 관리하는 구조다. 이 경우 두 계층의 정책이 중복되지 않도록 역할을 명확히 나누는 것이 중요하다. 예를 들어 레이트리밋은 엣지에서만 하고, 서비스 간 재시도 정책은 메시에서만 정의하는 식으로 경계를 그어두면 정책 충돌과 디버깅 부담을 줄일 수 있다.

## 설정 예제

Envoy Gateway 기준 엣지 레벨 레이트리밋 설정 예시다.

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: api-ratelimit
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: orders-route
  rateLimit:
    type: Global
    global:
      rules:
        - clientSelectors:
            - headers:
                - name: x-api-key
                  type: Distinct
          limit:
            requests: 100
            unit: Minute
```

Istio 기준 서비스 간 회로 차단(destination rule) 설정 예시다.

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: payments-circuit-breaker
spec:
  host: payments.svc.cluster.local
  trafficPolicy:
    connectionPool:
      http:
        http1MaxPendingRequests: 50
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
```

## 실무 포인트와 주의사항

Service Mesh 도입은 사이드카 리소스 오버헤드와 업그레이드 복잡도를 함께 가져온다는 점을 감안해야 한다. 모든 파드에 프록시가 붙으면 메모리·CPU 사용량이 늘고, 컨트롤 플레인 자체도 별도 운영 대상이 된다. 도입 전에 실제로 mTLS 강제나 세밀한 트래픽 제어가 필요한 범위인지, 아니면 일부 네임스페이스에만 우선 적용해도 되는지 단계적으로 검토하는 편이 부담을 줄인다.

API Gateway 쪽에서는 단일 진입점이라는 특성상 장애가 발생하면 전체 트래픽에 영향을 줄 수 있으므로 이중화와 헬스체크 구성을 꼼꼼히 챙겨야 한다. 또한 인증 로직을 게이트웨이와 개별 서비스에 중복 구현하지 않도록, 어디까지가 게이트웨이의 책임이고 어디부터가 서비스의 책임인지 팀 내에서 합의해두는 것이 좋다. 두 계층을 함께 쓸 때는 관측성 도구(분산 트레이싱 등)를 양쪽 모두에서 일관되게 연결해야 장애 지점을 빠르게 좁힐 수 있다.

## 3줄 요약

- API Gateway는 엣지에서 외부→내부 트래픽의 인증·라우팅·레이트리밋을 담당하고, Service Mesh는 서비스 간 트래픽의 mTLS·회로 차단·관측성을 담당한다.
- 서비스 수와 서비스 간 트래픽 복잡도가 낮으면 Gateway만으로 충분하며, 복잡도가 늘어날 때 Mesh 도입을 단계적으로 검토하는 편이 안전하다.
- 둘을 함께 쓸 때는 정책 중복을 피하고 역할 경계를 명확히 나눠야 운영 부담과 디버깅 비용을 줄일 수 있다.

## 참고 자료

- [Istio 공식 문서 - Traffic Management](https://istio.io/latest/docs/concepts/traffic-management/)
- [Envoy Gateway 공식 문서](https://gateway.envoyproxy.io/)
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
- [Linkerd 공식 문서 - Architecture](https://linkerd.io/2/reference/architecture/)
