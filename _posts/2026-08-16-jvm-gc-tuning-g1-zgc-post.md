---
layout: single
title: "JVM GC 튜닝 실전 — G1과 ZGC, 언제 무엇을 골라야 할까"
date: 2026-08-16 13:25:00 +0530
categories: backend
tags: ["jvm", "gc-tuning", "g1gc", "zgc", "java", "performance"]
toc: true
toc_sticky: true
excerpt: "G1이 기본 GC로 정착한 지 오래지만, 저지연이 곧 서비스 품질인 시대에는 ZGC를 언제 꺼내 들어야 하는지 판단 기준이 필요하다. G1과 ZGC의 구조 차이와 실전 튜닝 포인트를 정리한다."
---

## 왜 지금 GC 튜닝인가

JVM 애플리케이션을 운영하다 보면 결국 마주치는 질문이 있다. "왜 가끔씩 요청이 수백 ms씩 튀는가"라는 질문이다. 대부분은 코드나 인프라가 아니라 GC(Garbage Collection)의 일시정지(Stop-the-world) 때문이다. G1 GC가 JDK 9부터 기본 GC 자리를 지켜온 덕분에 많은 팀이 GC 튜닝을 "일단 기본값으로 두고 문제 생기면 그때 본다"는 식으로 미뤄왔지만, 실시간 트레이딩·게임 서버는 물론 최근에는 LLM 서빙 게이트웨이나 스트리밍 API처럼 응답 지연에 민감한 서비스가 늘면서 GC 선택이 다시 중요한 설계 결정이 되고 있다.

여기에 최근 JDK 릴리스 흐름도 한몫한다. ZGC는 JDK 15에서 프로덕션 지원으로 승격됐고, JDK 21에서는 세대(Generational) 개념을 도입한 Generational ZGC가 실험적으로 추가되면서 처리량 약점을 상당 부분 보완했다. 세대별 모드는 이후 릴리스에서 기본 동작 방향으로 자리잡아가는 추세이므로, 사용 중인 JDK 버전의 릴리스 노트는 미리 확인해 두는 편이 안전하다.

## 핵심 개념 1: G1 GC — 범용 기본값의 동작 방식

G1(Garbage-First) GC는 힙을 고정 크기의 여러 Region으로 나누고, 각 Region을 Young/Old/Humongous(거대 객체용)로 유동적으로 배정한다. GC가 필요할 때는 가비지가 가장 많은 Region부터 우선 회수하는 방식으로 동작하며, 개발자가 지정한 `MaxGCPauseMillis` 목표치에 맞춰 한 번에 회수할 Region 개수를 조절한다. 다만 이 목표치는 "노력 목표"에 가까워서, 힙이 크고 Old 영역에 살아있는 객체가 많아지면 목표를 넘는 순간(Full GC 포함)이 발생할 수 있다.

## 핵심 개념 2: ZGC — 초저지연을 위한 설계

ZGC는 애플리케이션 스레드와 대부분의 GC 작업(마킹, 압축, 재배치)을 동시(Concurrent)에 수행하도록 설계됐다. 컬러 포인터(Colored Pointer)와 로드 배리어(Load Barrier)라는 기법으로 객체 이동 중에도 애플리케이션이 계속 해당 객체를 안전하게 참조할 수 있게 만든 것이 핵심이다. 그 결과 일시정지 시간이 힙 크기에 거의 비례하지 않고 짧게 유지되도록 설계되어 있다 — 다만 정확한 수치는 워크로드와 하드웨어에 따라 달라지므로, 특정 ms 값을 절대적인 보장치로 받아들이기보다는 "설계상 목표"로 이해하는 것이 맞다. Generational ZGC 도입 이후로는 Young 세대를 자주, 가볍게 수집하도록 바뀌면서 처리량 측면의 약점도 눈에 띄게 개선됐다.

## 핵심 개념 3: G1 vs ZGC, 무엇을 선택할까

