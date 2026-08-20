---
layout: single
title: "Nginx 502 Bad Gateway, 원인과 해결법"
date: 2026-08-31 14:40:00 +0530
categories: infra
tags: ["nginx", "502에러", "트러블슈팅", "리버스프록시", "인프라"]
toc: true
toc_sticky: true
excerpt: "Nginx가 502 Bad Gateway를 반환할 때, 업스트림 서버 문제인지 Nginx 설정 문제인지 구분하는 진단 순서를 정리했다."
---

## 502는 Nginx가 아니라 뒷단 문제일 때가 많다

`502 Bad Gateway`는 Nginx가 리버스 프록시로서 뒤에 있는 애플리케이션 서버(업스트림)로부터 유효한 응답을 받지 못했다는 뜻이다. 즉 Nginx 자체는 정상 동작 중이고, 원인은 대부분 업스트림 서버 쪽이나 둘 사이의 통신 설정에 있다. Nginx 로그만 보지 말고 애플리케이션 서버 상태까지 함께 봐야 한다.

## 원인 후보와 확인 방법

| 원인 | 확인 방법 | 대응 |
|---|---|---|
| 업스트림 서버가 죽어 있음 | `curl localhost:<앱포트>`로 직접 호출 | 애플리케이션 프로세스 재시작·로그 확인 |
| 업스트림 응답이 너무 느림(타임아웃) | Nginx error.log의 `upstream timed out` | `proxy_read_timeout` 조정 또는 앱 성능 개선 |
| 업스트림이 순간적으로 커넥션 거부 | error.log의 `Connection refused` | 앱 서버의 max 커넥션·백로그 설정 확인 |
| Nginx 설정 자체 오류 | `nginx -t`로 설정 문법 검사 | `proxy_pass` 대상 주소 오타 확인 |

## 로그 확인이 최우선

```bash
# Nginx 에러 로그에서 502 관련 원인 문구 확인
tail -f /var/log/nginx/error.log

# 흔히 보이는 메시지 예시
# "connect() failed (111: Connection refused) while connecting to upstream"
# "upstream timed out (110: Connection timed out) while reading response header from upstream"
```

`Connection refused`면 애플리케이션 프로세스가 죽어 있거나 아예 그 포트를 리스닝하지 않는 것이고, `timed out`이면 앱은 살아 있지만 응답이 늦는 것이다. 이 둘은 원인도 대응도 완전히 다르다.

## Nginx 설정 예제: 타임아웃과 재시도

```nginx
upstream backend {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081 backup;  # 주 서버 장애 시 대체
}

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_read_timeout 30s;      # 앱 응답 대기 시간
        proxy_connect_timeout 5s;    # 앱 연결 시도 대기 시간
        proxy_next_upstream error timeout http_502;  # 실패 시 다음 서버로
    }
}
```

## 실무 포인트

- **502가 배포 직후에만 잠깐 발생한다면, 애플리케이션이 재시작되는 동안 잠깐 포트가 닫혀 있었을 가능성이 크다.** 무중단 배포(롤링 업데이트)로 전환하면 이 문제가 사라진다.
- **트래픽이 몰릴 때만 502가 발생한다면 앱 서버의 스레드 풀이나 커넥션 풀이 고갈됐을 가능성이 높다.** Nginx 설정보다 애플리케이션 쪽 용량 문제일 수 있다.
- **`proxy_read_timeout`을 무작정 늘리는 것은 임시방편이다.** 근본적으로는 왜 응답이 느려졌는지(느린 쿼리, 외부 API 대기 등)를 찾아야 한다.

## 마무리 요약

- 502는 대부분 Nginx가 아니라 업스트림 애플리케이션 서버 쪽 문제다.
- error.log의 `Connection refused`와 `timed out` 메시지는 원인이 완전히 다르므로 구분해서 대응해야 한다.
- 배포 직후에만 발생한다면 무중단 배포 전환을, 트래픽 몰릴 때만 발생한다면 앱 서버 용량 문제를 의심하자.

## 참고 자료

- [Nginx 공식 문서 - proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
