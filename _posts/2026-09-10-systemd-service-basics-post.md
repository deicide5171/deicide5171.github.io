---
layout: single
title: "systemd 서비스가 뭔가요 — 프로그램을 서버 부팅 시 자동 실행하기"
date: 2026-09-10 13:40:00 +0530
categories: infra
tags: ["systemd", "서비스", "리눅스", "데몬", "입문"]
toc: true
toc_sticky: true
excerpt: "리눅스에서 프로그램을 백그라운드 서비스로 등록해 부팅 시 자동 실행하고 죽으면 재시작하는 systemd 사용법을 처음 배우는 사람 기준으로 정리했다."
---

## 터미널을 닫으면 프로그램도 꺼진다

서버에서 `python app.py`로 프로그램을 실행하면, SSH 접속을 끊거나 서버가 재부팅되면 프로그램도 함께 꺼진다. 프로그램이 **항상 떠 있고, 죽으면 다시 살아나고, 부팅 시 자동 시작**되게 하려면 서비스로 등록해야 한다. 리눅스에서는 **systemd**가 이 역할을 한다.

## systemd로 할 수 있는 것

| 기능 | 설명 |
|---|---|
| 자동 시작 | 서버 부팅 시 함께 실행 |
| 자동 재시작 | 프로세스가 죽으면 다시 실행 |
| 로그 관리 | `journalctl`로 로그 조회 |
| 상태 확인 | `systemctl status`로 확인 |

## 서비스 파일 예시

```text
# /etc/systemd/system/myapp.service
[Unit]
Description=My App
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/user/app.py
Restart=always          # 죽으면 재시작
User=appuser

[Install]
WantedBy=multi-user.target
```

등록 후 명령:

```text
sudo systemctl daemon-reload    # 서비스 파일 반영
sudo systemctl enable myapp     # 부팅 시 자동 시작 설정
sudo systemctl start myapp      # 지금 시작
systemctl status myapp          # 상태 확인
journalctl -u myapp -f          # 로그 실시간 보기
```

## 실무 포인트

- **`enable`과 `start`는 다르다.** `start`는 지금 실행, `enable`은 부팅 시 자동 시작 설정이다. 둘 다 해야 "지금도 켜지고 재부팅 후에도 켜진다".
- **`Restart` 정책을 정하라.** `Restart=always`는 무조건 재시작, `on-failure`는 비정상 종료 시만 재시작이다. 재시작 폭주를 막으려면 `RestartSec`으로 간격도 준다.
- **로그는 `journalctl`로 본다.** systemd 서비스의 출력은 저널에 쌓인다. `journalctl -u 서비스명`으로 조회하고, 문제 발생 시 `-f`로 실시간 추적한다. 컨테이너 환경에선 systemd 대신 오케스트레이터가 이 역할을 한다.

## 마무리 요약

- systemd 서비스는 프로그램을 부팅 시 자동 실행하고, 죽으면 재시작하며, 로그를 관리한다.
- `.service` 파일에 실행 명령·재시작 정책을 정의하고 `enable`+`start`로 등록·실행한다.
- `enable`(부팅 자동)과 `start`(지금 실행)를 구분하고, 로그는 `journalctl`로 확인한다.

## 참고 자료

- [systemd 공식 문서](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
