---
name: aeo-weekly-audit
description: Run and maintain GV Skincare's recurring AEO audit. Use when executing the weekly/biweekly AEO audit, backfilling an audit date, sweeping for untracked local spa/medspa/derm competitors, regenerating the dashboard, or preparing the audit summary from outputs.
---

# GV Skincare AEO Weekly Audit

Use the repo as the source of truth. All paths in this skill are relative to the gvskincare repo root.

## Files

- Working directory: `tracking/`
- Queries: `tracking/queries.json` (`_schema` documents the format; `status: retired` drops a query from collection + dashboard aggregates but preserves its `trend.csv` history)
- Competitor tracker: `tracking/competitors.json` + `tracking/aliases.json`
- Runner: `tracking/audit.sh` (no separate weekly wrapper — use the `--analyze` flag, below)
- Analyzer: `tracking/analyze.py`
- Shared extractors (response text + citation URLs, imported by both `analyze.py` and `dashboard.py` — single source of truth; edit platform parsing here): `tracking/extractors.py`
- Dashboard generator: `tracking/dashboard.py`
- Dashboard template (HTML/CSS/JS; `dashboard.py` injects data into it): `tracking/dashboard-template.html`
- Append-only scored history, one row per (date, query, platform): `tracking/trend.csv`
- Per-run generated outputs: `tracking/runs/{date}/report.md` and `tracking/runs/{date}/summary.csv`
- Per-run raw responses: `tracking/runs/{date}/{platform}/q{id}.json`
- Published dashboard (self-contained, data + raw responses inlined): `docs/index.html`
- Query notes: `tracking/audit-queries.md`
- Strategy context: `STRATEGY.md`
- Narrative audits (this skill's human layer): `tracking/audit-{date}.md`

Read `audit-queries.md`, `STRATEGY.md`, and the most recent prior `audit-{date}.md` (if any) before writing a new audit.

## Workflow

1. Update local code (`git pull --rebase origin main`).
2. Run collection + analysis + dashboard in one shot with `./audit.sh --analyze`.
3. Sweep the run for untracked competitors (see "Sweep for untracked competitors"). If any are added, re-run analysis + dashboard so the run reflects them.
4. Read generated outputs from `runs/{date}/report.md` and `runs/{date}/summary.csv`.
5. Verify any `misidentified`/`dismissed` flags are genuine (see "Verify misidentifications").
6. Run the failure-mode check (see "Failure-mode check"). If any platform's tested-count dropped > 30% vs the prior run, surface it and pause before publishing.
7. Write `tracking/audit-{date}.md` as the narrative audit.
8. Commit and push on `main`. GitHub Pages republishes `docs/index.html` automatically.
9. Deliver the summary (see "Summary delivery").

## Run collection

From the repo root:

```bash
cd tracking
export DATE=$(date +%Y-%m-%d)   # or set explicitly for a backfill; export so the
                                # check/verify snippets below can read it
./audit.sh --analyze            # all platforms, all active queries, then analyze + dashboard
```

`audit.sh` skips queries already collected for the date (idempotent — safe to re-run after a partial failure), drops responses that are invalid JSON or carry an API error, and skips `status: retired` queries.

Use flags for debugging, partial reruns, or backfills:

```bash
./audit.sh --platform perplexity --date "$DATE"   # one platform
./audit.sh --queries 1,2,9 --date "$DATE"          # specific query IDs
./audit.sh --date 2026-04-04                        # backfill a past date
```

Platforms: `perplexity openai anthropic gemini grok`. API keys load from `tracking/.env`, `../.env`, or `~/repos/gotomarket/.env` (first found). The pre-flight prints which keys are set — check it before trusting a low mention rate.

## Analyze

`--analyze` already runs both of these. Run them manually only for a re-analysis (e.g. after editing `competitors.json`):

```bash
cd tracking
python3 analyze.py --date "$DATE" --compare
python3 dashboard.py
```

Treat `runs/{date}/report.md` and `runs/{date}/summary.csv` as the canonical generated outputs. Do not hand-score raw JSON unless debugging the pipeline.

## Sweep for untracked competitors

After the initial analysis, scan the run's responses for spa/medspa/derm names that aren't tracked yet. The goal is to keep `competitors.json` current without a self-maintaining regex.

**Inputs to read:**

- `competitors.json` — `seed[]` is the detected-names list (canonical + variant spellings the matcher reads); `additions[]` is where new names go with provenance; `domains{}` maps canonical name → primary domain (source of truth for favicons and the "Competitor" citation category); `categories{}` tags each canonical name `local|chain|other`.
- `aliases.json` — `map.{lowercase-variant}` → canonical name. Check before adding a variant that's already folded onto an existing competitor.
- `runs/{date}/{platform}/q*.json` — raw responses across all 5 platforms.
- `runs/{date}/report.md` — the "Top Competitors by Frequency" table and per-query lists already extracted by `analyze.py`. Names appearing in responses but missing from these lists are candidates.

**Scope policy:** which businesses count as tracked competitors is governed by [[competitor-scope-policy]] — read it before adding. In short: local Katy / west-Houston / greater-Houston spas, medspas, and dermatology/aesthetics clinics, plus national chains with a local presence. Out-of-market businesses and surgery-only practices do not count.

**Decision rule — add a name when ALL of:**

1. It's a real skincare/aesthetics business (facial spa, medspa, facial bar, dermatology/aesthetics clinic) — not a product/retail brand (Sephora, SkinCeuticals = `other`), a review/booking site (RealSelf, Groupon = `other`), or a generic category/treatment label.
2. It operates in GV Skincare's market per [[competitor-scope-policy]] (Katy / west Houston / greater Houston). Out-of-market or surgery-only → exclude.
3. Appears in ≥ 2 different platforms' responses for this run (cross-platform corroboration filters out hallucinations).
4. **Verbatim evidence quote exists** — the name appears as a verbatim substring in at least one `runs/{date}/{platform}/q*.json` response. Anti-hallucination guard.

Names that pass (1) and (2) but appear on only 1 platform — leave them out this cycle and list them under "Watchlist" in `audit-{date}.md`.

**How to add a competitor — touch up to 4 places (the schema is split):**

1. `additions[]` in `competitors.json` — append a structured object with full provenance:

   ```json
   {
     "name": "Example Med Spa",
     "added_date": "2026-05-31",
     "added_in_audit": "2026-05-31",
     "platforms": ["openai", "gemini"],
     "evidence_quote": "Example Med Spa in Katy offers HydraFacial and microneedling...",
     "evidence_file": "runs/2026-05-31/openai/q4.json",
     "category": "local",
     "domain": "examplemedspa.com",
     "justification": "Named on OpenAI + Gemini Q4 as a Katy medspa; competes on HydraFacial/microneedling."
   }
   ```

   `analyze.py` only reads `.name` from each `additions[]` entry, so the rest is provenance for humans.

2. `domains{}` — add `"Example Med Spa": "examplemedspa.com"` so its favicon shows and any cited `examplemedspa.com` URL is categorized as a Competitor.
3. `categories{}` — add `"Example Med Spa": "local"` (or `chain`/`other`) for color-coding and rank filters.
4. `aliases.json` `map{}` — if it has variant spellings (apostrophes, "and" vs "&", with/without "Katy"), add each lowercase variant → canonical. **Curly apostrophes are easy to miss** — `Anita's` (U+2019) will not match a straight-apostrophe entry; add both forms.

**Don't add** names that are common English words without a qualifier (they false-positive everywhere), product lines, or businesses you can't tie to the local market.

**Audit log:** also write a per-run log at `runs/{date}/new-competitors-added.json` listing every added entry. This is the auditable trail — if a name was added wrongly you can find and reverse it from this file alone, without diffing all of `competitors.json`.

**After adding, re-run** so the run reflects the expanded set:

```bash
cd tracking
python3 analyze.py --date "$DATE" --compare
python3 dashboard.py
```

## Failure-mode check

After analysis, compare each platform's tested count for this run against the prior run. If any platform dropped by > 30%, the API likely had partial failures and the apparent mention-rate change is an artifact. Surface it prominently and do NOT publish until verified.

```bash
cd tracking
python3 - <<'PY'
import csv
from collections import defaultdict
from pathlib import Path
import os

date = os.environ["DATE"]
prev = sorted(p.name for p in Path("runs").iterdir() if p.is_dir() and p.name < date)[-1]

def counts(d):
    c = defaultdict(int)
    with open(f"runs/{d}/summary.csv") as f:
        for r in csv.DictReader(f):
            c[r["platform"]] += 1
    return c

now, was = counts(date), counts(prev)
for p in sorted(set(now) | set(was)):
    delta = now.get(p, 0) - was.get(p, 0)
    if was.get(p, 0) and abs(delta) / was[p] > 0.30:
        print(f"WARN  {p}: {was[p]} -> {now.get(p, 0)} ({delta:+d})")
PY
```

(Each row in `summary.csv` is one tested query, so row-count per platform = tested count.)

## Verify misidentifications

`analyze.py` sets `position` to `dismissed` or `misidentified` (with `accurate=no`) using regex heuristics. These are noisy — always verify before publishing.

Query the run summary for non-accurate mentions:

```bash
cd tracking
python3 -c "
import csv, os
d = os.environ['DATE']
with open(f'runs/{d}/summary.csv') as f:
    for r in csv.DictReader(f):
        if r['mentioned'] == 'yes' and r['accurate'] == 'no':
            print(r['platform'], 'q'+r['query_id'], r['position'], '-', r['description'][:120])
"
```

For each hit, open `runs/{date}/{platform}/q{id}.json` and read the actual response:

- **misidentified** — is GV Skincare genuinely described as a *product line / retail skincare brand* rather than the Katy, TX facial spa? Or is the heuristic tripping on a citation to `gvskincare.com` sitting next to a product mention?
- **dismissed** — does the response genuinely say it has no information on GV Skincare / doesn't recognize it? Or is the regex matching a dismissive sentence about a *different* business?

If a flag is a false positive, either tighten the patterns in `analyze.py` (the `dismissive_patterns` / `misid_patterns` near the top of `analyze_response`) and re-run analysis, or call out the reclassification in the narrative. Do **not** ship an audit with unverified non-accurate flags — they distort the mention rate and the dashboard's incorrect-mentions view.

## Narrative audit format

Write `tracking/audit-{date}.md` with these sections:

1. **Executive summary** — table: platform, tested, mentioned, accurate, rate, change vs previous. (Mirror `runs/{date}/report.md`'s summary table.)
2. **Per-platform detail** — short narrative; pull the detail tables from `report.md` if useful.
3. **Changes from previous audit** — new mentions, lost mentions, accuracy/position movement, competitor movement (`report.md` already computes the new/lost/improved lists when run with `--compare`).
4. **Watchlist** — single-platform candidate competitors that didn't meet the 2-platform threshold this run.
5. **Top 3 opportunities.** Rank from these:
   - Non-branded queries with mention rate < 50% in `direct_discovery` or `treatment_discovery` (the highest-intent local categories).
   - Queries where GV Skincare's position regressed vs prior run (top → mid, featured → bottom, mentioned → absent).
   - Queries where a local competitor gained a featured slot GV Skincare didn't.
   - Spanish-language queries (Q37–40) with no mention — distinct, underserved audience per `STRATEGY.md`.
   - Skip queries already strong (mention rate ≥ 80%).
6. **Methodology** — platforms, query count, date, any failure-mode caveats.

Anchor every claim to the generated outputs for the current date; use the prior audit only for continuity.

## Branded query classification

Branded query: **Q25** ("GV Skincare Katy TX reviews") — the only query naming the brand. Treat all others as non-branded. (The old "X vs independent spa" comparison queries Q26–30 are retired.) If `queries.json` adds new "GV Skincare vs X" or "X vs GV Skincare" queries, add their IDs here.

## Git workflow

From the repo root:

```bash
git checkout main
git pull --rebase origin main
git add tracking/ docs/index.html
git commit -m "AEO audit - $DATE"
git push origin main
```

If there is nothing to commit, skip the commit instead of forcing an empty one.

## Dashboard deploy

GitHub Pages serves `main` from `/docs` (repo `yntema/gvskincare`, published at **https://yntema.github.io/gvskincare/**). `dashboard.py` rewrites `docs/index.html` as a single self-contained file — data and raw responses are inlined, so there are no separate response files to push. The output is deterministic, so re-running `dashboard.py` without new data produces no diff. Commit and push `docs/index.html` to republish.

## Summary delivery

No Slack/email channel is configured for this repo. The deliverable is `tracking/audit-{date}.md` plus a short headline you print at the end of the run:

```
AEO weekly audit — {date}
Mention rates: anthropic {a}%, gemini {g}%, grok {gk}%, openai {o}%, perplexity {p}%
{1–2 lines: notable changes vs previous audit}
New competitors added this run: {names or "none"}
Top 3 opportunities: {one line each}
Dashboard: https://yntema.github.io/gvskincare/
```

If a delivery channel (Slack, email to the owner) is wanted later, add the destination here and a step to the workflow.

## Scheduling

Cadence is not yet automated. To run this on a recurring basis, create a `/schedule` routine (via the `schedule` skill) that invokes this skill at the chosen cadence — everything else happens here. Keep process state in this file, not in the routine text.

## Maintenance rule

When the process changes, update this file first, then the referenced scripts. Don't let process state live in cron text or scripts.
