---
layout: single
title: "SSL 인증서 만료 직전, 뭘 확인해야 할까 — Let's Encrypt 자동 갱신 점검"
date: 2026-09-01 13:40:00 +0530
categories: infra
tags: ["ssl", "https", "letsencrypt", "인증서갱신", "트러블슈팅"]
toc: true
toc_sticky: true
excerpt: "SSL 인증서 만료로 서비스 장애가 나기 전에, Let's Encrypt 자동 갱신이 제대로 동작하는지 확인하는 방법과 흔한 실패 원인을 정리했다."
---

## 왜 자동 갱신을 설정했는데도 만료 사고가 나는가

Let's Encrypt 인증서는 유효기간이 90일로 짧기 때문에 처음부터 자동 갱신을 전제로 설계됐다. 문제는 "자동 갱신을 설정해뒀다"는 사실만으로 안심하고 그 뒤로 전혀 확인하지 않다가, 갱신 스크립트가 조용히 실패하고 있었던 것을 만료 당일에야 알게 되는 경우다. 브라우저에 "안전하지 않음" 경고가 뜨고 나서야 문제를 알아채면 이미 사용자에게 노출된 뒤다.

## 갱신 실패의 흔한 원인

| 원인 | 증상 | 확인 방법 |
|---|---:|---|
| 갱신 스크립트의 cron 자체가 등록 안 됨 | 만료 직전까지 아무 로그도 없음 | `crontab -l` 또는 systemd timer 확인 |
| 도메인 인증(HTTP-01)용 포트가 막힘 | 갱신 시도 로그에 타임아웃 | 80번 포트가 방화벽에 막혀 있는지 확인 |
| Nginx reload 누락 | 갱신은 성공했지만 서비스는 옛 인증서 사용 중 | 갱신 후 reload hook 등록 여부 확인 |
| Rate Limit 초과 | 반복 실패 로그에 rate limit 문구 | 짧은 기간 반복 발급 시도했는지 확인 |

## 확인 및 대응 명령

```bash
# 1. 인증서 만료일 직접 확인
echo | openssl s_client -servername example.com -connect example.com:443 2>/dev/null | openssl x509 -noout -dates

# 2. Let's Encrypt 인증서 상태 및 자동 갱신 대상 확인
sudo certbot certificates

# 3. 실제로 갱신이 되는지 dry-run으로 테스트 (실제 발급 없이 시뮬레이션)
sudo certbot renew --dry-run

# 4. 갱신 후 웹서버 reload가 자동으로 걸리는지 확인
cat /etc/letsencrypt/renewal/example.com.conf | grep deploy_hook
```

`--dry-run`은 실제 인증서를 발급하지 않고 갱신 프로세스만 검증하므로, Rate Limit 걱정 없이 정기적으로 점검할 수 있는 안전한 방법이다.

## 실무 포인트

- **만료 임박 모니터링을 인증서 자체와 별개로 외부에서 확인해야 한다.** 서버 안의 cron만 믿지 말고, 외부 모니터링 서비스(Uptime 체크 도구 등)로 인증서 만료일을 주기적으로 확인하는 것이 이중 안전장치가 된다.
- **로드밸런서나 CDN에서 SSL을 종료하는 구조라면, 인증서 갱신 위치가 오리진 서버가 아니라 로드밸런서/CDN 쪽일 수 있다.** 갱신 위치를 헷갈려 오리진 서버만 계속 확인하다 시간을 낭비하는 경우가 많다.
- **Let's Encrypt는 짧은 기간 반복 발급 시 Rate Limit에 걸린다.** 테스트할 때는 반드시 스테이징 환경(`--staging` 옵션)을 사용해야 실제 서비스 발급 한도를 소모하지 않는다.

## 마무리 요약

- 자동 갱신을 설정했다고 끝난 것이 아니라, `--dry-run`으로 정기적으로 실제 동작을 검증해야 한다.
- 갱신은 성공했는데 서비스가 옛 인증서를 계속 쓰는 경우가 있으므로 reload hook까지 확인해야 한다.
- 외부 모니터링으로 인증서 만료일을 이중 확인하는 것이 사고를 막는 가장 확실한 방법이다.

## 참고 자료

- [Let's Encrypt 공식 문서](https://letsencrypt.org/docs/)
- [Certbot 공식 문서](https://certbot.eff.org/docs/)
