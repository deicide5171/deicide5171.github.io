---
layout: single
title: "가상 스레드가 갑자기 안 가벼워지는 순간 — Virtual Thread Pinning 문제와 해결"
date: 2026-08-27 12:25:00 +0530
categories: backend
tags: ["java", "virtual-threads", "pinning", "jvm", "concurrency", "loom"]
toc: true
toc_sticky: true
excerpt: "가상 스레드를 도입했는데 캐리어 스레드 개수만큼만 동시성이 나온다면 피닝을 의심해야 한다. 원인과 감지, 해결 방법을 정리한다."
---

Virtual Thread를 도입하면서 기대하는 것은 "수백만 개를 만들어도 가벼운" 동시성이다. 캐리어 스레드(OS 스레드) 소수 위에 가상 스레드 수만 개를 올려두고, 블로킹 호출이 발생하면 가상 스레드는 캐리어 스레드에서 내려가(unmount) 다른 가상 스레드가 그 캐리어를 쓸 수 있게 양보한다. 그런데 특정 상황에서는 이 양보가 일어나지 않고 가상 스레드가 캐리어 스레드에 "고정(pinned)"된 채 블로킹된다. 이렇게 되면 그 캐리어 스레드는 다른 가상 스레드를 전혀 처리하지 못해, 결국 동시성이 캐리어 스레드 개수(기본적으로 CPU 코어 수)로 축소된다.

문제는 이 현상이 조용히 일어난다는 점이다. 애플리케이션은 정상적으로 동작하지만 부하 테스트에서 처리량이 예상보다 훨씬 낮게 나오고, 원인을 찾아보면 흔한 라이브러리 코드 안의 `synchronized` 블록이 범인인 경우가 많다. 이 글에서는 피닝이 왜 일어나는지, 어떻게 감지하는지, 어떻게 고치는지를 정리한다.

## 핵심 개념 1: 피닝이 발생하는 두 가지 경우

가상 스레드가 캐리어 스레드에 고정되는 대표적인 원인은 두 가지다.

첫째, **`synchronized` 블록/메서드 안에서 블로킹 작업을 수행할 때**다. JDK 21~23까지는 `synchronized`로 잠근 모니터를 쥔 채로 블로킹 호출(I/O, `Thread.sleep` 등)을 하면 JVM이 가상 스레드를 캐리어에서 분리할 수 없었다. 모니터 상태가 OS 스레드와 결합된 구현이었기 때문이다.

둘째, **JNI(네이티브 코드) 호출 중에 블로킹할 때**다. 네이티브 프레임이 스택에 있는 동안은 JVM이 가상 스레드를 다른 캐리어로 옮길 수 없어 피닝이 발생한다. JDBC 드라이버 중 일부가 네이티브 라이브러리를 호출하는 경우 이 문제에 걸릴 수 있다.

중요한 변화가 있다. **JEP 491(JDK 24)**은 `synchronized`로 인한 피닝 문제를 근본적으로 해결해, `synchronized` 블록 안에서 블로킹해도 더 이상 캐리어가 고정되지 않는다. 다만 JNI로 인한 피닝은 JDK 24에서도 여전히 남아 있고, JDK 24 미만 버전을 쓰는 프로덕션 환경은 여전히 `synchronized` 피닝에 노출돼 있다.

## 핵심 개념 2: 피닝 감지하기

피닝은 조용히 일어나므로 명시적으로 관측해야 잡을 수 있다. JDK는 두 가지 도구를 제공한다.

```bash
# 1. JFR(Java Flight Recorder)로 jdk.VirtualThreadPinned 이벤트 기록
java -XX:StartFlightRecording=filename=app.jfr,settings=profile MyApp

# 2. 피닝 발생 시 스택 트레이스를 즉시 로그로 출력 (문턱값 20ms 초과 시)
java -Djdk.tracePinnedThreads=full MyApp
```

