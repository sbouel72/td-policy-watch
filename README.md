# TD Global Policy Watch — setup (hosted, no local machine required)

This is the fix for "I should not have to rely on running this locally, and
it should cover adoption policy worldwide." It runs on GitHub's servers on a
schedule. Your Mac can be off, asleep, or a thousand miles away — it still runs.

**Follow Here for Daily Results** https://github.com/sbouel72/td-policy-watch/issues/

## What it actually covers, stated plainly

**Tier 1 — worldwide news signal (broad, unverified).** Scans Google News
across AU, US, GB, CA, NZ, IE for ~15 adoption-policy topics: OBC access,
forced adoption inquiries/apologies/redress, sealed records, intercountry
adoption bans/suspensions, agency fraud investigations, birth parent
registries, and related. This is signal detection, not a verified database —
every item needs your (or Claude's) eyes before it goes in an episode. Today's
test run alone surfaced a UK government forced-adoption apology, a Dutch
"Damaged by Disgrace" report, South Korea's adoption-fraud truth commission,
and Canada's 300,000-mothers redress story — none of which were in scope
before this existed.

**Tier 2 — specific bill tracking (narrow, verified).** For bills with an
official status page (currently CA state legislature via leginfo — same
mechanism as the standalone SB 381 watcher, folded in here). Add more states
or countries as tracked bills come up; each needs its own parser since every
legislature's status page is structured differently.

**Honest scope limit:** there is no single global database of "all adoption
policy worldwide" to query — no country publishes one, and most countries
don't have English-language legislative trackers at all. What this gives you
is broad English-language news signal across six anglophone jurisdictions
(where the bulk of TD's audience and the bulk of the forced-adoption/OBC
advocacy landscape sits) plus deep, verified tracking on the specific bills
you're actively covering. Non-English jurisdictions (e.g. South Korea,
Netherlands) will surface only when English-language press covers them —
which, per today's test, happens regularly for major developments.

## Install (15 minutes, one-time)

1. **Create a repo** (or use an existing one, e.g. under your `sbouel72`
   GitHub account) — private is fine, this doesn't need to be public.

2. **Add these files to the repo root:**
   - `td-global-policy-watch.py`
   - `state/bills-config.json` (pre-loaded with SB 381)
   - `.github/workflows/td-policy-watch.yml` (rename `td-policy-watch.yml`
     and put it at that exact path — GitHub only picks up workflows there)

3. **Commit and push.** That's it — no secrets to configure. GitHub
   automatically provides `GITHUB_TOKEN` inside Actions; the workflow uses it
   both to commit state back and to open issues.

4. **Enable Issues** on the repo if they're off (Settings → Features → Issues).
   This is how you get notified — GitHub emails you (per your notification
   settings) whenever an issue is opened, no extra setup needed on your end.

5. **First run:** go to the Actions tab → "TD Global Policy Watch" →
   "Run workflow" to trigger it manually and confirm it works, rather than
   waiting for the schedule. Expect a large first-run digest (everything is
   "new" with no prior state) — this settles down to only true deltas from
   the second run onward.

## Adding more jurisdictions or topics

Edit `JURISDICTIONS` (hl/gl pairs) or `TOPICS` (query strings) at the top of
`td-global-policy-watch.py`, commit, push. No other changes needed.

## Adding a new tracked bill (Tier 2)

Edit `state/bills-config.json`:
```json
{"bill_id": "...", "label": "...", "jurisdiction": "US-CA"}
```
Only `US-CA` (leginfo-pattern) is implemented right now. A new jurisdiction
(e.g. US federal via Congress.gov, UK via parliament.uk, Australia via
aph.gov.au) needs its own fetch function added to the script — flag which
one you want next and it can be built the same way SB 381 was.

## Checking in without waiting for a notification

The latest digest is always at `latest-digest.md` in the repo — readable
any time, on any device, without running anything.

## Reducing noise

