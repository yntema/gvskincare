# GV Skincare — AEO Audit

Workspace for tracking and improving GV Skincare's LLM/AI discoverability.

## About GV Skincare

- **Website:** https://www.gvskincare.com/
- **Location:** 23410 Grand Reserve Dr. Suite 302, Katy, TX 77494
- **Type:** Premium facial & body spa
- **Owner:** Gaby
- **Key services:** HydraFacial, PRP, microneedling, RF microneedling, Aquagold, chemical peels, dermaplaning, anti-aging facials, body treatments
- **Differentiators:** Advanced technology (HydraFacial MD, Glacial Skin CryoModulation, Ultha ultrasound), PRP treatments, bilingual (English/Spanish)

## Files

- `STRATEGY.md` — AEO strategy and execution plan
- `research/` — Source articles, competitive analysis
- `tracking/` — LLM audit infrastructure and results
  - `queries.json` — Audit queries (`_schema` documents the format; `status: retired` drops a query)
  - `competitors.json` — Competitor watchlist: name→domain map, `seed` list, and `local`/`chain`/`other` categories
  - `aliases.json` — Variant spelling → canonical name (folds "Hand and Stone" onto "Hand & Stone", etc.)
  - `audit.sh` — Automated audit runner (Perplexity, OpenAI, Anthropic, Gemini, Grok)
  - `extractors.py` — Shared per-platform text + citation extraction (imported by analyze.py and dashboard.py — single source of truth)
  - `analyze.py` — Scores raw responses into `trend.csv` (mention, accuracy, competitor ranks, brand rank)
  - `dashboard.py` — Builds `dashboard.html` from `trend.csv` + `runs/` by injecting data into `dashboard-template.html`
  - `dashboard-template.html` — The dashboard front-end (HTML/CSS/JS); edit this for layout/styling
  - `trend.csv` — Append-only scored history, one row per (date, query, platform)
  - `runs/` — Raw API responses per audit date (`runs/<date>/<platform>/q<id>.json`)

## Running an Audit

```bash
cd tracking

# Run full audit (all platforms, all queries)
./audit.sh

# Run single platform
./audit.sh --platform perplexity

# Run, auto-analyze, and regenerate the dashboard
./audit.sh --analyze

# Analyze most recent run
python3 analyze.py --compare
```

## Dashboard

```bash
cd tracking

# Regenerate docs/index.html from trend.csv + runs/ (and open it)
python3 dashboard.py --open
```

`docs/index.html` is a self-contained file (data + raw responses inlined) — open
it directly in a browser. It shows visibility rate + rank among local spas,
citation domains (with Owned/Competitor/Other categories), per-query/platform
heatmap, competitor rankings, and the raw LLM responses behind each answer.

### Publishing to GitHub Pages (optional)

The repo is **private**, and GitHub's free plan doesn't serve Pages from private
repos — so the dashboard isn't published yet. The output already lives in `docs/`
(the Pages convention) so it's one step away. To publish later, either make the
repo public **or** upgrade to GitHub Pro, then enable Pages from `main` `/docs`:

```bash
echo '{"source":{"branch":"main","path":"/docs"}}' \
  | gh api -X POST repos/yntema/gvskincare/pages --input -
# → https://yntema.github.io/gvskincare/
```

Re-running `dashboard.py` rewrites `docs/index.html`; commit and push to republish.

Citation/response parsing lives in `extractors.py` so the audit pipeline and the
dashboard can never drift. The competitor watchlist + categories live in
`competitors.json` (edit there, not in the code).

