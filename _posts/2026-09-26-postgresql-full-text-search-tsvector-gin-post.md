---
layout: single
title: "PostgreSQL 전문 검색 — tsvector·tsquery와 GIN 인덱스 내부 동작"
date: 2026-09-26 13:35:00 +0530
categories: database
tags: ["PostgreSQL", "전문검색", "tsvector", "GIN인덱스", "FullTextSearch"]
toc: true
toc_sticky: true
excerpt: "게시글 검색 기능을 붙이자마자 Elasticsearch부터 검토하던 습관을, PostgreSQL 자체 전문 검색이 어떻게 문서를 정규화된 어휘소 집합으로 바꾸고 GIN 인덱스로 빠르게 찾아내는지 그 내부 동작을 이해하고 나면 언제까지 미룰 수 있는지 정리했다."
---

## 왜 지금 PostgreSQL 전문 검색을 다시 봐야 하는가

검색 기능이 필요하다는 요구사항이 나오면 반사적으로 Elasticsearch나 별도 검색 엔진 도입을 검토하는 경우가 많다. 하지만 별도 검색 클러스터를 운영한다는 것은 데이터 동기화 파이프라인, 별도 장애 도메인, 추가 인프라 비용을 함께 짊어진다는 뜻이다. PostgreSQL은 `LIKE '%keyword%'`보다 훨씬 정교한 자체 전문 검색(Full-Text Search) 기능을 내장하고 있으며, 대부분의 서비스 초기~중기 규모에서는 이것만으로 충분한 검색 품질을 낼 수 있다. 문제는 `tsvector`, `tsquery`, `to_tsvector`, `@@` 연산자 같은 낯선 이름들이 진입 장벽처럼 느껴진다는 점인데, 실제 내부 동작을 이해하면 왜 이 구조가 필요한지 자연스럽게 납득이 된다.

## 핵심 개념 1 — tsvector: 텍스트를 정규화된 어휘소 목록으로

`LIKE` 검색이 문자열 그 자체를 부분 일치시키는 것과 달리, PostgreSQL 전문 검색은 텍스트를 먼저 `tsvector`라는 정규화된 형태로 변환한다. `to_tsvector('english', 'The runners are running quickly')`를 실행하면 불용어(the, are)가 제거되고, "running"과 "runners"가 모두 "run"이라는 어간(stem)으로 통합되며, 각 어휘소가 원문의 몇 번째 위치에 있었는지까지 함께 저장된다. 결과는 `'quickli':4 'run':2,3` 같은 형태다. 이 어간 추출 덕분에 사용자가 "running"으로 검색해도 "runs", "ran"이 포함된 문서를 찾을 수 있다. 검색어 쪽도 동일하게 `to_tsquery`로 같은 정규화를 거친 뒤, `@@` 연산자로 두 어휘소 집합이 매칭되는지 비교한다.

## 핵심 개념 2 — GIN 인덱스: 어휘소에서 문서로의 역색인

`tsvector` 매칭 자체는 정규화 덕분에 정확도가 높아지지만, 테이블 전체를 스캔하며 매번 변환·비교한다면 여전히 느리다. 여기서 GIN(Generalized Inverted Index)이 등장한다. GIN은 일반적인 B-tree처럼 "행 → 값"을 저장하는 대신, "어휘소 → 그 어휘소를 포함하는 행 목록"이라는 역방향 색인을 구축한다. 이는 검색 엔진의 역색인(inverted index)과 정확히 같은 구조다. 검색어가 여러 어휘소로 이루어져 있으면, GIN은 각 어휘소에 해당하는 행 목록들을 가져와 교집합·합집합 연산으로 빠르게 후보를 좁힌다. 이 구조 덕분에 수백만 건의 문서에서도 특정 단어를 포함하는 행을 즉시 찾아낼 수 있다.

| 검색 방식 | 매칭 정확도 | 인덱스 활용 | 대용량 성능 |
|---|---|---|---|
| LIKE '%keyword%' | 정확한 부분 문자열만(어간 변화 무시) | 불가능(선행 와일드카드) | 순차 스캔, 느림 |
| tsvector @@ tsquery (인덱스 없음) | 어간 정규화로 향상 | 매 쿼리마다 변환 | 여전히 순차 스캔 |
| tsvector @@ tsquery + GIN | 어간 정규화로 향상 | 역색인으로 즉시 조회 | 대용량에서도 빠름 |

## 코드 예제 — 검색 컬럼 구성과 GIN 인덱스 생성

```sql
-- 생성 컬럼(generated column)으로 tsvector를 자동 유지
ALTER TABLE articles
  ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body, '')), 'B')
  ) STORED;

CREATE INDEX idx_articles_search ON articles USING GIN (search_vector);

-- 검색 쿼리: 관련도 순 정렬까지 포함
SELECT id, title, ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'postgresql & index') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

`setweight`로 제목(A)과 본문(B)에 다른 가중치를 부여하면, `ts_rank`가 제목에 검색어가 포함된 문서를 더 높은 순위로 올려준다. `GENERATED ALWAYS ... STORED` 컬럼을 쓰면 트리거 없이도 원본 컬럼이 바뀔 때마다 자동으로 재계산된다.

## 실무 포인트

- **언어 설정(`'english'`)을 실제 콘텐츠 언어와 맞춰야 한다.** 한국어는 PostgreSQL 기본 어간 추출기가 지원하지 않으므로, `pg_bigm`이나 형태소 분석 확장(예: 한국어 전용 텍스트 검색 설정)을 별도로 구성해야 의미 있는 결과가 나온다.
- **GIN 인덱스는 쓰기 비용이 B-tree보다 크다.** 삽입·수정이 매우 빈번한 테이블이라면 `fastupdate` 옵션과 `gin_pending_list_limit` 설정으로 쓰기 성능과 검색 최신성 사이의 균형을 조정해야 한다.
- **PostgreSQL 전문 검색이 항상 충분한 것은 아니다.** 오타 허용 검색(fuzzy search), 다국어 형태소 분석 고도화, 대규모 벡터 유사도 검색이 필요해지는 시점이 바로 별도 검색 엔진 도입을 재검토할 신호다.

## 마무리 요약

- PostgreSQL 전문 검색은 텍스트를 불용어 제거·어간 추출을 거친 `tsvector`로 정규화해, 단순 문자열 일치보다 훨씬 유연한 매칭을 가능하게 한다.
- GIN 인덱스는 검색 엔진의 역색인과 동일한 구조로 "어휘소 → 행 목록"을 저장해, 대용량 테이블에서도 즉각적인 전문 검색을 가능하게 한다.
- 생성 컬럼과 setweight로 검색 파이프라인을 구성하면 별도 검색 클러스터 없이도 상당 수준의 검색 품질을 확보할 수 있지만, 언어 지원과 쓰기 비용은 미리 검증해야 한다.

## 참고 자료

- [PostgreSQL 공식 문서 — Full Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [PostgreSQL 공식 문서 — GIN Indexes](https://www.postgresql.org/docs/current/gin.html)