If a topic/jurisdiction combo produces mostly junk, either tighten the query
(more specific phrase) or add a pattern to `NOISE_PATTERNS` in the script.
This will need a pass or two of real-world tuning — the first run's backlog
is a reasonable sample to tune against before the schedule kicks in for real.

---

## AALS v2.0 — mechanism analyzer (separate subsystem)

`policy_evolution_analyzer.py` is a second, independent tool in this repo. It
does not scan news. It holds a hand-curated, citation-gated dataset of
adoption record-access mechanisms (`state/mechanism-dataset.json`) — things
like "discharge of adoption order" or "vacation of adoption" in specific
jurisdictions — and reports two objective things only:

- **Structural equivalence** — which verified mechanisms produce the same
  documented effect on legal identity, across jurisdictions.
- **Phase timing** — when each verified mechanism took effect, so timing can
  be compared.

It makes no claim about intent or coordination between jurisdictions — that's
enforced by the unit tests, not just a style choice. If a coordination
argument needs making, it belongs in prose in an episode, argued from the
evidence, never presented as this tool's output.

**Every row starts unverified and is excluded from findings until sourced.**
A row only counts once it has: the actual statute + section (not just "the
Adoption Act"), the year the *specific provision* took effect, and the
confirmed legal effect read from the primary text — not a secondhand summary.
Secondhand advocacy pages are a fine starting point for finding the citation,
but the citation itself has to trace to the primary source (the legislature's
own site, or a service like Justia/FindLaw that reproduces the current
official text with its amendment history).

### Running it

```bash
python3 test_analyzer.py                        # 7 unit tests on the analyzer's own logic
python3 policy_evolution_analyzer.py --check     # integrity gate: are dataset rows well-formed?
python3 policy_evolution_analyzer.py             # full report -> mechanism-analysis.md / .json
```

Both `mechanism-analysis.md` and `mechanism-analysis.json` are gitignored —
they're regenerated output, not tracked deliverables.

### Adding a verified row

Edit `state/mechanism-dataset.json`. Each entry needs:

```json
{
  "id": "US-CA-VACATION",
  "jurisdiction": "US",
  "subnational": "CA",
  "mechanism_name": "...",
  "year_effective": 2023,
  "phase": "P3_CONDITIONAL",
  "effect_on_legal_identity": "severs_adoptive_legal_relationship",
  "access_granted": "...",
  "citation": "Full statute text quoted, section cited, primary source URL(s), and any material caveats about how well it actually matches other rows in the same effect category.",
  "verified": true
}
```

The `citation` field is where nuance goes — if a mechanism differs in some
material way from others sharing its `effect_on_legal_identity` value (who
can invoke it, what actually happens afterward, whether it touches
birth-record access at all), say so directly in the citation text. The
analyzer only groups by the coarse effect category; the citation is what
keeps the report from silently overstating how alike two mechanisms really
are.

### CI

The scheduled workflow (`.github/workflows/td-policy-watch.yml`) runs, after
the news watch commits its state:

1. `test_analyzer.py` — the analyzer's own logic is still correct.
2. `policy_evolution_analyzer.py --check` — every dataset row is well-formed
   (known phase, no `verified: true` without a real citation and year).

Either failing fails the workflow run.

### It's folded into the daily email

Earlier in the same workflow run, before the news watch, a
`policy_evolution_analyzer.py` (full report, not `--check`) step generates
`mechanism-analysis.md`. `td-global-policy-watch.py` reads that file if
present and appends it as an "AALS v2.0 — mechanism analyzer status" section
to the digest it builds — so the same GitHub Issue/email that carries the
news signal also carries the current mechanism-tracker findings, always
regenerated fresh from `state/mechanism-dataset.json` rather than stale
output. This only adds a section to an email that's already going out for
news/bill reasons; the mechanism dataset changing (rarely, since rows are
added by hand) does not by itself trigger a new email. That analyzer step is
deliberately non-fatal (`|| true`) — a broken analyzer never blocks the news
watch or its email; it just means that day's digest omits the section. The
integrity gate later in the same run is the real enforcement point for
dataset correctness.
