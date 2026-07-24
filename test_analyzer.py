#!/usr/bin/env python3
"""
test_analyzer.py — proves the forensic discipline of policy_evolution_analyzer.

Guarantees under test:
  1. Unverified rows never become findings.
  2. verified:true without a real citation is caught by integrity_check.
  3. Two verified rows with the same effect produce an equivalence finding.
  4. Finding values never assert intent/coordination.

Run: python3 test_analyzer.py
"""

import json
import policy_evolution_analyzer as A


def _row(**kw):
    base = {
        "id": "X", "jurisdiction": "AU", "subnational": None,
        "mechanism_name": "m", "year_effective": 2000, "phase": "P3_CONDITIONAL",
        "effect_on_legal_identity": "severs_adoptive_legal_relationship",
        "access_granted": "origin_information", "citation": "Real Act s1",
        "verified": True,
    }
    base.update(kw)
    return base


def test_unverified_excluded():
    data = {"mechanisms": [_row(verified=False)]}
    assert A.verified_rows(data) == [], "unverified row leaked into findings"


def test_placeholder_citation_excluded():
    data = {"mechanisms": [_row(citation="")]}
    assert A.verified_rows(data) == [], "empty citation treated as verified"


def test_integrity_catches_verified_without_citation():
    data = {"mechanisms": [_row(citation="TODO")]}
    problems = A.integrity_check(data)
    assert any("citation" in p for p in problems), "integrity_check missed uncited claim"


def test_integrity_catches_bad_phase():
    data = {"mechanisms": [_row(phase="NONSENSE")]}
    problems = A.integrity_check(data)
    assert any("phase" in p for p in problems), "integrity_check missed bad phase"


def test_equivalence_requires_two_jurisdictions():
    data = {"mechanisms": [_row(id="a", jurisdiction="AU"),
                           _row(id="b", jurisdiction="AU")]}
    assert A.analyze_effect_equivalence(A.verified_rows(data)) == [], \
        "same-jurisdiction rows should not form a cross-jurisdiction equivalence"


def test_equivalence_found_across_jurisdictions():
    data = {"mechanisms": [_row(id="a", jurisdiction="AU"),
                           _row(id="b", jurisdiction="US")]}
    findings = A.analyze_effect_equivalence(A.verified_rows(data))
    assert len(findings) == 1 and set(findings[0]["jurisdictions"]) == {"AU", "US"}


def test_no_intent_language_in_findings():
    data = {"mechanisms": [_row(id="a", jurisdiction="AU"),
                           _row(id="b", jurisdiction="US")]}
    report = A.build_report(data)
    findings_blob = json.dumps({
        "structural_equivalences": report["structural_equivalences"],
        "phase_timing": report["phase_timing"],
    }).lower()
    for banned in ("coordination", "conspiracy", "deliberate", "intent"):
        assert banned not in findings_blob, \
            "findings assert '{}' — must stay descriptive".format(banned)


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("  ok  {}".format(t.__name__))
    print("\n{}/{} passed".format(len(tests), len(tests)))


if __name__ == "__main__":
    run()
