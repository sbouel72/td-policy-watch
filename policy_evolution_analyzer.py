#!/usr/bin/env python3
"""
policy_evolution_analyzer.py  —  AALS v2.0

Comparative-jurisdiction analysis layer for td-global-policy-watch.

Holds a citation-backed dataset of adoption record-access mechanisms and
reports two objective things: structural equivalence (same documented effect
on legal identity, across jurisdictions) and phase timing (when comparable
mechanisms took effect). It asserts nothing about intent or coordination.

Run:
    python3 policy_evolution_analyzer.py            # full report
    python3 policy_evolution_analyzer.py --check    # integrity gate only
    python3 policy_evolution_analyzer.py --json-only
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "state", "mechanism-dataset.json")
REPORT_JSON_PATH = os.path.join(SCRIPT_DIR, "mechanism-analysis.json")
REPORT_MD_PATH = os.path.join(SCRIPT_DIR, "mechanism-analysis.md")

PHASES = {
    "P1_CLOSED": "Records legally closed; no adoptee access route.",
    "P2_MEDIATED": "Access only via institutional intermediary / registry / veto.",
    "P3_CONDITIONAL": "Direct access exists but is conditioned on a legal step "
                      "affecting the adoptee's status (e.g. discharge/annulment) "
                      "or a contact/information veto.",
    "P4_OVERSIGHT_DECAY": "An oversight/redress mechanism was created then wound "
                          "down, narrowed, or closed.",
}

PLACEHOLDER_MARKERS = {"", "TODO", "TBD", "FIXME", "PLACEHOLDER", None}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("[{}] {}".format(ts, msg))


def seed_dataset():
    return {
        "schema_version": "2.0",
        "note": "Each entry is a claim about a record-access mechanism. "
                "Fill 'citation' with a primary source (statute/section or "
                "official page) and set 'verified': true once checked. "
                "Unverified rows are excluded from comparative findings.",
        "mechanisms": [
            {
                "id": "AU-SA-DISCHARGE",
                "jurisdiction": "AU",
                "subnational": "SA",
                "mechanism_name": "Discharge of adoption order",
                "year_effective": None,
                "phase": "P3_CONDITIONAL",
                "effect_on_legal_identity": "severs_adoptive_legal_relationship",
                "access_granted": "origin_information",
                "citation": "",
                "verified": False,
            },
            {
                "id": "US-GENERIC-ANNULMENT",
                "jurisdiction": "US",
                "subnational": None,
                "mechanism_name": "Annulment / abrogation of adoption",
                "year_effective": None,
                "phase": "P3_CONDITIONAL",
                "effect_on_legal_identity": "severs_adoptive_legal_relationship",
                "access_granted": "origin_information",
                "citation": "",
                "verified": False,
            },
        ],
    }


def load_dataset():
    if not os.path.exists(DATA_PATH):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        data = seed_dataset()
        with open(DATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
        log("No dataset found — wrote seed scaffold to {}".format(DATA_PATH))
        log("ACTION NEEDED: fill in citations + set verified:true, then re-run.")
        return data
    with open(DATA_PATH) as f:
        content = f.read()
    if not content.strip():
        raise ValueError("{} is empty. Delete it to regenerate the seed.".format(DATA_PATH))
    return json.loads(content)


def integrity_check(data):
    problems = []
    seen_ids = set()
    for i, m in enumerate(data.get("mechanisms", [])):
        rid = m.get("id") or "<row {}>".format(i)
        if m.get("id") in seen_ids:
            problems.append("{}: duplicate id".format(rid))
        seen_ids.add(m.get("id"))
        if m.get("phase") not in PHASES:
            problems.append("{}: unknown phase '{}'".format(rid, m.get("phase")))
        if m.get("verified") is True:
            if m.get("citation") in PLACEHOLDER_MARKERS:
                problems.append("{}: verified:true but citation is empty/placeholder".format(rid))
            if m.get("year_effective") in (None, 0):
                problems.append("{}: verified:true but year_effective missing".format(rid))
    return problems


def verified_rows(data):
    out = []
    for m in data.get("mechanisms", []):
        if m.get("verified") is True and m.get("citation") not in PLACEHOLDER_MARKERS:
            out.append(m)
    return out


def analyze_effect_equivalence(rows):
    by_effect = {}
    for m in rows:
        by_effect.setdefault(m["effect_on_legal_identity"], []).append(m)
    findings = []
    for effect, group in by_effect.items():
        jurisdictions = sorted({m["jurisdiction"] for m in group})
        if len(jurisdictions) >= 2:
            findings.append({
                "type": "structural_equivalence",
                "effect_on_legal_identity": effect,
                "jurisdictions": jurisdictions,
                "mechanisms": [
                    {"id": m["id"], "name": m["mechanism_name"],
                     "jurisdiction": m["jurisdiction"], "citation": m["citation"]}
                    for m in group
                ],
                "statement": "{} verified mechanisms across {} jurisdictions "
                             "produce the same documented effect: {}.".format(
                                 len(group), len(jurisdictions), effect),
            })
    return findings


def analyze_phase_timing(rows):
    by_phase = {}
    for m in rows:
        if m.get("year_effective"):
            by_phase.setdefault(m["phase"], []).append(m)
    out = []
    for phase, group in by_phase.items():
        years = sorted(m["year_effective"] for m in group)
        if len(years) >= 2:
            out.append({
                "phase": phase,
                "phase_description": PHASES[phase],
                "n_jurisdictions": len({m["jurisdiction"] for m in group}),
                "earliest_year": years[0],
                "latest_year": years[-1],
                "span_years": years[-1] - years[0],
                "entries": [
                    {"jurisdiction": m["jurisdiction"], "year": m["year_effective"],
                     "mechanism": m["mechanism_name"], "citation": m["citation"]}
                    for m in sorted(group, key=lambda x: x["year_effective"])
                ],
            })
    return out


def build_report(data):
    problems = integrity_check(data)
    rows = verified_rows(data)
    total = len(data.get("mechanisms", []))
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "schema_version": data.get("schema_version"),
        "dataset_summary": {
            "total_rows": total,
            "verified_rows": len(rows),
            "unverified_rows": total - len(rows),
            "integrity_problems": problems,
        },
        "structural_equivalences": analyze_effect_equivalence(rows),
        "phase_timing": analyze_phase_timing(rows),
        "disclaimer": "This report describes DOCUMENTED mechanism effects and "
                      "their timing only. It makes no claim about intent or "
                      "coordination. Unverified rows are excluded. Every finding "
                      "is traceable to the cited source in the dataset.",
    }


def render_markdown(report):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# AALS v2.0 — Mechanism Analysis — {}".format(ts), ""]
    s = report["dataset_summary"]
    L.append("**Dataset:** {} verified of {} rows ({} awaiting source/verification).".format(
        s["verified_rows"], s["total_rows"], s["unverified_rows"]))
    L.append("")
    if s["integrity_problems"]:
        L.append("## Integrity problems (fix before citing)")
        for p in s["integrity_problems"]:
            L.append("- {}".format(p))
        L.append("")
    if not report["structural_equivalences"] and not report["phase_timing"]:
        L.append("_No verified comparative findings yet. Add citations and set "
                 "`verified: true` on dataset rows, then re-run._")
        return "\n".join(L)
    if report["structural_equivalences"]:
        L.append("## Documented structural equivalences")
        L.append("_Same documented effect on legal identity, across jurisdictions._")
        for f in report["structural_equivalences"]:
            L.append("\n### Effect: `{}` ({})".format(
                f["effect_on_legal_identity"], ", ".join(f["jurisdictions"])))
            L.append(f["statement"])
            for m in f["mechanisms"]:
                L.append("- **{}** ({}) — {}".format(m["name"], m["jurisdiction"], m["id"]))
                L.append("  - source: {}".format(m["citation"]))
        L.append("")
    if report["phase_timing"]:
        L.append("## Phase timing across jurisdictions")
        L.append("_Descriptive only — when comparable mechanisms took effect._")
        for pt in report["phase_timing"]:
            L.append("\n### {} — {}".format(pt["phase"], pt["phase_description"]))
            L.append("{} jurisdictions · {}–{} (span {} yrs)".format(
                pt["n_jurisdictions"], pt["earliest_year"], pt["latest_year"], pt["span_years"]))
            for e in pt["entries"]:
                L.append("- {} · {} · {}".format(e["year"], e["jurisdiction"], e["mechanism"]))
                L.append("  - source: {}".format(e["citation"]))
        L.append("")
    L.append("---")
    L.append("_{}_".format(report["disclaimer"]))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only run dataset integrity checks")
    ap.add_argument("--json-only", action="store_true", help="write JSON, skip markdown")
    args = ap.parse_args()

    data = load_dataset()

    if args.check:
        problems = integrity_check(data)
        if not problems:
            log("Integrity check: clean.")
            return 0
        log("Integrity check: {} problem(s):".format(len(problems)))
        for p in problems:
            print("  - {}".format(p))
        return 1

    report = build_report(data)
    with open(REPORT_JSON_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log("JSON report → {}".format(REPORT_JSON_PATH))

    if not args.json_only:
        md = render_markdown(report)
        with open(REPORT_MD_PATH, "w") as f:
            f.write(md)
        log("Markdown report → {}".format(REPORT_MD_PATH))
        print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
