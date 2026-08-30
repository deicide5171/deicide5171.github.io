---
layout: single
title: "최단경로 탐색 심화 — Contraction Hierarchies로 대규모 도로망 가속화하기"
date: 2026-09-24 13:20:00 +0530
categories: gis
tags: ["ContractionHierarchies", "라우팅", "최단경로", "Dijkstra", "그래프알고리즘"]
toc: true
toc_sticky: true
excerpt: "수백만 개 노드로 이뤄진 전국 단위 도로망에서 Dijkstra만으로는 실시간 경로 탐색이 불가능해지는 이유와, OSRM 같은 라우팅 엔진이 전처리 단계에서 그래프를 축약해 질의 시간을 극적으로 줄이는 Contraction Hierarchies 알고리즘을 정리했다."
---

## 왜 지금 Contraction Hierarchies를 알아야 하는가

내비게이션 앱이나 배달 서비스의 경로 탐색 기능을 처음 구현할 때는 Dijkstra 알고리즘으로 최단경로를 계산하는 것으로 충분하다. 도시 하나 규모의 도로망이라면 노드 수가 수만 개 수준이라 밀리초 단위로 답을 얻을 수 있다. 문제는 전국 단위, 대륙 단위로 서비스 범위가 넓어지면서 노드 수가 수백만~수천만 개로 늘어날 때 발생한다. Dijkstra는 목적지 방향과 무관하게 출발지에서 사방으로 탐색 범위를 넓혀가기 때문에, 그래프가 커질수록 탐색해야 하는 노드 수가 거의 선형으로 늘어나 실시간 응답이 불가능한 수준까지 느려진다. Contraction Hierarchies(CH)는 이 문제를 "질의 시점에 더 똑똑하게 찾는다"가 아니라 "질의 전에 미리 그래프 자체를 가공해둔다"는 전처리 중심 접근으로 해결한다.

## 핵심 개념 1 — 노드 축약(Contraction)과 숏컷(Shortcut)

CH의 핵심 아이디어는 그래프의 모든 노드에 중요도 순서를 매긴 뒤, 중요도가 낮은 노드부터 순서대로 그래프에서 제거(축약)하는 것이다. 어떤 노드를 제거할 때, 그 노드를 거쳐야만 최단경로가 성립하던 두 이웃 노드 사이에는 그 노드를 우회하는 새로운 직접 엣지, 즉 숏컷(shortcut)을 추가한다. 이렇게 하면 제거된 노드를 거치지 않고도 원래의 최단거리 정보를 그대로 보존할 수 있다. 이 과정을 모든 노드에 대해 반복하면, 원본 그래프 위에 숏컷들이 겹겹이 쌓인 계층 구조가 만들어진다.

<img src="/assets/images/posts/2026-09-24-contraction-hierarchies-shortest-path-routing-1.svg" alt="원본 도로망 그래프에서 낮은 차수의 교차로를 축약하며 숏컷 엣지를 추가해 계층 구조를 만들고, 질의 시 양방향 탐색이 상위 계층에서만 만나 탐색 범위가 대폭 줄어드는 과정을 보여주는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 질의 시 양방향 탐색이 훨씬 좁은 범위에서 끝나는 이유

전처리로 계층 구조가 만들어진 뒤에는, 실제 경로 탐색 질의를 출발지에서 시작하는 정방향 탐색과 목적지에서 시작하는 역방향 탐색을 동시에 진행하는 양방향 다익스트라로 처리한다. 이때 핵심 제약이 하나 추가된다 — 두 탐색 모두 "더 중요도가 높은 노드로만" 이동하도록 제한한다. 중요도가 낮은 노드 방향으로는 탐색이 진행되지 않으므로, 자연스럽게 탐색은 계층의 상위로만 좁혀 올라가다가 상위 계층의 어느 지점에서 두 탐색이 만나는 순간 종료된다. 원본 그래프 전체를 훑는 대신 소수의 상위 계층 노드만 방문하면 되므로, 그래프 규모가 아무리 커도 질의 시간은 사실상 상수에 가깝게 유지된다.

