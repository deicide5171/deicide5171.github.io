---
layout: single
title: "[추천 지식] 다음으로 파봐야 할 것 — 실무에서 쓰는 자료구조 심화"
date: 2026-08-15 17:10:00 +0530
categories: dev-insight
tags: ["자료구조", "trie", "bloom-filter", "lru-cache", "학습로드맵"]
toc: true
toc_sticky: true
excerpt: "Flutter, 지도 API, PostGIS, AI 에이전트, 분산 시스템, Docker/CI-CD, DB 인덱스, 테스트 전략, 네트워크, 웹 보안까지 다뤄온 이 블로그의 마지막 추천 지식으로 트라이·스킵리스트·LRU 캐시·Bloom Filter 같은 실무 자료구조 심화를 추천하는 이유를 정리한다."
---

## 왜 지금 이 주제인가

이 블로그는 Flutter 앱 개발에서 시작해 네이버 클라우드 지도 API, PostGIS 공간 데이터, AI 에이전트 프로토콜, 분산 시스템, Docker와 CI/CD 파이프라인, DB 인덱스 내부 구조, 테스트 피라미드, TCP/TLS 네트워크 심화, 웹 애플리케이션 보안까지 폭넓은 주제를 "추천 지식" 시리즈로 다뤄왔다. 돌이켜보면 이 로드맵은 "무언가를 만든다 → 데이터를 저장하고 조회한다 → 안전하게 배포한다 → 신뢰할 수 있게 검증한다 → 네트워크로 연결하고 지킨다"는 흐름을 순서대로 밟아온 셈이다.

그런데 이 모든 글에서 은근히 당연하게 취급하고 넘어간 것이 하나 있다. 바로 "그 데이터를 메모리 안에서 어떤 구조로 들고 있을 것인가"라는 질문이다. DB 인덱스 글에서 B-Tree를 다뤘지만, 자동완성 기능을 만들 때 문자열 접두사를 빠르게 찾는 구조나, 대량의 캐시를 메모리 안에서 효율적으로 유지하는 구조, 수십억 건의 존재 여부를 아주 적은 메모리로 확인하는 구조는 아직 다루지 않았다. 이런 자료구조들은 화려하지 않지만, 검색 엔진의 자동완성, Redis의 정렬 컬렉션, CDN과 브라우저의 캐시 정책, 대규모 분산 시스템의 중복 체크 등 실무 곳곳에 이미 들어가 있다.

그래서 이번 글에서는 이 시리즈의 마지막 추천 지식으로 트라이(Trie), 스킵리스트(Skip List), LRU 캐시 구현, Bloom Filter 같은 "실무에서 실제로 쓰이는 자료구조 심화"를 다룬다. 알고리즘 수업에서 이론으로만 배우고 지나가기 쉬운 주제들이지만, 지금까지 쌓아온 백엔드·인프라·네트워크·보안 지식 위에 이 자료구조들을 얹으면 왜 특정 시스템이 그렇게 설계되었는지가 훨씬 선명하게 보인다.

## 학습 로드맵

| 단계 | 주제 | 왜 필요한가 |
|---|---|---|
| 1 | 트라이(Trie) | 자동완성·접두사 검색을 O(문자열 길이)에 처리 |
| 2 | 스킵리스트(Skip List) | 균형 트리 없이 정렬된 데이터를 O(log n)에 탐색·삽입 |
| 3 | LRU 캐시 구현 | 해시맵과 이중 연결 리스트로 O(1) 캐시 교체 정책 구현 |
| 4 | Bloom Filter | 적은 메모리로 "확실히 없음"을 빠르게 판별 |
| 5 | HyperLogLog·Count-Min Sketch | 대용량 스트림에서 근사치로 집계·카디널리티 추정 |

이 순서로 학습하면 "정확한 구조(트라이, 스킵리스트) → 캐시 정책(LRU) → 확률적 구조(Bloom Filter, HyperLogLog)"로 자연스럽게 이어지며, 메모리와 정확도를 맞바꾸는 실무적 판단 감각을 익힐 수 있다.

## 핵심 개념: 트라이와 Bloom Filter

