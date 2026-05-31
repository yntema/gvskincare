#!/usr/bin/env python3
"""
Generates the GV Skincare AEO dashboard from trend.csv and raw API results.

Usage:
    python3 dashboard.py                # writes dashboard.html
    python3 dashboard.py --open         # generates and opens in browser

This is a data builder: it scans runs/ once (via the shared extractors.py),
assembles a JSON blob, and injects it into dashboard-template.html. The HTML/CSS/JS
front-end lives in that template so it can be edited with normal tooling.
"""

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
TREND_FILE = SCRIPT_DIR / "trend.csv"
QUERIES_FILE = SCRIPT_DIR / "queries.json"
COMPETITORS_FILE = SCRIPT_DIR / "competitors.json"
RUNS_DIR = SCRIPT_DIR / "runs"
TEMPLATE_FILE = SCRIPT_DIR / "dashboard-template.html"
# Published to docs/, the GitHub Pages surface (served at the repo's Pages URL).
# The dashboard is self-contained (data + raw responses inlined), so this single
# file is all Pages needs.
OUTPUT_FILE = REPO_ROOT / "docs" / "index.html"

MIN_SAMPLE = 5  # minimum queries tested to show a data point in the trend chart
BRAND_DOMAIN = "gvskincare.com"

sys.path.insert(0, str(SCRIPT_DIR))
import extractors  # noqa: E402
from analyze import BRAND_PATTERN  # noqa: E402


def is_branded(query_text):
    return bool(BRAND_PATTERN.search(query_text))


def load_data():
    with open(TREND_FILE) as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r["query_id"] = int(r["query_id"])
        r["branded"] = is_branded(r["query_text"])
        r["mentioned_bool"] = r["mentioned"] == "yes"
        r["accurate_bool"] = r["accurate"] == "yes"

    return rows


def scan_runs():
    """Single pass over runs/. Reads every raw API result once and returns:
      citations : list of {date, platform, query_id, url, domain}
      responses : {"date|platform|qid": text} — LLM response text, inlined into
                  the page so the local-file dashboard's response viewer works.
    """
    citations = []
    responses = {}

    if not RUNS_DIR.exists():
        return citations, responses

    import re
    for date_dir in sorted(RUNS_DIR.iterdir()):
        if not date_dir.is_dir():
            continue
        date = date_dir.name
        for platform_dir in sorted(date_dir.iterdir()):
            if not platform_dir.is_dir():
                continue
            platform = platform_dir.name
            if platform not in extractors.KNOWN_PLATFORMS:
                continue
            for result_file in sorted(platform_dir.glob("q*.json")):
                m = re.match(r'q(\d+)\.json', result_file.name)
                if not m:
                    continue
                qid = int(m.group(1))
                try:
                    with open(result_file) as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    continue
                for url in extractors.extract_citation_urls(data, platform):
                    citations.append({
                        "date": date,
                        "platform": platform,
                        "query_id": qid,
                        "url": url,
                        "domain": extractors.url_domain(url),
                    })
                content = extractors.extract_text(data, platform)
                if content:
                    responses[f"{date}|{platform}|{qid}"] = content

    return citations, responses


def _derive_queries():
    """Build the query list from queries.json (canonical order/set, active only)."""
    with open(QUERIES_FILE) as f:
        defined = json.load(f)["queries"]
    return [
        {"id": q["id"], "text": q["text"], "category": q["category"], "branded": is_branded(q["text"])}
        for q in defined
        if q.get("status", "active") != "retired"
    ]


def load_competitors():
    """Return (domains, categories) maps from competitors.json."""
    try:
        with open(COMPETITORS_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}, {}
    domains = {name: dom.lower() for name, dom in data.get("domains", {}).items()}
    categories = dict(data.get("categories", {}))
    return domains, categories


def _domain_matches(domain, domain_list):
    """Suffix match: 'reviews.gvskincare.com' matches 'gvskincare.com'."""
    return any(domain == v or domain.endswith("." + v) for v in domain_list)


def _categorize_domain(domain, competitor_domains):
    """Owned / Competitor / Other for a citation domain."""
    if not domain:
        return "Other"
    if domain == BRAND_DOMAIN or domain.endswith("." + BRAND_DOMAIN):
        return "Owned"
    if _domain_matches(domain, competitor_domains):
        return "Competitor"
    return "Other"


def _share_rows(latest, prev, limit=None):
    """Rank domains by citation share in the latest run, with change vs prev.

    share = a domain's citations / all citations in that run (0-100). delta =
    latest share - previous-run share (pp); a domain absent from the previous
    run surfaces as +full-share. Returns (rows, total_unique_domains).
    """
    total_l = len(latest)
    total_p = len(prev)
    cl = Counter(c["domain"] for c in latest if c["domain"])
    cp = Counter(c["domain"] for c in prev if c["domain"])
    rows = []
    for d, c in cl.most_common(limit):
        share = c / total_l * 100 if total_l else 0.0
        prev_share = (cp.get(d, 0) / total_p * 100) if total_p else 0.0
        rows.append({
            "domain": d,
            "count": c,
            "share": round(share, 2),
            "delta": round(share - prev_share, 2),
        })
    return rows, len(cl)


