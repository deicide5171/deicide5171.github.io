---
layout: single
title: "MySQL Too many connections 에러 원인과 해결"
date: 2026-08-31 13:35:00 +0530
categories: database
tags: ["mysql", "too many connections", "트러블슈팅", "커넥션풀", "데이터베이스"]
toc: true
toc_sticky: true
excerpt: "MySQL에서 Too many connections 에러가 발생하는 원인을 애플리케이션·DB 양쪽에서 짚고, 근본적인 해결 방법을 정리했다."
---

## 왜 max_connections를 올리는 것만으로는 안 되는가

`Too many connections` 에러를 처음 만나면 대부분 `max_connections` 값을 늘리는 것으로 대응한다. 하지만 이는 임시방편일 뿐이다. 실제 동시 접속자가 늘어서가 아니라, 애플리케이션이 커넥션을 제대로 반납하지 않아서 발생하는 경우가 훨씬 많기 때문이다. 근본 원인을 확인하지 않고 숫자만 올리면 언젠가 그 늘린 한도마저 다 채워버린다.

## 원인을 좁히는 순서

| 확인 항목 | 명령/방법 | 의미 |
|---|---|---|
| 현재 연결 수와 한도 | `SHOW STATUS LIKE 'Threads_connected';` `SHOW VARIABLES LIKE 'max_connections';` | 실제로 한도에 근접했는지 |
| 연결 출처 분포 | `SHOW PROCESSLIST;` | 특정 애플리케이션 서버가 몰아서 연결하는지 |
| Sleep 상태 연결 비율 | PROCESSLIST의 `Command` 컬럼 | Sleep이 대부분이면 커넥션 반납 누락 의심 |
| 애플리케이션 풀 설정 | HikariCP/Sequelize 등 설정값 | 풀 최대 크기 × 인스턴스 수가 max_connections 초과 여부 |

`SHOW PROCESSLIST`에서 `Command: Sleep`인 연결이 대다수라면, 이는 쿼리를 실행 중인 게 아니라 커넥션 풀에 반납되지 않고 방치된 연결일 가능성이 높다.

## 코드 예제: 커넥션 풀 크기 계산

```text
안전한 최대 커넥션 수 공식(대략적 가이드):
max_connections(DB) >= (애플리케이션 인스턴스 수) × (풀 최대 크기) + 여유분(관리자 접속·배치 작업용)

예: 인스턴스 5대 × 풀 크기 20 = 100
    관리 작업 여유분 20을 더해 max_connections는 최소 120 이상으로 설정
```

인스턴스를 오토스케일링하는 환경이라면 최대 스케일 시점의 인스턴스 수를 기준으로 계산해야 스케일 아웃 도중 커넥션 고갈이 발생하지 않는다.

## 실무 포인트

- **애플리케이션 커넥션 풀에 `타임아웃`을 반드시 설정한다.** 커넥션을 획득한 뒤 반납하지 않는 코드(try-with-resources 누락 등)가 있으면 결국 풀이 고갈된다.
- **PgBouncer의 MySQL 대응인 ProxySQL을 검토하라.** 다수의 애플리케이션 인스턴스가 DB에 직접 연결하는 대신 프록시를 거치면 DB 쪽 연결 수를 훨씬 적게 유지할 수 있다.
- **배치 작업이나 관리 스크립트가 커넥션을 안 닫고 종료되는 경우도 흔한 원인이다.** cron으로 도는 스크립트는 특히 커넥션 정리를 명시적으로 확인해야 한다.

## 마무리 요약

- max_connections를 올리기 전에 PROCESSLIST로 Sleep 연결 비율부터 확인해야 한다.
- 커넥션 수는 인스턴스 수 × 풀 크기 + 여유분 공식으로 미리 계산해두는 것이 안전하다.
- ProxySQL 같은 커넥션 프록시를 도입하면 DB 쪽 연결 수 자체를 줄일 수 있다.

## 참고 자료

- [MySQL 공식 문서 - max_connections](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_max_connections)
- [ProxySQL 공식 문서](https://proxysql.com/documentation/)
