---
layout: single
title: "io_uring으로 리눅스 I/O 성능 한계 넘기 — epoll 다음 이야기"
date: 2026-08-22 12:40:00 +0530
categories: infra
tags: ["infra", "linux", "io-uring", "epoll", "syscall", "performance"]
toc: true
toc_sticky: true
excerpt: "epoll조차 시스템 콜 오버헤드에서 자유롭지 못한 고성능 I/O 시나리오에서, 공유 링 버퍼로 커널과 통신하는 io_uring이 어떻게 이를 극복하는지 정리한다."
---

epoll은 select/poll이 가진 "감시 대상이 늘어날수록 매번 전체 목록을 커널에 넘겨야 하는" 문제를 해결하면서, 오랫동안 리눅스에서 대규모 동시 연결을 다루는 표준 방식으로 자리 잡았다. 커널이 이벤트 발생 여부를 미리 추적해두고 준비된 파일 디스크립터만 골라 돌려주기 때문에, 감시 대상 수에 비례해 매 호출 비용이 커지는 문제는 확실히 줄어든다.

그런데 epoll이 최적화하는 지점은 어디까지나 "무엇이 준비됐는지 통지받는" 단계다. 실제로 데이터를 읽고 쓰는 read/write 시스템 콜 자체는 여전히 이벤트 하나마다 별도로 호출해야 하고, 각 호출은 사용자 공간과 커널 공간을 오가는 컨텍스트 스위치 비용을 수반한다. 초당 수만~수십만 건의 I/O를 처리하는 서버라면, 이 시스템 콜 자체의 누적 오버헤드가 무시할 수 없는 비중을 차지하게 된다. 또한 epoll_wait 이후 각 fd에 대해 다시 read/write를 호출하는 구조는, 요청과 실행 사이에 최소 두 번의 커널 진입을 강제한다는 점에서 근본적인 한계를 안고 있다.

io_uring은 이 문제를 다른 각도에서 접근한다. 이벤트 통지 방식을 개선하는 대신, 애초에 시스템 콜 자체를 줄이거나 아예 없애는 쪽으로 설계됐다. 사용자 공간과 커널이 메모리를 공유하는 링 버퍼를 통해 요청과 결과를 주고받음으로써, 매 I/O마다 커널에 진입할 필요를 없애는 것이 핵심 아이디어다. 이 글에서는 io_uring이 이를 구현하는 기본 구조와, epoll 기반 모델과 비교했을 때 어떤 지점에서 차이가 나는지를 정리한다.

## 핵심 개념 1: 제출 큐(SQ)와 완료 큐(CQ)라는 공유 메모리 구조

io_uring의 핵심은 `io_uring_setup` 시스템 콜로 커널에 두 개의 링 버퍼를 만들고, 이를 `mmap`으로 사용자 공간에 매핑해 커널과 애플리케이션이 동일한 메모리를 직접 들여다보게 만드는 것이다. 하나는 **제출 큐(Submission Queue, SQ)**로, 애플리케이션이 수행하고 싶은 I/O 요청(`io_uring_sqe` 구조체)을 채워 넣는 공간이다. 다른 하나는 **완료 큐(Completion Queue, CQ)**로, 커널이 처리를 끝낸 요청의 결과(`io_uring_cqe` 구조체)를 채워 넣는 공간이다.

두 큐 모두 링 버퍼이므로 헤드(head)와 테일(tail) 포인터로 위치를 관리한다. 애플리케이션은 SQ의 테일을 옮겨 새 요청을 넣고, 커널은 SQ의 헤드를 옮겨 요청을 가져가 처리한다. 반대로 커널은 CQ의 테일을 옮겨 완료 결과를 넣고, 애플리케이션은 CQ의 헤드를 옮겨 결과를 소비한다. 이 포인터들 자체도 공유 메모리에 있기 때문에, "무엇을 요청했고 무엇이 끝났는지"를 확인하는 데 시스템 콜이 필요 없다. 그저 공유 메모리를 읽고 쓰는 것만으로 요청을 쌓고 결과를 확인할 수 있다.

