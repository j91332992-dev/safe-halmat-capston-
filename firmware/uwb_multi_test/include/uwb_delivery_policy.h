#pragma once
#include <stdint.h>
#include <stddef.h>

// Build flags may override these values. Ages use the original Poll time.
#ifndef UWB_USB_QUEUE_CAPACITY
#define UWB_USB_QUEUE_CAPACITY 8
#endif
#ifndef UWB_HTTP_QUEUE_CAPACITY
#define UWB_HTTP_QUEUE_CAPACITY 4
#endif
#ifndef UWB_HTTP_MAX_AGE_MS
#define UWB_HTTP_MAX_AGE_MS 1500
#endif
#ifndef UWB_HTTP_MAX_ATTEMPTS
#define UWB_HTTP_MAX_ATTEMPTS 2
#endif
#ifndef UWB_HTTP_RETRY_MS
#define UWB_HTTP_RETRY_MS 200
#endif
#ifndef UWB_HTTP_CONNECT_TIMEOUT_MS
#define UWB_HTTP_CONNECT_TIMEOUT_MS 300
#endif
#ifndef UWB_HTTP_READ_TIMEOUT_MS
#define UWB_HTTP_READ_TIMEOUT_MS 500
#endif
static_assert(UWB_HTTP_MAX_AGE_MS > 0 && UWB_HTTP_MAX_ATTEMPTS >= 1 &&
              UWB_HTTP_RETRY_MS > 0 && UWB_HTTP_CONNECT_TIMEOUT_MS > 0 &&
              UWB_HTTP_READ_TIMEOUT_MS > 0, "delivery limits must be positive");

// Caller supplies the short critical section; no heap, strings, I/O or waits.
template<class T, size_t Capacity> class LatestQueue {
    static_assert(Capacity > 0, "queue must have storage");
    T entries[Capacity] = {};
    size_t head = 0, count = 0;
public:
    bool push(const T &value) {
        bool dropped = count == Capacity;
        if (dropped) { head = (head + 1) % Capacity; --count; }
        entries[(head + count) % Capacity] = value;
        ++count;
        return dropped;
    }
    bool pop(T &value) {
        if (!count) return false;
        value = entries[head]; head = (head + 1) % Capacity; --count;
        return true;
    }
    bool pop_latest(T &value, uint32_t &discarded) {
        if (!count) return false;
        discarded += count - 1;
        head = (head + count - 1) % Capacity; count = 1;
        return pop(value);
    }
    size_t size() const { return count; }
};

inline bool delivery_expired(uint64_t measured_us, uint64_t now_us) {
    return now_us < measured_us || now_us - measured_us >= uint64_t(UWB_HTTP_MAX_AGE_MS) * 1000;
}
inline bool delivery_retryable(int status, unsigned attempts) {
    return attempts < UWB_HTTP_MAX_ATTEMPTS &&
        (status <= 0 || status == 408 || status == 429 || status >= 500);
}
