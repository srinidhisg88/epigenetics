"""
Smoke Tests — Epilepsy Diagnostic Assistant
============================================
Fast sanity checks run immediately after deployment.
If ANY of these fail, the system is not ready for use.

Goal: < 60 seconds total runtime.
No deep validation — just "is the system alive and basically working?"

Run:
    pytest tests/test_smoke.py -v
(backend must be running at localhost:8000)
"""

import pytest
import requests

BASE = "http://localhost:8000"

STANDARD_VARIANT = {
    "gene": "SCN1A",
    "chromosome": "2",
    "reference_allele": "C",
    "alternate_allele": "T",
    "consequence": "stop_gained",
    "variant_type": "single nucleotide variant",
    "review_status": "criteria provided, multiple submitters",
    "origin": "germline",
}


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-01: Service is alive
# ─────────────────────────────────────────────────────────────────────────────

class TestServiceAlive:

    def test_health_endpoint_returns_ok(self):
        r = requests.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200

    def test_model_is_loaded(self):
        r = requests.get(f"{BASE}/health").json()
        assert r["model_loaded"] is True, "ML model not loaded — system not ready"

    def test_rag_is_loaded(self):
        r = requests.get(f"{BASE}/health").json()
        assert r["rag_loaded"] is True, "RAG not loaded — system not ready"

    def test_status_field_is_ok(self):
        r = requests.get(f"{BASE}/health").json()
        assert r["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-02: Core endpoints respond
# ─────────────────────────────────────────────────────────────────────────────

class TestCoreEndpointsRespond:

    def test_predict_variant_accepts_request(self):
        r = requests.post(f"{BASE}/predict_variant", json=STANDARD_VARIANT, timeout=10)
        assert r.status_code == 200

    def test_analyze_variant_accepts_request(self):
        r = requests.post(f"{BASE}/analyze_variant", json=STANDARD_VARIANT, timeout=35)
        assert r.status_code == 200

    def test_genes_endpoint_responds(self):
        r = requests.get(f"{BASE}/genes", timeout=5)
        assert r.status_code == 200

    def test_consequences_endpoint_responds(self):
        r = requests.get(f"{BASE}/consequences", timeout=5)
        assert r.status_code == 200

    def test_literature_endpoint_responds(self):
        r = requests.get(f"{BASE}/literature/SCN1A", timeout=10)
        assert r.status_code == 200

    def test_chat_endpoint_responds(self):
        r = requests.post(f"{BASE}/chat", json={
            "messages": [{"role": "user", "content": "What is SCN1A?"}],
            "variant_context": None,
        }, timeout=15)
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-03: Core prediction works
# ─────────────────────────────────────────────────────────────────────────────

class TestCorePredictionWorks:

    def test_pathogenic_variant_returns_pathogenic(self):
        r = requests.post(f"{BASE}/predict_variant", json=STANDARD_VARIANT).json()
        assert r["prediction"] == "Pathogenic"

    def test_benign_variant_returns_benign(self):
        r = requests.post(f"{BASE}/predict_variant", json={
            "gene": "SLC2A1", "chromosome": "1",
            "reference_allele": "C", "alternate_allele": "T",
            "consequence": "synonymous_variant",
            "variant_type": "single nucleotide variant",
            "review_status": "no assertion criteria provided",
            "origin": "germline",
        }).json()
        assert r["prediction"] == "Benign"

    def test_response_has_probability_fields(self):
        r = requests.post(f"{BASE}/predict_variant", json=STANDARD_VARIANT).json()
        assert "pathogenic_probability" in r
        assert "benign_probability" in r
        assert "confidence" in r

    def test_acmg_classification_present_in_full_analysis(self):
        r = requests.post(f"{BASE}/analyze_variant", json=STANDARD_VARIANT).json()
        assert "acmg_classification" in r
        assert "classification" in r["acmg_classification"]

    def test_invalid_input_returns_422_not_500(self):
        r = requests.post(f"{BASE}/predict_variant", json={})
        assert r.status_code == 422, \
            f"Expected 422, got {r.status_code} — input validation may be broken"


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-04: Data lists are populated
# ─────────────────────────────────────────────────────────────────────────────

class TestDataListsPopulated:

    def test_genes_list_is_nonempty(self):
        data = requests.get(f"{BASE}/genes").json()
        genes = data.get("genes", data) if isinstance(data, dict) else data
        assert isinstance(genes, list)
        assert len(genes) > 0

    def test_genes_list_contains_scn1a(self):
        data = requests.get(f"{BASE}/genes").json()
        genes = data.get("genes", data) if isinstance(data, dict) else data
        assert "SCN1A" in genes

    def test_consequences_list_is_nonempty(self):
        data = requests.get(f"{BASE}/consequences").json()
        cons = data.get("consequences", data) if isinstance(data, dict) else data
        assert isinstance(cons, list)
        assert len(cons) > 0

    def test_consequences_includes_stop_gained(self):
        data = requests.get(f"{BASE}/consequences").json()
        cons = data.get("consequences", data) if isinstance(data, dict) else data
        assert "stop_gained" in cons
