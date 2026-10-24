"""Provisional Ipatov signal rules; classifications are not NLOS ground truth."""
import math


def quality_policy(cfg):
    return {name.removeprefix("uwb_quality_"): getattr(cfg, name) for name in (
        "uwb_quality_gap_warn_db", "uwb_quality_gap_bad_db", "uwb_quality_path_warn_samples",
        "uwb_quality_path_bad_samples", "uwb_quality_rx_weak_dbm", "uwb_quality_fp_weak_dbm",
        "uwb_quality_gap_tolerance_db", "uwb_quality_suspect_weight", "uwb_quality_unknown_weight",
        "uwb_quality_unknown_policy", "uwb_quality_recovery_samples", "uwb_quality_recovery_span_seconds",
        "uwb_quality_nlos_weight", "uwb_quality_weight_recovery_step")}


def classify_signal(diagnostics, cfg):
    d = diagnostics.model_dump() if hasattr(diagnostics, "model_dump") else diagnostics
    names = ("rx_power_dbm", "first_path_power_dbm", "power_difference_db", "peak_minus_first_path_samples", "clock_offset_ppm")
    metrics = {name: d.get(name) for name in names}
    result = dict(classification="unknown", diagnostic_status=d.get("status", "missing"),
                  diagnostic_validity=d.get("status", "missing"), diagnostic_reason=d.get("reason"),
                  raw_available=bool(d.get("raw")), metrics=metrics, thresholds=quality_policy(cfg),
                  suspected_nlos=None, evidence=[], reasons=[])
    if result["diagnostic_status"] != "valid":
        result["reasons"].append("diagnostics_"+result["diagnostic_status"])
    elif any(v is None or not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()):
        result.update(diagnostic_validity="invalid", diagnostic_reason="incomplete_or_nonfinite")
        result["reasons"].append("diagnostics_incomplete_or_nonfinite")
    elif abs(metrics["rx_power_dbm"]-metrics["first_path_power_dbm"]-metrics["power_difference_db"]) > cfg.uwb_quality_gap_tolerance_db:
        result.update(diagnostic_validity="invalid", diagnostic_reason="power_gap_inconsistent")
        result["reasons"].append("power_gap_inconsistent")
    else:
        rx, fp, gap, path = (metrics[name] for name in names[:4])
        path = abs(path)
        tests = (("weak_rx", "rx_power_dbm", rx, "<=", cfg.uwb_quality_rx_weak_dbm, rx <= cfg.uwb_quality_rx_weak_dbm),
                 ("weak_first_path", "first_path_power_dbm", fp, "<=", cfg.uwb_quality_fp_weak_dbm, fp <= cfg.uwb_quality_fp_weak_dbm),
                 ("large_power_gap", "power_difference_db", gap, ">=", cfg.uwb_quality_gap_warn_db, gap >= cfg.uwb_quality_gap_warn_db),
                 ("separated_paths", "abs_peak_minus_first_path_samples", path, ">=", cfg.uwb_quality_path_warn_samples, path >= cfg.uwb_quality_path_warn_samples))
        for reason, metric, value, op, threshold, triggered in tests:
            result["evidence"].append(dict(metric=metric, value=value, operator=op, threshold=threshold, triggered=triggered))
            if triggered:
                result["reasons"].append(reason)
        bad = gap >= cfg.uwb_quality_gap_bad_db and path >= cfg.uwb_quality_path_bad_samples
        result["evidence"].append(dict(rule="severe_gap_and_separated_paths", gap_threshold=cfg.uwb_quality_gap_bad_db,
                                       path_threshold=cfg.uwb_quality_path_bad_samples, triggered=bad))
        result.update(classification="nlos_suspected" if bad else "suspect" if result["reasons"] else "nominal",
                      suspected_nlos=gap >= cfg.uwb_quality_gap_warn_db or path >= cfg.uwb_quality_path_warn_samples)
    category = result["classification"]
    action = "exclude" if category == "nlos_suspected" else (
        cfg.uwb_quality_unknown_policy if category == "unknown" else "downweight" if category == "suspect" else "use")
    weight = 0.0 if action == "exclude" else cfg.uwb_quality_unknown_weight if category == "unknown" else cfg.uwb_quality_suspect_weight if category == "suspect" else 1.0
    result.update(would_action=action, proposed_weight=weight)
    return result


def quality_gate(state, anchor, classification, cfg, sample_time):
    """Called only for fresh usable ranges after frame dedup, before calibration."""
    category = classification["classification"]
    entry = state["quality_states"].setdefault(anchor, {"last_class": None, "blocked": False, "recovering": False, "good_count": 0})
    previous = entry["last_class"]
    if classification["would_action"] == "exclude":
        state["histories"].pop(anchor, None)
        entry.update(last_class=category, blocked=True, recovering=False, good_count=0, touched=sample_time)
        return False, "signal_excluded", True
    if category != "nominal" and entry["blocked"]:
        state["histories"].pop(anchor, None)
        entry.update(last_class=category, recovering=False, good_count=0, touched=sample_time)
        return False, "quality_recovery_requires_nominal", True
    if category == "nominal" and (entry["blocked"] or entry["recovering"] or previous not in (None, "nominal")):
        state["histories"].pop(anchor, None)
        if not entry["recovering"] or sample_time-entry.get("touched", sample_time) > cfg.uwb_median_sample_ttl_seconds:
            entry.update(good_count=0, recovery_start=sample_time)
        entry.update(recovering=True, touched=sample_time, good_count=entry["good_count"]+1)
        if entry["good_count"] < cfg.uwb_quality_recovery_samples or sample_time-entry["recovery_start"]+1e-9 < cfg.uwb_quality_recovery_span_seconds:
            return False, "quality_recovery_wait", True
        entry.update(last_class="nominal", blocked=False, recovering=False, good_count=0)
        return True, "quality_recovered_fresh_window", True
    cleared = previous is not None and previous != category
    if cleared:
        state["histories"].pop(anchor, None)
    entry.update(last_class=category, recovering=False, good_count=0, touched=sample_time)
    return True, "quality_class_changed_fresh_window" if cleared else "quality_allowed", cleared
