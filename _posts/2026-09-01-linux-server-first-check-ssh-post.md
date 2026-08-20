---
layout: single
title: "리눅스 서버 처음 접속했을 때 확인해야 할 것들 — SSH 기초 체크리스트"
date: 2026-09-01 12:40:00 +0530
categories: infra
tags: ["리눅스", "ssh", "서버관리", "입문", "체크리스트"]
toc: true
toc_sticky: true
excerpt: "새로 받은 리눅스 서버에 SSH로 처음 접속했을 때, 보안과 운영을 위해 가장 먼저 확인하고 설정해야 할 항목들을 정리했다."
---

## 왜 접속하자마자 바로 작업을 시작하면 안 되는가

새 서버를 받으면 바로 애플리케이션 배포부터 시작하고 싶은 마음이 들지만, 기본적인 서버 상태와 보안 설정을 먼저 확인하지 않으면 나중에 더 큰 문제로 돌아온다. 특히 클라우드에서 발급받은 서버는 기본 설정이 보안상 최소한만 되어 있는 경우가 많다.

## 접속 직후 확인 체크리스트

| 항목 | 확인 명령 | 왜 중요한가 |
|---|---|---|
| 시스템 정보 | `uname -a`, `cat /etc/os-release` | OS 버전에 맞는 패키지 관리자·문서 확인 |
| 디스크 여유 공간 | `df -h` | 배포 도중 디스크 부족으로 실패하는 것을 사전 방지 |
| 메모리·CPU | `free -h`, `nproc` | 애플리케이션 리소스 설정값 결정 |
| 열려 있는 포트 | `ss -tulnp` | 불필요하게 열린 서비스 파악 |
| 방화벽 상태 | `sudo ufw status` 또는 `firewall-cmd --list-all` | 의도한 포트만 열려 있는지 확인 |

## 최우선으로 해야 할 보안 설정

```bash
# 1. root 직접 로그인 비활성화, 비밀번호 로그인 대신 키 인증만 허용
sudo vi /etc/ssh/sshd_config
# PermitRootLogin no
# PasswordAuthentication no

# 2. SSH 포트 변경(선택, 자동 스캔 봇 노출 감소)
# Port 2222

# 3. 설정 반영
sudo systemctl restart sshd

# 4. 기본 방화벽 규칙 설정 (필요한 포트만 열기)
sudo ufw allow 2222/tcp   # 변경한 SSH 포트
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

`PasswordAuthentication no`로 바꾸기 전에 **반드시 키 인증으로 접속이 되는지 먼저 확인**해야 한다. 확인 없이 바꿨다가 키 설정이 잘못됐으면 서버에서 완전히 잠겨버릴 수 있다.

## 실무 포인트

- **`sudo` 없이 root로 상시 작업하는 습관은 피해야 한다.** 일반 사용자 계정을 만들고 `sudo` 그룹에 추가해 필요할 때만 권한을 상승시키는 것이 실수를 줄이는 방법이다.
- **자동 보안 업데이트(`unattended-upgrades` 등)를 켜두면 치명적인 취약점 패치를 놓치지 않는다.** 다만 운영 서버는 자동 재시작이 예기치 않은 다운타임을 만들 수 있으니 재시작 정책은 별도로 검토해야 한다.
- **클라우드 서버라면 보안 그룹(Security Group)이나 방화벽 규칙이 이미 클라우드 콘솔에서 관리되고 있을 수 있다.** 서버 내부 방화벽과 클라우드 방화벽이 이중으로 걸려 있으면 포트가 안 열리는 원인을 서버 안에서만 찾다가 시간을 낭비할 수 있다.

## 마무리 요약

- 접속 직후에는 배포보다 시스템 상태·리소스·열린 포트부터 확인하는 것이 순서다.
- 비밀번호 로그인 비활성화는 키 인증이 확실히 되는 것을 확인한 뒤에 적용해야 한다.
- 클라우드 환경에서는 서버 내부 방화벽과 클라우드 보안 그룹을 모두 확인해야 포트 문제를 놓치지 않는다.

## 참고 자료

- [Ubuntu 공식 문서 - OpenSSH 서버](https://ubuntu.com/server/docs/openssh-server)
- [DigitalOcean - 초기 서버 설정 가이드](https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu-22-04)
