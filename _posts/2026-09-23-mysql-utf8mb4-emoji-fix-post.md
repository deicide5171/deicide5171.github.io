---
layout: single
title: "MySQL에서 이모지 저장하면 깨지는 이유 — utf8과 utf8mb4 문자셋 제대로 잡기"
date: 2026-09-23 12:35:00 +0530
categories: database
tags: ["mysql", "utf8mb4", "문자셋", "인코딩", "이모지"]
toc: true
toc_sticky: true
excerpt: "닉네임이나 채팅 메시지에 이모지를 넣으면 저장이 안 되거나 물음표로 깨지는 문제를, MySQL의 utf8과 utf8mb4 문자셋 차이로 진단하고 스키마 전체를 안전하게 전환하는 방법을 정리했다."
---

## 왜 분명 UTF-8인데 이모지가 깨질까

사용자 닉네임이나 채팅 메시지에 😀 같은 이모지를 입력했더니 저장이 안 되거나, 저장은 됐는데 조회하면 물음표(？)나 깨진 문자로 보이는 문제를 겪게 된다. 테이블 인코딩을 `utf8`로 이미 설정해뒀는데도 이런 일이 생기면 당황스럽다. 하지만 여기서 함정이 있다 — MySQL의 `utf8`은 이름과 달리 진짜 UTF-8이 아니다.

MySQL의 `utf8` 문자셋은 실제로는 **최대 3바이트**까지만 표현하는 축소판이다. 그런데 이모지 대부분과 일부 한자(중국어 고어, 특수 한자)는 UTF-8 인코딩에서 4바이트를 차지한다. 3바이트 한도의 `utf8`에 4바이트 문자를 넣으려 하면 MySQL은 그 문자를 자르거나 에러를 내거나, 설정에 따라 조용히 물음표로 치환해버린다.

## 핵심 개념 1 — utf8과 utf8mb4는 다른 문자셋이다

이 둘의 관계를 헷갈리기 쉬운데, 이름만 비슷할 뿐 저장 가능한 문자 범위가 다른 완전히 별개의 문자셋으로 취급해야 한다.

| 항목 | utf8 (MySQL 레거시) | utf8mb4 |
|---|---|---|
| 최대 바이트 수 | 3바이트 | 4바이트 |
| 표현 가능 범위 | 기본 다국어 평면(BMP) | 이모지 포함 전체 유니코드 |
| 이모지 저장 | 불가능 (깨짐/잘림) | 가능 |
| 컬럼당 저장 공간 | 상대적으로 작음 | 조금 더 큼 (문자당 최대 1바이트 추가) |

MySQL 8.0부터는 기본 문자셋이 `utf8mb4`로 바뀌었지만, 오래된 DB를 이어받았거나 MySQL 5.x 시절에 만든 테이블을 그대로 쓰고 있다면 여전히 `utf8`로 남아 있는 경우가 흔하다. `mb4`는 "multi-byte 4"의 줄임말로, 진짜 완전한 UTF-8을 의미한다고 기억하면 헷갈리지 않는다.

<img src="/assets/images/posts/2026-09-23-mysql-utf8mb4-emoji-fix-1.svg" alt="MySQL utf8 문자셋은 최대 3바이트까지만 저장 가능해 4바이트인 이모지가 잘리고, utf8mb4는 4바이트를 온전히 저장하는 과정을 비교하는 다이어그램" style="width:100%;">

## 핵심 개념 2 — 문자셋은 서버, DB, 테이블, 컬럼, 연결 다섯 곳 모두 확인해야 한다

가장 흔한 실수는 테이블 문자셋만 `utf8mb4`로 바꾸고 끝냈다고 생각하는 것이다. MySQL 연결 문자셋(클라이언트가 서버와 통신할 때 쓰는 인코딩)이 여전히 `utf8`이면, 애플리케이션에서 아무리 4바이트 문자를 보내도 연결 계층에서 깨진다. JDBC 커넥션 URL이나 애플리케이션 설정 파일의 `characterEncoding`도 함께 확인해야 한다.

## 예제 — 기존 테이블을 utf8mb4로 안전하게 전환하기

```sql
-- 1. 현재 문자셋 확인
SHOW CREATE TABLE users;
SHOW VARIABLES LIKE 'character_set%';

-- 2. 데이터베이스 기본 문자셋 변경
ALTER DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 3. 테이블과 모든 컬럼을 함께 변환 (컬럼만 두고 테이블만 바꾸면 다시 꼬인다)
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```
# JDBC 연결 문자열에도 반드시 명시
jdbc:mysql://localhost:3306/mydb?useUnicode=true&characterEncoding=utf8&connectionCollation=utf8mb4_unicode_ci
```

여기서 헷갈리는 부분이 있는데, JDBC URL의 `characterEncoding=utf8`은 자바 진영에서 쓰는 이름 표기일 뿐 MySQL의 `utf8`(3바이트)을 의미하지 않는다. 실제 서버-클라이언트 간 문자셋 협상은 드라이버 버전에 따라 다르므로, 최신 MySQL Connector/J를 쓰고 있다면 `connectionCollation` 옵션으로 명시하는 편이 안전하다.

## 전환 시 흔한 함정

| 함정 | 결과 |
|---|---|
| `CONVERT TO CHARACTER SET` 없이 컬럼 정의만 바꿈 | 기존 데이터는 여전히 옛 인코딩으로 저장돼 있어 재해석 시 깨짐 |
| 인덱스가 걸린 VARCHAR 컬럼을 그대로 전환 | utf8mb4는 문자당 최대 1바이트가 늘어 인덱스 최대 길이(보통 767바이트) 초과 에러 발생 가능 |
| 연결 문자셋만 바꾸고 테이블은 안 바꿈 | 저장은 여전히 3바이트 한도라 이모지가 깨짐 |
| collation을 unicode_ci와 general_ci를 혼용 | 조인·비교 시 "Illegal mix of collations" 에러 |

특히 인덱스 길이 초과 문제는 `utf8mb4`로 전환하면서 자주 마주친다. `VARCHAR(255)`에 `utf8mb4`를 적용하면 문자당 최대 4바이트라 인덱스가 1020바이트를 요구하게 되는데, InnoDB의 기본 인덱스 키 길이 제한(767바이트, `innodb_large_prefix` 비활성 시)을 넘어서 에러가 난다. 이런 경우 컬럼 길이를 줄이거나 `innodb_large_prefix`와 `innodb_file_format=Barracuda` 설정을 확인해야 한다.

## 마무리 요약

- MySQL의 `utf8`은 최대 3바이트까지만 저장하는 축소판이라 4바이트인 이모지를 저장할 수 없고, 진짜 전체 UTF-8은 `utf8mb4`다.
- 문자셋은 서버, DB, 테이블, 컬럼, 연결(JDBC) 다섯 곳이 모두 일치해야 하며 하나라도 `utf8`로 남아 있으면 깨진다.
- `utf8mb4` 전환 시 인덱스 컬럼은 바이트 수 증가로 키 길이 제한을 초과할 수 있으니 컬럼 길이와 InnoDB 설정을 함께 점검해야 한다.

## 참고 자료

- [MySQL 공식 문서 - The utf8mb4 Character Set](https://dev.mysql.com/doc/refman/8.0/en/charset-unicode-utf8mb4.html)
- [MySQL 공식 문서 - Character Set Configuration](https://dev.mysql.com/doc/refman/8.0/en/charset-configuration.html)
