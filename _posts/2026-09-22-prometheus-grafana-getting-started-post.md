---
layout: single
title: "Prometheus와 Grafana로 컨테이너 모니터링 대시보드 만들기 — 첫 설정 가이드"
date: 2026-09-22 13:40:00 +0530
categories: infra
tags: ["prometheus", "grafana", "모니터링", "도커컴포즈", "관측성"]
toc: true
toc_sticky: true
excerpt: "서버가 느려질 때마다 SSH로 접속해 top과 로그를 뒤지는 대신, Prometheus와 Grafana를 docker-compose로 함께 띄워 첫 대시보드를 만드는 과정을 흔한 실수와 함께 정리했다."
---

## 왜 로그만으로는 한계에 부딪히나

서비스 초기에는 문제가 생기면 서버에 SSH로 접속해 `top`으로 CPU·메모리를 확인하고, 로그 파일을 `tail -f`로 지켜보는 방식으로 충분하다. 하지만 서버가 여러 대로 늘고, 요청량 추이나 에러율 변화를 시간에 따라 추적해야 하는 상황이 오면 이 방식은 급격히 한계를 드러낸다. "어제 오후 3시쯤부터 응답이 느려졌다"는 사용자 제보를 받았을 때, 그 시점의 CPU·메모리·요청량이 어땠는지 즉시 확인할 방법이 없다면 원인 파악에 걸리는 시간이 길어진다.

**Prometheus**는 시계열 형태로 메트릭(수치 데이터)을 주기적으로 수집·저장하는 시스템이고, **Grafana**는 그 데이터를 시각적인 대시보드로 보여주는 도구다. 이 둘을 함께 쓰면 "지금 얼마나 바쁜지"뿐 아니라 "지난 일주일 동안 어떻게 변해왔는지"까지 한눈에 확인할 수 있는 모니터링 체계를 만들 수 있다.

## 첫 설정: docker-compose로 한 번에 띄우기

가장 빠르게 시작하는 방법은 Prometheus, Grafana, 그리고 리눅스 호스트 자체의 지표(CPU, 메모리, 디스크)를 수집하는 `node_exporter`를 docker-compose 하나로 함께 띄우는 것이다.

```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=changeme
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['node_exporter:9100']
```

여기서 처음 설정할 때 자주 놓치는 부분이 `scrape_configs`의 `targets`에 서비스 이름(`node_exporter`)을 그대로 쓴다는 점이다. docker-compose 네트워크 안에서는 서비스 이름이 곧 호스트명으로 동작하므로, `localhost`나 IP 대신 compose에서 정의한 서비스 이름을 써야 Prometheus 컨테이너가 다른 컨테이너를 찾을 수 있다.

## 흔한 실수: Grafana에 데이터소스 연결을 빠뜨리기

컨테이너를 다 띄웠는데 Grafana 대시보드에 아무 데이터도 안 나온다며 당황하는 경우가 많다. Grafana는 Prometheus와 자동으로 연결되지 않으며, 반드시 **데이터소스(Data Source)** 를 수동으로 등록해야 한다.

1. Grafana(`localhost:3000`)에 로그인 (기본 계정 admin, 위에서 설정한 비밀번호)
2. `Connections > Data sources > Add data source`에서 Prometheus 선택
3. URL에 `http://prometheus:9090` 입력 (역시 서비스 이름 사용)
4. `Save & Test`로 연결 확인

<img src="/assets/images/posts/2026-09-22-prometheus-grafana-getting-started-1.svg" alt="node_exporter가 지표를 노출하면 Prometheus가 주기적으로 가져와 저장하고 Grafana가 이를 조회해 대시보드로 시각화하는 흐름도" style="width:100%;">

## 첫 대시보드: 이미 만들어진 것부터 가져오기

`node_exporter`처럼 널리 쓰이는 익스포터는 커뮤니티가 이미 잘 만들어둔 대시보드를 Grafana 공식 저장소에서 ID로 바로 가져올 수 있다. 처음부터 패널을 하나하나 만들기보다, 검증된 대시보드를 가져와 필요에 맞게 수정하는 편이 훨씬 빠르다.

```
Grafana > Dashboards > New > Import
Dashboard ID 입력 (node_exporter full: 1860)
데이터소스로 방금 등록한 Prometheus 선택
```

이 방법으로 CPU 사용률, 메모리, 디스크 I/O, 네트워크 트래픽 같은 핵심 지표가 담긴 대시보드를 몇 분 안에 확인할 수 있다.

## 실무 포인트

- **scrape_interval을 너무 짧게 잡지 마라.** 15초 정도가 일반적인 시작점이며, 지나치게 짧게 잡으면 Prometheus 자체의 저장 공간과 CPU 부담이 커진다. 세밀한 지표가 필요한 특정 작업에만 별도로 짧은 주기를 적용하는 것이 낫다.
- **레이블 카디널리티에 주의하라.** 사용자 ID나 요청 ID처럼 값의 종류가 무한히 늘어나는 항목을 레이블로 붙이면 Prometheus 메모리 사용량이 폭발적으로 증가할 수 있다. 레이블은 값의 종류가 제한적인 항목(HTTP 메서드, 상태 코드, 엔드포인트 그룹)에만 쓴다.
- **알림(Alerting)은 대시보드를 다 만든 뒤 마지막 단계로 설정하라.** 지표를 눈으로 보는 것과 임계치를 넘었을 때 자동으로 알려주는 것은 다른 작업이다. 먼저 정상 범위의 지표 패턴을 파악한 뒤 알림 규칙을 설정해야 오탐(false positive)을 줄일 수 있다.
- **데이터 보존 기간을 계획하라.** Prometheus는 기본적으로 로컬 디스크에 시계열 데이터를 쌓는데, 장기 보관이 필요하면 Thanos나 Mimir 같은 장기 저장소 연동을 별도로 검토해야 한다.

## 마무리 요약

- 서버가 여러 대로 늘어나고 시간에 따른 추이를 봐야 하는 순간부터, SSH로 직접 확인하는 방식은 한계에 부딪힌다.
- Prometheus는 메트릭을 주기적으로 수집·저장하고, Grafana는 이를 대시보드로 시각화하는 역할을 분담하며, docker-compose로 손쉽게 함께 띄울 수 있다.
- 서비스 이름 기반 네트워킹, 데이터소스 수동 등록, 커뮤니티 대시보드 임포트라는 세 가지를 챙기면 첫 모니터링 체계를 빠르게 구축할 수 있다.

## 참고 자료

- [Prometheus 공식 문서 - Getting started](https://prometheus.io/docs/prometheus/latest/getting_started/)
- [Grafana 공식 문서 - Data sources](https://grafana.com/docs/grafana/latest/datasources/)
