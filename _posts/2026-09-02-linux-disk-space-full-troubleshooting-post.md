---
layout: single
title: "디스크 공간이 꽉 찼을 때 뭘 지워야 할까 — 리눅스 디스크 사용량 진단"
date: 2026-09-02 13:40:00 +0530
categories: infra
tags: ["리눅스", "디스크사용량", "트러블슈팅", "df", "인프라"]
toc: true
toc_sticky: true
excerpt: "리눅스 서버에서 No space left on device 에러가 났을 때, 무엇이 공간을 차지하고 있는지 빠르게 찾아 정리하는 방법을 정리했다."
---

## df는 꽉 찼다고 하는데 뭘 지워야 할지 모르겠다면

`df -h`로 디스크가 꽉 찼다는 것은 확인했는데, 정작 어느 디렉터리가 그 공간을 차지하고 있는지 몰라 막막한 경우가 많다. 무작정 로그 파일을 지우다가 필요한 데이터까지 삭제하는 사고로 이어질 수 있으므로, 순서대로 원인을 좁혀가는 것이 중요하다.

## 진단 순서

```bash
# 1. 전체 디스크 사용률 확인
df -h

# 2. 어느 디렉터리가 큰지 상위 레벨부터 확인
du -sh /* 2>/dev/null | sort -rh | head -10

# 3. 의심되는 디렉터리를 한 단계씩 더 파고들기
du -sh /var/log/* 2>/dev/null | sort -rh | head -10

# 4. 최근에 급격히 커진 파일 찾기 (예: 최근 1일 내 100MB 이상)
find / -type f -size +100M -mtime -1 2>/dev/null
```

`du -sh /*`를 상위 디렉터리부터 시작해 점점 하위로 내려가면, 어느 경로가 공간을 차지하는지 트리 구조로 빠르게 좁혀갈 수 있다.

## 자주 범인으로 지목되는 위치

| 위치 | 흔한 원인 |
|---|---|
| `/var/log` | 로그 로테이션 설정 누락으로 로그가 무한히 쌓임 |
| `/var/lib/docker` | 사용하지 않는 이미지·컨테이너·볼륨이 정리 안 됨 |
| `/tmp` | 임시 파일이 정리되지 않고 계속 쌓임 |
| 애플리케이션 업로드 디렉터리 | 사용자 업로드 파일이 예상보다 빠르게 증가 |

## 흔한 대응 명령

```bash
# Docker 관련 불필요한 리소스 정리 (사용 중이 아닌 것만 삭제)
docker system prune -a

# journald 로그가 과도하게 쌓인 경우 크기 제한
journalctl --vacuum-size=200M

# 로그 로테이션이 설정되어 있는지 확인
cat /etc/logrotate.d/*
```

## 실무 포인트

- **`df`와 `du`의 결과가 다를 때가 있다.** 파일을 지웠는데도 프로세스가 그 파일을 계속 열고 있으면(파일 디스크립터가 살아있으면) 디스크 공간이 바로 회수되지 않는다. 이 경우 해당 프로세스를 재시작해야 실제로 공간이 반환된다.
- **`docker system prune`은 사용하지 않는 리소스만 지우지만, `-a` 옵션을 쓰면 태그가 없는 이미지까지 광범위하게 삭제한다.** 운영 서버에서는 무엇이 삭제되는지 먼저 `--dry-run`류의 확인 없이 바로 실행하지 않는 것이 안전하다.
- **디스크 공간 문제는 한 번 해결해도 재발하기 쉽다.** 근본적으로는 로그 로테이션, 오래된 백업 자동 삭제, 디스크 사용률 알림(모니터링)을 함께 설정해야 같은 사고가 반복되지 않는다.

## 마무리 요약

- `du -sh /* | sort -rh`로 상위 디렉터리부터 점점 좁혀가는 것이 원인을 빠르게 찾는 방법이다.
- `/var/log`, Docker 리소스, `/tmp`가 디스크를 채우는 가장 흔한 범인이다.
- 파일을 지워도 공간이 회수되지 않으면 그 파일을 물고 있는 프로세스를 의심해야 한다.

## 참고 자료

- [Docker 공식 문서 - 시스템 정리](https://docs.docker.com/engine/manage-resources/pruning/)
- [Red Hat 공식 문서 - 로그 로테이션](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/assembly_managing-log-files-with-logrotate_configuring-basic-system-settings)
