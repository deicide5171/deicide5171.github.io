---
layout: single
title: "curl로 API 테스트하기 — 개발자가 자주 쓰는 명령 정리"
date: 2026-09-03 13:40:00 +0530
categories: infra
tags: ["curl", "api테스트", "http", "입문", "명령어"]
toc: true
toc_sticky: true
excerpt: "브라우저나 Postman 없이 터미널에서 API를 빠르게 테스트할 수 있는 curl의 필수 옵션들을 예제와 함께 정리했다."
---

## 왜 curl을 익혀두면 좋은가

API를 테스트할 때 Postman 같은 GUI 도구도 좋지만, 서버에 SSH로 접속한 상태에서 빠르게 확인하거나, 스크립트에 넣어 자동화하거나, 문서에 예제로 남길 때는 **curl**이 훨씬 편하다. curl은 거의 모든 리눅스·맥 환경에 기본 설치되어 있어 별도 설치도 필요 없다.

## 자주 쓰는 옵션

| 옵션 | 의미 |
|---|---|
| `-X` | HTTP 메서드 지정 (GET, POST 등) |
| `-H` | 헤더 추가 (Content-Type, Authorization 등) |
| `-d` | 요청 본문 데이터 전송 |
| `-i` | 응답 헤더까지 함께 출력 |
| `-v` | 요청·응답 전 과정을 상세히 출력(디버깅용) |
| `-o` | 응답을 파일로 저장 |

## 기본 예제

```bash
# GET 요청 (가장 기본)
curl https://api.example.com/users/1

# 헤더 포함해서 보기 (상태 코드 확인에 유용)
curl -i https://api.example.com/users/1

# POST로 JSON 데이터 전송
curl -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -d '{"name": "김철수", "email": "kim@example.com"}'

# 인증 토큰 붙이기
curl https://api.example.com/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 디버깅에 유용한 조합

```bash
# 무슨 일이 일어나는지 전부 보기 (연결·TLS·헤더까지)
curl -v https://api.example.com/users/1

# 상태 코드만 딱 확인하기
curl -o /dev/null -s -w "%{http_code}\n" https://api.example.com/users/1
# -> 200, 404 등 숫자만 출력. 스크립트에서 헬스체크할 때 유용
```

`-v`는 요청이 왜 실패하는지 알 수 없을 때 가장 먼저 써보는 옵션이다. DNS 조회, TLS 핸드셰이크, 실제 주고받은 헤더까지 전부 보여줘서 문제 지점을 좁힐 수 있다.

## 실무 포인트

- **JSON 응답이 한 줄로 뭉쳐서 읽기 어렵다면 `jq`와 함께 쓰면 좋다.** `curl ... | jq`로 파이프하면 JSON이 보기 좋게 정렬되고 특정 필드만 추출할 수도 있다.
- **`-d`를 쓰면 메서드를 지정하지 않아도 자동으로 POST가 된다.** 다만 명시적으로 `-X POST`를 함께 써주면 의도가 분명해져 협업 시 혼동이 줄어든다.
- **따옴표 처리에 주의해야 한다.** JSON 본문에는 큰따옴표가 들어가므로, 바깥은 작은따옴표로 감싸는 것이 편하다. 셸에 따라 이스케이프 규칙이 다르니 복잡한 요청은 파일로 분리(`-d @data.json`)하는 것도 방법이다.

## 마무리 요약

- curl은 별도 설치 없이 터미널에서 API를 빠르게 테스트할 수 있는 도구다.
- `-X`(메서드), `-H`(헤더), `-d`(본문)가 가장 자주 쓰이는 핵심 옵션이다.
- 요청이 왜 실패하는지 모를 때는 `-v`로 전 과정을 확인하고, JSON 응답은 `jq`와 함께 쓰면 읽기 편하다.

## 참고 자료

- [curl 공식 문서](https://curl.se/docs/manpage.html)
- [jq 공식 매뉴얼](https://jqlang.github.io/jq/manual/)
