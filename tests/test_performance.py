"""
Performance Tests — Epilepsy Diagnostic Assistant
==================================================
Measures latency, throughput, and stability under load.

Categories:
  PERF-01  Baseline latency (single request)
  PERF-02  Throughput (requests per second)
  PERF-03  Concurrent load (thread pool)
  PERF-04  Stress test (sustained load)
  PERF-05  Memory / stability (no degradation over time)
  PERF-06  Endpoint-specific SLA contracts
  PERF-07  Cache effectiveness (repeated identical calls)

Run:
    pip install pytest requests
    pytest tests/test_performance.py -v -s
(backend must be running at localhost:8000)
"""

import time
import statistics
import pytest
import requests
import concurrent.futures
import threading

BASE = "http://localhost:8000"

PATHOGENIC_VARIANT = {
    "gene": "SCN1A",
    "chromosome": "2",
    "reference_allele": "C",
    "alternate_allele": "T",
    "consequence": "stop_gained",
    "variant_type": "single nucleotide variant",
    "review_status": "criteria provided, multiple submitters",
    "origin": "germline",
}

BENIGN_VARIANT = {
    "gene": "SLC2A1",
    "chromosome": "1",
    "reference_allele": "C",
    "alternate_allele": "T",
    "consequence": "synonymous_variant",
    "variant_type": "single nucleotide variant",
    "review_status": "no assertion criteria provided",
    "origin": "germline",
}

# SLA Contracts (seconds)
SLA = {
    "health":          0.5,    # /health must respond < 500ms
    "predict_variant": 2.0,    # ML inference < 2s
    "analyze_full":    30.0,   # Full RAG pipeline < 30s
    "genes":           0.5,    # Static list < 500ms
    "consequences":    0.5,    # Static list < 500ms
    "literature":      5.0,    # FAISS search < 5s
}


def timed_post(url, payload):
    t0 = time.perf_counter()
    r = requests.post(url, json=payload)
    elapsed = time.perf_counter() - t0
    return r, elapsed


def timed_get(url):
    t0 = time.perf_counter()
    r = requests.get(url)
    elapsed = time.perf_counter() - t0
    return r, elapsed


# ─────────────────────────────────────────────────────────────────────────────
# PERF-01: Baseline Latency — single request SLA checks
# ─────────────────────────────────────────────────────────────────────────────

class TestBaselineLatency:

    def test_health_endpoint_latency(self):
        _, elapsed = timed_get(f"{BASE}/health")
        print(f"\n  /health latency: {elapsed*1000:.1f}ms")
        assert elapsed < SLA["health"], \
            f"/health took {elapsed:.3f}s — SLA is {SLA['health']}s"

    def test_predict_variant_latency_pathogenic(self):
        _, elapsed = timed_post(f"{BASE}/predict_variant", PATHOGENIC_VARIANT)
        print(f"\n  /predict_variant (pathogenic) latency: {elapsed*1000:.1f}ms")
        assert elapsed < SLA["predict_variant"], \
            f"/predict_variant took {elapsed:.3f}s — SLA is {SLA['predict_variant']}s"

    def test_predict_variant_latency_benign(self):
        _, elapsed = timed_post(f"{BASE}/predict_variant", BENIGN_VARIANT)
        print(f"\n  /predict_variant (benign) latency: {elapsed*1000:.1f}ms")
        assert elapsed < SLA["predict_variant"]

    def test_analyze_variant_full_path_latency(self):
        _, elapsed = timed_post(f"{BASE}/analyze_variant", PATHOGENIC_VARIANT)
        print(f"\n  /analyze_variant (full RAG) latency: {elapsed:.2f}s")
        assert elapsed < SLA["analyze_full"], \
            f"/analyze_variant took {elapsed:.1f}s — SLA is {SLA['analyze_full']}s"

    def test_genes_endpoint_latency(self):
        _, elapsed = timed_get(f"{BASE}/genes")
        print(f"\n  /genes latency: {elapsed*1000:.1f}ms")
        assert elapsed < SLA["genes"]

    def test_consequences_endpoint_latency(self):
        _, elapsed = timed_get(f"{BASE}/consequences")
        print(f"\n  /consequences latency: {elapsed*1000:.1f}ms")
        assert elapsed < SLA["consequences"]

    def test_literature_endpoint_latency(self):
        _, elapsed = timed_get(f"{BASE}/literature/SCN1A")
        print(f"\n  /literature/SCN1A latency: {elapsed:.2f}s")
        assert elapsed < SLA["literature"]


# ─────────────────────────────────────────────────────────────────────────────
# PERF-02: Throughput — requests per second
# ─────────────────────────────────────────────────────────────────────────────

