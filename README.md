# TD Global Policy Watch — setup (hosted, no local machine required)

This is the fix for "I should not have to rely on running this locally, and
it should cover adoption policy worldwide." It runs on GitHub's servers on a
schedule. Your Mac can be off, asleep, or a thousand miles away — it still runs.

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
