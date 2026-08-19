---
layout: single
title: "디스크를 훔쳐가도 데이터는 못 읽게 — 저장 데이터 암호화(TDE)와 컬럼 단위 암호화"
date: 2026-08-28 13:35:00 +0530
categories: database
tags: ["database", "encryption", "tde", "column-encryption", "data-security"]
toc: true
toc_sticky: true
excerpt: "DB 파일 자체가 유출돼도 내용을 못 읽게 막는 TDE(Transparent Data Encryption)의 동작 원리와, 특정 컬럼만 애플리케이션에서 암호화하는 방식과의 차이·트레이드오프를 정리한다."
---

DB 서버가 침해당하거나 백업 파일이 유출되는 사고는 SQL 인젝션 같은 애플리케이션 레벨 공격과는 다른 층위의 위협이다. 접근 제어와 쿼리 검증을 아무리 잘 해놔도, 디스크에 있는 데이터 파일이나 백업 아카이브 자체를 통째로 복사해가면 그 안의 평문 데이터는 고스란히 노출된다. **저장 데이터 암호화(encryption at rest)**는 이런 상황에 대비해 디스크에 내려간 데이터 자체를 암호화해두는 방어선이다.

이를 구현하는 방법은 크게 두 갈래다. DB 엔진 전체가 파일 시스템 레벨에서 암호화를 처리하는 **TDE(Transparent Data Encryption)**와, 특정 민감 컬럼만 애플리케이션이나 DB 함수로 암호화하는 **컬럼 단위 암호화**다. 둘은 막아주는 위협의 범위와 성능·검색 가능성에 대한 트레이드오프가 다르다. 이 글에서는 TDE의 동작 원리와, 두 접근을 실무에서 어떻게 함께 쓰는지 정리한다.

## 핵심 개념 1: TDE — 파일 레벨에서 투명하게 암호화한다

TDE는 데이터 파일, WAL/redo 로그, 백업 파일이 디스크에 쓰이는 시점에 자동으로 암호화하고, 읽을 때 자동으로 복호화한다. "투명하다(Transparent)"는 이름처럼 애플리케이션이나 쿼리 코드는 암호화 여부를 전혀 알 필요가 없다 — `SELECT * FROM users`는 암호화 유무와 무관하게 똑같이 동작하고, 복호화는 DB 엔진 내부에서 메모리에 올라올 때 처리된다.

키 관리는 보통 2단계 구조다. 실제 데이터를 암호화하는 DEK(Data Encryption Key)가 있고, 이 DEK 자체는 별도의 마스터 키(KEK, Key Encryption Key)로 다시 암호화되어 저장된다. 마스터 키는 AWS KMS, Azure Key Vault, HashiCorp Vault 같은 별도의 키 관리 서비스(KMS)에 보관하는 것이 일반적이며, DB 서버가 부팅 시 KMS에 인증해 마스터 키를 받아온 뒤에야 DEK를 풀어 데이터를 복호화할 수 있다.

<img src="/assets/images/posts/2026-08-28-database-encryption-tde-1.svg" alt="DEK로 데이터 파일을 암호화하고, DEK 자체는 KMS에 보관된 마스터 키(KEK)로 다시 암호화하는 TDE의 2단계 키 관리 구조" style="width:100%;">

## 핵심 개념 2: TDE가 막아주는 것과 못 막아주는 것

TDE는 "디스크나 백업 파일을 통째로 훔쳤을 때" 시나리오에 정확히 대응한다. 도난당한 디스크, 유출된 백업 파일, 클라우드 스토리지 설정 실수로 노출된 스냅샷 모두 마스터 키 없이는 무의미한 바이트 덩어리일 뿐이다. 하지만 TDE는 **DB가 정상적으로 실행 중이고 인증된 세션으로 쿼리를 던질 수 있는 공격자**에게는 아무 방어력이 없다. SQL 인젝션으로 데이터를 뽑아가거나, DB 계정 자격 증명이 유출돼 정상 쿼리로 접근하는 경우 TDE는 무력하다 — DB 엔진이 이미 복호화해서 응답하기 때문이다.

## 핵심 개념 3: 컬럼 단위 암호화 — 특정 데이터를 DB 관리자로부터도 숨긴다

TDE가 막지 못하는 지점을 보완하는 것이 컬럼 단위 암호화다. 주민등록번호, 카드번호처럼 극히 민감한 컬럼만 애플리케이션 레벨(또는 DB의 `pgcrypto` 같은 확장, SQL Server의 Always Encrypted)에서 별도 키로 암호화해 저장한다. 이렇게 하면 DB 관리자 권한으로 직접 쿼리를 날려도 암호화된 바이트만 보이고, 복호화 키를 가진 애플리케이션만 실제 값을 볼 수 있다. TDE는 "DB 밖의 물리적 유출"을 막고, 컬럼 단위 암호화는 "DB 안에서의 권한 오남용"까지 막는다는 점에서 방어 범위가 다르다.