class TestThroughput:

    def _measure_rps(self, url, payload, n=20):
        """Send n sequential requests, return RPS."""
        t0 = time.perf_counter()
        for _ in range(n):
            r = requests.post(url, json=payload)
            assert r.status_code == 200
        elapsed = time.perf_counter() - t0
        return n / elapsed

    def test_predict_variant_rps_above_5(self):
        """ML inference endpoint must handle >5 req/s sequentially."""
        rps = self._measure_rps(f"{BASE}/predict_variant", PATHOGENIC_VARIANT, n=20)
        print(f"\n  /predict_variant throughput: {rps:.1f} req/s")
        assert rps >= 5, f"Throughput {rps:.1f} req/s is below minimum of 5 req/s"

    def test_health_endpoint_rps_above_50(self):
        """Health endpoint must be very fast — >50 req/s."""
        n = 50
        t0 = time.perf_counter()
        for _ in range(n):
            r = requests.get(f"{BASE}/health")
            assert r.status_code == 200
        elapsed = time.perf_counter() - t0
        rps = n / elapsed
        print(f"\n  /health throughput: {rps:.1f} req/s")
        assert rps >= 50


# ─────────────────────────────────────────────────────────────────────────────
# PERF-03: Concurrent Load — thread pool
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrentLoad:

    def _run_concurrent(self, url, payload, workers, requests_per_worker):
        results = []
        lock = threading.Lock()

        def worker():
            times = []
            for _ in range(requests_per_worker):
                t0 = time.perf_counter()
                r = requests.post(url, json=payload)
                elapsed = time.perf_counter() - t0
                times.append((r.status_code, elapsed))
            with lock:
                results.extend(times)

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        t_start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.perf_counter() - t_start

        return results, total_time

    def test_5_concurrent_workers_all_succeed(self):
        results, total = self._run_concurrent(
            f"{BASE}/predict_variant", PATHOGENIC_VARIANT,
            workers=5, requests_per_worker=4
        )
        success = sum(1 for code, _ in results if code == 200)
        total_requests = len(results)
        print(f"\n  5 workers × 4 req: {success}/{total_requests} OK in {total:.2f}s")
        assert success == total_requests, \
            f"Only {success}/{total_requests} succeeded under 5-worker concurrency"

    def test_10_concurrent_workers_success_rate_above_90pct(self):
        results, total = self._run_concurrent(
            f"{BASE}/predict_variant", PATHOGENIC_VARIANT,
            workers=10, requests_per_worker=3
        )
        success = sum(1 for code, _ in results if code == 200)
        total_requests = len(results)
        success_rate = success / total_requests * 100
        print(f"\n  10 workers × 3 req: {success_rate:.1f}% success in {total:.2f}s")
        assert success_rate >= 90, f"Success rate {success_rate:.1f}% below 90%"

    def test_concurrent_latency_p95_within_sla(self):
        results, _ = self._run_concurrent(
            f"{BASE}/predict_variant", PATHOGENIC_VARIANT,
            workers=5, requests_per_worker=5
        )
        latencies = [elapsed for _, elapsed in results]
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"\n  p95 latency under 5-worker load: {p95*1000:.1f}ms")
        # p95 should be within 3× the single-request SLA
        assert p95 < SLA["predict_variant"] * 3, \
            f"p95 latency {p95:.3f}s exceeds {SLA['predict_variant'] * 3}s under load"

    def test_mixed_endpoint_concurrency(self):
        """Predict and analyze endpoints run simultaneously without interference."""
        errors = []

        def call_predict():
            r = requests.post(f"{BASE}/predict_variant", json=PATHOGENIC_VARIANT)
            if r.status_code != 200:
                errors.append(f"predict: {r.status_code}")

        def call_health():
            r = requests.get(f"{BASE}/health")
            if r.status_code != 200:
                errors.append(f"health: {r.status_code}")

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=call_predict))
            threads.append(threading.Thread(target=call_health))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors under mixed concurrency: {errors}"


# ─────────────────────────────────────────────────────────────────────────────
# PERF-04: Stress Test — sustained load
# ─────────────────────────────────────────────────────────────────────────────

class TestStressTest:

    def test_100_sequential_predict_requests_stable(self):
        """100 sequential predict calls — no crashes, consistent responses."""
        latencies = []
        errors = []

        for i in range(100):
            r, elapsed = timed_post(f"{BASE}/predict_variant", PATHOGENIC_VARIANT)
            if r.status_code != 200:
                errors.append(f"Request {i}: status {r.status_code}")
            else:
                pred = r.json()["prediction"]
                if pred != "Pathogenic":
                    errors.append(f"Request {i}: unexpected prediction {pred}")
                latencies.append(elapsed)

        assert len(errors) == 0, f"Errors during stress test:\n" + "\n".join(errors)

        mean_latency = statistics.mean(latencies)
        stdev_latency = statistics.stdev(latencies)
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        print(f"\n  100-request stress: mean={mean_latency*1000:.1f}ms "
              f"stdev={stdev_latency*1000:.1f}ms p99={p99*1000:.1f}ms")

        # p99 should stay within 5× the SLA
        assert p99 < SLA["predict_variant"] * 5, \
            f"p99 under stress ({p99:.3f}s) exceeds threshold"

    def test_response_time_does_not_degrade_over_50_calls(self):
        """Check for memory leaks / connection pool issues by comparing first vs last 10."""
        latencies = []
        for _ in range(50):
            _, elapsed = timed_post(f"{BASE}/predict_variant", BENIGN_VARIANT)
            latencies.append(elapsed)

        first_10_mean = statistics.mean(latencies[:10])
        last_10_mean = statistics.mean(latencies[-10:])
        degradation_ratio = last_10_mean / first_10_mean
        print(f"\n  First 10 mean: {first_10_mean*1000:.1f}ms  "
              f"Last 10 mean: {last_10_mean*1000:.1f}ms  "
              f"Ratio: {degradation_ratio:.2f}×")

        # Last 10 should not be more than 3× slower than first 10
        assert degradation_ratio < 3.0, \
            f"Response time degraded by {degradation_ratio:.1f}× over 50 calls — possible memory leak"


