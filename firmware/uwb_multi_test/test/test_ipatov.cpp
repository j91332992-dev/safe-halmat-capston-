#include "../include/uwb_diagnostics.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main() {
    IpatovRaw raw = {200, 40000, 42000, 38000, (751UL << 21) | 45000,
                     750 * 64 + 16, 128, 1UL << 28, 1, 0, -302, true};
    IpatovResult result = calculate_ipatov(raw, 9, 5);
    assert(!result.reason);
    const double expected_rx = 10 * log10(200.0 * 2097152 / (128 * 128)) + 6 - 121.7;
    const double expected_fp = 10 * log10((10000.0*10000 + 10500.0*10500 + 9500.0*9500) / (128*128)) + 6 - 121.7;
    assert(fabs(result.rx_dbm - expected_rx) < 1e-10);
    assert(fabs(result.fp_dbm - expected_fp) < 1e-10);
    assert(fabs(result.difference_db - (expected_rx - expected_fp)) < 1e-10);
    assert(result.peak_minus_fp_samples == 0.75);
    assert(fabs(result.clock_ppm - (-302e6 / 67108864)) < 1e-10);
    raw.dgc_config = 0;
    assert(fabs(calculate_ipatov(raw, 9, 9).rx_dbm - (expected_rx - 6)) < 1e-10);
    assert(fabs(calculate_ipatov(raw, 1, 5).rx_dbm - (expected_rx - 6 + 7.9)) < 1e-10);
    raw.accum_count = 0;
    result = calculate_ipatov(raw, 9, 5);
    assert(strcmp(result.reason, "zero_accum_count") == 0 && isnan(result.rx_dbm) && isnan(result.fp_dbm));
    raw.accum_count = 128;
    raw.power = 0;
    assert(strcmp(calculate_ipatov(raw, 9, 5).reason, "zero_channel_power") == 0);
    raw.power = 200; raw.f1 = raw.f2 = raw.f3 = 0;
    assert(strcmp(calculate_ipatov(raw, 9, 5).reason, "zero_first_path") == 0);
    raw.f1 = 0x3fffff;
    assert(strcmp(calculate_ipatov(raw, 9, 5).reason, "diagnostic_at_register_limit") == 0);
    raw.f1 = 40000; raw.cia_done = false;
    result = calculate_ipatov(raw, 9, 5);
    assert(strcmp(result.reason, "cia_not_done") == 0 && isnan(result.clock_ppm));
    raw.cia_done = true; raw.rx_status = 1UL << 18;
    assert(strcmp(calculate_ipatov(raw, 9, 5).reason, "cia_error") == 0);
    raw.rx_status = 0;
    assert(strcmp(calculate_ipatov(raw, 0, 5).reason, "unsupported_prf") == 0);
    assert(strcmp(calculate_ipatov(raw, 9, 1).reason, "unsupported_channel") == 0);
    puts("Ipatov calculation checks passed (Q20.2, Q10.6, DGC, PRF, invalid/null, signed clock)");
}