대신 대가도 명확하다. 암호화된 컬럼은 일반적인 방식으로는 `WHERE encrypted_ssn = ?` 같은 등호 검색이나 `LIKE` 검색, 인덱스 활용이 어려워진다(결정적 암호화로 일부는 가능하지만 그만큼 안전성이 낮아진다). 그래서 검색이 자주 필요한 컬럼과 검색이 거의 필요 없는 초민감 컬럼을 구분해 암호화 방식을 다르게 적용하는 것이 일반적이다.

| 기준 | TDE | 컬럼 단위 암호화 |
|---|---|---|
| 막아주는 위협 | 디스크·백업 물리적 유출 | DB 내부 권한 오남용까지 |
| 적용 범위 | DB 전체 | 지정한 컬럼만 |
| 쿼리 코드 영향 | 없음(투명) | 암호화/복호화 로직 필요 |
| 검색·인덱스 | 영향 없음 | 등호·범위 검색이 크게 제약됨 |
| SQL 인젝션 방어 | 없음 | 부분적(암호화된 값만 노출) |

## 예제: PostgreSQL TDE(pgcrypto 기반 컬럼 암호화)와 클라우드 관리형 TDE

```sql
-- pgcrypto 확장으로 특정 컬럼만 암호화 (애플리케이션 키 관리와 결합해야 함)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO customers (id, name, ssn_encrypted)
VALUES (
  1, '홍길동',
  pgp_sym_encrypt('900101-1234567', current_setting('app.encryption_key'))
);

-- 조회 시 애플리케이션이 키를 함께 제공해야 복호화됨
SELECT id, name, pgp_sym_decrypt(ssn_encrypted, current_setting('app.encryption_key'))
FROM customers WHERE id = 1;
```

```bash
# 관리형 클라우드 DB(RDS 등)에서는 TDE가 옵션 하나로 활성화되는 경우가 많다
aws rds create-db-instance \
  --db-instance-identifier prod-db \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:ap-northeast-2:123456789012:key/abcd-...
```

PostgreSQL 자체는 오픈소스 코어에 TDE를 기본 내장하지 않으므로, 파일 시스템 레벨 암호화(LUKS 등)나 클라우드 관리형 서비스의 스토리지 암호화 옵션으로 사실상 TDE와 동등한 효과를 얻는 경우가 많다. 반면 MySQL(InnoDB), Oracle, SQL Server는 DB 엔진 자체에 TDE 기능을 내장하고 있다.

## 실무 포인트

- **키 순환(key rotation) 정책을 미리 세워둘 것**: 마스터 키가 유출됐을 때 즉시 교체할 수 있는 절차가 없으면 TDE의 방어력 자체가 무의미해진다. KMS의 자동 키 순환 기능을 활용하고, DEK 재암호화 절차를 문서화해둔다.
- **백업도 암호화 범위에 포함되는지 확인할 것**: TDE가 데이터 파일은 암호화하지만 백업 도구가 별도 경로로 평문 덤프를 뜨는 구성이라면 백업 파일이 여전히 노출 지점이 된다. 백업 파이프라인 전체가 암호화 대상인지 별도로 점검해야 한다.
- **컬럼 단위 암호화는 애플리케이션 성능 영향을 테스트할 것**: 암복호화 연산이 애플리케이션 레벨에서 일어나면 대량 조회 시 지연이 누적될 수 있다. 정말 필요한 최소한의 컬럼에만 적용하고, 검색이 필요한 필드는 별도의 해시 컬럼(예: SHA-256 해시로 등호 검색만 지원)을 병행하는 방식도 고려한다.

## 3줄 요약

- TDE는 데이터 파일·백업이 통째로 유출됐을 때를 대비해 DB 엔진이 투명하게 암복호화하는 방어선이며, DB가 정상 작동 중인 상태에서의 공격에는 무력하다.
- 컬럼 단위 암호화는 DB 관리자 권한 오남용이나 SQL 인젝션까지 막을 수 있지만, 검색·인덱스 활용이 크게 제약되는 대가를 치른다.
- 두 방식은 막아주는 위협 층위가 달라 배타적이지 않으며, 전체 DB에 TDE를 걸고 극히 민감한 컬럼에만 추가로 컬럼 단위 암호화를 적용하는 계층적 구성이 실무에서 흔하다.

## 참고 자료

- [Microsoft SQL Server 공식 문서: Transparent Data Encryption (TDE)](https://learn.microsoft.com/en-us/sql/relational-databases/security/encryption/transparent-data-encryption)
- [PostgreSQL 공식 문서: pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html)
- [AWS 공식 문서: Amazon RDS Encryption at Rest](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html)
