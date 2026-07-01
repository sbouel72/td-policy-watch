#!/usr/bin/env python3
"""
td-global-policy-watch.py

Worldwide adoption-policy signal watcher for Thoughtless Delineation.

Two tiers:

1. NEWS SIGNAL (broad, worldwide) — runs a matrix of topic x jurisdiction
   queries against Google News RSS (no API key required, works for any
   country Google indexes news for). This is signal detection, not a
   verified legislative tracker: it surfaces candidate developments across
   sealed/original birth certificate law, forced adoption inquiries and
   apologies, intercountry adoption policy, adoption agency investigations,
   and related topics, across AU/US/GB/CA/NZ/IE by default (edit
   JURISDICTIONS below to add more).

2. SPECIFIC BILL TRACKING (narrow, verified) — for bills you're actively
   tracking with an official status page (currently: US state legislatures
   via leginfo-style pages, starting with CA SB 381). This tier is the same
   verified mechanism as td-bill-watcher.py, folded in here so one run
   covers both breadth (tier 1) and precision (tier 2).

Designed to run on GitHub Actions on a schedule -- NOT dependent on your
Mac being on. State is committed back to the repo each run, and any new
finding opens or updates a GitHub Issue (which GitHub emails you about
automatically, no extra notification setup needed).

Can still be run locally / manually for testing:
    python3 td-global-policy-watch.py
    python3 td-global-policy-watch.py --dry-run    (don't write state or open issues)
"""

import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import Request, urlopen

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(SCRIPT_DIR, "state", "seen-news-items.json")
BILLS_CONFIG_PATH = os.path.join(SCRIPT_DIR, "state", "bills-config.json")
BILLS_STATE_PATH = os.path.join(SCRIPT_DIR, "state", "bills-state.json")
DIGEST_PATH = os.path.join(SCRIPT_DIR, "latest-digest.md")

# ---------------------------------------------------------------------------
# TIER 1 CONFIG — broad worldwide news signal
# ---------------------------------------------------------------------------

TOPICS = [
    "original birth certificate adoptee",
    "sealed adoption records",
    "forced adoption inquiry",
    "forced adoption apology",
    "forced adoption redress scheme",
    "adoptee rights legislation",
    "intercountry adoption suspended",
    "intercountry adoption banned",
    "adoption agency investigation fraud",
    "birth parent registry law",
    "closed adoption records reform",
    "adoption records unsealed",
    "child citizenship act adoptee deportation",
    "foundling registry identity rights",
    "adoptee original birth certificate bill",
]

# (hl, gl) pairs -- language/country codes Google News RSS expects.
# Add more jurisdictions here as needed.
JURISDICTIONS = [
    ("en-AU", "AU"),
    ("en-US", "US"),
    ("en-GB", "GB"),
    ("en-CA", "CA"),
    ("en-NZ", "NZ"),
    ("en-IE", "IE"),
]

# Crude noise filters -- titles containing these are almost always false
# positives from a broad news query (celebrity gossip, unrelated "adoption"
# usage like pet/software adoption, etc). Extend as you see junk in digests.
NOISE_PATTERNS = [
    r"\bpet adoption\b",
    r"\bdog adoption\b",
    r"\bcat adoption\b",
    r"\badopts? (a |the )?(cloud|framework|standard|policy)\b",
    r"\bMiley Cyrus\b",
]

MAX_ITEMS_PER_QUERY = 15  # keep it bounded per query
RECENCY_WINDOW_DAYS = 14  # only alert on items published within this window
MAX_ISSUE_BODY_CHARS = 60000  # stay safely under GitHub's 65536 limit


def parse_pub_date(pub_date_str: str):
    """Parse RFC 822-style pubDate from Google News RSS. Returns None on failure."""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def is_recent(pub_date_str: str, window_days: int = RECENCY_WINDOW_DAYS) -> bool:
    dt = parse_pub_date(pub_date_str)
    if dt is None:
        return False  # unparseable date -- treat as not-recent rather than risk false alerts
    age = datetime.now(timezone.utc) - dt
    return age.days <= window_days


