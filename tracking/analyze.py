#!/usr/bin/env python3
"""
AEO Audit Analyzer — GV Skincare
Processes raw API results into trend data and reports.

Usage:
    python3 analyze.py                    # analyze most recent run
    python3 analyze.py --date 2026-04-04  # analyze specific run
    python3 analyze.py --compare          # include diff vs previous run

Citation + response-text extraction lives in extractors.py (shared with
dashboard.py). The competitor watchlist lives in competitors.json; variant
spellings fold onto canonical names via aliases.json. Edit those, not this file.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.json"
COMPETITORS_FILE = SCRIPT_DIR / "competitors.json"
ALIASES_FILE = SCRIPT_DIR / "aliases.json"
RUNS_DIR = SCRIPT_DIR / "runs"
TREND_FILE = SCRIPT_DIR / "trend.csv"

sys.path.insert(0, str(SCRIPT_DIR))
import extractors  # noqa: E402


def _load_competitors():
    """Return the flat list of tracked competitor surface forms (seed + additions)."""
    with open(COMPETITORS_FILE) as f:
        data = json.load(f)
    names = list(data.get("seed", []))
    for entry in data.get("additions", []):
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            names.append(name)
    # Case-insensitive dedupe, preserve first-seen casing
    seen = set()
    deduped = []
    for n in names:
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(n)
    return deduped


def _load_aliases():
    with open(ALIASES_FILE) as f:
        return json.load(f).get("map", {})


COMPETITORS = _load_competitors()

# Build regex pattern for competitor detection. Longest names first so multi-word
# names match before shorter substrings (e.g. "Spa at the Post Oak" before "Spa Lux").
COMPETITOR_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(c) for c in sorted(COMPETITORS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# Merge near-duplicates onto a single canonical name.
# Format: matched-name (lowercase) -> canonical display name.
CANONICAL_NAME = _load_aliases()

# GV Skincare detection — match "GV Skincare", "GV Skin Care", "gvskincare.com", etc.
BRAND_PATTERN = re.compile(
    r'gv\s*skin\s*care|gvskincare(?:\.com)?|gvskincarecenter',
    re.IGNORECASE,
)


def canonicalize(raw):
    """Normalize a matched competitor surface form to its canonical display name."""
    # First snap to the COMPETITORS list spelling (case-insensitive)…
    canonical = next((known for known in COMPETITORS if known.lower() == raw.lower()), raw)
    # …then fold near-duplicates onto a single company via aliases.
    return CANONICAL_NAME.get(canonical.lower(), canonical)


def load_queries():
    with open(QUERIES_FILE) as f:
        return {q["id"]: q for q in json.load(f)["queries"]}


def analyze_response(content, citations):
    """Analyze a single response for GV Skincare mentions and competitors."""
    mentioned = bool(BRAND_PATTERN.search(content))

    accurate = False
    position = ""
    description = ""
    if mentioned:
        # Check for negative/dismissive mentions
        dismissive_patterns = [
            r'not a recognized',
            r'no (?:direct )?information.*(?:about|on).*gv\s*skin',
            r'could not find',
            r'no.*appears in.*results',
        ]
        is_dismissive = any(re.search(p, content, re.IGNORECASE) for p in dismissive_patterns)

        # Check for misidentification — GV Skincare confused with a product/retail
        # brand rather than the Katy, TX facial spa.
        misid_patterns = [
            r'gv\s*skin\s*care[^.\n]{0,40}\b(?:product line|product brand|skincare brand|retail brand|cosmetics? brand)\b',
        ]
        is_misidentified = any(re.search(p, content, re.IGNORECASE) for p in misid_patterns)

        if is_dismissive:
            accurate = False
            position = "dismissed"
        elif is_misidentified:
            accurate = False
            position = "misidentified"
        else:
            accurate = True
            # Try to determine position
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if BRAND_PATTERN.search(line):
                    if line.strip().startswith('#'):
                        position = "featured"
                    elif i < len(lines) * 0.25:
                        position = "top"
                    elif i < len(lines) * 0.5:
                        position = "mid"
                    else:
                        position = "bottom"
                    break
            if not position:
                position = "mentioned"

        # Extract description snippet around the mention
        for line in content.split('\n'):
            if BRAND_PATTERN.search(line):
                description = line.strip()[:200]
                break

    # Extract competitors in first-mention order (rank proxy)
    comp_first_pos = {}  # canonical name -> character position of first mention
    for match in COMPETITOR_PATTERN.finditer(content):
        canonical = canonicalize(match.group())
        if canonical not in comp_first_pos:
            comp_first_pos[canonical] = match.start()
    # Sort by first appearance = rank order in LLM response
    competitors = sorted(comp_first_pos.keys(), key=lambda c: comp_first_pos[c])

    # Check if gvskincare.com is in citations
    brand_cited = any("gvskincare" in c.lower() for c in citations)

    # Find GV Skincare's rank among all mentions (competitors + brand)
    brand_rank = None
    if mentioned:
        brand_match = BRAND_PATTERN.search(content)
        if brand_match:
            brand_pos = brand_match.start()
            brand_rank = 1 + sum(1 for pos in comp_first_pos.values() if pos < brand_pos)

    # Build numbered rank string: "1:Hand & Stone; 2:Woodhouse Spa; ..."
    competitor_ranks = "; ".join(f"{i+1}:{c}" for i, c in enumerate(competitors))

    return {
        "mentioned": mentioned,
        "accurate": accurate,
        "position": position,
        "description": description,
        "competitors": competitors,
        "competitor_ranks": competitor_ranks,
        "brand_rank": brand_rank,
        "brand_cited": brand_cited,
        "citation_count": len(citations),
    }


def get_available_runs():
    """List all available run dates, sorted."""
    if not RUNS_DIR.exists():
        return []
    return sorted([d.name for d in RUNS_DIR.iterdir() if d.is_dir()])


def get_previous_run(current_date):
    """Find the most recent run before current_date."""
    runs = get_available_runs()
    prev = [r for r in runs if r < current_date]
    return prev[-1] if prev else None


def load_trend_data():
    """Load existing trend.csv data."""
    rows = []
    if TREND_FILE.exists():
        with open(TREND_FILE) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return rows


def save_trend_data(rows):
    """Save trend data to CSV."""
    if not rows:
        return
    fieldnames = [
        "date", "query_id", "query_text", "category", "platform",
        "mentioned", "accurate", "position", "competitors",
        "competitor_ranks", "brand_rank", "brand_cited", "description"
    ]
    with open(TREND_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze_run(date, compare=False):
    """Analyze a full audit run."""
    run_dir = RUNS_DIR / date
    if not run_dir.exists():
        print(f"ERROR: No run found at {run_dir}")
        sys.exit(1)

    queries = load_queries()
    platforms = [d.name for d in run_dir.iterdir() if d.is_dir()]

    if not platforms:
        print(f"ERROR: No platform directories in {run_dir}")
        sys.exit(1)

    print(f"=== GV Skincare AEO Analysis: {date} ===")
    print(f"Platforms: {', '.join(platforms)}")
    print()

    # Load previous run for comparison
    prev_data = {}
    prev_date = None
    if compare:
        prev_date = get_previous_run(date)
        if prev_date:
            trend_rows = load_trend_data()
            for row in trend_rows:
                if row["date"] == prev_date:
                    key = (int(row["query_id"]), row["platform"])
                    prev_data[key] = row
            print(f"Comparing against: {prev_date}")
        else:
            print("No previous run found for comparison")
        print()

    # Analyze each platform
    results = []  # list of dicts for trend CSV
    platform_report_lines = []  # per-platform detail sections

    # Executive summary table
    summary = {}
    for platform in sorted(platforms):
        summary[platform] = {"total": 0, "mentioned": 0, "accurate": 0, "tested": 0}

    for platform in sorted(platforms):
        platform_dir = run_dir / platform
        if platform not in extractors.KNOWN_PLATFORMS:
            print(f"  WARNING: No extractor for platform '{platform}', skipping")
            continue

        platform_report_lines.append(f"\n## {platform.title()} Results\n")

        table_header = "| # | Query | GV Skincare? | Position | Competitors | Notes |"
        table_sep = "|---|-------|-------------|----------|-------------|-------|"
        platform_report_lines.append(table_header)
        platform_report_lines.append(table_sep)

        for qid in sorted(queries.keys()):
            q = queries[qid]
            result_file = platform_dir / f"q{qid}.json"

            if not result_file.exists():
                continue

            summary[platform]["tested"] += 1

            try:
                with open(result_file) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  WARNING: Could not read {result_file}: {e}")
                continue

            content = extractors.extract_text(data, platform)
            citations = extractors.extract_citation_urls(data, platform)
            if not content:
                continue

            analysis = analyze_response(content, citations)
            summary[platform]["total"] += 1
            if analysis["mentioned"]:
                summary[platform]["mentioned"] += 1
            if analysis["accurate"]:
                summary[platform]["accurate"] += 1

            # Build trend row
            row = {
                "date": date,
                "query_id": qid,
                "query_text": q["text"],
                "category": q["category"],
                "platform": platform,
                "mentioned": "yes" if analysis["mentioned"] else "no",
                "accurate": "yes" if analysis["accurate"] else "no",
                "position": analysis["position"],
                "competitors": "; ".join(analysis["competitors"]),
                "competitor_ranks": analysis["competitor_ranks"],
                "brand_rank": analysis["brand_rank"] if analysis["brand_rank"] else "",
                "brand_cited": "yes" if analysis["brand_cited"] else "no",
                "description": analysis["description"][:200],
            }
            results.append(row)

            # Build report table row
            brand_str = "yes" if analysis["mentioned"] else "no"
            if analysis["mentioned"] and not analysis["accurate"]:
                brand_str += " (inaccurate)"
            # Show competitors with rank numbers (first mention order)
            ranked_comps = [f"{i+1}. {c}" for i, c in enumerate(analysis["competitors"][:5])]
            comp_str = ", ".join(ranked_comps)
            if len(analysis["competitors"]) > 5:
                comp_str += f" +{len(analysis['competitors'])-5}"

            # Comparison note
            note = ""
            if compare and prev_date:
                prev_key = (qid, platform)
                prev = prev_data.get(prev_key)
                if prev:
                    was_mentioned = prev["mentioned"] == "yes"
                    now_mentioned = analysis["mentioned"]
                    if now_mentioned and not was_mentioned:
                        note = "NEW mention"
                    elif not now_mentioned and was_mentioned:
                        note = "LOST mention"
                    elif now_mentioned and was_mentioned:
                        was_accurate = prev["accurate"] == "yes"
                        if analysis["accurate"] and not was_accurate:
                            note = "accuracy improved"
                        elif not analysis["accurate"] and was_accurate:
                            note = "accuracy regressed"

            platform_report_lines.append(
                f"| {qid} | {q['text'][:60]} | {brand_str} | {analysis['position']} | {comp_str} | {note} |"
            )

    # Build final report: title, summary, then platform sections
    report_lines = []
    report_lines.append(f"# GV Skincare AEO Audit — {date}\n")

    if compare and prev_date:
        report_lines.append(f"> Comparison against previous audit ({prev_date}).\n")

    # Executive summary
    report_lines.append("\n## Executive Summary\n")
    report_lines.append("| Platform | Tested | Mentioned | Accurate | Rate |")
    report_lines.append("|----------|--------|-----------|----------|------|")
    for platform in sorted(summary.keys()):
        s = summary[platform]
        tested = s["tested"]
        mentioned = s["mentioned"]
        accurate = s["accurate"]
        rate = f"{mentioned}/{tested} ({100*mentioned//tested}%)" if tested else "—"
        report_lines.append(
            f"| **{platform.title()}** | {tested} | {mentioned} | {accurate} | {rate} |"
        )
    report_lines.append("")

    # Competitor frequency
    all_comps = {}
    for r in results:
        for c in r["competitors"].split("; "):
            c = c.strip()
            if c:
                all_comps[c] = all_comps.get(c, 0) + 1
    if all_comps:
        report_lines.append("### Top Competitors by Frequency\n")
        report_lines.append("| Competitor | Mentions |")
        report_lines.append("|-----------|----------|")
        for comp, count in sorted(all_comps.items(), key=lambda x: -x[1])[:15]:
            report_lines.append(f"| {comp} | {count} |")
        report_lines.append("")

    # Append platform detail sections
    report_lines.extend(platform_report_lines)

    # Append changes section if comparing
    if compare and prev_date:
        changes_new = []
        changes_lost = []
        changes_improved = []
        for r in results:
            prev_key = (int(r["query_id"]), r["platform"])
            prev = prev_data.get(prev_key)
            if prev:
                was = prev["mentioned"] == "yes"
                now = r["mentioned"] == "yes"
                if now and not was:
                    changes_new.append(f"Q{r['query_id']} on {r['platform']}: \"{r['query_text'][:60]}\"")
                elif not now and was:
                    changes_lost.append(f"Q{r['query_id']} on {r['platform']}: \"{r['query_text'][:60]}\"")
                elif now and was:
                    was_acc = prev["accurate"] == "yes"
                    now_acc = r["accurate"] == "yes"
                    if now_acc and not was_acc:
                        changes_improved.append(f"Q{r['query_id']} on {r['platform']}: accuracy improved")

        report_lines.append(f"\n## Changes vs {prev_date}\n")
        if changes_new:
            report_lines.append("### New Mentions")
            for c in changes_new:
                report_lines.append(f"- {c}")
        if changes_lost:
            report_lines.append("\n### Lost Mentions")
            for c in changes_lost:
                report_lines.append(f"- {c}")
        if changes_improved:
            report_lines.append("\n### Accuracy Improvements")
            for c in changes_improved:
                report_lines.append(f"- {c}")
        if not changes_new and not changes_lost and not changes_improved:
            report_lines.append("No changes detected.")

    # Write report
    report_file = run_dir / "report.md"
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines) + '\n')
    print(f"\nReport: {report_file}")

    # Write run summary CSV
    summary_csv = run_dir / "summary.csv"
    if results:
        fieldnames = list(results[0].keys())
        with open(summary_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Summary CSV: {summary_csv}")

    # Append to trend.csv
    existing_trend = load_trend_data()
    # Remove existing entries for this date (in case of re-run)
    existing_trend = [r for r in existing_trend if r["date"] != date]
    existing_trend.extend(results)
    # Sort by date, then query_id, then platform
    existing_trend.sort(key=lambda r: (r["date"], int(r["query_id"]), r["platform"]))
    save_trend_data(existing_trend)
    print(f"Trend data: {TREND_FILE} ({len(existing_trend)} total rows)")

    # Print summary to stdout
    print(f"\n{'='*60}")
    print(f"RESULTS: {date}")
    print(f"{'='*60}")
    for platform in sorted(summary.keys()):
        s = summary[platform]
        tested = s["tested"]
        mentioned = s["mentioned"]
        if tested:
            print(f"  {platform:12s}: {mentioned}/{tested} mentioned ({100*mentioned//tested}%)")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GV Skincare AEO Audit Analyzer")
    parser.add_argument("--date", help="Run date to analyze (YYYY-MM-DD). Default: most recent.")
    parser.add_argument("--compare", action="store_true", help="Compare against previous run")
    args = parser.parse_args()

    if args.date:
        date = args.date
    else:
        runs = get_available_runs()
        if not runs:
            print("ERROR: No runs found. Run audit.sh first.")
            sys.exit(1)
        date = runs[-1]

    analyze_run(date, compare=args.compare)