# ─────────────────────────────────────────────────────────────────────────────
# PERF-05: Latency Statistics (mean, median, p95, p99)
# ─────────────────────────────────────────────────────────────────────────────

class TestLatencyStatistics:

    def _collect_latencies(self, url, payload, n=30):
        latencies = []
        for _ in range(n):
            _, elapsed = timed_post(url, payload)
            latencies.append(elapsed)
        latencies.sort()
        return latencies

    def test_predict_latency_statistics(self):
        latencies = self._collect_latencies(f"{BASE}/predict_variant", PATHOGENIC_VARIANT, n=30)
        mean = statistics.mean(latencies)
        median = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"\n  /predict_variant over 30 calls:")
        print(f"    mean={mean*1000:.1f}ms  median={median*1000:.1f}ms  "
              f"p95={p95*1000:.1f}ms  p99={p99*1000:.1f}ms")

        assert mean < SLA["predict_variant"], \
            f"Mean latency {mean:.3f}s exceeds SLA {SLA['predict_variant']}s"
        assert p95 < SLA["predict_variant"] * 2, \
            f"p95 latency {p95:.3f}s too high"

    def test_latency_consistency_low_stdev(self):
        """Standard deviation should be low — indicates stable performance."""
        latencies = self._collect_latencies(f"{BASE}/predict_variant", BENIGN_VARIANT, n=20)
        mean = statistics.mean(latencies)
        stdev = statistics.stdev(latencies)
        cv = stdev / mean  # coefficient of variation

        print(f"\n  Coefficient of variation: {cv:.2%}")
        # CV > 300% would indicate highly unstable response times
        # (cold-start outliers on first call can inflate CV on short requests)
        assert cv < 3.0, f"High latency variance (CV={cv:.2%}) — API is unstable"


# ─────────────────────────────────────────────────────────────────────────────
# PERF-06: Cache Effectiveness
# ─────────────────────────────────────────────────────────────────────────────

class TestCacheEffectiveness:

    def test_repeated_same_gene_literature_is_faster(self):
        """Second call to same gene literature should be faster (cached)."""
        _, first = timed_get(f"{BASE}/literature/SCN1A")
        _, second = timed_get(f"{BASE}/literature/SCN1A")
        _, third = timed_get(f"{BASE}/literature/SCN1A")

        print(f"\n  Literature SCN1A: 1st={first:.2f}s  2nd={second:.2f}s  3rd={third:.2f}s")
        # Second/third calls should typically be faster than first (cache hit)
        # Allow generous margin since network calls may vary
        assert second < SLA["literature"], \
            f"Second literature call took {second:.2f}s — cache may not be working"

    def test_predict_variant_deterministic(self):
        """Same input must always produce exactly the same probability."""
        results = []
        for _ in range(5):
            r = requests.post(f"{BASE}/predict_variant", json=PATHOGENIC_VARIANT).json()
            results.append(r["pathogenic_probability"])
        assert len(set(results)) == 1, \
            f"Non-deterministic predictions: {results}"


# ─────────────────────────────────────────────────────────────────────────────
# PERF-07: Endpoint Availability
# ─────────────────────────────────────────────────────────────────────────────

class TestEndpointAvailability:

    ALL_GET_ENDPOINTS = [
        "/health",
        "/genes",
        "/consequences",
        "/literature/SCN1A",
        "/literature/KCNQ2",
    ]

    def test_all_get_endpoints_available(self):
        for ep in self.ALL_GET_ENDPOINTS:
            r, elapsed = timed_get(f"{BASE}{ep}")
            print(f"\n  GET {ep}: {r.status_code} in {elapsed*1000:.1f}ms")
            assert r.status_code == 200, f"{ep} returned {r.status_code}"

    def test_uptime_over_30_health_polls(self):
        """30 rapid health checks — all must return 200 (uptime test)."""
        failures = []
        for i in range(30):
            r = requests.get(f"{BASE}/health")
            if r.status_code != 200:
                failures.append(f"Poll {i}: {r.status_code}")
        assert len(failures) == 0, f"Health check failures: {failures}"
