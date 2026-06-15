from __future__ import annotations

"""Expose the in-memory metrics snapshot in Prometheus exposition format.

Giữ nguyên endpoint JSON `/metrics` (dùng cho validate_logs và tests); module này
chỉ thêm một lớp render sang Prometheus để Grafana scrape được time-series.
"""

from prometheus_client import REGISTRY, Gauge, generate_latest

from .metrics import snapshot

# Gauges được tạo một lần, cập nhật giá trị mỗi lần Prometheus scrape.
_LATENCY = Gauge("lab_latency_ms", "Request latency in ms", ["quantile"])
_TRAFFIC = Gauge("lab_traffic_total", "Total number of requests served")
_ERRORS = Gauge("lab_errors_total", "Total errors grouped by type", ["type"])
_ERROR_RATE = Gauge("lab_error_rate_pct", "Error rate as percentage of traffic")
_COST_TOTAL = Gauge("lab_cost_usd_total", "Cumulative cost in USD")
_COST_AVG = Gauge("lab_cost_usd_avg", "Average cost per request in USD")
_TOKENS = Gauge("lab_tokens_total", "Total tokens", ["direction"])
_QUALITY = Gauge("lab_quality_score_avg", "Average heuristic quality score")
_REQUESTS_BY_MODEL = Gauge("lab_requests_by_model", "Requests grouped by model", ["model"])


def render_prometheus() -> bytes:
    snap = snapshot()

    _LATENCY.labels(quantile="p50").set(snap["latency_p50"])
    _LATENCY.labels(quantile="p95").set(snap["latency_p95"])
    _LATENCY.labels(quantile="p99").set(snap["latency_p99"])

    traffic = snap["traffic"]
    _TRAFFIC.set(traffic)

    error_breakdown = snap["error_breakdown"]
    total_errors = sum(error_breakdown.values())
    for error_type, count in error_breakdown.items():
        _ERRORS.labels(type=error_type).set(count)
    _ERROR_RATE.set((total_errors / traffic * 100) if traffic else 0.0)

    _COST_TOTAL.set(snap["total_cost_usd"])
    _COST_AVG.set(snap["avg_cost_usd"])
    _TOKENS.labels(direction="in").set(snap["tokens_in_total"])
    _TOKENS.labels(direction="out").set(snap["tokens_out_total"])
    _QUALITY.set(snap["quality_avg"])

    for model, count in snap["requests_by_model"].items():
        _REQUESTS_BY_MODEL.labels(model=model).set(count)

    return generate_latest(REGISTRY)
