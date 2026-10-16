#include "../include/uwb_delivery_policy.h"
#include "../include/uwb_measurement_snapshot.h"
#include <assert.h>
#include <stdio.h>

int main() {
    LatestQueue<CycleSnapshot, 2> queue;
    CycleSnapshot cycle = {}, sent = {}, output = {};
    cycle.cycle_id = 255; cycle.sequence = 255; cycle.uptime_us = 123;
    cycle.anchors[0].raw_distance_m = 2.125;
    cycle.anchors[0].diagnostic.power = 201;
    assert(!queue.push(cycle));
    cycle.cycle_id = 256; cycle.sequence = 0;
    cycle.anchors[0].raw_distance_m = 9;
    cycle.anchors[0].diagnostic.power = 999;
    assert(queue.pop(sent));
    assert(sent.cycle_id == 255 && sent.sequence == 255 && sent.uptime_us == 123);
    assert(sent.anchors[0].raw_distance_m == 2.125 && sent.anchors[0].diagnostic.power == 201);
    assert(!queue.pop(output));
    // The in-flight snapshot does not change when the producer wraps sequence,
    // overwrites its buffer, or overflows the pending queue.
    for (unsigned i = 256; i < 300; ++i) {
        cycle.cycle_id = i;
        assert(queue.push(cycle) == (i >= 258));
    }
    assert(queue.size() == 2 && sent.cycle_id == 255);
    assert(queue.pop(output) && output.cycle_id == 298);
    assert(queue.pop(output) && output.cycle_id == 299);
    for (unsigned i = 0; i < 2; ++i) { cycle.cycle_id = i; queue.push(cycle); }
    uint32_t discarded = 0;
    assert(queue.pop_latest(output, discarded) && output.cycle_id == 1 && discarded == 1);
    assert(queue.size() == 0);
    const uint64_t measured = 8000000;
    assert(!delivery_expired(measured, measured));
    assert(!delivery_expired(measured, measured + UWB_HTTP_MAX_AGE_MS * 1000 - 1));
    assert(delivery_expired(measured, measured + UWB_HTTP_MAX_AGE_MS * 1000));
    assert(delivery_expired(measured, measured - 1));
    assert(delivery_retryable(-1, 1));
    assert(delivery_retryable(500, 1) && delivery_retryable(503, 1));
    assert(delivery_retryable(408, 1) && delivery_retryable(429, 1));
    assert(!delivery_retryable(200, 1) && !delivery_retryable(422, 1));
    assert(!delivery_retryable(500, UWB_HTTP_MAX_ATTEMPTS));
    // Producer at 300ms; stalled HTTP consumer for 3 seconds. USB continues,
    // network storage stays bounded and recovery selects only the latest cycle.
    LatestQueue<CycleSnapshot, UWB_HTTP_QUEUE_CAPACITY> network;
    LatestQueue<CycleSnapshot, UWB_USB_QUEUE_CAPACITY> usb;
    unsigned overflow = 0;
    for (unsigned i = 0; i < 10; ++i) {
        cycle.cycle_id = i; cycle.uptime_us = measured + i * 300000;
        overflow += network.push(cycle);
        usb.push(cycle);
        assert(usb.pop(output) && output.cycle_id == i);
        assert(network.size() <= UWB_HTTP_QUEUE_CAPACITY);
    }
    assert(overflow == 10 - UWB_HTTP_QUEUE_CAPACITY);
    discarded = 0;
    assert(network.pop_latest(output, discarded) && output.cycle_id == 9);
    assert(discarded == UWB_HTTP_QUEUE_CAPACITY - 1);
    assert(!delivery_expired(output.uptime_us, measured + 3000000));
    assert(delivery_expired(output.uptime_us, measured + 6000000));
    // Retransmission retains original ID, timestamp, range and diagnostics.
    assert(sent.cycle_id == 255 && sent.uptime_us == 123 && sent.anchors[0].diagnostic.power == 201);
    printf("Delivery policy checks passed (snapshot=%u bytes)\n", (unsigned)sizeof(CycleSnapshot));
}