`tracePinnedThreads=full`은 피닝이 20ms 넘게 지속될 때마다 그 시점의 전체 스택을 표준 출력에 찍어준다. 로컬 개발 중 의심 가는 코드 경로를 빠르게 확인할 때 유용하고, 운영 환경에서는 JFR로 지속 수집해 나중에 분석하는 편이 오버헤드가 적다.

<img src="/assets/images/posts/2026-08-27-virtual-threads-pinning-pitfalls-1.svg" alt="synchronized 블록 안에서 블로킹 호출 시 가상 스레드가 캐리어 스레드에 고정되어 다른 가상 스레드가 그 캐리어를 쓰지 못하는 구조와 ReentrantLock으로 교체했을 때 언마운트가 정상 동작하는 비교도" style="width:100%;">

## 예제: `synchronized`를 `ReentrantLock`으로 교체하기

```java
// 피닝 위험: synchronized 블록 안에서 블로킹 I/O 호출
public class LegacyCache {
    private final Map<String, String> store = new HashMap<>();

    public synchronized String getOrFetch(String key) {
        if (!store.containsKey(key)) {
            String value = httpClient.fetch(key); // 블로킹 I/O — 캐리어 고정!
            store.put(key, value);
        }
        return store.get(key);
    }
}

// 개선: ReentrantLock은 가상 스레드 인식 구현이라 언마운트가 정상 동작
public class VirtualThreadFriendlyCache {
    private final Map<String, String> store = new HashMap<>();
    private final ReentrantLock lock = new ReentrantLock();

    public String getOrFetch(String key) {
        lock.lock();
        try {
            if (!store.containsKey(key)) {
                String value = httpClient.fetch(key); // 언마운트되어 캐리어 반납
                store.put(key, value);
            }
            return store.get(key);
        } finally {
            lock.unlock();
        }
    }
}
```

`java.util.concurrent.locks.ReentrantLock`은 애초에 가상 스레드를 염두에 두고 구현돼 있어, 락을 쥔 채로 블로킹해도 가상 스레드가 정상적으로 캐리어에서 분리된다.

## 실무 포인트

- **JDBC 드라이버 호환성을 먼저 확인한다**: 가상 스레드 도입 전, 사용 중인 JDBC 드라이버와 커넥션 풀이 가상 스레드 친화적인지(내부적으로 `synchronized`를 과하게 쓰지 않는지) 확인해야 한다. HikariCP는 가상 스레드 대응이 잘 되어 있지만, 오래된 드라이버는 내부에서 `synchronized`를 광범위하게 쓸 수 있다.
- **핫 패스의 `synchronized`부터 우선 교체한다**: 애플리케이션 전체의 `synchronized`를 한 번에 바꾸려 하지 말고, 트래픽이 몰리는 핫 패스(캐시 접근, 커넥션 풀 획득 등)부터 우선순위를 정해 `ReentrantLock`으로 교체한다.
- **JDK 24 이상으로 올릴 수 있다면 우선 검토한다**: JEP 491 적용 버전으로 올리면 `synchronized` 피닝 문제 자체가 사라진다. 다만 라이브러리 의존성이 해당 JDK 버전과 호환되는지, JNI 기반 피닝은 여전히 남는다는 점은 별도로 확인해야 한다.

## 3줄 요약

- 가상 스레드는 `synchronized` 블록 안에서의 블로킹이나 JNI 네이티브 호출 중 블로킹 시 캐리어 스레드에 고정돼 동시성이 무너진다.
- `-Djdk.tracePinnedThreads=full`이나 JFR의 `jdk.VirtualThreadPinned` 이벤트로 피닝 발생 지점을 구체적으로 찾아낼 수 있다.
- JDK 24(JEP 491)는 `synchronized` 피닝을 해결했지만, 그 이전 버전이거나 JNI 호출이 있다면 `ReentrantLock`으로의 교체가 여전히 필요하다.

## 참고 자료

- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444)
- [JEP 491: Synchronize Virtual Threads without Pinning](https://openjdk.org/jeps/491)
- [Oracle 공식 문서: Virtual Threads Guide](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)