## 핵심 개념 2: 배치 제출과 시스템 콜 횟수 감소

io_uring 이전 모델에서는 I/O 요청 하나마다 시스템 콜 하나가 대응된다. 반면 io_uring에서는 여러 개의 SQE를 SQ에 미리 채워둔 뒤, `io_uring_enter` 시스템 콜을 단 한 번만 호출해 "지금까지 쌓아둔 요청을 한꺼번에 커널에 알린다"는 방식을 취할 수 있다. 즉 N개의 I/O 요청을 처리하는 데 필요한 시스템 콜 수가 N번이 아니라 1번(또는 그보다 적은 횟수)으로 줄어드는 구조다.

여기서 한 걸음 더 나아가면, `IORING_SETUP_SQPOLL` 옵션으로 커널 스레드가 SQ를 주기적으로 폴링하도록 설정할 수도 있다. 이 모드에서는 애플리케이션이 SQE를 채워 넣기만 하면 커널 스레드가 알아서 가져가 처리하므로, 이상적인 조건에서는 `io_uring_enter` 호출조차 매번 필요하지 않게 된다. 다만 이 방식은 커널 스레드가 지속적으로 CPU를 점유하게 되므로, CPU 자원과 지연시간 사이의 트레이드오프를 감안해 선택해야 한다.

## 핵심 개념 3: epoll과 io_uring의 구조 비교

두 모델의 차이는 "무엇을 커널과 협상하는가"에서 갈린다. epoll은 준비 상태(readiness)를 통지하는 데는 효율적이지만, 실제 데이터 전송은 여전히 개별 시스템 콜에 의존한다. io_uring은 요청 제출과 완료 통지 모두를 공유 메모리 큐로 옮겨, 통지와 실행을 하나의 파이프라인 안에서 처리한다.

| 구분 | epoll | io_uring |
|---|---|---|
| 통지 방식 | 준비된 fd 목록을 시스템 콜로 반환 | 완료 결과를 공유 CQ에 적재 |
| I/O 실행 | 이벤트마다 별도의 read/write 호출 필요 | SQE 제출 후 커널이 비동기로 처리 |
| 시스템 콜 빈도 | 이벤트 수에 비례 | 배치 제출로 감소, SQPOLL로 추가 절감 가능 |
| 비동기 지원 대상 | 소켓 등 준비 상태 개념이 있는 fd 위주 | 파일 I/O, 네트워크, 타이머 등 폭넓게 지원 |
| 커널 요구 버전 | 오래전부터 안정적으로 지원 | 5.1 이상, 기능별로 더 최신 버전 필요 |

<img src="/assets/images/posts/2026-08-22-linux-io-uring-performance-1.svg" alt="애플리케이션과 커널이 mmap으로 공유하는 SQ(제출 큐)와 CQ(완료 큐) 링 버퍼를 통해 요청과 완료 결과를 주고받는 io_uring 구조도" style="width:100%;">

## 예제

아래는 liburing을 사용해 파일 하나를 읽는 가장 기본적인 흐름을 정리한 예시다. 실제 프로덕션 코드에서는 오류 처리와 버퍼 관리가 훨씬 정교해야 하지만, SQ에 요청을 채우고 CQ에서 결과를 꺼내는 핵심 흐름은 이 구조를 벗어나지 않는다.

```c
#include <liburing.h>
#include <fcntl.h>
#include <stdio.h>

int main(void) {
    struct io_uring ring;
    struct io_uring_sqe *sqe;
    struct io_uring_cqe *cqe;
    struct iovec iov;
    char buf[4096];

    // 1) 링 초기화: SQ/CQ 각각 8개 엔트리 크기로 설정
    io_uring_queue_init(8, &ring, 0);

    int fd = open("example.txt", O_RDONLY);
    iov.iov_base = buf;
    iov.iov_len = sizeof(buf);

    // 2) SQ에 read 요청을 채워 넣는다 (시스템 콜 없이 메모리에만 기록)
    sqe = io_uring_get_sqe(&ring);
    io_uring_prep_readv(sqe, fd, &iov, 1, 0);

    // 3) 지금까지 쌓인 SQE를 커널에 알린다 (여기서만 시스템 콜 발생)
    io_uring_submit(&ring);

    // 4) 완료를 기다렸다가 CQ에서 결과를 꺼낸다
    io_uring_wait_cqe(&ring, &cqe);
    if (cqe->res < 0) {
        fprintf(stderr, "read 실패: %d\n", cqe->res);
    } else {
        printf("읽은 바이트 수: %d\n", cqe->res);
    }

    // 5) 처리 완료를 커널에 알려 CQE 슬롯을 회수시킨다
    io_uring_cqe_seen(&ring, cqe);

    io_uring_queue_exit(&ring);
    close(fd);
    return 0;
}
```