| 항목 | G1 GC | ZGC (Generational) |
|---|---|---|
| 설계 목표 | 처리량과 지연시간의 균형 | 저지연 우선, 짧고 예측 가능한 일시정지 |
| 도입 시점(참고) | JDK 9부터 기본 GC | JDK 15 프로덕션, JDK 21 세대별 모드 실험 도입 |
| 힙 구조 | Region 기반, Young/Old/Humongous | Region 기반 + 세대 분리, 컬러 포인터 활용 |
| 일시정지 시간 | `MaxGCPauseMillis`로 목표 설정(노력 목표) | 힙 크기에 덜 민감하게 짧은 정지를 목표로 설계 |
| 메모리·CPU 오버헤드 | 상대적으로 낮음 | 동시 실행 작업이 많아 CPU·메모리 사용량이 더 필요할 수 있음 |
| 적합한 상황 | 범용 웹 서비스, 배치+온라인 혼합 워크로드 | 응답 지연 SLA가 엄격한 서비스, 대형 힙 운용 시 |

일반적인 CRUD 백엔드나 배치 혼합 워크로드라면 G1로 충분한 경우가 많다. 반면 P99 레이턴시 자체가 SLA인 서비스거나, 힙을 수십 GB 이상 크게 잡는데 GC 정지가 그 크기에 비례해 길어지는 게 부담스럽다면 ZGC를 검토할 이유가 충분하다.

## 예제: G1과 ZGC JVM 옵션 비교

```bash
# G1 GC — 범용 튜닝 예시
java \
  -XX:+UseG1GC \
  -Xms4g -Xmx4g \
  -XX:MaxGCPauseMillis=200 \
  -XX:G1HeapRegionSize=8m \
  -Xlog:gc*:file=gc-g1.log:time,uptime,level,tags \
  -jar app.jar

# ZGC(Generational) — 저지연 튜닝 예시
java \
  -XX:+UseZGC \
  -XX:+ZGenerational \
  -Xms8g -Xmx8g \
  -XX:SoftMaxHeapSize=6g \
  -Xlog:gc*:file=gc-zgc.log:time,uptime,level,tags \
  -jar app.jar
```

`-XX:+ZGenerational` 플래그는 이후 릴리스에서 기본값으로 흡수되는 방향으로 발전 중이라 JDK 버전마다 필요 여부가 다를 수 있으니, 배포 전 공식 문서로 유효성을 확인한다. `SoftMaxHeapSize`는 ZGC에게 "가능하면 이 크기 이하로 유지하라"는 힌트를 주는 옵션으로, `Xmx`보다 낮게 잡아 여유분을 남겨두는 용도다.

## 실무 포인트

- **GC 로그 없이 튜닝하지 않는다**: `-Xlog:gc*`를 항상 켜 두고 일시정지 빈도·길이·Full GC 발생 여부를 먼저 관찰한 뒤 옵션을 바꾼다.
- **컨테이너 CPU 제한을 함께 고려한다**: GC 스레드 수는 가용 코어 수 기준으로 정해지는데, cgroup 제한과 인식된 코어 수가 어긋나면 GC가 예상보다 느려질 수 있다. 필요하면 `-XX:ActiveProcessorCount`로 명시한다.
- **ZGC는 동시 실행만큼 리소스 여유가 필요하다**: 리소스가 빠듯한 환경에서는 오히려 전체 처리량이 G1보다 떨어질 수 있으므로 부하 테스트로 실측하고 결정한다.
- **워밍업 이후 기준으로 판단한다**: JIT 컴파일이 안정화되기 전 초기 구간의 GC 지표는 정상 운영 상태를 대표하지 않는다.

## 3줄 요약

- G1은 처리량과 지연시간의 균형을 노리는 범용 기본 GC이고, ZGC는 짧고 예측 가능한 일시정지를 목표로 설계된 저지연 특화 GC다.
- 응답 지연 SLA가 엄격하거나 대형 힙을 운용해야 하는 서비스라면 Generational ZGC 도입을 검토할 가치가 있다.
- 어떤 GC든 로그 기반 관찰, 컨테이너 CPU 제한 고려, 워밍업 이후 지표 비교라는 기본 원칙 없이는 제대로 튜닝하기 어렵다.

## 참고 자료

- [OpenJDK — Garbage-First Garbage Collector (G1) Tuning Guide](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector.html)
- [JEP 439: Generational ZGC](https://openjdk.org/jeps/439)
- [OpenJDK Wiki — ZGC](https://wiki.openjdk.org/display/zgc)