| 항목 | 순수 Dijkstra | Contraction Hierarchies |
|---|---|---|
| 사전 준비 | 없음 | 전처리(축약)로 숏컷 그래프 생성 필요 |
| 질의 시간 | 그래프 크기에 비례해 증가 | 그래프 크기와 거의 무관 (수 ms) |
| 그래프 변경 대응 | 즉시 반영 가능 | 부분 변경 시 재전처리 부담 |
| 적합한 사례 | 소규모·자주 변하는 그래프 | 대규모 정적 도로망(전국 단위 내비게이션) |

## 예제 — 축약 순서 결정에 쓰이는 간단한 엣지 차수 휴리스틱

```python
def edge_difference(graph, node):
    neighbors = graph.neighbors(node)
    shortcuts_needed = 0
    for u in neighbors:
        for v in neighbors:
            if u != v and not has_better_path_without(graph, node, u, v):
                shortcuts_needed += 1
    removed_edges = len(neighbors) * 2  # 양방향 엣지 제거 수
    return shortcuts_needed - removed_edges

def build_contraction_order(graph):
    # 엣지 차이(edge difference)가 작을수록 먼저 축약
    # (숏컷을 적게 만들면서 그래프를 정리할 수 있는 노드 우선)
    return sorted(graph.nodes(), key=lambda n: edge_difference(graph, n))
```

실제 OSRM이나 GraphHopper 같은 라우팅 엔진은 엣지 차이 외에도 이미 축약된 이웃 수, 탐색 공간 크기 등 여러 지표를 함께 고려한 더 정교한 우선순위 함수를 쓰지만, 기본 원리는 "숏컷을 적게 만드는 노드부터 먼저 없앤다"는 것으로 동일하다.

## 실무 포인트

- **직접 CH를 구현하기보다 OSRM, GraphHopper, Valhalla 같은 검증된 라우팅 엔진을 먼저 검토하라.** CH 전처리 알고리즘 자체는 구현 난이도가 상당히 높고, 미묘한 버그가 최단경로의 정확성을 은근히 훼손할 수 있어 직접 구현은 웬만하면 피하는 것이 좋다.
- **도로망 데이터가 자주 바뀌는 서비스라면 전처리 비용을 감안해 갱신 주기를 설계하라.** 공사·통제 구간이 실시간으로 반영돼야 하는 경우, 전체 재전처리 대신 일부 변경만 반영하는 증분 갱신 전략이나 실시간 페널티를 별도 레이어로 얹는 방식을 함께 고려해야 한다.
- **CH는 최단'거리'와 최단'시간'을 별도 가중치로 계산해야 한다면 각각 별도의 전처리가 필요하다는 점을 기억하라.** 하나의 축약 순서가 거리 기준과 시간 기준 모두에 최적이라는 보장은 없다.

## 마무리 요약

- Contraction Hierarchies는 질의 시점이 아니라 전처리 시점에 노드를 중요도 순으로 축약하고 숏컷을 추가해 그래프를 가공하는 방식이다.
- 질의 시 양방향 탐색이 더 높은 중요도의 노드로만 이동하도록 제한하면, 탐색 범위가 상위 계층으로 좁혀져 대규모 그래프에서도 거의 상수에 가까운 질의 시간을 얻을 수 있다.
- 정적인 대규모 도로망에는 강력하지만, 그래프가 자주 바뀌는 상황에서는 재전처리 비용을 감안한 갱신 전략이 별도로 필요하다.

## 참고 자료

- [OSRM - Contraction Hierarchies](http://project-osrm.org/docs/v5.24.0/api/#contraction-hierarchies)
- [Geisberger et al. - Contraction Hierarchies: Faster and Simpler Hierarchical Routing in Road Networks](https://algo2.iti.kit.edu/documents/routeplanning/geisberger-dissertation.pdf)