요청 하나만 다룬 예시지만, 실제로는 여러 개의 SQE를 연속으로 채운 뒤 `io_uring_submit`을 한 번만 호출하고, CQ를 순회하며 여러 결과를 한꺼번에 처리하는 배치 패턴으로 확장하는 것이 io_uring의 이점을 살리는 일반적인 사용법이다.

## 실무 포인트

- **커널 버전 호환성을 먼저 확인한다**: io_uring은 리눅스 5.1에서 처음 도입됐지만, 초기 버전은 기능이 제한적이고 보안 이슈도 몇 차례 보고된 바 있다. `IORING_SETUP_SQPOLL`이나 파일 등록(`io_uring_register`) 같은 세부 기능은 도입 시점이 서로 다르므로, 대상 배포판의 커널 버전과 필요한 기능이 실제로 그 버전에 포함돼 있는지를 커널 문서나 changelog로 직접 확인해야 한다.
- **컨테이너·클라우드 환경에서의 제약을 점검한다**: 일부 관리형 컨테이너 런타임이나 클라우드 환경은 보안 정책상 io_uring 관련 시스템 콜을 seccomp 프로파일에서 차단하거나 제한적으로만 허용하는 경우가 있다. 배포 대상 환경에서 실제로 io_uring이 허용되는지 사전에 검증하는 절차가 필요하다.
- **아직 io_uring을 채택하지 않은 런타임이 많다**: Node.js, 대부분의 JVM 기반 런타임, 여러 언어의 표준 네트워킹 라이브러리는 여전히 epoll 기반 이벤트 루프를 기본으로 사용한다. io_uring 지원이 추가된 런타임이나 라이브러리라도 실험적 단계이거나 일부 기능만 지원하는 경우가 있으므로, 도입 전 해당 생태계의 지원 범위와 성숙도를 확인하는 편이 안전하다.
- **동기 폴백 경로를 함께 준비한다**: io_uring이 비활성화된 환경에서도 서비스가 동작해야 한다면, epoll 기반 경로를 완전히 걷어내기보다는 두 구현을 함께 유지하며 런타임에 감지해 전환하는 구조를 고려할 만하다.

## 3줄 요약

- epoll은 이벤트 통지는 효율화했지만 read/write 시스템 콜 자체의 호출 횟수와 오버헤드는 줄이지 못한다.
- io_uring은 SQ/CQ라는 공유 링 버퍼로 요청 제출과 완료 통지를 커널과 직접 주고받아, 시스템 콜 횟수 자체를 배치 단위로 줄인다.
- 커널 버전 호환성과 런타임·라이브러리의 지원 성숙도를 먼저 점검한 뒤, epoll 경로와 병행하며 도입하는 편이 안전하다.

## 참고 자료

- [io_uring 공식 매뉴얼(io_uring(7)) - man7.org](https://man7.org/linux/man-pages/man7/io_uring.7.html)
- [io_uring_setup(2) man page](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html)
- [io_uring_enter(2) man page](https://man7.org/linux/man-pages/man2/io_uring_enter.2.html)
- [liburing GitHub 저장소](https://github.com/axboe/liburing)
- [Efficient IO with io_uring (Jens Axboe, kernel.dk PDF)](https://kernel.dk/io_uring.pdf)
- [LWN: Ringing in a new asynchronous I/O API](https://lwn.net/Articles/776703/)