def log(line: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {line}")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        content = f.read()
    if not content.strip():
        raise ValueError(
            f"{path} exists but is empty. This usually means a file copy didn't "
            f"actually transfer content (0 bytes). Check with: wc -c {path}"
        )
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON: {e}") from e


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def is_noise(title: str) -> bool:
    return any(re.search(p, title, re.IGNORECASE) for p in NOISE_PATTERNS)


def fetch_news(topic: str, hl: str, gl: str) -> list:
    lang = hl.split("-")[0]
    q = urllib.parse.quote(topic)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (TD-Global-Policy-Watch/1.0)"})
    try:
        with urlopen(req, timeout=30) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ERROR fetching '{topic}' [{gl}]: {e}")
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log(f"  ERROR parsing '{topic}' [{gl}]: {e}")
        return []

    items = []
    for item in root.findall(".//item")[:MAX_ITEMS_PER_QUERY]:
        title = (item.find("title").text or "").strip()
        link = (item.find("link").text or "").strip()
        pub_date = (item.find("pubDate").text or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        if is_noise(title):
            continue
        items.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "source": source,
            "topic": topic,
            "jurisdiction": gl,
        })
    return items


def run_news_scan(seen: dict) -> list:
    """Returns list of NEW and RECENT items not seen in a prior run.
    All fetched items are recorded as seen regardless of age, so stale
    backlog items (which can resurface in RSS ordering) never re-trigger
    an alert later -- but only recent items are surfaced as alertable now.
    """
    new_items = []
    for topic in TOPICS:
        for hl, gl in JURISDICTIONS:
            items = fetch_news(topic, hl, gl)
            for it in items:
                key = it["link"]
                if key in seen:
                    continue
                seen[key] = {
                    "title": it["title"],
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                    "topic": topic,
                    "jurisdiction": gl,
                    "pub_date": it["pub_date"],
                }
                if is_recent(it["pub_date"]):
                    new_items.append(it)
                # else: recorded as seen, but not surfaced -- backlog, not signal
    return new_items


# ---------------------------------------------------------------------------
# TIER 2 — specific bill tracking (same mechanism as td-bill-watcher.py)
# ---------------------------------------------------------------------------

LEGINFO_URL = "https://leginfo.legislature.ca.gov/faces/billStatusClient.xhtml?bill_id={bill_id}"


def fetch_ca_bill_status(bill_id: str) -> dict:
    url = LEGINFO_URL.format(bill_id=bill_id)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (TD-Global-Policy-Watch/1.0)"})
    with urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    history_match = re.search(
        r'id="billhistory".*?<tbody>\s*<tr>\s*<td[^>]*>([^<]+)</td>\s*<td>([^<]+)</td>',
        html, re.DOTALL,
    )
    latest_date = history_match.group(1).strip() if history_match else None
    latest_action = re.sub(r"\s+", " ", history_match.group(2)).strip() if history_match else None
    return {"latest_date": latest_date, "latest_action": latest_action, "source_url": url}


def run_bill_checks() -> list:
    """Returns list of change events across all configured tracked bills."""
    config = load_json(BILLS_CONFIG_PATH, {"bills": []})
    state = load_json(BILLS_STATE_PATH, {})
    changes = []
    for entry in config.get("bills", []):
        bill_id, label, jurisdiction = entry["bill_id"], entry["label"], entry.get("jurisdiction", "US-CA")
        try:
            if jurisdiction.startswith("US-"):
                current = fetch_ca_bill_status(bill_id)  # currently: CA-pattern leginfo sites
            else:
                log(f"  skip {label}: jurisdiction '{jurisdiction}' has no tracker implemented yet")
                continue
        except Exception as e:
            log(f"  ERROR checking {label}: {e}")
            continue

        previous = state.get(bill_id)
        if previous is None or (previous.get("latest_date"), previous.get("latest_action")) != \
                (current.get("latest_date"), current.get("latest_action")):
            if previous is not None:
                changes.append({
                    "label": label, "bill_id": bill_id,
                    "was": f"{previous.get('latest_date')} — {previous.get('latest_action')}",
                    "now": f"{current.get('latest_date')} — {current.get('latest_action')}",
                    "source_url": current.get("source_url"),
                })
            state[bill_id] = current
    save_json(BILLS_STATE_PATH, state)
    return changes


