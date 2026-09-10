"""Generate SYNTHETIC benchmark rows for report layout testing only.

These numbers are NOT measured results. Replace them with actual Locust/k6 exports before
using the report in a portfolio or interview.
"""
from pathlib import Path
import pandas as pd

rows = [
    {"scenario": "sync-baseline", "users": 10, "throughput_rps": 7.8, "p50_ms": 1260, "p95_ms": 1510, "error_rate_pct": 0.0},
    {"scenario": "async", "users": 10, "throughput_rps": 8.0, "p50_ms": 1240, "p95_ms": 1420, "error_rate_pct": 0.0},
    {"scenario": "sync-baseline", "users": 50, "throughput_rps": 21.5, "p50_ms": 2210, "p95_ms": 4760, "error_rate_pct": 1.4},
    {"scenario": "async", "users": 50, "throughput_rps": 36.9, "p50_ms": 1410, "p95_ms": 2180, "error_rate_pct": 0.2},
    {"scenario": "sync-baseline", "users": 100, "throughput_rps": 24.1, "p50_ms": 3790, "p95_ms": 8410, "error_rate_pct": 5.8},
    {"scenario": "async", "users": 100, "throughput_rps": 58.4, "p50_ms": 1730, "p95_ms": 3120, "error_rate_pct": 0.9},
]
path = Path(__file__).parent / "results" / "sample_results.csv"
pd.DataFrame(rows).to_csv(path, index=False)
print(path)
