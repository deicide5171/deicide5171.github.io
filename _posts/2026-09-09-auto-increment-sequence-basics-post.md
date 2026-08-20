---
layout: single
title: "AUTO_INCREMENT와 시퀀스가 뭔가요 — ID를 자동으로 매기기"
date: 2026-09-09 13:35:00 +0530
categories: database
tags: ["autoincrement", "시퀀스", "sequence", "기본키", "입문"]
toc: true
toc_sticky: true
excerpt: "새 행을 넣을 때 고유한 ID를 자동으로 만들어주는 AUTO_INCREMENT와 시퀀스의 개념과 주의점을 처음 배우는 사람 기준으로 정리했다."
---

## ID를 직접 1, 2, 3... 매겨야 하나

테이블에 데이터를 넣을 때마다 고유한 기본키(ID)가 필요하다. 그런데 매번 "지금 제일 큰 ID가 몇이지?"를 조회해 +1 하는 것은 번거롭고, 동시에 여러 요청이 들어오면 같은 값이 겹칠 수 있다. **AUTO_INCREMENT(시퀀스)**는 **새 행이 들어올 때 DB가 알아서 다음 번호를 부여**해 이 문제를 해결한다.

## DB별 이름

| DB | 방식 |
|---|---|
| MySQL | `AUTO_INCREMENT` 속성 |
| PostgreSQL | `SERIAL` / `IDENTITY`(내부적으로 시퀀스) |
| Oracle | `SEQUENCE` 객체 |

이름은 달라도 "행마다 자동으로 증가하는 고유 번호를 준다"는 개념은 같다.

## 사용 예시

```sql
-- MySQL
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50)
);

INSERT INTO users(name) VALUES ('철수'); -- id: 1 자동
INSERT INTO users(name) VALUES ('영희'); -- id: 2 자동
```

`id`를 직접 넣지 않아도 1, 2, 3...으로 자동 부여된다.

## 실무 포인트

- **삭제해도 번호는 되돌아가지 않는다.** id 2를 지워도 다음 값은 3부터다. 번호에 "빈 칸"이 생기는 것은 정상이며, 이 값으로 "총 몇 개인지"를 유추하면 안 된다.
- **자동 증가 ID는 예측 가능하다.** id가 순차적이면 `/users/1`, `/users/2`처럼 다른 사용자의 데이터를 URL로 넘겨짚을 수 있다. 외부에 노출되는 식별자는 UUID나 별도 공개 ID를 쓰는 것이 안전하다.
- **분산 환경에선 한계가 있다.** DB가 여러 대로 나뉘면(샤딩) 단일 자동 증가로는 전역 고유성을 보장하기 어렵다. 이럴 땐 UUID나 스노플레이크(Snowflake) 같은 분산 ID 생성 방식을 고려한다.

## 마무리 요약

- AUTO_INCREMENT·시퀀스는 새 행마다 DB가 다음 고유 번호를 자동 부여하는 기능이다.
- MySQL은 `AUTO_INCREMENT`, PostgreSQL은 `SERIAL/IDENTITY`, Oracle은 `SEQUENCE`로 부른다.
- 삭제해도 번호는 안 돌아가며, 순차 ID는 예측 가능하니 외부 노출엔 UUID 등을 고려한다.

## 참고 자료

- [MySQL 공식 문서 - AUTO_INCREMENT](https://dev.mysql.com/doc/refman/8.0/en/example-auto-increment.html)