# ---------------------------------------------------------------------------
# Digest + GitHub Issue output
# ---------------------------------------------------------------------------

def build_digest(new_news_items: list, bill_changes: list) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# TD Global Policy Watch — {ts}", ""]

    if bill_changes:
        lines.append("## Tracked bill status changes (verified, official source)")
        for c in bill_changes:
            lines.append(f"- **{c['label']}**")
            lines.append(f"  - was: {c['was']}")
            lines.append(f"  - now: {c['now']}")
            lines.append(f"  - source: {c['source_url']}")
        lines.append("")

    if new_news_items:
        lines.append(f"## New worldwide signal items ({len(new_news_items)})")
        lines.append("_Unverified news signal — check each before citing in an episode._")
        by_jurisdiction = {}
        for it in new_news_items:
            by_jurisdiction.setdefault(it["jurisdiction"], []).append(it)
        for gl, items in sorted(by_jurisdiction.items()):
            lines.append(f"\n### {gl}")
            for it in items:
                lines.append(f"- [{it['title']}]({it['link']}) — {it['source']} ({it['pub_date']}) — topic: _{it['topic']}_")
        lines.append("")

    if not bill_changes and not new_news_items:
        lines.append("No new items this run.")

    return "\n".join(lines)


def maybe_open_github_issue(digest: str, has_content: bool):
    """If running inside GitHub Actions with a token and there's new content,
    open an issue so a notification email goes out. No-ops otherwise.
    Truncates the body if needed -- GitHub's API rejects issue bodies over
    65536 characters; the full digest always remains in latest-digest.md
    regardless of what fits in the issue."""
    if not has_content:
        return
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # e.g. "sbouel72/td-policy-watch"
    if not token or not repo:
        log("  (not running in GitHub Actions with a token -- skipping issue creation, digest still written to file)")
        return
    import requests  # local import; only needed in this path

    body = digest
    if len(body) > MAX_ISSUE_BODY_CHARS:
        cutoff = body[:MAX_ISSUE_BODY_CHARS]
        # cut at the last full line so we don't split mid-item
        cutoff = cutoff.rsplit("\n", 1)[0]
        body = (
            cutoff
            + f"\n\n---\n_Truncated at {MAX_ISSUE_BODY_CHARS} characters "
              f"({len(digest)} total). Full digest: see latest-digest.md in the repo._"
        )

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    payload = {
        "title": f"TD Policy Watch — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "body": body,
        "labels": ["policy-watch"],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code == 422 and "label" in r.text.lower():
        # label doesn't exist on repo yet -- retry once without it rather than losing the alert
        log("  label 'policy-watch' rejected, retrying without labels...")
        payload.pop("labels")
        r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code >= 300:
        log(f"  ERROR opening GitHub issue: {r.status_code} {r.text[:300]}")
    else:
        log(f"  Opened issue: {r.json().get('html_url')}")


def main():
    dry_run = "--dry-run" in sys.argv

    log("Tier 1: worldwide news signal scan...")
    seen = load_json(STATE_PATH, {})
    new_news_items = run_news_scan(seen)
    log(f"  {len(new_news_items)} new item(s) found.")

    log("Tier 2: tracked bill status checks...")
    bill_changes = run_bill_checks()
    log(f"  {len(bill_changes)} bill change(s) found.")

    digest = build_digest(new_news_items, bill_changes)
    with open(DIGEST_PATH, "w") as f:
        f.write(digest)
    log(f"Digest written to {DIGEST_PATH}")

    has_content = bool(new_news_items or bill_changes)

    if not dry_run:
        save_json(STATE_PATH, seen)
        maybe_open_github_issue(digest, has_content)
    else:
        log("(dry run -- state not saved, no issue opened)")

    print("\n" + digest)


if __name__ == "__main__":
    main()