**트라이**는 문자열 집합을 트리 형태로 저장해, 각 노드가 문자 하나에 대응하는 자식을 갖는 구조다. 검색할 때 문자를 한 글자씩 따라 내려가기만 하면 되므로, 검색 대상 문자열 개수와 무관하게 입력한 접두사 길이에 비례하는 시간만 걸린다. 검색창 자동완성, IP 라우팅 테이블(최장 접두사 매칭), 사전 기반 맞춤법 검사기가 대표적인 활용 사례다.

**Bloom Filter**는 "이 값이 집합에 있을 수도 있다" 또는 "확실히 없다"만 답하는 확률적 자료구조다. 비트 배열과 여러 개의 해시 함수로 구성되며, 원소를 넣을 때마다 여러 해시 값 위치의 비트를 1로 세팅한다. 조회 시 해당 비트가 하나라도 0이면 확실히 없는 것이고, 모두 1이면 "있을 가능성이 있다"고 판단한다. 오탐(false positive)은 있지만 미탐(false negative)은 없다는 특성 덕분에, 캐시 미스 판별이나 악성 URL 사전 필터링처럼 "일단 걸러내고 나머지만 정확히 확인"하는 용도에 널리 쓰인다.

## 예제: Python으로 구현한 간단한 LRU 캐시

```python
class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # OrderedDict 대신 dict + 순서 관리 원리를 직접 보여주기 위한 예시
        self.order = []

    def get(self, key):
        if key not in self.cache:
            return -1
        self.order.remove(key)
        self.order.append(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.capacity:
            oldest = self.order.pop(0)
            del self.cache[oldest]
        self.cache[key] = value
        self.order.append(key)
```

이 구현은 이해를 돕기 위해 리스트로 순서를 관리했지만, 실무에서는 `list.remove`가 O(n)이라 성능이 나오지 않는다. 실제로는 `collections.OrderedDict`나, 해시맵 + 이중 연결 리스트를 직접 조합해 `get`/`put` 모두 O(1)로 만드는 것이 표준적인 접근이다.

## 실무 포인트

- **트라이는 메모리를 많이 먹는다**: 자식 노드를 배열이 아니라 해시맵으로 구현하거나, 압축 트라이(radix tree)를 쓰면 메모리 사용량을 크게 줄일 수 있다.
- **LRU만이 정답은 아니다**: 접근 빈도가 중요한 워크로드에는 LFU가, 스캔 패턴이 섞인 워크로드에는 LRU-K나 ARC 같은 변형 정책이 더 적합할 수 있다.
- **Bloom Filter 크기 설계가 핵심이다**: 비트 배열 크기와 해시 함수 개수를 예상 원소 수·허용 오탐률에 맞춰 계산해야 하며, 과소 설계하면 오탐률이 급격히 치솟는다.
- **기존 라이브러리를 먼저 확인한다**: Redis의 `BF.ADD`, Guava의 `BloomFilter`, Java의 `LinkedHashMap` 기반 LRU 등 검증된 구현이 이미 있는 경우가 많다.

## 3줄 요약

- 지금까지 다룬 DB·네트워크·보안·분산 시스템 지식 아래에는 항상 "메모리 안에서 데이터를 어떻게 들고 있을 것인가"라는 자료구조 문제가 깔려 있다.
- 트라이·스킵리스트·LRU 캐시·Bloom Filter는 이론이 아니라 검색 엔진, 캐시, 라우팅 테이블, 중복 필터링 등 실무 시스템 곳곳에서 실제로 쓰인다.
- 직접 구현해보되, 실무에서는 검증된 라이브러리 구현을 우선 검토하는 것이 안전하다.

## 참고 자료

- [Redis — Probabilistic Data Structures](https://redis.io/docs/latest/develop/data-types/probabilistic/)
- [Skip Lists: A Probabilistic Alternative to Balanced Trees (William Pugh)](https://epaperpress.com/sortsearch/download/skiplist.pdf)
- [Guava BloomFilter 문서](https://guava.dev/releases/snapshot/api/docs/com/google/common/hash/BloomFilter.html)
