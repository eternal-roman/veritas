"""Expanded evaluation harness: fidelity, refusal, calibration proxy, baseline comparison."""

from typing import List, Dict, Any
from veritas.pipeline import run_research
from veritas.hashing import verify_content_hash

def evaluate_fidelity(queries: List[str] = None) -> Dict[str, Any]:
    if queries is None:
        queries = [
            "What is the x402 protocol?",
            "How does the CDP Bazaar help agents?",
            "What is the Model Context Protocol?"
        ]
    total_claims = 0
    hash_valid = 0
    details = []
    for q in queries:
        resp = run_research(q)
        n = len(resp.get("claims", []))
        total_claims += n
        valid_count = 0
        for claim in resp.get("claims", []):
            for ev in resp.get("evidence", []):
                if ev.get("content_hash") == claim.get("evidence_hash"):
                    ok, _ = verify_content_hash(ev["excerpt"], ev["content_hash"])
                    if ok:
                        valid_count += 1
                        hash_valid += 1
                    break
        details.append({"query": q, "status": resp["status"], "claims": n, "hash_valid": valid_count})
    fidelity = hash_valid / max(1, total_claims)
    return {"citation_fidelity": round(fidelity, 3), "total_claims": total_claims, "details": details}

def evaluate_refusal() -> Dict[str, Any]:
    resp = run_research("xyznonexistenttopic12345 obscure query with no public support")
    return {
        "status": resp["status"],
        "posterior": resp.get("posterior"),
        "n_claims": len(resp.get("claims", [])),
        "custody_valid": resp.get("custody_valid")
    }

def evaluate_baseline_comparison() -> Dict[str, Any]:
    """Simple baseline: just return the first evidence text as the 'answer'."""
    q = "What is x402?"
    veritas = run_research(q)
    baseline_answer = veritas["evidence"][0]["excerpt"] if veritas.get("evidence") else "No information"
    return {
        "query": q,
        "veritas_status": veritas["status"],
        "veritas_claims": len(veritas.get("claims", [])),
        "veritas_posterior": veritas.get("posterior"),
        "baseline_length": len(baseline_answer),
        "veritas_has_custody": veritas.get("custody_valid")
    }

def run_full_harness() -> Dict[str, Any]:
    return {
        "fidelity": evaluate_fidelity(),
        "refusal": evaluate_refusal(),
        "baseline_comparison": evaluate_baseline_comparison()
    }

if __name__ == "__main__":
    import json
    print(json.dumps(run_full_harness(), indent=2))
