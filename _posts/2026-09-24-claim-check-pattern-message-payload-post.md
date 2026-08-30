---
layout: single
title: "Claim Check 패턴 — 메시지 브로커에 큰 페이로드를 직접 넣지 않는 법"
date: 2026-09-24 12:45:00 +0530
categories: system-design
tags: ["ClaimCheck", "메시지큐", "이벤트기반아키텍처", "Kafka", "페이로드설계"]
toc: true
toc_sticky: true
excerpt: "이미지 처리 결과나 대용량 리포트를 이벤트에 그대로 실어 보냈다가 Kafka 메시지 크기 제한에 걸리거나 브로커 디스크를 압박하는 문제를, 실제 데이터는 객체 스토리지에 두고 참조만 메시지로 주고받는 Claim Check 패턴으로 정리했다."
---

## 왜 지금 Claim Check 패턴을 다시 봐야 하는가

이벤트 기반 아키텍처를 설계하다 보면 "이 이벤트에 필요한 데이터를 전부 담아서 보내면 컨슈머가 다시 조회할 필요가 없어 편하지 않을까"라는 유혹에 빠지기 쉽다. 처음에는 이벤트 페이로드가 몇 킬로바이트 수준이라 문제가 없지만, 이미지 분석 결과·PDF 리포트·대용량 로그 배치처럼 크기가 큰 데이터를 다루는 이벤트가 하나둘 늘어나면 문제가 생긴다. Kafka는 기본적으로 메시지 하나의 크기에 제한(`message.max.bytes`)을 두고 있고, 이 제한을 억지로 늘리면 브로커의 페이지 캐시 효율이 떨어지고 복제 지연이 커지는 부작용이 함께 따라온다. Claim Check 패턴은 물류에서 수하물을 맡기고 claim check(물표) 하나만 받아 나중에 그 표로 짐을 찾는 방식에서 이름을 따와, "큰 데이터는 별도 저장소에 두고 메시지에는 그 데이터를 가리키는 참조만 싣는다"는 원칙으로 이 문제를 해결한다.

## 핵심 개념 1 — 메시지는 가볍게, 무거운 데이터는 별도 스토리지로

Claim Check 패턴의 구조는 단순하다. 생산자는 큰 데이터를 객체 스토리지(S3, GCS 등)에 먼저 업로드하고, 그 객체의 키(경로)와 최소한의 메타데이터만 담은 작은 메시지를 브로커에 발행한다. 컨슈머는 이 메시지를 받으면 그 안의 키를 이용해 필요한 시점에 객체 스토리지에서 실제 데이터를 가져온다. 이 구조 덕분에 메시지 브로커는 항상 작고 예측 가능한 크기의 메시지만 다루게 되어, 처리량과 복제 성능이 데이터 크기와 무관하게 안정적으로 유지된다.

## 핵심 개념 2 — 모든 이벤트를 이렇게 처리할 필요는 없다는 트레이드오프

Claim Check을 적용하면 컨슈머가 실제 데이터를 쓰기 위해 항상 스토리지에 추가로 접근해야 하므로, 지연시간과 스토리지 조회 비용이 늘어난다. 작은 페이로드(몇 킬로바이트 수준)까지 이 패턴을 적용하면 오히려 불필요한 네트워크 왕복만 늘리는 과잉 설계가 된다. 실무에서는 페이로드 크기에 임계값을 두고, 그 임계값을 넘는 경우에만 자동으로 Claim Check 방식으로 전환하는 하이브리드 설계를 쓰는 경우가 많다. 또한 스토리지에 업로드한 원본 데이터의 만료 정책(TTL)을 반드시 함께 설계해야 한다 — 그렇지 않으면 이벤트는 사라져도 참조되지 않는 객체가 스토리지에 무기한 쌓이는 문제가 생긴다.

| 항목 | 페이로드 직접 포함 | Claim Check 패턴 |
|---|---|---|
| 메시지 크기 | 데이터 크기에 비례 | 항상 작고 일정함 |
| 브로커 부하 | 큰 데이터일수록 증가 | 데이터 크기와 무관 |
| 컨슈머 처리 | 즉시 사용 가능 | 스토리지 조회 한 단계 추가 |
| 적합한 데이터 크기 | 수 KB 이하 | 수백 KB 이상, 특히 MB 단위 |

## 예제 — Claim Check 발행과 소비 (Kafka + S3)

```python
def publish_large_event(topic, payload_bytes, metadata):
    if len(payload_bytes) > CLAIM_CHECK_THRESHOLD:  # 예: 100KB
        object_key = f"events/{uuid4()}.bin"
        s3_client.put_object(
            Bucket="event-payloads",
            Key=object_key,
            Body=payload_bytes,
            # 참조되지 않는 객체를 자동 정리하기 위한 만료 태그
            Tagging="ttl=7days",
        )
        message = {
            "type": "claim_check",
            "storage_key": object_key,
            "metadata": metadata,
        }
    else:
        message = {"type": "inline", "payload": payload_bytes, "metadata": metadata}

    kafka_producer.send(topic, json.dumps(message).encode())


def consume_event(message):
    data = json.loads(message.value)
    if data["type"] == "claim_check":
        payload = s3_client.get_object(Bucket="event-payloads", Key=data["storage_key"])["Body"].read()
    else:
        payload = data["payload"]
    process(payload, data["metadata"])
```

임계값을 기준으로 인라인 방식과 Claim Check 방식을 자동 전환하면, 작은 이벤트의 지연시간은 그대로 유지하면서 큰 이벤트만 브로커 부하에서 분리할 수 있다.

## 실무 포인트

- **스토리지 객체의 생명주기 정책을 메시지 발행 로직과 함께 설계하라.** S3의 Lifecycle Rule 같은 기능으로 일정 기간 지난 객체를 자동 삭제하지 않으면, 이벤트는 소비되고 사라져도 원본 데이터만 스토리지에 계속 쌓이는 누수가 생긴다.
- **컨슈머의 스토리지 접근 실패를 재시도 정책에 포함하라.** 메시지 자체는 성공적으로 소비됐더라도 스토리지 조회가 일시적으로 실패할 수 있으므로, 이 실패를 메시지 처리 실패와 동일하게 다뤄 재시도되도록 해야 한다.
- **여러 컨슈머가 같은 참조를 반복 조회하는 경우 캐시를 고려하라.** 동일한 대용량 객체를 여러 컨슈머 그룹이 각자 소비한다면, 매번 원본 스토리지에서 다시 받는 대신 로컬 캐시나 CDN을 앞단에 두는 것이 스토리지 비용과 지연시간을 함께 줄인다.

## 마무리 요약

- Claim Check 패턴은 큰 데이터를 객체 스토리지에 두고 메시지에는 참조만 실어, 메시지 브로커가 항상 작고 예측 가능한 크기의 메시지만 다루게 만든다.
- 모든 이벤트에 적용하기보다 페이로드 크기 임계값을 기준으로 인라인 방식과 자동 전환하는 하이브리드 설계가 실무에 적합하다.
- 스토리지에 업로드된 원본 데이터의 만료 정책을 빠뜨리면 참조되지 않는 객체가 무기한 쌓이는 문제가 생기므로 반드시 함께 설계해야 한다.

## 참고 자료

- [Enterprise Integration Patterns - Claim Check](https://www.enterpriseintegrationpatterns.com/patterns/messaging/StoreInLibrary.html)
- [Apache Kafka - message.max.bytes 설정](https://kafka.apache.org/documentation/#brokerconfigs_message.max.bytes)