def build_dashboard_data(rows, citations, responses, competitor_domains, competitor_categories):
    competitor_domain_set = sorted(set(competitor_domains.values()))

    # Tag citations branded by their query.
    branded_qids = {r["query_id"] for r in rows if r["branded"]}
    for c in citations:
        c["branded"] = c["query_id"] in branded_qids

    # Top Citation Domains — latest run only, organic queries, ranked by share,
    # with change vs the previous run. Cumulative counts bury recently-surging
    # sources; share-of-latest-run is the live signal.
    organic_citations = [c for c in citations if not c["branded"]]
    cite_dates = sorted({c["date"] for c in organic_citations})
    latest_cite_date = cite_dates[-1] if cite_dates else None
    prev_cite_date = cite_dates[-2] if len(cite_dates) >= 2 else None
    latest_organic = [c for c in organic_citations if c["date"] == latest_cite_date] if latest_cite_date else []
    prev_organic = [c for c in organic_citations if c["date"] == prev_cite_date] if prev_cite_date else []
    domain_rows, domain_total = _share_rows(latest_organic, prev_organic)
    for r in domain_rows:
        r["category"] = _categorize_domain(r["domain"], competitor_domain_set)

    # GV Skincare's rank among cited domains by share, latest + previous run.
    def _brand_domain_rank(table_rows=None, raw=None):
        if table_rows is not None:
            return next((i + 1 for i, r in enumerate(table_rows) if r["domain"] == BRAND_DOMAIN), None)
        for i, (d, _) in enumerate(Counter(c["domain"] for c in (raw or [])).most_common()):
            if d == BRAND_DOMAIN:
                return i + 1
        return None
    brand_cite_rank = _brand_domain_rank(table_rows=domain_rows)
    brand_cite_rank_prev = _brand_domain_rank(raw=prev_organic)

    # Citation share by date — % of organic citations pointing to gvskincare.com.
    def _is_brand_cite(c):
        return c["domain"] == BRAND_DOMAIN or c["domain"].endswith("." + BRAND_DOMAIN)
    citation_share_by_date = []
    for d in cite_dates:
        day = [c for c in organic_citations if c["date"] == d]
        plats = {}
        for c in day:
            p = plats.setdefault(c["platform"], {"brand": 0, "total": 0})
            p["total"] += 1
            if _is_brand_cite(c):
                p["brand"] += 1
        citation_share_by_date.append({
            "date": d,
            "brand": sum(1 for c in day if _is_brand_cite(c)),
            "total": len(day),
            "platforms": plats,
        })

    return {
        "responses": responses,
        "rows": [
            {
                "date": r["date"],
                "query_id": r["query_id"],
                "query_text": r["query_text"],
                "category": r["category"],
                "platform": r["platform"],
                "mentioned": r["mentioned_bool"],
                "accurate": r["accurate_bool"],
                "position": r["position"],
                "competitors": r["competitors"],
                "competitor_ranks": r.get("competitor_ranks", ""),
                "brand_rank": int(r["brand_rank"]) if r.get("brand_rank") else None,
                "brand_cited": r.get("brand_cited", "") == "yes",
                "branded": r["branded"],
                "description": r.get("description", ""),
            }
            for r in rows
        ],
        "queries": _derive_queries(),
        "citationDomains": domain_rows,
        "citationDomainsTotal": domain_total,
        "citationLatestDate": latest_cite_date,
        "citationPrevDate": prev_cite_date,
        "citationLatestTotal": len(latest_organic),
        "citationShareByDate": citation_share_by_date,
        "brandCiteRank": brand_cite_rank,
        "brandCiteRankPrev": brand_cite_rank_prev,
        "competitorDomains": competitor_domains,
        "competitorCategories": competitor_categories,
        "minSample": MIN_SAMPLE,
    }


def render_html(data_json):
    return TEMPLATE_FILE.read_text().replace("__DATA_PLACEHOLDER__", data_json)


def main():
    rows = load_data()
    citations, responses = scan_runs()
    competitor_domains, competitor_categories = load_competitors()
    data = build_dashboard_data(rows, citations, responses, competitor_domains, competitor_categories)
    data_json = json.dumps(data, default=str)

    html = render_html(data_json)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    n_domains = len(set(c["domain"] for c in citations))
    print(f"Dashboard: {OUTPUT_FILE}")
    print(f"  {len(rows)} trend rows, {len(citations)} citations from {n_domains} domains, {len(responses)} raw responses")

    if "--open" in sys.argv:
        if sys.platform == "darwin":
            subprocess.run(["open", str(OUTPUT_FILE)])
        elif sys.platform == "linux":
            subprocess.run(["xdg-open", str(OUTPUT_FILE)])


if __name__ == "__main__":
    main()
