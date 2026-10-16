#pragma once
#include <stdint.h>
#include <math.h>

// DW3000 User Manual 4.7.1/4.7.2 and 8.2.13; driver 04.00.00.
// Separate from SPI/Arduino so exactly this calculation can be host-tested.
struct IpatovRaw {
    uint32_t power, f1, f2, f3, peak;
    uint16_t fp_index, accum_count;
    uint32_t dgc_debug, dgc_config, rx_status;
    int16_t clock_offset;
    bool cia_done;
};

struct IpatovResult {
    const char *reason;
    double rx_dbm, fp_dbm, difference_db, peak_minus_fp_samples, clock_ppm;
};

inline IpatovResult calculate_ipatov(const IpatovRaw &raw, uint8_t rx_code, uint8_t channel)
{
    IpatovResult out = {nullptr, NAN, NAN, NAN, NAN, NAN};
    if (raw.cia_done && !(raw.rx_status & (1UL << 18)))
        out.clock_ppm = raw.clock_offset * (1e6 / 67108864.0);
    if (!raw.cia_done) out.reason = "cia_not_done";
    else if (raw.rx_status & (1UL << 18)) out.reason = "cia_error";
    else if (channel != 5 && channel != 9) out.reason = "unsupported_channel";
    else if (rx_code < 1 || rx_code > 24) out.reason = "unsupported_prf";
    else if (!raw.accum_count) out.reason = "zero_accum_count";
    else if (!raw.power) out.reason = "zero_channel_power";
    else if (!(raw.f1 || raw.f2 || raw.f3)) out.reason = "zero_first_path";
    else if (raw.power == 0x1ffff || raw.f1 == 0x3fffff || raw.f2 == 0x3fffff || raw.f3 == 0x3fffff)
        out.reason = "diagnostic_at_register_limit";
    if (out.reason) return out;
    const double a = rx_code <= 8 ? 113.8 : 121.7;
    const double dgc = (raw.dgc_config & 1) ? 6.0 * ((raw.dgc_debug >> 28) & 7) : 0.0;
    const double n2 = (double)raw.accum_count * raw.accum_count;
    // F1/F2/F3 are unsigned Q20.2, not integers. Cast before squaring.
    const double f1 = raw.f1 / 4.0, f2 = raw.f2 / 4.0, f3 = raw.f3 / 4.0;
    out.rx_dbm = 10.0 * log10(raw.power * 2097152.0 / n2) + dgc - a;
    out.fp_dbm = 10.0 * log10((f1*f1 + f2*f2 + f3*f3) / n2) + dgc - a;
    out.difference_db = out.rx_dbm - out.fp_dbm;
    out.peak_minus_fp_samples = ((raw.peak >> 21) & 0x3ff) - raw.fp_index / 64.0;
    return out;
}
