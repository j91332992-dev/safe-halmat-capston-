"""Shared distance processing. SQLite transactions serialize local workers."""
import json
import math
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from statistics import median

from .uwb_service import calibration_offsets
from .uwb_quality_service import classify_signal, quality_gate, quality_policy


SESSION_RE = re.compile(r"^([0-9a-f]{12})-(\d+)-[0-9a-f]{32}$")


class DistanceFilter:
    def __init__(self, settings, offsets=None):
        self.settings = settings
        self.offsets = offsets

    def process(self, payload, now=None):
        now = time.time() if now is None else now
        cfg = self.settings
        path = Path(cfg.uwb_filter_state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        key = json.dumps([payload.organization_id, payload.site_id, payload.uwb_tag_id])
        with closing(sqlite3.connect(path, timeout=10)) as db, db:
            # This file contains recoverable filter history, not event records.
            # WAL/NORMAL avoids full journal fsync for every 100 ms sample.
            # Concurrent first connections can collide while SQLite switches
            # journal mode even with a connection timeout. Retry only this
            # transient setup lock; steady-state WAL has no added sleep.
            deadline = time.monotonic()+0.5
            while True:
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if 'locked' not in str(exc).lower() or time.monotonic() >= deadline:
                        raise
                    time.sleep(.01)
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("CREATE TABLE IF NOT EXISTS distance_state (key TEXT PRIMARY KEY, touched REAL, data TEXT)")
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM distance_state WHERE touched < ?", (now-cfg.uwb_filter_state_ttl_seconds,))
            row = db.execute("SELECT data FROM distance_state WHERE key=?", (key,)).fetchone()
            state = json.loads(row[0]) if row else {}
            result = self._process(payload, state, now)
            if result["accepted"] and result["identity_complete"]:
                db.execute("INSERT OR REPLACE INTO distance_state VALUES (?, ?, ?)", (key, now, json.dumps(state)))
                db.execute("DELETE FROM distance_state WHERE key IN (SELECT key FROM distance_state ORDER BY touched DESC, key LIMIT -1 OFFSET ?)", (cfg.uwb_filter_max_tags,))
            return result

    def _process(self, p, state, now):
        cfg = self.settings
        complete = all(value is not None for value in (p.session_id, p.measurement_id, p.cycle_id, p.measured_uptime_us))
        result = {"accepted": True, "identity_complete": complete, "reason": "accepted" if complete else "legacy_identity_missing_no_history",
                  "measurements": [], "anchor_processing": [], "filter_enabled": cfg.uwb_median_enabled,
                  "window_size": cfg.uwb_median_window}

        def reject(reason):
            result.update(accepted=False, reason=reason)
            return result

        if p.measured_at is not None:
            timestamp = p.measured_at
            if timestamp.tzinfo is None:
                return reject("measured_at_timezone_required")
            if now - timestamp.timestamp() > cfg.uwb_frame_max_age_seconds:
                return reject("stale_frame")
            if timestamp.timestamp() - now > 1:
                return reject("future_frame")
        reset = None
        if complete:
            if p.session_id in state.get("retired", []):
                return reject("retired_session")
            if state.get("session") == p.session_id:
                if p.measurement_id in state.get("seen", []):
                    return reject("duplicate_measurement")
                if p.cycle_id <= state["cycle"]:
                    return reject("duplicate_cycle" if p.cycle_id == state["cycle"] else "out_of_order")
                if p.measured_uptime_us <= state["uptime"]:
                    return reject("non_increasing_uptime")
            else:
                previous_boot = SESSION_RE.fullmatch(state.get("session", ""))
                incoming_boot = SESSION_RE.fullmatch(p.session_id)
                if previous_boot and incoming_boot and previous_boot[1] == incoming_boot[1] and int(incoming_boot[2]) <= int(previous_boot[2]):
                    return reject("older_or_conflicting_boot")
                retired = state.get("retired", [])
                if state.get("session"):
                    retired.append(state["session"])
                    reset = "session_changed"
                state.clear()
                latest_uptime = max([p.measured_uptime_us] + [o.measured_uptime_us for o in p.observations if o.measured_uptime_us is not None])
                state.update(session=p.session_id, retired=retired[-64:], origin=now-latest_uptime/1e6, histories={}, seen=[])
            event_time = p.measured_at.timestamp() if p.measured_at else state["origin"] + p.measured_uptime_us/1e6
            if p.measured_at is None and 1 < event_time-now <= 5:
                # An uptime clock has no UTC epoch. Its arrival-time origin can
                # drift (or Windows wall time can be corrected) while the tag
                # retains the same boot ID. Do not reject every subsequent
                # ordered frame until the persisted state expires. Re-anchor
                # only this small forward offset; retain boot/replay checks,
                # absolute timestamp validation and the stale-frame limit.
                latest_uptime = max([p.measured_uptime_us] + [o.measured_uptime_us
                    for o in p.observations if o.measured_uptime_us is not None])
                new_origin = now-latest_uptime/1e6
                result['clock_origin_rebase_ms'] = round((new_origin-state['origin'])*1000,3)
                state['origin'] = new_origin
                state['histories'] = {}
                state['quality_states'] = {}
                state.pop('quality_weights',None)
                reset = 'clock_origin_rebased'
                event_time = state['origin']+p.measured_uptime_us/1e6
            if now-event_time > cfg.uwb_frame_max_age_seconds:
                return reject("stale_frame")
            if event_time-now > 1:
                return reject("future_frame")
            if now-state.get("accepted_at", now) > cfg.uwb_filter_reset_seconds:
                state["histories"] = {}
                state["quality_states"] = {}
                state.pop("quality_weights", None)
                reset = "long_gap_reset"
            # Prune missing anchors too; missing data never produces a distance.
            state["histories"] = {anchor: [s for s in samples if now-s[0] <= cfg.uwb_median_sample_ttl_seconds]
                                  for anchor, samples in state["histories"].items()}
            state["histories"] = {k: v for k, v in state["histories"].items() if v}
        else:
            event_time = now
            state = {"histories": {}}
        policy = [cfg.uwb_quality_mode, quality_policy(cfg) if cfg.uwb_quality_mode != "observe" else None,
                  cfg.uwb_quality_nlos_weight, cfg.uwb_quality_weight_recovery_step]
        previous_policy = state.get("signal_policy")
        policy_reset = previous_policy != policy and (cfg.uwb_quality_mode != "observe" or previous_policy is not None and previous_policy[0] != "observe")
        if policy_reset:
            state["histories"] = {}
            state["quality_states"] = {}
            state.pop("quality_weights", None)
        state.update(signal_policy=policy)
        state.setdefault("quality_states", {})
        result.update(quality_mode=cfg.uwb_quality_mode, quality_policy_reset=policy_reset,
                      server_calibration_enabled=cfg.uwb_calibration_enabled)
        offsets = (self.offsets if self.offsets is not None else calibration_offsets()) if cfg.uwb_calibration_enabled else {}
        observations = {item.anchor_id: item for item in p.observations}
        supplied = {item.anchor_id: item for item in p.measurements}
        gated = set()
        for anchor in sorted(set(observations) | set(supplied)):
            item, obs = supplied.get(anchor), observations.get(anchor)
            record = {"anchor_id": anchor, "raw_distance_m": obs.raw_distance_m if obs else (item.raw_distance_m if item else None),
                      "calibrated_distance_m": None, "filtered_distance_m": None, "sample_count": 0,
                      "sample_ages_seconds": [], "held": False, "reason": "missing",
                      "diagnostics": obs.diagnostics.model_dump() if obs else item.diagnostics.model_dump()}
            result["anchor_processing"].append(record)
            diagnostic = obs.diagnostics if obs else item.diagnostics
            decision = classify_signal(diagnostic, cfg)
            decision.update(mode=cfg.uwb_quality_mode, client_quality=item.quality if item else None,
                            client_quality_is_uwb_diagnostic=False, applied_action="observe" if cfg.uwb_quality_mode == "observe" else "not_evaluated",
                            applied_weight=None, history_reset=False)
            record["signal_quality"] = decision
            if obs is not None and obs.status != "valid":
                record["reason"] = obs.status
                continue
            if item is None:
                record["reason"] = "no_current_measurement"
                continue
            if item.held:
                record["reason"] = "client_held_rejected"
                continue
            if item.source_measurement_id is not None and item.source_measurement_id != p.measurement_id:
                record["reason"] = "source_measurement_mismatch"
                continue
            # v2 uncalibrated observations preserve sub-centimetre precision.
            value = obs.raw_distance_m if obs is not None and not p.distances_calibrated else item.distance_m
            if value is None or not math.isfinite(value) or not 0 < value < 100:
                record["reason"] = "invalid_distance"
                continue
            if record["raw_distance_m"] is None and not p.distances_calibrated:
                record["raw_distance_m"] = value
            sample_uptime = obs.measured_uptime_us if obs else None
            sample_time = event_time
            if complete and sample_uptime is not None:
                sample_time += (sample_uptime-p.measured_uptime_us)/1e6
            if sample_time-now > 1 or now-sample_time > cfg.uwb_median_sample_ttl_seconds:
                record["reason"] = "stale_or_future_sample"
                continue
            effective_quality = item.quality
            if cfg.uwb_quality_mode == "weighted":
                weights = state.setdefault("quality_weights", {})
                target = {"nominal": 1.0, "suspect": cfg.uwb_quality_suspect_weight,
                          "nlos_suspected": cfg.uwb_quality_nlos_weight,
                          "unknown": cfg.uwb_quality_unknown_weight}[decision["classification"]]
                previous = weights.get(anchor, target)
                factor = min(target, previous+cfg.uwb_quality_weight_recovery_step)
                weights[anchor] = factor
                # Signal degradation applies immediately; recovery is gradual.
                # Never promote a range above the client's existing quality.
                effective_quality = max(.05, min(item.quality, factor))
                decision.update(applied_action="downweight" if factor < 1 else "use",
                    gate_reason="weighted_keep_geometry", target_weight=target,
                    previous_weight=previous, weight_recovery_limited=factor < target)
            if cfg.uwb_quality_mode == "enforce":
                gated.add(anchor)
                allowed, gate_reason, cleared = quality_gate(state, anchor, decision, cfg, sample_time)
                decision.update(applied_action=decision["would_action"] if allowed else "exclude",
                                gate_reason=gate_reason, history_reset=cleared)
                if not allowed:
                    record["reason"] = gate_reason
                    continue
                effective_quality = decision["proposed_weight"]
            decision["applied_weight"] = effective_quality
            offset = 0.0 if p.distances_calibrated else offsets.get(anchor, 0.0)
            calibrated = max(0.05, value+offset)
            # Calibrated and raw legacy contracts cannot share a window.
            mode = [p.distances_calibrated, offset]
            samples = state["histories"].get(anchor, []) if complete else []
            samples = [s for s in samples if s[2] == mode]
            samples = (samples + [[sample_time, calibrated, mode]])[-cfg.uwb_median_window:]
            if complete:
                state["histories"][anchor] = samples
            filtered = median(s[1] for s in samples) if cfg.uwb_median_enabled and complete else calibrated
            reason = reset or ("filter_disabled" if not cfg.uwb_median_enabled else
                               "warmup_partial_window" if len(samples) < cfg.uwb_median_window else "median")
            if not complete:
                reason = "legacy_identity_missing_no_history"
            record.update(calibrated_distance_m=calibrated, filtered_distance_m=filtered,
                          server_calibration_offset_m=offset, calibration_source="client" if p.distances_calibrated else "server" if cfg.uwb_calibration_enabled else "disabled",
                          sample_count=len(samples), sample_ages_seconds=[round(max(0, now-s[0]), 6) for s in samples], reason=reason)
            result["measurements"].append({**record, "distance_m": filtered, "quality": effective_quality})
        if cfg.uwb_quality_mode == "enforce":
            for anchor, entry in state["quality_states"].items():
                if anchor not in gated:
                    entry.update(good_count=0, recovering=False)
        used = [m["anchor_id"] for m in result["measurements"]]
        result["quality_summary"] = {
            "mode": cfg.uwb_quality_mode, "usable_anchor_ids": used,
            "effective_weights": {m['anchor_id']: m['quality'] for m in result['measurements']},
            "excluded_anchor_ids": [r["anchor_id"] for r in result["anchor_processing"] if r["signal_quality"]["applied_action"] == "exclude"],
            "degraded_reasons": sorted({reason for r in result["anchor_processing"] for reason in
                                        (r["signal_quality"]["reasons"] if r["signal_quality"]["classification"] != "nominal" else [])} |
                                       {r["reason"] for r in result["anchor_processing"] if r["signal_quality"]["applied_action"] == "exclude"}),
            "classifications": {r["anchor_id"]: r["signal_quality"]["classification"] for r in result["anchor_processing"]}}
        if complete:
            state.update(cycle=p.cycle_id, measurement=p.measurement_id, uptime=p.measured_uptime_us, accepted_at=now)
            state["seen"] = (state["seen"] + [p.measurement_id])[-256:]
            # Bound even clients which continually invent anchor identifiers.
            state["histories"] = dict(sorted(state["histories"].items(), key=lambda kv: kv[1][-1][0], reverse=True)[:64])
            state["quality_states"] = dict(sorted(state["quality_states"].items(), key=lambda kv: kv[1]["touched"], reverse=True)[:64])
            if "quality_weights" in state:
                state["quality_weights"] = {k:v for k,v in state["quality_weights"].items() if k in state["histories"]}
        return result
